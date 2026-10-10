"""Celery worker entrypoint.

Run with::

    celery -A finagent_api.jobs.celery_app:celery_app worker --loglevel=info

A single generic task dispatches to the job registry so adding a job never requires
touching Celery configuration, and the inline backend stays behaviour-identical.
"""

from __future__ import annotations

from typing import Any

from finagent_api.jobs import tasks  # noqa: F401 - registers every job
from finagent_api.jobs.queue import registered_jobs
from finagent_api.settings import get_settings
from finagent_core.logging import configure_logging, get_logger

logger = get_logger(__name__)

settings = get_settings()
configure_logging(settings.log_level, json_output=settings.log_format == "json")

try:  # pragma: no cover - Celery is an optional deployment dependency
    from celery import Celery

    celery_app = Celery(
        "finagent",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_time_limit=settings.celery_task_time_limit,
        task_soft_time_limit=max(60, settings.celery_task_time_limit - 60),
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        timezone="UTC",
        beat_schedule={
            "retry-pending-webhooks": {
                "task": "finagent.run_job",
                "schedule": 120.0,
                "args": ("webhook.retry_pending", {}),
            },
            "expire-stuck-runs": {
                "task": "finagent.run_job",
                "schedule": 600.0,
                "args": ("maintenance.expire_runs", {}),
            },
        },
    )

    @celery_app.task(name="finagent.run_job", bind=True, max_retries=2)
    def run_job(self, job_name: str, kwargs: dict[str, Any]) -> Any:  # noqa: ANN001
        func = registered_jobs().get(job_name)
        if func is None:
            raise KeyError(f"unknown job: {job_name}")
        logger.info("celery_job_started", extra={"job_name": job_name, "task_id": self.request.id})
        return func(**kwargs)

except ImportError:  # pragma: no cover - celery not installed
    celery_app = None
    run_job = None
    logger.info("celery_not_installed", extra={"detail": "the inline job backend will be used"})
