from fastapi import APIRouter

from app.application.list_notifications import ListNotifications, ListNotificationsByEmployee
from app.infrastructure.http.schemas import NotificationListResponse, NotificationSchema


def create_notification_router(
    list_notifications: ListNotifications,
    list_notifications_by_employee: ListNotificationsByEmployee,
) -> APIRouter:
    router = APIRouter(tags=["Notificaciones"])

    @router.get(
        "/notificaciones",
        summary="Listar todas las notificaciones registradas",
        response_model=NotificationListResponse,
    )
    async def list_all() -> NotificationListResponse:
        notifications = await list_notifications.execute()
        return NotificationListResponse(
            message="Notificaciones consultadas correctamente",
            data=[NotificationSchema.from_domain(n) for n in notifications],
        )

    @router.get(
        "/notificaciones/{empleado_id}",
        summary="Listar las notificaciones de un empleado específico",
        response_model=NotificationListResponse,
    )
    async def list_for_employee(empleado_id: str) -> NotificationListResponse:
        notifications = await list_notifications_by_employee.execute(empleado_id)
        return NotificationListResponse(
            message=f"Notificaciones del empleado {empleado_id} consultadas correctamente",
            data=[NotificationSchema.from_domain(n) for n in notifications],
        )

    return router
