import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.entities import Notification
from app.domain.repositories import DedupNotificationRepository, EmployeeDirectoryRepository
from app.infrastructure.messaging.envelope import EventEnvelope


async def handle_employee_created(
    envelope: EventEnvelope,
    repository: DedupNotificationRepository,
    directory: EmployeeDirectoryRepository,
    logger: logging.Logger,
) -> None:
    data = envelope.data
    nombre = data.get("nombre", "")
    apellido = data.get("apellido", "")
    destinatario = data["email"]
    mensaje = f'Bienvenido {f"{nombre} {apellido}".strip()}, tu cuenta ha sido creada exitosamente.'

    notification = Notification(
        id=str(uuid4()),
        tipo="BIENVENIDA",
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

    # Alimenta el directorio local que vacaciones.programadas necesita para resolver destinatario
    # (ese evento no trae nombre/email). Solo en la primera vez que se procesa el evento: si fuera
    # un duplicado ya se hizo arriba y el directorio ya quedó correcto desde entonces.
    await directory.upsert(data["id"], nombre, apellido, destinatario)

    logger.info(
        f'[NOTIFICACIÓN] Tipo: BIENVENIDA | Para: {destinatario} | Mensaje: "{mensaje}"',
        extra={
            "fields": {
                "eventId": envelope.id,
                "empleadoId": saved.empleado_id,
                "notificationId": saved.id,
            }
        },
    )
