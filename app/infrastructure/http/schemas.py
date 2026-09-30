from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import Notification


class NotificationSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    tipo: str = Field(examples=["BIENVENIDA"])
    destinatario: str = Field(examples=["juan.perez@empresa.com"])
    mensaje: str
    fecha_envio: str = Field(serialization_alias="fechaEnvio", examples=["2026-03-01T10:00:00.000Z"])
    empleado_id: str = Field(serialization_alias="empleadoId", examples=["E001"])

    @staticmethod
    def from_domain(notification: Notification) -> "NotificationSchema":
        return NotificationSchema(
            id=notification.id,
            tipo=notification.tipo,
            destinatario=notification.destinatario,
            mensaje=notification.mensaje,
            fecha_envio=notification.fecha_envio,
            empleado_id=notification.empleado_id,
        )


class NotificationListResponse(BaseModel):
    success: bool = True
    message: str
    data: list[NotificationSchema]


class HealthResponse(BaseModel):
    success: bool = True
    message: str = "Servicio disponible"
    data: dict = Field(default_factory=lambda: {"status": "UP"})
