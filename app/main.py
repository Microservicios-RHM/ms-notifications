from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.application.list_notifications import ListNotifications, ListNotificationsByEmployee
from app.application.notify_employee_created import handle_employee_created
from app.application.notify_employee_retired import handle_employee_retired
from app.application.notify_security_token import handle_security_token
from app.application.notify_vacation_scheduled import handle_vacation_scheduled
from app.application.notify_account_status import handle_account_status
from app.config import load_settings
from app.infrastructure.http.health_routes import router as health_router
from app.infrastructure.http.notification_routes import create_notification_router
from app.infrastructure.email.smtp_email_sender import SmtpEmailSender
from app.infrastructure.messaging.consumer import RabbitMqConsumer
from app.infrastructure.persistence.database import create_pool
from app.infrastructure.persistence.employee_directory_repository import (
    PostgresEmployeeDirectoryRepository,
)
from app.infrastructure.persistence.migrations import run_migrations
from app.infrastructure.persistence.notification_repository import PostgresNotificationRepository
from app.logging_setup import configure_logging, silence_health_check_access_logs

settings = load_settings()
logger = configure_logging(settings.log_level)
silence_health_check_access_logs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Connecting to PostgreSQL",
        extra={"fields": {"host": settings.db_host, "database": settings.db_name}},
    )
    pool = await create_pool(
        settings.database_dsn,
        settings.db_connect_max_attempts,
        settings.db_connect_retry_delay_ms,
        logger,
        max_size=settings.db_pool_max,
    )
    applied = await run_migrations(pool)
    for migration in applied:
        logger.info("Database migration applied", extra={"fields": {"migration": migration}})
    logger.info("PostgreSQL connection ready")

    repository = PostgresNotificationRepository(pool)
    directory = PostgresEmployeeDirectoryRepository(pool)
    email_sender = SmtpEmailSender(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_from,
        settings.smtp_use_tls,
        logger,
    )

    app.include_router(
        create_notification_router(
            ListNotifications(repository),
            ListNotificationsByEmployee(repository),
        )
    )

    consumer = RabbitMqConsumer(
        settings.broker_url,
        settings.broker_exchange,
        settings.broker_queue,
        logger,
        connect_max_attempts=settings.broker_connect_max_attempts,
        connect_retry_delay_ms=settings.broker_connect_retry_delay_ms,
    )
    consumer.on(
        "empleado.creado",
        lambda envelope: handle_employee_created(envelope, repository, directory, logger, email_sender),
    )
    consumer.on(
        "empleado.retirado",
        lambda envelope: handle_employee_retired(envelope, repository, logger, email_sender),
    )
    consumer.on(
        "vacaciones.programadas",
        lambda envelope: handle_vacation_scheduled(envelope, repository, directory, logger, email_sender),
    )
    for evento_de_seguridad in ("usuario.creado", "usuario.recuperacion"):
        consumer.on(
            evento_de_seguridad,
            lambda envelope: handle_security_token(envelope, repository, logger, email_sender),
        )
    for evento_de_cuenta in ("cuenta.activada", "cuenta.desactivada"):
        consumer.on(
            evento_de_cuenta,
            lambda envelope: handle_account_status(envelope, repository, logger, email_sender),
        )

    logger.info(
        "Connecting to RabbitMQ",
        extra={"fields": {"exchange": settings.broker_exchange, "queue": settings.broker_queue}},
    )
    await consumer.start()
    logger.info("Notifications service started", extra={"fields": {"port": settings.port}})

    yield

    await consumer.close()
    await pool.close()
    logger.info("Notifications service stopped")


# docs_url/openapi_url montados bajo /notificaciones (no en la raíz) para poder vivir detrás del
# API Gateway sin reescritura de rutas: el Gateway ya proxea /notificaciones/* preservando la
# ruta, así que quedan alcanzables en http://localhost:8080/notificaciones/docs sin ningún cambio
# en api-gateway. FastAPI genera la página de Swagger UI con esta URL absoluta ya incorporada, sin
# problema de rutas relativas.
app = FastAPI(
    title="Microservicio de notificaciones",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/notificaciones/docs",
    openapi_url="/notificaciones/openapi.json",
)
app.include_router(health_router)


# FastAPI construye el documento OpenAPI por su cuenta a partir de las rutas, así que el esquema de
# seguridad se inyecta sobre el resultado. Es solo documentación: quien valida el token es el API
# Gateway, no este servicio. Sin esto el botón Authorize de Swagger no existe y, como desde el
# Reto 5 todo exige token, cada "Try it out" respondería 401 sin forma de autenticarse.
def _openapi_con_bearer() -> dict:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Token obtenido en POST /auth/login a través del API Gateway. "
                "Pulse Authorize y pegue el valor de accessToken."
            ),
        }
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema


app.openapi = _openapi_con_bearer
