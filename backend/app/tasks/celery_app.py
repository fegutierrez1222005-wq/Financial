from celery import Celery
from app.config import get_settings


settings = get_settings()
celery_app = Celery(
    "fdms",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "daily-spreadsheet-workflow": {
        "task": "app.tasks.spreadsheet.run_spreadsheet_workflow",
        "schedule": 60 * 60 * 24,  # every 24 hours
    }
}
