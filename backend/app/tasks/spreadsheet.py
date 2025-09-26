from __future__ import annotations

from .celery_app import celery_app
from app.services.spreadsheet.workflow import run_update_and_outreach


@celery_app.task
def run_spreadsheet_workflow() -> dict:
    return run_update_and_outreach()


