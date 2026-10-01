from html import escape


_PALETTES = {
    "BIENVENIDA": ("#146C94", "#E8F5FA", "¡Te damos la bienvenida!"),
    "DESVINCULACION": ("#6B7280", "#F3F4F6", "Información sobre tu cuenta"),
    "VACACIONES": ("#0F766E", "#E6FFFB", "Vacaciones confirmadas"),
}


def render_notification_email(notification_type: str, recipient_name: str, message: str) -> str:
    accent, soft_accent, heading = _PALETTES[notification_type]
    safe_name = escape(recipient_name or "colaborador(a)")
    safe_message = escape(message).replace("\n", "<br>")

    return f"""<!doctype html>
<html lang="es">
  <body style="margin:0;padding:0;background:#f4f7fb;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f7fb;padding:32px 12px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 24px rgba(15,23,42,.10);">
          <tr><td style="padding:26px 36px;background:{accent};color:#ffffff;">
            <div style="font-size:12px;letter-spacing:2px;font-weight:700;opacity:.85;">RHM</div>
            <div style="font-size:24px;font-weight:700;margin-top:8px;">Gestión humana cercana</div>
          </td></tr>
          <tr><td style="padding:36px;">
            <div style="display:inline-block;padding:7px 12px;border-radius:999px;background:{soft_accent};color:{accent};font-size:12px;font-weight:700;letter-spacing:.4px;">{escape(notification_type)}</div>
            <h1 style="margin:20px 0 12px;font-size:26px;line-height:1.25;color:#111827;">{heading}</h1>
            <p style="margin:0 0 18px;font-size:16px;line-height:1.6;">Hola, {safe_name}.</p>
            <div style="padding:20px;border-left:4px solid {accent};background:#f8fafc;border-radius:4px;font-size:16px;line-height:1.6;">{safe_message}</div>
            <p style="margin:28px 0 0;font-size:14px;line-height:1.6;color:#6b7280;">Este es un mensaje automático de la plataforma RHM. Si tienes preguntas, comunícate con el área de Gestión Humana.</p>
          </td></tr>
          <tr><td style="padding:18px 36px;background:#111827;color:#cbd5e1;font-size:12px;text-align:center;">© RHM · Recursos Humanos</td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""
