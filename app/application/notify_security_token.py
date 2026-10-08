import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.entities import Notification
from app.domain.email_sender import EmailSender
from app.domain.repositories import DedupNotificationRepository
from app.infrastructure.messaging.envelope import EventEnvelope
from app.infrastructure.email.notification_template import render_notification_email

_RESET_LINK_BASE = "https://app.empresa.com/reset?token="


async def handle_security_token(
    envelope: EventEnvelope,
    repository: DedupNotificationRepository,
    logger: logging.Logger,
    email_sender: EmailSender | None = None,
) -> None:
    """Atiende usuario.creado y usuario.recuperacion.

    Ambos eventos traen email y token, así que no hace falta consultar el directorio local: a
    diferencia de vacaciones.programadas, auth-service sí conoce el correo de primera mano.
    El correo de bienvenida del onboarding se dispara aquí y no con empleado.creado, porque es
    este evento el que trae el token de activación y sin token el mensaje sería inútil.
    """
    data = envelope.data
    destinatario = data["email"]
    enlace = f'{_RESET_LINK_BASE}{data["token"]}'
    mensaje = f"Para establecer o restablecer su contraseña, ingrese a {enlace}"

    notification = Notification(
        id=str(uuid4()),
        tipo="SEGURIDAD",
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
            "Acceso a su cuenta RHM",
            mensaje,
            render_notification_email("SEGURIDAD", "", mensaje),
        )

    logger.info(
        f'[NOTIFICACIÓN] Tipo: SEGURIDAD | Para: {destinatario} | Mensaje: "{mensaje}"',
        extra={
            "fields": {
                "eventId": envelope.id,
                "empleadoId": saved.empleado_id,
                "notificationId": saved.id,
            }
        },
    )
