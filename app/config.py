import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REQUIRED_VARS = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD", "BROKER_URL")


@dataclass(frozen=True)
class Settings:
    port: int
    log_level: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_pool_max: int
    db_connect_max_attempts: int
    db_connect_retry_delay_ms: int
    broker_url: str
    broker_exchange: str
    broker_queue: str
    broker_connect_max_attempts: int
    broker_connect_retry_delay_ms: int
    smtp_host: str
    smtp_port: int
    smtp_from: str
    smtp_use_tls: bool

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


def load_settings() -> Settings:
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    missing = [name for name in _REQUIRED_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Configuración inválida o incompleta: {', '.join(missing)}")

    broker_url = os.environ["BROKER_URL"]
    if not (broker_url.startswith("amqp://") or broker_url.startswith("amqps://")):
        raise RuntimeError("BROKER_URL debe ser una URL amqp:// o amqps://")

    return Settings(
        port=int(os.environ.get("PORT", "8080")),
        log_level=os.environ.get("LOG_LEVEL", "info"),
        db_host=os.environ["DB_HOST"],
        db_port=int(os.environ.get("DB_PORT", "5432")),
        db_name=os.environ["DB_NAME"],
        db_user=os.environ["DB_USER"],
        db_password=os.environ["DB_PASSWORD"],
        db_pool_max=int(os.environ.get("DB_POOL_MAX", "5")),
        db_connect_max_attempts=int(os.environ.get("DB_CONNECT_MAX_ATTEMPTS", "5")),
        db_connect_retry_delay_ms=int(os.environ.get("DB_CONNECT_RETRY_DELAY_MS", "1000")),
        broker_url=broker_url,
        broker_exchange=os.environ.get("BROKER_EXCHANGE", "rhm.events"),
        broker_queue=os.environ.get("BROKER_QUEUE", "notificaciones.queue"),
        broker_connect_max_attempts=int(os.environ.get("BROKER_CONNECT_MAX_ATTEMPTS", "5")),
        broker_connect_retry_delay_ms=int(os.environ.get("BROKER_CONNECT_RETRY_DELAY_MS", "1000")),
        smtp_host=os.environ.get("SMTP_HOST", "mailhog"),
        smtp_port=int(os.environ.get("SMTP_PORT", "1025")),
        smtp_from=os.environ.get("SMTP_FROM", "notificaciones@rhm.local"),
        smtp_use_tls=os.environ.get("SMTP_USE_TLS", "false").lower() == "true",
    )
