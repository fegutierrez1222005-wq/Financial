from .celery_app import celery_app
from app.services.validator import validate_financial_point


@celery_app.task
def validate_point_task(point: dict) -> dict:
    return validate_financial_point(point)


