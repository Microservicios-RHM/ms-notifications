import json
import logging
import sys
from datetime import datetime, timezone
from opentelemetry import trace

SERVICE_NAME = "ms-notifications"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "service": "notificaciones-service",
            "message": record.getMessage(),
            "context": getattr(record, "fields", {}),
            "traceId": (
                trace.get_current_span().get_span_context().trace_id.to_bytes(16, "big").hex()
                if trace.get_current_span().get_span_context().is_valid
                else None
            ),
        }
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
        return "/health" not in record.getMessage()


def silence_health_check_access_logs() -> None:
    logging.getLogger("uvicorn.access").addFilter(_HealthCheckAccessFilter())
