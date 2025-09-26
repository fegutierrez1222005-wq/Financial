from dataclasses import dataclass
from typing import Optional

from app.config import get_settings


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def send(self, message: EmailMessage) -> bool:
        # Mock email send for sandbox
        return True


