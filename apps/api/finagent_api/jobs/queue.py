"""Job queue abstraction.

Long operations (research runs, suites, backtests, experiments, ingestion) are submitted
through this interface instead of being called directly from a request handler. Two
backends exist:

``inline``
    Runs the job synchronously in the calling process. Correct, fully observable and the
    default for development, tests and single-node deployments.
``celery``
    Hands the job to a Celery worker over Redis. Required for production, where a research
    run must not hold an HTTP worker for minutes.

The submission result is deliberately identical in both cases so callers never branch on
the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from finagent_api.settings import Settings, get_settings
from finagent_core.logging import get_logger

logger = get_logger(__name__)

#: Job name -> callable. Jobs are registered by ``finagent_api.jobs.tasks``.
_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_job(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        _REGISTRY[name] = func
        return func

    return decorator


def registered_jobs() -> dict[str, Callable[..., Any]]:
    return dict(_REGISTRY)


@dataclass(frozen=True)
class JobHandle:
    """What the API tells a client about a submitted job."""

    job_name: str
    backend: str
    job_id: str | None = None
    completed: bool = False
    result: Any = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_name": self.job_name,
            "backend": self.backend,
            "job_id": self.job_id,
            "completed": self.completed,
            "error": self.error,
        }


class JobQueue:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def backend(self) -> str:
        return self.settings.job_backend

    def submit(self, job_name: str, **kwargs: Any) -> JobHandle:
        func = _REGISTRY.get(job_name)
        if func is None:
            raise KeyError(f"unknown job: {job_name}")

        if self.backend == "celery":
            handle = self._submit_celery(job_name, kwargs)
            if handle is not None:
                return handle
            logger.warning("celery_unavailable_running_inline", extra={"job_name": job_name})

        return self._run_inline(job_name, func, kwargs)

    def _run_inline(
        self, job_name: str, func: Callable[..., Any], kwargs: dict[str, Any]
    ) -> JobHandle:
        logger.info("job_started", extra={"job_name": job_name, "backend": "inline"})
        try:
            result = func(**kwargs)
        except Exception as exc:  # noqa: BLE001 - the handle carries the failure to the caller
            logger.exception("job_failed", extra={"job_name": job_name})
            return JobHandle(
                job_name=job_name, backend="inline", completed=True, error=str(exc)[:500]
            )
        logger.info("job_finished", extra={"job_name": job_name, "backend": "inline"})
        return JobHandle(job_name=job_name, backend="inline", completed=True, result=result)

    def _submit_celery(self, job_name: str, kwargs: dict[str, Any]) -> JobHandle | None:
        try:  # pragma: no cover - requires a broker
            from finagent_api.jobs.celery_app import run_job

            async_result = run_job.delay(job_name, kwargs)
            return JobHandle(job_name=job_name, backend="celery", job_id=async_result.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "celery_submit_failed", extra={"job_name": job_name, "detail": str(exc)[:200]}
            )
            return None


_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        _queue = JobQueue()
    return _queue


def reset_queue() -> None:
    """Drop the cached queue so a test can change the backend setting."""
    global _queue
    _queue = None
