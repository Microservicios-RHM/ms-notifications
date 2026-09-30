import logging

from app.domain.entities import Notification

test_logger = logging.getLogger("test")
test_logger.addHandler(logging.NullHandler())


class RecordingRepository:
    def __init__(self, already_processed: bool = False) -> None:
        self.already_processed = already_processed
        self.saved: list[tuple[str, Notification]] = []

    async def save_if_new(self, event_id: str, notification: Notification) -> Notification | None:
        self.saved.append((event_id, notification))
        if self.already_processed:
            return None
        return notification


class RecordingDirectory:
    def __init__(self, seed: dict[str, tuple[str, str, str]] | None = None) -> None:
        self.entries: dict[str, tuple[str, str, str]] = dict(seed or {})
        self.upserts: list[tuple[str, str, str, str]] = []

    async def upsert(self, empleado_id: str, nombre: str, apellido: str, email: str) -> None:
        self.upserts.append((empleado_id, nombre, apellido, email))
        self.entries[empleado_id] = (email, nombre, apellido)

    async def find(self, empleado_id: str) -> tuple[str, str, str] | None:
        return self.entries.get(empleado_id)
