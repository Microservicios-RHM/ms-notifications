from typing import Protocol


class EmailSender(Protocol):
    async def send(self, recipient: str, subject: str, body: str, html_body: str) -> bool: ...
