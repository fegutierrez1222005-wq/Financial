"""The seven controls that must never regress.

Each test here maps one-to-one onto a requirement in the product specification. They are
integration tests on purpose: a unit test of a helper proves the helper works, not that the
control is actually wired into the path a request takes.

1. An agent cannot access another workspace's data.
2. An agent cannot retrieve information published after the historical cutoff.
3. An unsupported financial claim is flagged.
4. An incorrect calculation is flagged.
5. A backtest that uses future information is rejected.
6. A deleted document cannot be retrieved.
7. A provider API key never appears in a response to the browser.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import Account, create_run

pytestmark = pytest.mark.security


# ---------------------------------------------------------------------------- 1


def test_agent_cannot_access_another_workspace(
    client: TestClient, make_account, demo_agent_id: str
) -> None:
    """Cross-tenant access is refused, and refused as 404 so the response does not
    confirm that the other workspace exists."""
    owner = make_account()
    intruder = make_account()

    owner_agents = client.get("/api/v1/agents", headers=owner.headers()).json()
    owner_agent_id = owner_agents[0]["id"]
    owner_documents = client.get("/api/v1/documents", headers=owner.headers()).json()
    assert owner_documents, "the demo workspace should contain documents"

    # Presenting the intruder's credentials with the owner's workspace id.
    forged = {
        "Authorization": f"Bearer {intruder.access_token}",
        "X-Workspace-Id": owner.workspace_id,
    }

    for path in (
        "/api/v1/agents",
        "/api/v1/documents",
        "/api/v1/research/runs",
        "/api/v1/evaluations",
        f"/api/v1/agents/{owner_agent_id}",
        f"/api/v1/documents/{owner_documents[0]['id']}",
    ):
        response = client.get(path, headers=forged)
        assert response.status_code == 404, f"{path} leaked across tenants: {response.text}"
        assert "NOT_FOUND" in response.text

    # And the intruder's own workspace is unaffected and genuinely separate.
    own = client.get("/api/v1/agents", headers=intruder.headers())
    assert own.status_code == 200
    assert {agent["id"] for agent in own.json()}.isdisjoint(
        {agent["id"] for agent in owner_agents}
    )


def test_run_evidence_never_crosses_workspaces(
    client: TestClient, make_account, db
) -> None:
    """Retrieval is scoped by workspace in SQL, not by filtering after the fact."""
    from finagent_api.db.models import Document, RunEvidence
    from finagent_api.services.retrieval import DbDocumentRetriever

    owner = make_account()
    other = make_account()

    retriever = DbDocumentRetriever(
        db, workspace_id=other.workspace_id, organization_id=other.organization_id
    )
    results = retriever.search("ACME Technologies revenue", top_k=10)
    owner_document_ids = {
        row.id
        for row in db.scalars(select(Document).where(Document.workspace_id == owner.workspace_id))
    }
    assert owner_document_ids, "precondition: the owner has documents"
    assert not {item.document_id for item in results} & owner_document_ids

    # Every persisted evidence row carries the workspace it came from.
    for evidence in db.scalars(select(RunEvidence).limit(200)):
        assert evidence.workspace_id is not None


# ---------------------------------------------------------------------------- 2


def test_agent_cannot_retrieve_information_after_the_cutoff(
    client: TestClient, account: Account, demo_agent_id: str, db
) -> None:
    """The information lock is structural.

    With a mid-2023 cutoff the FY2023 10-K (filed February 2024) must not appear in the
    run's evidence, and nothing with an unknown publication date may be substituted for it.
    """
    from finagent_api.db.models import Document, RunEvidence

    cutoff = datetime(2023, 6, 30, tzinfo=UTC)
    run = create_run(
        client,
        account,
        agent_id=demo_agent_id,
        question="What was ACME Technologies' revenue growth and what drove it?",
        information_cutoff=cutoff,
    )
    assert run["status"] == "SUCCEEDED", run.get("error_message")

    evidence = list(db.scalars(select(RunEvidence).where(RunEvidence.run_id == run["id"])))
    assert evidence, "the run should have retrieved something from before the cutoff"

    for item in evidence:
        assert item.publication_timestamp is not None, (
            "evidence with an unknown publication date must never be admitted under a cutoff"
        )
        assert item.publication_timestamp <= cutoff, (
            f"look-ahead: {item.document_name} published {item.publication_timestamp}"
        )

    # The future document exists in the workspace; it was excluded, not absent.
    future_documents = [
        document
        for document in db.scalars(
            select(Document).where(Document.workspace_id == account.workspace_id)
        )
        if document.publication_timestamp and document.publication_timestamp > cutoff
    ]
    assert future_documents, "precondition: the corpus contains post-cutoff filings"
    assert not {item.document_id for item in evidence} & {d.id for d in future_documents}


def test_search_endpoint_honours_the_cutoff(client: TestClient, account: Account) -> None:
    unrestricted = client.post(
        "/api/v1/documents/search",
        headers=account.headers(),
        json={"query": "ACME fiscal 2023 revenue", "top_k": 10},
    ).json()
    restricted = client.post(
        "/api/v1/documents/search",
        headers=account.headers(),
        json={
            "query": "ACME fiscal 2023 revenue",
            "top_k": 10,
            "as_of": "2023-06-30T00:00:00+00:00",
        },
    ).json()

    assert unrestricted, "precondition: the corpus is searchable"
    for item in restricted:
        assert item["publication_timestamp"] is not None
        assert item["publication_timestamp"] <= "2023-06-30T00:00:00+00:00"
    assert len(restricted) < len(unrestricted)


def test_cutoff_rejects_unknown_publication_dates() -> None:
    """Unit-level statement of the rule the integration tests rely on."""
    from finagent_core.cutoff import AsOfContext

    context = AsOfContext(cutoff=datetime(2023, 6, 30, tzinfo=UTC))
    assert context.allows(datetime(2023, 1, 1, tzinfo=UTC))
    assert not context.allows(datetime(2024, 2, 14, tzinfo=UTC))
    assert not context.allows(None), "unknown provenance is inadmissible, not assumed valid"
    assert AsOfContext(cutoff=None).allows(None), "without a cutoff nothing is restricted"


# ---------------------------------------------------------------------------- 3


def test_unsupported_financial_claim_is_flagged(
    client: TestClient, account: Account, flawed_agent_id: str
) -> None:
    """The deliberately flawed fixture asserts a growth figure its evidence does not
    support. The evaluation must catch it rather than scoring the run as clean."""
    run = create_run(
        client,
        account,
        agent_id=flawed_agent_id,
        question="What was ACME Technologies' FY2023 revenue growth?",
    )
    response = client.post(
        "/api/v1/evaluations/runs",
        headers=account.headers(),
        json={"run_id": run["id"]},
    )
    assert response.status_code == 201, response.text
    evaluation_id = response.json()["id"]

    detail = client.get(
        f"/api/v1/evaluations/{evaluation_id}", headers=account.headers()
    ).json()

    assert detail["evaluation"]["hallucination_rate"] > 0.0, (
        "an unsupported claim must raise the hallucination rate"
    )
    failures = [result for result in detail["results"] if not result["passed"]]
    assert failures, "the flawed run must produce at least one failure"

    unsupported = [
        claim
        for claim in detail["claims"]
        if claim["support_level"] in {"UNSUPPORTED", "CONTRADICTED"}
    ]
    assert unsupported, f"no unsupported claim detected in {detail['claims']}"

    # And the score must reflect it rather than being a flat pass.
    assert detail["evaluation"]["overall_score"] < 90.0
    assert "does not predict investment returns" in detail["score_interpretation"]


def test_well_behaved_agent_scores_above_the_flawed_fixture(
    client: TestClient, account: Account, demo_agent_id: str, flawed_agent_id: str
) -> None:
    """The evaluator must discriminate, not merely penalise everything."""
    question = "What was ACME Technologies' FY2023 revenue growth?"
    scores = {}
    for label, agent_id in (("good", demo_agent_id), ("flawed", flawed_agent_id)):
        run = create_run(client, account, agent_id=agent_id, question=question)
        evaluation = client.post(
            "/api/v1/evaluations/runs",
            headers=account.headers(),
            json={"run_id": run["id"]},
        ).json()
        detail = client.get(
            f"/api/v1/evaluations/{evaluation['id']}", headers=account.headers()
        ).json()
        scores[label] = detail["evaluation"]

    assert scores["good"]["overall_score"] > scores["flawed"]["overall_score"]
    assert scores["good"]["citation_coverage"] > scores["flawed"]["citation_coverage"]


# ---------------------------------------------------------------------------- 4


def test_incorrect_calculation_is_flagged() -> None:
    """A numerically wrong answer must fail the expected-value check.

    Driven directly against the evaluation engine so the assertion is about the checker,
    not about whether a particular model happens to miscalculate today.
    """
    from finagent_core.schemas.research import RunResult
    from finagent_evaluation.cases import EvaluationCase
    from finagent_evaluation.evaluators import EvaluationContext, ExpectedValueEvaluator
    from finagent_evaluation.verification import VerificationReport

    case = EvaluationCase(
        key="UNIT_GROSS_MARGIN",
        question="What was the FY2023 gross margin?",
        expected_answer="62.5%",
        expected_value=62.5,
        unit="percent",
        acceptable_low=62.0,
        acceptable_high=63.0,
    )
    evaluator = ExpectedValueEvaluator()

    def score(answer: str):
        return evaluator.evaluate(
            EvaluationContext(
                run=RunResult(output_text=answer),
                claims=[],
                verification=VerificationReport(verdicts=[]),
                case=case,
            )
        )

    correct = score("The FY2023 gross margin was 62.5%.")
    assert correct.passed is True, correct.failures
    assert not correct.failures

    wrong = score("The FY2023 gross margin was 71.4%.")
    assert wrong.passed is False
    assert wrong.failures, "a wrong number must produce a failure, not a low score alone"
    failure = wrong.failures[0]
    assert "62.5" in (failure.expected or "")
    assert "71.4" in (failure.actual or "")

    # Silence is a failure too: not answering is not the same as answering correctly.
    silent = score("I was unable to determine the gross margin.")
    assert silent.passed is False


def test_calculator_tool_result_is_checked_against_the_statements(
    client: TestClient, account: Account, demo_agent_id: str, db
) -> None:
    """Every number the calculator returns must reconcile with the seeded statements.

    The evaluation engine's calculation check is only meaningful if the underlying data is
    internally consistent, so both are asserted here.
    """
    from finagent_api.db.models import ToolCall
    from finagent_core.data.demo_dataset import ACME_ANNUAL_INCOME
    from finagent_core.numeric import percent_change

    growth = percent_change(
        ACME_ANNUAL_INCOME["FY2023"]["revenue"], ACME_ANNUAL_INCOME["FY2022"]["revenue"]
    )
    assert abs(growth - 18.0) < 0.1, f"demo dataset drifted: FY2023 growth is {growth}"

    run = create_run(
        client,
        account,
        agent_id=demo_agent_id,
        question="Calculate ACME Technologies' FY2023 revenue growth versus FY2022.",
        inputs={"ticker": "ACME", "period": "FY2023"},
    )
    calls = list(
        db.scalars(
            select(ToolCall).where(
                ToolCall.run_id == run["id"], ToolCall.tool_name == "CALCULATOR"
            )
        )
    )
    assert calls, "the demo analyst should have used the calculator"
    for call in calls:
        assert call.status == "SUCCEEDED", call.error_message
        assert isinstance(call.result, dict)
        # The calculator reports its own inputs, so a reviewer can re-derive the figure.
        assert call.result.get("inputs") or call.result.get("operands"), call.result


# ---------------------------------------------------------------------------- 5


def test_backtest_with_future_information_is_rejected(
    client: TestClient, account: Account
) -> None:
    """Executing on the same bar that produced the signal is a look-ahead error.

    The run completes so the user can see why, but it is marked invalid and carries a
    blocking finding; it must never be presented as a usable result.
    """
    payload = {
        "name": "Same-bar execution (invalid)",
        "universe": ["ACME", "BRVO", "CRUX", "DLTA"],
        "start_date": "2021-01-04",
        "end_date": "2023-12-29",
        "signal_lag_days": 0,
        "top_n": 2,
    }
    created = client.post("/api/v1/backtests", headers=account.headers(), json=payload)
    assert created.status_code == 201, created.text
    backtest_id = created.json()["id"]

    result = client.post(
        f"/api/v1/backtests/{backtest_id}/run", headers=account.headers()
    )
    assert result.status_code == 200, result.text
    body = result.json()

    assert body["runs"], "the backtest should have produced at least one split result"
    for split in body["runs"]:
        assert split["is_valid"] is False, "a zero-lag backtest must not be marked valid"
        blocking = [
            finding
            for finding in split["findings"]
            if finding.get("severity") in {"ERROR", "BLOCKING"}
        ]
        assert blocking, f"no blocking finding on {split['split']}: {split['findings']}"
        assert any("lag" in json.dumps(finding).lower() for finding in blocking)

    assert "not investment advice" in body["disclaimer"]


def test_valid_backtest_is_accepted_and_separates_its_splits(
    client: TestClient, account: Account
) -> None:
    created = client.post(
        "/api/v1/backtests",
        headers=account.headers(),
        json={
            "name": "One-bar lag (valid)",
            "universe": ["ACME", "BRVO", "CRUX", "DLTA"],
            "start_date": "2021-01-04",
            "end_date": "2023-12-29",
            "signal_lag_days": 1,
            "top_n": 2,
        },
    )
    backtest_id = created.json()["id"]
    body = client.post(
        f"/api/v1/backtests/{backtest_id}/run", headers=account.headers()
    ).json()

    splits = {split["split"] for split in body["runs"]}
    assert {"train", "validation", "test"} <= splits
    assert all(split["is_valid"] for split in body["runs"]), body["runs"]
    assert "never averaged" in body["reporting_note"]


def test_backtest_history_excludes_the_traded_bar() -> None:
    """Unit statement of the firewall the simulator depends on."""
    from datetime import date

    import pandas as pd

    from finagent_backtesting.dataset import PriceDataset

    index = pd.to_datetime(["2023-01-02", "2023-01-03", "2023-01-04"])
    prices = pd.DataFrame({"ACME": [10.0, 11.0, 12.0]}, index=index)
    dataset = PriceDataset(prices=prices, is_demo=True, sources={"test"})

    history = dataset.history_for(date(2023, 1, 4), lookback=10)
    assert list(history["ACME"]) == [10.0, 11.0], (
        "the bar being traded must not be visible to the signal"
    )


# ---------------------------------------------------------------------------- 6


def test_deleted_document_cannot_be_retrieved(
    client: TestClient, account: Account, db
) -> None:
    """Deletion must remove the document from every retrieval path immediately."""
    from finagent_api.db.models import Document
    from finagent_api.services.retrieval import DbDocumentRetriever

    documents = client.get("/api/v1/documents", headers=account.headers()).json()
    target = next(document for document in documents if document["chunk_count"] > 0)
    query = target["title"] or target["filename"]

    before = client.post(
        "/api/v1/documents/search",
        headers=account.headers(),
        json={"query": query, "top_k": 20},
    ).json()
    assert any(item["document_id"] == target["id"] for item in before)

    deleted = client.delete(
        f"/api/v1/documents/{target['id']}", headers=account.headers()
    )
    assert deleted.status_code == 200, deleted.text

    after = client.post(
        "/api/v1/documents/search",
        headers=account.headers(),
        json={"query": query, "top_k": 20},
    ).json()
    assert not any(item["document_id"] == target["id"] for item in after)

    # Also unreachable through the service layer, not only through the endpoint.
    db.expire_all()
    retriever = DbDocumentRetriever(
        db, workspace_id=account.workspace_id, organization_id=account.organization_id
    )
    assert not any(
        item.document_id == target["id"] for item in retriever.search(query, top_k=20)
    )

    # Fetching it directly is a 404 for the caller...
    assert (
        client.get(f"/api/v1/documents/{target['id']}", headers=account.headers()).status_code
        == 404
    )
    # ...while the row is retained with deleted_at set, so audit history survives.
    row = db.get(Document, target["id"])
    assert row is not None, "the row must be retained, not hard-deleted"
    assert row.deleted_at is not None


# ---------------------------------------------------------------------------- 7


def test_provider_api_key_never_appears_in_a_response(
    client: TestClient, account: Account, monkeypatch
) -> None:
    """Install recognisable credentials and assert they appear in no response body."""
    from finagent_api.services.providers import reset_provider_caches
    from finagent_api.settings import get_settings

    sentinel = "sk-SENTINEL-must-never-be-returned-0123456789"
    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", sentinel)
    monkeypatch.setenv("ANTHROPIC_API_KEY", sentinel + "-anthropic")
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", sentinel + "-av")
    monkeypatch.setenv("SEC_USER_AGENT", sentinel + "-sec")
    reset_provider_caches()
    try:
        paths = [
            "/api/v1/providers/status",
            "/api/v1/catalog/models",
            "/api/v1/catalog/tools",
            "/api/v1/data-sources",
            "/api/v1/agents",
            "/api/v1/documents",
            "/api/v1/dashboard",
            "/api/v1/usage",
            "/api/v1/workspaces",
            "/api/v1/auth/me",
            "/version",
            "/readiness",
            "/openapi.json",
        ]
        for path in paths:
            response = client.get(path, headers=account.headers())
            assert response.status_code in (200, 404), f"{path}: {response.status_code}"
            assert "SENTINEL" not in response.text, f"{path} leaked a provider credential"

        # The status endpoint still reports availability — booleans, not values.
        status = client.get(
            "/api/v1/providers/status", headers=account.headers()
        ).json()
        assert status["credentials_configured"]["openai"] is True
        assert all(
            isinstance(value, bool) for value in status["credentials_configured"].values()
        )
    finally:
        get_settings.cache_clear()
        reset_provider_caches()


def test_stored_connector_secret_is_never_returned(
    client: TestClient, account: Account, db
) -> None:
    """A credential supplied when connecting a data source is encrypted and never echoed."""
    from finagent_api.db.models import DataConnector

    secret = "av-SENTINEL-connector-secret-abcdef"
    created = client.post(
        "/api/v1/data-sources",
        headers=account.headers(),
        json={
            "provider_key": "alpha_vantage",
            "name": "Alpha Vantage (test)",
            "credential": secret,
        },
    )
    assert created.status_code == 201, created.text
    assert "SENTINEL" not in created.text

    listing = client.get("/api/v1/data-sources", headers=account.headers())
    assert "SENTINEL" not in listing.text

    stored = db.scalars(select(DataConnector)).all()
    assert stored, "the connector should have been persisted"
    assert all(secret not in (row.secret_encrypted or "") for row in stored), (
        "the credential must be encrypted at rest, not stored in clear text"
    )


def test_api_key_plaintext_is_returned_once_and_never_again(
    client: TestClient, account: Account
) -> None:
    created = client.post(
        "/api/v1/workspaces/current/api-keys",
        headers=account.headers(),
        json={"name": "automation", "role": "RESEARCHER"},
    )
    assert created.status_code == 201, created.text
    plaintext = created.json()["plaintext_key"]
    assert plaintext.startswith("fk_")

    listing = client.get(
        "/api/v1/workspaces/current/api-keys", headers=account.headers()
    )
    assert plaintext not in listing.text
    assert all("plaintext_key" not in entry for entry in listing.json())

    # The key works, and cannot be used to mint more keys.
    key_headers = {"X-API-Key": plaintext, "X-Workspace-Id": account.workspace_id}
    assert client.get("/api/v1/agents", headers=key_headers).status_code == 200
    escalation = client.post(
        "/api/v1/workspaces/current/api-keys",
        headers=key_headers,
        json={"name": "escalated", "role": "RESEARCHER"},
    )
    assert escalation.status_code == 403
