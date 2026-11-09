import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection
from opentelemetry import propagate, trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

from app.infrastructure.messaging.envelope import EventEnvelope

Handler = Callable[[EventEnvelope], Awaitable[None]]

tracer = trace.get_tracer("rhm-messaging")


def _carrier(headers: dict | None) -> dict[str, str]:
    carrier: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if isinstance(value, str):
            carrier[key] = value
    return carrier


class RabbitMqConsumer:
    """Consumidor con fan-out: declara su propia cola y la enlaza (bind) a los routing keys
    registrados con on(). El exchange se declara también aquí (idempotente) para no depender del
    orden de arranque entre este servicio y empleados-service.
    """

    def __init__(
        self,
        url: str,
        exchange_name: str,
        queue_name: str,
        logger: logging.Logger,
        connect_max_attempts: int = 5,
        connect_retry_delay_ms: int = 1000,
    ) -> None:
        self._url = url
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._logger = logger
        self._connect_max_attempts = connect_max_attempts
        self._connect_retry_delay_ms = connect_retry_delay_ms
        self._handlers: dict[str, Handler] = {}
        self._connection: AbstractRobustConnection | None = None

    def on(self, routing_key: str, handler: Handler) -> None:
        self._handlers[routing_key] = handler

    async def start(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self._connect_max_attempts + 1):
            try:
                self._connection = await aio_pika.connect_robust(self._url)
                break
            except Exception as error:  # noqa: BLE001
                last_error = error
                self._logger.warning(
                    "RabbitMQ connection attempt failed",
                    extra={"fields": {"attempt": attempt, "error": str(error)}},
                )
                if attempt < self._connect_max_attempts:
                    await asyncio.sleep((self._connect_retry_delay_ms / 1000) * attempt)
        if self._connection is None:
            raise RuntimeError("No fue posible conectar a RabbitMQ") from last_error

        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=10)
        exchange = await channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await channel.declare_queue(self._queue_name, durable=True)
        for routing_key in self._handlers:
            await queue.bind(exchange, routing_key=routing_key)

        await queue.consume(self._dispatch)
        self._logger.info(
            "RabbitMQ connection ready",
            extra={
                "fields": {
                    "exchange": self._exchange_name,
                    "queue": self._queue_name,
                    "bindings": list(self._handlers.keys()),
                }
            },
        )

    def is_connected(self) -> bool:
        """Reto 8: usado por GET /health (check messageBroker)."""
        return self._connection is not None and not self._connection.is_closed

    async def _dispatch(self, message: AbstractIncomingMessage) -> None:
        # Reto 8: la propagación por RabbitMQ es manual. El productor (empleados, auth, vacaciones)
        # dejó su `traceparent` en las cabeceras del mensaje; se extrae para que este span
        # CONSUMER, la consulta a PostgreSQL y el envío SMTP cuelguen de la misma traza en Zipkin.
        routing_key = message.routing_key or ""
        parent = propagate.extract(_carrier(getattr(message, "headers", None)))
        with tracer.start_as_current_span(
            f"{routing_key} process",
            context=parent,
            kind=SpanKind.CONSUMER,
            attributes={
                "messaging.system": "rabbitmq",
                "messaging.operation.type": "process",
                "messaging.destination.name": self._queue_name,
                "messaging.rabbitmq.destination.routing_key": routing_key,
            },
        ) as span:
            await self._process(message, routing_key, span)

    async def _process(self, message: AbstractIncomingMessage, routing_key: str, span: Span) -> None:
        async with message.process(requeue=False):
            handler = self._handlers.get(routing_key)
            if handler is None:
                return
            try:
                envelope = EventEnvelope.parse(json.loads(message.body))
            except Exception:
                span.set_status(Status(StatusCode.ERROR, "malformed event"))
                self._logger.error(
                    "Malformed event received; discarded without reprocessing",
                    extra={"fields": {"routingKey": routing_key}},
                )
                return
            try:
                await handler(envelope)
            except Exception as error:  # noqa: BLE001
                span.record_exception(error)
                span.set_status(Status(StatusCode.ERROR, str(error)))
                # Cualquier fallo del handler (p. ej. un dato inválido que la base de datos
                # rechaza) se registra limpio y se descarta el mensaje (no se reintenta) — igual
                # que ms-profiles/ms-vacation, en vez de dejar un traceback crudo sin contexto.
                self._logger.error(
                    "Event handler failed; discarded without reprocessing",
                    extra={
                        "fields": {
                            "routingKey": routing_key,
                            "eventId": envelope.id,
                            "error": str(error),
                        }
                    },
                )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
