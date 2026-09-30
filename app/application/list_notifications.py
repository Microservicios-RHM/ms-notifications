from app.domain.entities import Notification
from app.domain.repositories import NotificationQueryRepository


class ListNotifications:
    def __init__(self, repository: NotificationQueryRepository) -> None:
        self._repository = repository

    async def execute(self) -> list[Notification]:
        return await self._repository.list_all()


class ListNotificationsByEmployee:
    def __init__(self, repository: NotificationQueryRepository) -> None:
        self._repository = repository

    async def execute(self, empleado_id: str) -> list[Notification]:
        return await self._repository.list_by_employee(empleado_id)
