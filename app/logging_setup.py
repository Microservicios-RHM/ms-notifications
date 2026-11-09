import json
import logging
import os
import sys
from datetime import datetime, timezone

from opentelemetry import trace

# Reto 8: mismo nombre que OTEL_SERVICE_NAME, para cruzar en Grafana los logs (Loki) con las
# trazas (Zipkin) del mismo servicio.
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "notificaciones-service")


def trace_context_fields() -> dict[str, str]:
    """traceId/spanId del span activo: con ellos un log de Loki lleva a su traza en Zipkin."""
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return {}
    return {
        "traceId": format(span_context.trace_id, "032x"),
        "spanId": format(span_context.span_id, "016x"),
    }


class JsonFormatter(logging.Formatter):
    """Log estructurado con los campos mínimos del Reto 8:
    {"timestamp":"...","level":"INFO","service":"notificaciones-service","traceId":"...","message":"..."}
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname.upper(),
            "service": SERVICE_NAME,
            **trace_context_fields(),
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["err"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger(SERVICE_NAME)
    logger.setLevel(level.upper())
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


class _HealthCheckAccessFilter(logging.Filter):
    """Excluye /health del access log de uvicorn, igual que ms-employees excluye ese endpoint de
    su access log: el healthcheck de Docker pega cada pocos segundos y ahoga los eventos reales."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/health" not in message and "/metrics" not in message


def silence_health_check_access_logs() -> None:
    logging.getLogger("uvicorn.access").addFilter(_HealthCheckAccessFilter())
