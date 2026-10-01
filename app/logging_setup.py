import json
import logging
import sys
from datetime import datetime, timezone

SERVICE_NAME = "ms-notifications"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname.lower(),
            "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "service": SERVICE_NAME,
            "msg": record.getMessage(),
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
        return "/health" not in record.getMessage()


def silence_health_check_access_logs() -> None:
    logging.getLogger("uvicorn.access").addFilter(_HealthCheckAccessFilter())
