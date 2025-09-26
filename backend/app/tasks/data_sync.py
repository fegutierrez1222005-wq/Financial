from datetime import datetime

from .celery_app import celery_app


@celery_app.task
def sync_data():
    return {"synced_at": datetime.utcnow().isoformat()}


