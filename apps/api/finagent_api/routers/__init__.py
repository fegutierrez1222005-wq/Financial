"""HTTP routers.

``ALL_ROUTERS`` is the single place every route is mounted from, so no endpoint can be
added without appearing here.
"""

from fastapi import APIRouter

from finagent_api.routers import (
    agents,
    auth,
    backtests,
    data,
    evaluations,
    experiments,
    health,
    platform,
    research,
    workspaces,
)

#: Mounted under the API prefix.
ALL_ROUTERS: list[APIRouter] = [
    auth.router,
    workspaces.router,
    agents.router,
    research.router,
    evaluations.router,
    backtests.router,
    experiments.router,
    data.router,
    platform.router,
]

#: Mounted at the root so probes do not depend on the versioned prefix.
ROOT_ROUTERS: list[APIRouter] = [health.router]

__all__ = ["ALL_ROUTERS", "ROOT_ROUTERS"]
