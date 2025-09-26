from sqlalchemy.orm import Session

from .celery_app import celery_app
from app.database import SessionLocal
from app.services.outreach_manager import OutreachManager


@celery_app.task
def send_outreach_task(to: str, subject: str, body: str) -> dict:
    db: Session = SessionLocal()
    try:
        manager = OutreachManager(db)
        record = manager.queue_email(to, subject, body)
        return {"id": record.id, "status": record.status}
    finally:
        db.close()


