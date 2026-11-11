"""Trazabilidad distribuida con OpenTelemetry (Reto 8).

- service.name: OTEL_SERVICE_NAME (notificaciones-service).
- Exportador: Zipkin JSON hacia OTEL_EXPORTER_ZIPKIN_ENDPOINT (nombre de red Docker `zipkin`).
- Propagación: W3C Trace Context + Baggage, igual que los servicios en Node, Go, Ruby y PHP.
- Automático: spans de entrada de FastAPI y consultas asyncpg.
- Manual: el consumo de RabbitMQ (consumer.py) extrae el `traceparent` de las cabeceras del mensaje
  y el envío SMTP crea su propio span, para ver en Zipkin cuánto tarda el correo.

Si OTEL_EXPORTER_ZIPKIN_ENDPOINT no está definida (pruebas, ejecución local sin Zipkin) el
servicio usa el proveedor no-op de la API: los spans no se registran ni se exportan.
"""

import os

from fastapi import FastAPI
from opentelemetry import propagate, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.zipkin.json import ZipkinExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

DEFAULT_SERVICE_NAME = "notificaciones-service"

tracer = trace.get_tracer("rhm-notifications")


def service_name() -> str:
    return os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)


def configure_tracing(app: FastAPI) -> bool:
    endpoint = os.getenv("OTEL_EXPORTER_ZIPKIN_ENDPOINT")
    if not endpoint:
        return False

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name()}))
    provider.add_span_processor(BatchSpanProcessor(ZipkinExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    propagate.set_global_textmap(
        CompositePropagator([TraceContextTextMapPropagator(), W3CBaggagePropagator()])
    )

    # /health y /metrics los consultan Docker y Prometheus cada pocos segundos: sin excluirlos,
    # taparían en Zipkin las trazas de negocio.
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,metrics")
    AsyncPGInstrumentor().instrument()
    return True
