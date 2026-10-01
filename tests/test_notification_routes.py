from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.list_notifications import ListNotifications, ListNotificationsByEmployee
from app.domain.entities import Notification
from app.infrastructure.http.notification_routes import create_notification_router

NOTIFICATIONS = [
    Notification(
        id="n1",
        tipo="BIENVENIDA",
        destinatario="juan.perez@empresa.com",
        mensaje="Bienvenido Juan Pérez.",
        fecha_envio="2026-03-01T10:00:00.000Z",
        empleado_id="E001",
    ),
    Notification(
        id="n2",
        tipo="VACACIONES",
        destinatario="ana.gomez@empresa.com",
        mensaje="Sus vacaciones fueron confirmadas.",
        fecha_envio="2026-04-01T10:00:00.000Z",
        empleado_id="E002",
    ),
]


class FakeQueryRepository:
    async def list_all(self) -> list[Notification]:
        return NOTIFICATIONS

    async def list_by_employee(self, empleado_id: str) -> list[Notification]:
        return [n for n in NOTIFICATIONS if n.empleado_id == empleado_id]


def build_test_app() -> FastAPI:
    repository = FakeQueryRepository()
    router = create_notification_router(
        ListNotifications(repository),
        ListNotificationsByEmployee(repository),
    )
    app = FastAPI()
    app.include_router(router)
    return app


def test_lista_todas_las_notificaciones_con_camelcase():
    client = TestClient(build_test_app())

    response = client.get("/notificaciones")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Notificaciones consultadas correctamente"
    assert len(body["data"]) == 2
    assert body["data"][0]["empleadoId"] == "E001"
    assert body["data"][0]["fechaEnvio"] == "2026-03-01T10:00:00.000Z"


def test_lista_las_notificaciones_de_un_empleado_especifico():
    client = TestClient(build_test_app())

    response = client.get("/notificaciones/E002")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["tipo"] == "VACACIONES"


def test_responde_lista_vacia_para_un_empleado_sin_notificaciones():
    client = TestClient(build_test_app())

    response = client.get("/notificaciones/E999")

    assert response.status_code == 200
    assert response.json()["data"] == []
