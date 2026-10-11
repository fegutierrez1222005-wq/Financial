"""Liveness, readiness and build information.

``/health`` answers "is the process up" and must stay dependency-free so a failing database
does not take the container out of the load balancer for the wrong reason. ``/readiness``
answers "can this process serve traffic" and does check dependencies.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from finagent_api import __version__
from finagent_api.db.session import get_engine, is_postgres
from finagent_api.jobs.queue import get_queue
from finagent_api.middleware import get_rate_limiter
from finagent_api.schemas import HealthResponse, ReadinessComponent, ReadinessResponse
from finagent_api.services.providers import provider_overview
from finagent_api.services.retrieval import pgvector_degradation
from finagent_api.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="finagent-api",
        version=__version__,
        environment=settings.environment,
    )


@router.get("/readiness", response_model=ReadinessResponse, summary="Readiness probe")
def readiness() -> ReadinessResponse:
    components: list[ReadinessComponent] = []

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        components.append(ReadinessComponent(name="database", ready=True))
    except Exception as exc:
        components.append(
            ReadinessComponent(name="database", ready=False, detail=str(exc)[:200])
        )

    queue = get_queue()
    components.append(
        ReadinessComponent(name="job_queue", ready=True, detail=f"backend={queue.backend}")
    )

    degraded = pgvector_degradation()
    components.append(
        ReadinessComponent(
            name="vector_search",
            ready=degraded is None,
            detail=(
                f"falling back to an in-process scan — {degraded}"
                if degraded
                else "indexed similarity search"
                if is_postgres()
                else "in-process similarity (SQLite)"
            ),
        )
    )
    components.append(
        ReadinessComponent(
            name="rate_limiter", ready=True, detail=f"backend={get_rate_limiter().backend}"
        )
    )

    overview = provider_overview()
    available = overview.get("available_models", [])
    vendor = [entry for entry in available if not entry.get("is_mock")]
    components.append(
        ReadinessComponent(
            name="model_provider",
            ready=bool(available),
            detail=(
                f"{len(vendor)} vendor model(s) configured"
                if vendor
                else "only the deterministic local provider is available; output will be "
                "labelled as simulated"
                if available
                else "no model provider is available"
            ),
        )
    )

    return ReadinessResponse(
        ready=all(component.ready for component in components), components=components
    )


@router.get("/version", summary="Build and configuration summary")
def version() -> dict[str, object]:
    settings = get_settings()
    return {
        "service": "finagent-api",
        "version": __version__,
        "environment": settings.environment,
        "api_prefix": settings.api_prefix,
        "job_backend": settings.job_backend,
        "data_training_policy": (
            "Customer data is isolated and is not used for model training unless explicitly "
            "authorized."
        ),
    }
