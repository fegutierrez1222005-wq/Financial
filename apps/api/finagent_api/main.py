"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finagent_api import __version__
from finagent_api.errors import register_exception_handlers
from finagent_api.jobs import queue as job_queue  # noqa: F401 - registers the job table
from finagent_api.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from finagent_api.routers import ALL_ROUTERS, ROOT_ROUTERS
from finagent_api.settings import Settings, get_settings
from finagent_core.logging import configure_logging, get_logger

logger = get_logger(__name__)

DESCRIPTION = """
The evaluation and observability layer for institutional financial AI.

**What this API does.** Build research agents, run them against financial documents and
market data, capture every action they take, score the output against a golden dataset,
and backtest the ideas under explicit cost and execution-lag assumptions.

**Three guarantees the API makes about its own output.**

1. *Nothing simulated is presented as live.* Any response produced by a deterministic mock
   provider or the demo dataset is flagged (`used_mock_model`, `is_demo`, `is_mock`).
2. *Historical research cannot see the future.* A run with an information cutoff is
   restricted by SQL and provider-level filters, not by instructions in a prompt. Evidence
   with an unknown publication timestamp is excluded rather than assumed admissible.
3. *A score is a research-quality score.* It measures evidence grounding, citation accuracy
   and numerical correctness. It is not a prediction of investment returns.

Customer data is isolated and is not used for model training unless explicitly authorized.
""".strip()

TAGS_METADATA = [
    {"name": "health", "description": "Liveness, readiness and build information."},
    {"name": "auth", "description": "Registration, sessions, MFA and invitations."},
    {"name": "workspaces", "description": "Organizations, workspaces, members and API keys."},
    {"name": "agents", "description": "Agent builder and immutable version history."},
    {"name": "research", "description": "Research tasks, runs, traces and debate."},
    {"name": "evaluations", "description": "Suites, scoring and the agent scoreboard."},
    {"name": "backtests", "description": "Historical simulation with explicit assumptions."},
    {"name": "experiments", "description": "A/B experiments, benchmarks and comparisons."},
    {"name": "data", "description": "Documents, retrieval, datasets and provider status."},
    {"name": "platform", "description": "Observability, billing, webhooks and administration."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.log_format == "json")

    problems = settings.insecure_defaults()
    if problems and settings.is_production:
        # Refuse to serve production traffic with development defaults rather than warn.
        raise RuntimeError(f"unsafe production configuration: {'; '.join(problems)}")
    for problem in problems:
        logger.warning("insecure_default", extra={"detail": problem})

    logger.info(
        "api_started",
        extra={
            "version": __version__,
            "environment": settings.environment,
            "job_backend": settings.job_backend,
        },
    )
    yield
    logger.info("api_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.product_name,
        description=DESCRIPTION,
        version=__version__,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Workspace-Id", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms", "X-RateLimit-Remaining"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    for router in ROOT_ROUTERS:
        app.include_router(router)
    for router in ALL_ROUTERS:
        app.include_router(router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": settings.product_name,
            "version": __version__,
            "docs": "/docs",
            "api": settings.api_prefix,
        }

    return app


app = create_app()
