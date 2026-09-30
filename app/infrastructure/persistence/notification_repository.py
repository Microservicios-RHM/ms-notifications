from datetime import datetime

import asyncpg

from app.domain.entities import Notification
from app.domain.repositories import DedupNotificationRepository, NotificationQueryRepository

_LIST_COLUMNS = "id, tipo, destinatario, mensaje, fecha_envio, empleado_id"


class PostgresNotificationRepository(DedupNotificationRepository, NotificationQueryRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_if_new(self, event_id: str, notification: Notification) -> Notification | None:
        async with self._pool.acquire() as conn, conn.transaction():
            # INSERT ... ON CONFLICT DO NOTHING RETURNING id: si ya existe, no retorna fila y no
            # se ejecuta el INSERT de la notificación — chequeo y efecto atómicos en una sola
            # transacción, sin condición de carrera entre dos entregas concurrentes del mismo id.
            inserted_id = await conn.fetchval(
                "INSERT INTO eventos_procesados (id) VALUES ($1) ON CONFLICT DO NOTHING RETURNING id",
                event_id,
            )
            if inserted_id is None:
                return None

            await conn.execute(
                """
                INSERT INTO notificaciones (id, tipo, destinatario, mensaje, fecha_envio, empleado_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                notification.id,
                notification.tipo,
                notification.destinatario,
                notification.mensaje,
                # asyncpg exige datetime para TIMESTAMPTZ; el dominio guarda ISO 8601 (string)
                # porque así viaja en el envelope/JSON del resto del ecosistema.
                datetime.fromisoformat(notification.fecha_envio.replace("Z", "+00:00")),
                notification.empleado_id,
            )
        return notification

    async def list_all(self) -> list[Notification]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_LIST_COLUMNS} FROM notificaciones ORDER BY fecha_envio DESC"
            )
        return [self._to_domain(row) for row in rows]

    async def list_by_employee(self, empleado_id: str) -> list[Notification]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_LIST_COLUMNS} FROM notificaciones WHERE empleado_id = $1 ORDER BY fecha_envio DESC",
                empleado_id,
            )
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: asyncpg.Record) -> Notification:
        return Notification(
            id=str(row["id"]),
            tipo=row["tipo"],
            destinatario=row["destinatario"],
            mensaje=row["mensaje"],
            fecha_envio=row["fecha_envio"].isoformat().replace("+00:00", "Z"),
            empleado_id=row["empleado_id"],
        )
