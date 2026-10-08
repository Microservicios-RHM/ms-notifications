import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.entities import Notification
from app.domain.email_sender import EmailSender
from app.domain.repositories import DedupNotificationRepository
from app.infrastructure.messaging.envelope import EventEnvelope
from app.infrastructure.email.notification_template import render_notification_email

_DEACTIVATION_MESSAGES = {
    "VACACIONES": "Su cuenta fue desactivada temporalmente mientras disfruta de sus vacaciones.",
    "RETIRO": "Su cuenta fue desactivada de forma permanente tras su desvinculación.",
}

_ACTIVATION_MESSAGES = {
    "FIN_VACACIONES": "Bienvenido de regreso. Su cuenta fue reactivada y ya puede iniciar sesión.",
    "ACTIVACION_INICIAL": "Su cuenta quedó activada y ya puede iniciar sesión.",
}


async def handle_account_status(
    envelope: EventEnvelope,
    repository: DedupNotificationRepository,
    logger: logging.Logger,
    email_sender: EmailSender | None = None,
) -> None:
    """Atiende cuenta.activada y cuenta.desactivada.

    El texto se elige por el motivo del evento y no por su tipo: una desactivación por vacaciones
    y una por retiro llegan como el mismo evento, y para el empleado no significan lo mismo.
    """
    data = envelope.data
    motivo = data["motivo"]
    activada = envelope.type == "cuenta.activada"
    plantilla = _ACTIVATION_MESSAGES if activada else _DEACTIVATION_MESSAGES

    mensaje = plantilla.get(motivo)
    if mensaje is None:
        logger.warning(
            "Motivo de cuenta desconocido; notificación omitida",
            extra={"fields": {"eventId": envelope.id, "eventType": envelope.type, "motivo": motivo}},
        )
        return

    destinatario = data["email"]
    notification = Notification(
        id=str(uuid4()),
        tipo="CUENTA",
        destinatario=destinatario,
        mensaje=mensaje,
        fecha_envio=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        empleado_id=data["empleadoId"],
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
            destinatario,
            "Estado de su cuenta RHM",
            mensaje,
            render_notification_email("CUENTA", "", mensaje),
        )

    logger.info(
        f'[NOTIFICACIÓN] Tipo: CUENTA | Para: {destinatario} | Mensaje: "{mensaje}"',
        extra={
            "fields": {
                "eventId": envelope.id,
                "empleadoId": saved.empleado_id,
                "notificationId": saved.id,
                "motivo": motivo,
            }
        },
    )
