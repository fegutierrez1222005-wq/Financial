"""Shared test fixtures.

Tests run entirely offline against SQLite. That is deliberate: the seven critical security
controls must be verifiable on any machine without Postgres, Redis or a provider API key,
so there is no excuse for skipping them. The portable column types in
``finagent_api.db.types`` are what make it possible.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

#: Must be set before anything imports application settings.
_TMP = Path(tempfile.mkdtemp(prefix="finagent-test-"))
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite:///{_TMP / 'finagent.db'}",
        "SECRET_KEY": "test-secret-key-not-for-production-use",
        "JOB_BACKEND": "inline",
        "RATE_LIMIT_ENABLED": "false",
        "STORAGE_DIR": str(_TMP / "storage"),
        "ENABLE_DEMO_PROVIDERS": "true",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "text",
        "BCRYPT_ROUNDS": "4",
        # No provider credentials: every model and embedding call must resolve to the
        # deterministic local providers, which is what the offline guarantees require.
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_API_KEY": "",
        "ALPHA_VANTAGE_API_KEY": "",
        "POLYGON_API_KEY": "",
        "SEC_USER_AGENT": "",
    }
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session as DbSession  # noqa: E402

from finagent_api.db.session import create_all, get_engine, get_session_factory, reset_engine  # noqa: E402
from finagent_api.main import create_app  # noqa: E402
from finagent_api.services.providers import reset_provider_caches  # noqa: E402
from finagent_api.settings import get_settings  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    get_settings.cache_clear()
    reset_engine()
    reset_provider_caches()
    create_all()
    yield
    get_engine().dispose()


@pytest.fixture
def db() -> Iterator[DbSession]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture(scope="session")
def app():  # noqa: ANN201
    return create_app()


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # noqa: ANN001
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@dataclass
class Account:
    """A registered user plus everything a test needs to act as them."""

    email: str
    password: str
    user_id: str
    organization_id: str
    access_token: str
    refresh_token: str
    workspace_id: str
    workspace_name: str

    def headers(self, workspace_id: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Workspace-Id": workspace_id or self.workspace_id,
        }


_counter = {"n": 0}


def _next_email() -> str:
    _counter["n"] += 1
    return f"user{_counter['n']}@example.com"


@pytest.fixture
def make_account(client: TestClient):  # noqa: ANN201
    """Register an account and return it with its demo workspace resolved."""

    def factory(*, seed_demo: bool = True, email: str | None = None) -> Account:
        address = email or _next_email()
        password = "Correct-Horse-Battery-9"
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": address,
                "password": password,
                "full_name": "Test Analyst",
                "organization_name": f"Org for {address}",
                "seed_demo_workspace": seed_demo,
            },
        )
        assert response.status_code == 201, response.text
        tokens = response.json()

        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        workspaces = client.get("/api/v1/workspaces", headers=headers).json()
        assert workspaces, "registration should always create at least one workspace"
        # Prefer the seeded demo workspace when it exists: it has the corpus the tests need.
        workspace = next(
            (candidate for candidate in workspaces if candidate["is_demo"]), workspaces[0]
        )

        return Account(
            email=address,
            password=password,
            user_id=tokens["user_id"],
            organization_id=tokens["organization_id"],
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            workspace_id=workspace["id"],
            workspace_name=workspace["name"],
        )

    return factory


@pytest.fixture
def account(make_account) -> Account:  # noqa: ANN001
    return make_account()


def _agent_id_by_name(client: TestClient, account: Account, fragment: str) -> str:
    agents = client.get("/api/v1/agents", headers=account.headers()).json()
    matches = [agent for agent in agents if fragment.lower() in agent["name"].lower()]
    assert matches, f"no seeded agent matching {fragment!r} in {[a['name'] for a in agents]}"
    return matches[0]["id"]


@pytest.fixture
def demo_agent_id(client: TestClient, account: Account) -> str:
    """The well-behaved seeded analyst."""
    return _agent_id_by_name(client, account, "Equity Research Analyst")


@pytest.fixture
def flawed_agent_id(client: TestClient, account: Account) -> str:
    """The deliberately flawed fixture, used to prove the evaluators catch failures."""
    return _agent_id_by_name(client, account, "Unreliable Analyst")


def create_run(
    client: TestClient,
    account: Account,
    *,
    agent_id: str,
    question: str,
    information_cutoff: datetime | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create and execute a research run, returning the run payload."""
    response = client.post(
        "/api/v1/research/runs",
        headers=account.headers(),
        json={
            "agent_id": agent_id,
            "run_now": True,
            "task": {
                "template": "custom",
                "question": question,
                "inputs": inputs or {},
                "information_cutoff": (
                    information_cutoff.astimezone(timezone.utc).isoformat()
                    if information_cutoff
                    else None
                ),
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
