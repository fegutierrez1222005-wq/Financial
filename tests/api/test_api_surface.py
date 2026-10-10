"""API-level tests: authentication, authorisation, validation and error shape."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import Account


class TestHealth:
    def test_liveness_does_not_depend_on_the_database(self, client: TestClient) -> None:
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["service"] == "finagent-api"

    def test_readiness_reports_each_component(self, client: TestClient) -> None:
        body = client.get("/readiness").json()
        names = {component["name"] for component in body["components"]}
        assert {"database", "job_queue", "model_provider"} <= names

    def test_version_states_the_data_training_policy(self, client: TestClient) -> None:
        body = client.get("/version").json()
        assert "is not used for model training unless explicitly authorized" in (
            body["data_training_policy"]
        )


class TestAuthentication:
    def test_protected_routes_require_credentials(self, client: TestClient) -> None:
        response = client.get("/api/v1/agents")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"

    def test_a_garbage_token_is_rejected(self, client: TestClient, account: Account) -> None:
        response = client.get(
            "/api/v1/agents",
            headers={"Authorization": "Bearer not.a.real.token", "X-Workspace-Id": account.workspace_id},
        )
        assert response.status_code == 401

    def test_refresh_rotates_the_token(self, client: TestClient, account: Account) -> None:
        first = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": account.refresh_token}
        )
        assert first.status_code == 200
        rotated = first.json()["refresh_token"]
        assert rotated != account.refresh_token

        replay = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": account.refresh_token}
        )
        assert replay.status_code == 401, "a used refresh token must not work twice"

    def test_logout_revokes_the_session(self, client: TestClient, make_account) -> None:
        account = make_account(seed_demo=False)
        assert client.get("/api/v1/workspaces", headers=account.headers()).status_code == 200
        client.post("/api/v1/auth/logout", json={"refresh_token": account.refresh_token})
        # The access token is bound to the session, so it stops working immediately.
        assert client.get("/api/v1/workspaces", headers=account.headers()).status_code == 401

    def test_wrong_password_does_not_reveal_whether_the_account_exists(
        self, client: TestClient, account: Account
    ) -> None:
        known = client.post(
            "/api/v1/auth/login", json={"email": account.email, "password": "Wrong-Password-1"}
        )
        unknown = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "Wrong-Password-1"},
        )
        assert known.status_code == unknown.status_code == 401
        assert known.json()["error"]["message"] == unknown.json()["error"]["message"]

    def test_weak_passwords_are_refused(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "password", "seed_demo_workspace": False},
        )
        assert response.status_code == 422


class TestAuthorization:
    def _invite(self, client: TestClient, owner: Account, member: Account, role: str) -> None:
        invitation = client.post(
            "/api/v1/workspaces/current/invitations",
            headers=owner.headers(),
            json={"email": member.email, "role": role},
        )
        assert invitation.status_code == 201, invitation.text
        accepted = client.post(
            "/api/v1/auth/invitations/accept",
            headers={"Authorization": f"Bearer {member.access_token}"},
            json={"token": invitation.json()["invitation_token"]},
        )
        assert accepted.status_code == 200, accepted.text

    def test_a_viewer_can_read_but_not_create(
        self, client: TestClient, make_account
    ) -> None:
        owner = make_account()
        viewer = make_account(seed_demo=False)
        self._invite(client, owner, viewer, "VIEWER")

        headers = {
            "Authorization": f"Bearer {viewer.access_token}",
            "X-Workspace-Id": owner.workspace_id,
        }
        assert client.get("/api/v1/agents", headers=headers).status_code == 200

        forbidden = client.post(
            "/api/v1/agents", headers=headers, json={"name": "Viewer's agent"}
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["details"]["required_permission"] == "agent:create"

    def test_a_researcher_can_create_but_not_invite(
        self, client: TestClient, make_account
    ) -> None:
        owner = make_account()
        researcher = make_account(seed_demo=False)
        self._invite(client, owner, researcher, "RESEARCHER")

        headers = {
            "Authorization": f"Bearer {researcher.access_token}",
            "X-Workspace-Id": owner.workspace_id,
        }
        created = client.post(
            "/api/v1/agents", headers=headers, json={"name": "Researcher's agent"}
        )
        assert created.status_code == 201

        invite = client.post(
            "/api/v1/workspaces/current/invitations",
            headers=headers,
            json={"email": "someone@example.com", "role": "VIEWER"},
        )
        assert invite.status_code == 403

    def test_the_permission_matrix_is_published(self, client: TestClient, account: Account) -> None:
        roles = client.get("/api/v1/roles", headers=account.headers()).json()
        by_role = {entry["role"]: set(entry["permissions"]) for entry in roles}
        assert by_role["VIEWER"] < by_role["RESEARCHER"] < by_role["ADMIN"] < by_role["OWNER"]
        assert "workspace:delete" in by_role["OWNER"] - by_role["ADMIN"]


class TestErrorHandling:
    def test_every_error_carries_a_code_and_request_id(self, client: TestClient) -> None:
        response = client.get("/api/v1/agents/does-not-exist")
        body = response.json()["error"]
        assert set(body) >= {"code", "message", "retryable", "details", "request_id"}
        assert body["request_id"]

    def test_internals_are_never_echoed(self, client: TestClient, account: Account) -> None:
        response = client.get(
            "/api/v1/agents/' OR 1=1 --", headers=account.headers()
        )
        assert response.status_code == 404
        text = response.text.lower()
        for leak in ("traceback", "sqlalchemy", "select ", "sqlite"):
            assert leak not in text

    def test_validation_errors_name_the_offending_field(
        self, client: TestClient, account: Account
    ) -> None:
        response = client.post(
            "/api/v1/agents",
            headers=account.headers(),
            json={"name": "Over-hot agent", "temperature": 99.0},
        )
        assert response.status_code == 422
        fields = {item["field"] for item in response.json()["error"]["details"]["fields"]}
        assert "temperature" in fields

    def test_security_headers_are_present(self, client: TestClient) -> None:
        headers = client.get("/health").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Request-ID"]


class TestAgentBuilder:
    def test_updating_an_agent_creates_a_new_version(
        self, client: TestClient, account: Account
    ) -> None:
        created = client.post(
            "/api/v1/agents",
            headers=account.headers(),
            json={"name": "Versioned analyst", "tools": ["DOCUMENT_SEARCH"]},
        ).json()
        first_version = created["current_version"]["id"]

        updated = client.post(
            f"/api/v1/agents/{created['id']}/versions",
            headers=account.headers(),
            json={
                "name": "Versioned analyst",
                "tools": ["DOCUMENT_SEARCH", "CALCULATOR"],
                "change_note": "Added the calculator.",
            },
        )
        assert updated.status_code == 201, updated.text
        assert updated.json()["id"] != first_version
        assert updated.json()["version_number"] == 2
        assert updated.json()["config_hash"] != created["current_version"]["config_hash"]

        history = client.get(
            f"/api/v1/agents/{created['id']}/versions", headers=account.headers()
        ).json()
        assert len(history) == 2, "the previous version must remain retrievable"

    def test_unknown_tools_are_refused(self, client: TestClient, account: Account) -> None:
        response = client.post(
            "/api/v1/agents",
            headers=account.headers(),
            json={"name": "Over-powered agent", "tools": ["SHELL_ACCESS"]},
        )
        assert response.status_code == 422

    def test_the_tool_catalog_declares_network_requirements(
        self, client: TestClient, account: Account
    ) -> None:
        tools = client.get("/api/v1/catalog/tools", headers=account.headers()).json()
        by_name = {tool["name"]: tool for tool in tools}
        assert by_name["PYTHON"]["requires_network"] is False
        assert by_name["PYTHON"]["is_deterministic"] is True
        for tool in tools:
            if not tool["available"]:
                assert tool["unavailable_reason"], tool["name"]

    def test_the_model_catalog_marks_mock_models(
        self, client: TestClient, account: Account
    ) -> None:
        models = client.get("/api/v1/catalog/models", headers=account.headers()).json()
        mocks = [model for model in models if model["is_mock"]]
        assert mocks, "the deterministic provider must be listed"
        for model in mocks:
            assert model["available"] is True
            assert "deterministic" in (model["notes"] or "").lower()
        real = [model for model in models if not model["is_mock"]]
        assert all(model["available"] is False for model in real), (
            "no vendor credentials are configured in tests, so no vendor model may claim to be available"
        )
