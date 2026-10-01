import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.entities import Notification
from app.domain.email_sender import EmailSender
from app.domain.repositories import DedupNotificationRepository, EmployeeDirectoryRepository
from app.infrastructure.messaging.envelope import EventEnvelope
from app.infrastructure.email.notification_template import render_notification_email


async def handle_vacation_scheduled(
    envelope: EventEnvelope,
    repository: DedupNotificationRepository,
    directory: EmployeeDirectoryRepository,
    logger: logging.Logger,
    email_sender: EmailSender | None = None,
) -> None:
    data = envelope.data
    empleado_id = data["empleadoId"]

    entry = await directory.find(empleado_id)
    if entry is None:
        # No debería ocurrir en operación normal: vacaciones-service ya validó que el empleado
        # existe antes de publicar. Si pasa, es una señal de que el directorio local quedó
        # desincronizado (p. ej. este servicio arrancó después de acumularse eventos que ya
        # expiraron de la cola) — se advierte y se omite, sin intentar adivinar un destinatario.
        logger.warning(
            "Empleado no encontrado en el directorio local; notificación de vacaciones omitida",
            extra={"fields": {"eventId": envelope.id, "empleadoId": empleado_id}},
        )
        return
    email, nombre, apellido = entry
    nombre_completo = f"{nombre} {apellido}".strip()

    mensaje = (
        f'Sus vacaciones del {data["fechaInicio"]} al {data["fechaFin"]} '
        f"han sido confirmadas, {nombre_completo}."
    )

    notification = Notification(
        id=str(uuid4()),
        tipo="VACACIONES",
        destinatario=email,
        mensaje=mensaje,
        fecha_envio=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        empleado_id=empleado_id,
    )

    saved = await repository.save_if_new(event_id=envelope.id, notification=notification)
    if saved is None:
        logger.info(
            "Duplicate event ignored",
            extra={"fields": {"eventId": envelope.id, "eventType": envelope.type}},
        )
        return

    if email_sender is not None:
        await email_sender.send(
            email,
            "Confirmación de vacaciones RHM",
            mensaje,
            render_notification_email("VACACIONES", nombre_completo, mensaje),
        )

    logger.info(
        f'[NOTIFICACIÓN] Tipo: VACACIONES | Para: {email} | Mensaje: "{mensaje}"',
        extra={
            "fields": {
                "eventId": envelope.id,
                "empleadoId": saved.empleado_id,
                "notificationId": saved.id,
            }
        },
    )
