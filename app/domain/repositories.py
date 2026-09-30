from typing import Protocol

from app.domain.entities import Notification


class DedupNotificationRepository(Protocol):
    """Persiste una notificación solo si su event_id no fue procesado antes.

    Contrato: la verificación de duplicado y la inserción ocurren en una sola transacción, para que
    dos entregas concurrentes del mismo evento nunca produzcan dos notificaciones. Retorna la
    notificación guardada, o None si el evento ya se había procesado (duplicado descartado).
    """

    async def save_if_new(self, event_id: str, notification: Notification) -> Notification | None: ...


class NotificationQueryRepository(Protocol):
    """Lado de lectura, usado por los endpoints GET /notificaciones."""

    async def list_all(self) -> list[Notification]: ...

    async def list_by_employee(self, empleado_id: str) -> list[Notification]: ...


class EmployeeDirectoryRepository(Protocol):
    """Réplica local mínima (empleadoId -> nombre/apellido/email), construida a partir de
    empleado.creado. Existe porque vacaciones.programadas no trae esos datos en su payload, y este
    servicio no debe llamar a empleados-service por REST (rompería su autonomía como consumidor
    puramente reactivo).
    """

    async def upsert(self, empleado_id: str, nombre: str, apellido: str, email: str) -> None: ...

    async def find(self, empleado_id: str) -> tuple[str, str, str] | None:
        """Retorna (email, nombre, apellido), o None si el empleado no está en el directorio."""
        ...
