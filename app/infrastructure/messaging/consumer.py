import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika.abc import AbstractIncomingMessage, AbstractRobustConnection

from app.infrastructure.messaging.envelope import EventEnvelope

Handler = Callable[[EventEnvelope], Awaitable[None]]


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

    async def _dispatch(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            routing_key = message.routing_key or ""
            handler = self._handlers.get(routing_key)
            if handler is None:
                return
            try:
                envelope = EventEnvelope.parse(json.loads(message.body))
            except Exception:
                self._logger.error(
                    "Malformed event received; discarded without reprocessing",
                    extra={"fields": {"routingKey": routing_key}},
                )
                return
            try:
                await handler(envelope)
            except Exception as error:  # noqa: BLE001
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
