import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from prometheus_client import CollectorRegistry

from app.infrastructure.http.health_routes import router as health_router
from app.infrastructure.messaging.consumer import RabbitMqConsumer
from app.logging_setup import JsonFormatter
from app.observability.health import evaluate_health
from app.observability.metrics import UNMATCHED_ROUTE, HttpMetrics, install_metrics

logger = logging.getLogger("test-observability")
logger.addHandler(logging.NullHandler())

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)


async def _up() -> bool:
    return True


async def _down() -> bool:
    return False


async def _boom() -> bool:
    raise ConnectionError("refused")


@pytest.mark.asyncio
async def test_health_reporta_up_y_down_por_dependencia():
    assert await evaluate_health("notificaciones-service", {"database": _up, "messageBroker": _up}) == {
        "status": "UP",
        "service": "notificaciones-service",
        "checks": {"database": "UP", "messageBroker": "UP"},
    }
    report = await evaluate_health("notificaciones-service", {"database": _boom, "messageBroker": _down})
    assert report["status"] == "DOWN"
    assert report["checks"] == {"database": "DOWN", "messageBroker": "DOWN"}


def test_health_endpoint_responde_503_antes_de_conectar_y_200_despues():
    app = FastAPI()
    app.include_router(health_router)
    client = TestClient(app)

    starting = client.get("/health")
    assert starting.status_code == 503
    assert starting.json()["checks"] == {"database": "DOWN", "messageBroker": "DOWN"}

    app.state.health_checks = {"database": _up, "messageBroker": _up}
    ready = client.get("/health")
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "UP",
        "service": "notificaciones-service",
        "checks": {"database": "UP", "messageBroker": "UP"},
    }


def test_metricas_por_plantilla_de_ruta_sin_ids():
    app = FastAPI()

    @app.get("/notificaciones/{empleado_id}")
    async def by_employee(empleado_id: str):
        return {"id": empleado_id}

    install_metrics(app, HttpMetrics("notificaciones-service", CollectorRegistry()))
    client = TestClient(app)
    client.get("/notificaciones/E001")
    client.get("/notificaciones/E002")
    client.get("/no-existe")

    body = client.get("/metrics").text
    assert (
        'http_requests_total{method="GET",route="/notificaciones/{empleado_id}",'
        'service="notificaciones-service",status="200"} 2.0'
    ) in body
    assert f'route="{UNMATCHED_ROUTE}"' in body
    assert "http_request_duration_seconds_count" in body
    assert "E001" not in body


def test_log_json_con_campos_del_reto_y_trace_id():
    formatter = JsonFormatter()
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "Notificación registrada", None, None)
    record.fields = {"empleadoId": "E001"}

    sin_traza = json.loads(formatter.format(record))
    assert sin_traza["level"] == "INFO"
    assert sin_traza["service"] == "notificaciones-service"
    assert sin_traza["message"] == "Notificación registrada"
    assert sin_traza["empleadoId"] == "E001"
    assert "timestamp" in sin_traza and "traceId" not in sin_traza

    with trace.get_tracer("test").start_as_current_span("op") as span:
        con_traza = json.loads(formatter.format(record))
    assert con_traza["traceId"] == format(span.get_span_context().trace_id, "032x")


class _NoopAsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False


class HeaderMessage:
    def __init__(self, routing_key: str, headers: dict) -> None:
        self.body = json.dumps(
            {
                "id": "evt-9",
                "type": routing_key,
                "version": 1,
                "occurredAt": "2026-03-01T10:00:00.000Z",
                "producer": "auth-service",
                "data": {"empleadoId": "E001"},
            }
        ).encode()
        self.routing_key = routing_key
        self.headers = headers

    def process(self, requeue: bool = False):  # noqa: ARG002
        return _NoopAsyncContext()


@pytest.mark.asyncio
async def test_consumer_continua_la_traza_del_productor():
    exporter.clear()
    trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
    parent_span_id = "00f067aa0ba902b7"
    consumer = RabbitMqConsumer("amqp://x", "rhm.events", "notificaciones", logger)
    handled = []

    async def handler(envelope):
        handled.append(envelope.id)

    consumer.on("cuenta.desactivada", handler)
    await consumer._dispatch(
        HeaderMessage("cuenta.desactivada", {"traceparent": f"00-{trace_id}-{parent_span_id}-01".encode()})
    )

    assert handled == ["evt-9"]
    [span] = exporter.get_finished_spans()
    assert span.name == "cuenta.desactivada process"
    assert span.kind == SpanKind.CONSUMER
    assert format(span.context.trace_id, "032x") == trace_id
    assert format(span.parent.span_id, "016x") == parent_span_id
    assert consumer.is_connected() is False


@pytest.mark.asyncio
async def test_consumer_marca_error_si_el_handler_falla():
    exporter.clear()
    consumer = RabbitMqConsumer("amqp://x", "rhm.events", "notificaciones", logger)

    async def failing(_envelope):
        raise ValueError("dato inválido")

    consumer.on("cuenta.activada", failing)
    await consumer._dispatch(HeaderMessage("cuenta.activada", {}))
    [span] = exporter.get_finished_spans()
    assert span.status.status_code.name == "ERROR"
