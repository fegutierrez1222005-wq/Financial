from sqlalchemy.orm import Session

from app.models.outreach import Outreach
from .email_service import EmailMessage, EmailService


class OutreachManager:
    def __init__(self, db: Session):
        self.db = db
        self.email = EmailService()

    def queue_email(self, to: str, subject: str, body: str) -> Outreach:
        record = Outreach(to_email=to, subject=subject, body=body, status="queued")
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        # Mock immediate send success
        self.email.send(EmailMessage(to=to, subject=subject, body=body))
        record.status = "sent"
        self.db.commit()
        self.db.refresh(record)
        return record


