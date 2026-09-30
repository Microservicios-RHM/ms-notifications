import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.entities import Notification
from app.domain.repositories import DedupNotificationRepository
from app.infrastructure.messaging.envelope import EventEnvelope


async def handle_employee_retired(
    envelope: EventEnvelope,
    repository: DedupNotificationRepository,
    logger: logging.Logger,
) -> None:
    data = envelope.data
    nombre_completo = f"{data.get('nombre', '')} {data.get('apellido', '')}".strip()
    destinatario = data["email"]
    mensaje = f"Su cuenta ha sido desactivada. Gracias por su trabajo, {nombre_completo}."

    notification = Notification(
        id=str(uuid4()),
        tipo="DESVINCULACION",
        destinatario=destinatario,
        mensaje=mensaje,
        fecha_envio=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        empleado_id=data["id"],
    )

    saved = await repository.save_if_new(event_id=envelope.id, notification=notification)
    if saved is None:
        logger.info(
            "Duplicate event ignored",
            extra={"fields": {"eventId": envelope.id, "eventType": envelope.type}},
        )
        return

    logger.info(
        f'[NOTIFICACIÓN] Tipo: DESVINCULACION | Para: {destinatario} | Mensaje: "{mensaje}"',
        extra={
            "fields": {
                "eventId": envelope.id,
                "empleadoId": saved.empleado_id,
                "notificationId": saved.id,
            }
        },
    )
