from html import escape
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


_PALETTES = {
    "BIENVENIDA": ("#146C94", "#E8F5FA", "¡Te damos la bienvenida!"),
    "DESVINCULACION": ("#6B7280", "#F3F4F6", "Información sobre tu cuenta"),
    "VACACIONES": ("#0F766E", "#E6FFFB", "Vacaciones confirmadas"),
    "SEGURIDAD": ("#B45309", "#FEF3C7", "Acceso a tu cuenta"),
    "CUENTA": ("#4338CA", "#EEF2FF", "Estado de tu cuenta"),
}


def render_notification_email(
    notification_type: str,
    recipient_name: str,
    message: str,
    template_dir: str | None = None,
) -> str:
    accent, soft_accent, heading = _PALETTES[notification_type]
    environment = Environment(
        loader=FileSystemLoader(Path(template_dir or os.environ.get("NOTIFICATION_TEMPLATE_DIR", "/app/templates"))),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return environment.get_template("notification.html.j2").render(
        accent=accent,
        soft_accent=soft_accent,
        heading=heading,
        notification_type=escape(notification_type),
        recipient_name=escape(recipient_name or "colaborador(a)"),
        message=escape(message).replace("\n", "<br>"),
    )
