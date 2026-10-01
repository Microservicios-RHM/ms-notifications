import json
import logging

import pytest

from app.infrastructure.messaging.consumer import RabbitMqConsumer
from app.infrastructure.messaging.envelope import EventEnvelope

logger = logging.getLogger("test")
logger.addHandler(logging.NullHandler())

ENVELOPE_JSON = json.dumps(
    {
        "id": "evt-1",
        "type": "empleado.creado",
        "version": 1,
        "occurredAt": "2026-03-01T10:00:00.000Z",
        "producer": "empleados-service",
        "data": {"id": "E001"},
    }
).encode()


class _NoopAsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


class FakeMessage:
    def __init__(self, body: bytes, routing_key: str) -> None:
        self.body = body
        self.routing_key = routing_key

    def process(self, requeue: bool = False):  # noqa: ARG002
        return _NoopAsyncContext()


@pytest.mark.asyncio
async def test_despacha_al_handler_registrado_para_la_routing_key():
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    consumer = RabbitMqConsumer("amqp://localhost", "rhm.events", "test.queue", logger)
    consumer.on("empleado.creado", handler)

    await consumer._dispatch(FakeMessage(ENVELOPE_JSON, "empleado.creado"))

    assert len(received) == 1
    assert received[0].id == "evt-1"
    assert received[0].data == {"id": "E001"}


@pytest.mark.asyncio
async def test_ignora_mensajes_de_routing_keys_sin_handler_registrado():
    consumer = RabbitMqConsumer("amqp://localhost", "rhm.events", "test.queue", logger)
    consumer.on("empleado.creado", lambda _e: (_ for _ in ()).throw(AssertionError("no debería llamarse")))

    # No debe lanzar: simplemente no hay handler para "empleado.retirado" todavía.
    await consumer._dispatch(FakeMessage(ENVELOPE_JSON, "empleado.retirado"))


@pytest.mark.asyncio
async def test_descarta_mensajes_malformados_sin_lanzar():
    consumer = RabbitMqConsumer("amqp://localhost", "rhm.events", "test.queue", logger)
    consumer.on("empleado.creado", lambda _e: (_ for _ in ()).throw(AssertionError("no debería llamarse")))

    await consumer._dispatch(FakeMessage(b"esto no es JSON", "empleado.creado"))
