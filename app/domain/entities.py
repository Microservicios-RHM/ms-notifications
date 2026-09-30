from dataclasses import dataclass
from typing import Literal

NotificationType = Literal["BIENVENIDA", "DESVINCULACION", "VACACIONES"]


@dataclass(frozen=True)
class Notification:
    id: str
    tipo: NotificationType
    destinatario: str
    mensaje: str
    fecha_envio: str
    empleado_id: str
