import asyncio
import logging
import smtplib
from email.message import EmailMessage


class SmtpEmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        use_tls: bool,
        logger: logging.Logger,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._use_tls = use_tls
        self._logger = logger

    async def send(self, recipient: str, subject: str, body: str, html_body: str) -> bool:
        try:
            await asyncio.to_thread(self._send_sync, recipient, subject, body, html_body)
            self._logger.info(
                "Email delivered through SMTP",
                extra={"fields": {"recipient": recipient, "subject": subject}},
            )
            return True
        except (OSError, smtplib.SMTPException) as error:
            self._logger.error(
                "SMTP delivery failed; notification remains persisted",
                extra={"fields": {"recipient": recipient, "subject": subject, "error": str(error)}},
            )
            return False

    def _send_sync(self, recipient: str, subject: str, body: str, html_body: str) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(self._host, self._port, timeout=5) as smtp:
            if self._use_tls:
                smtp.starttls()
            smtp.send_message(message)
