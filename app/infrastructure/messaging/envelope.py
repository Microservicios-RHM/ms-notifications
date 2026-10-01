from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventEnvelope:
    """Espejo del envelope publicado por empleados-service. Ver event-catalog.md."""

    id: str
    type: str
    version: int
    occurred_at: str
    producer: str
    data: dict[str, Any]

    @staticmethod
    def parse(raw: dict[str, Any]) -> "EventEnvelope":
        return EventEnvelope(
            id=raw["id"],
            type=raw["type"],
            version=raw["version"],
            occurred_at=raw["occurredAt"],
            producer=raw["producer"],
            data=raw["data"],
        )
