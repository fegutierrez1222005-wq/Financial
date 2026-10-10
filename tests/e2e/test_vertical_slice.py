"""The vertical slice, exercised through the HTTP API exactly as a user would.

Sign up → demo workspace → agent → research run → trace → evaluation → suite → backtest →
experiment → dashboard. If this test passes, the product's core loop works end to end
without any external service.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Account, create_run

pytestmark = pytest.mark.slow


def test_full_research_loop(
    client: TestClient, account: Account, demo_agent_id: str
) -> None:
    headers = account.headers()

    # --- the seeded corpus is present and labelled as demo data -------------------
    documents = client.get("/api/v1/documents", headers=headers).json()
    assert documents
    assert all(document["is_demo"] for document in documents)
    assert all(document["status"] == "INDEXED" for document in documents)
    assert all(document["publication_timestamp"] for document in documents)

    # --- run the agent ------------------------------------------------------------
    run = create_run(
        client,
        account,
        agent_id=demo_agent_id,
        question="Summarise ACME Technologies' fiscal 2023 performance and the drivers behind it.",
        inputs={"ticker": "ACME", "period": "FY2023"},
    )
    assert run["status"] == "SUCCEEDED", run.get("error_message")
    assert run["evidence_count"] > 0
    assert run["used_mock_model"] is True, "offline runs must be labelled as simulated"
    assert run["used_demo_data"] is True
    assert run["reproducibility_key"]

    # --- the trace explains what the agent did ------------------------------------
    detail = client.get(f"/api/v1/research/runs/{run['id']}", headers=headers).json()
    assert detail["plan"], "a run must produce a readable plan"
    assert detail["trace"], "every action must be recorded"
    assert detail["evidence"], "every claim's source must be retrievable"
    assert detail["model_runs"] and all(entry["is_mock"] for entry in detail["model_runs"])
    tool_names = {call["tool_name"] for call in detail["tool_calls"]}
    assert "DOCUMENT_SEARCH" in tool_names

    sequences = [step["sequence"] for step in detail["trace"]]
    assert sequences == sorted(sequences), "the trace must be ordered"

    # --- score the run ------------------------------------------------------------
    evaluation = client.post(
        "/api/v1/evaluations/runs", headers=headers, json={"run_id": run["id"]}
    ).json()
    scored = client.get(
        f"/api/v1/evaluations/{evaluation['id']}", headers=headers
    ).json()
    assert scored["evaluation"]["status"] == "SUCCEEDED"
    assert 0.0 <= scored["evaluation"]["overall_score"] <= 100.0
    assert scored["scores"], "the report must break the score down by dimension"
    assert scored["claims"], "the report must show the claims it checked"
    assert sum(entry["weight"] for entry in scored["scores"]) == pytest.approx(1.0, abs=0.01)
    assert scored["evaluation"]["judge_is_mock"] is True

    # --- run the golden dataset ---------------------------------------------------
    suites = client.get("/api/v1/evaluations/suites", headers=headers).json()
    assert suites
    suite_key = suites[0]["key"]
    assert suites[0]["case_count"] >= 25

    suite_result = client.post(
        "/api/v1/evaluations/suites/run",
        headers=headers,
        json={"suite_key": suite_key, "agent_id": demo_agent_id, "max_cases": 3},
    ).json()
    assert suite_result["status"] == "SUCCEEDED", suite_result.get("error_message")
    assert suite_result["case_count"] == 3
    assert suite_result["pass_rate"] is not None

    # --- the scoreboard reflects it -----------------------------------------------
    scoreboard = client.get("/api/v1/evaluations/scoreboard", headers=headers).json()
    assert any(entry["agent_id"] == demo_agent_id for entry in scoreboard)

    # --- the dashboard aggregates the workspace -----------------------------------
    dashboard = client.get("/api/v1/dashboard", headers=headers).json()
    assert dashboard["headline"]["total_runs"] >= 1
    assert dashboard["headline"]["evaluations_in_window"] >= 1
    assert dashboard["recent_runs"]
    assert dashboard["usage"]["unit_economics"]["cost_per_run_usd"] >= 0.0
    assert any(
        entry["agent_id"] == demo_agent_id for entry in dashboard["agent_performance"]
    )


def test_reproducing_a_run_produces_the_same_answer(
    client: TestClient, account: Account, demo_agent_id: str
) -> None:
    """The deterministic provider must reproduce exactly; that is what makes the
    reproducibility dimension measurable at all."""
    original = create_run(
        client,
        account,
        agent_id=demo_agent_id,
        question="What drove ACME Technologies' fiscal 2023 operating margin?",
        inputs={"ticker": "ACME"},
    )
    repeat = client.post(
        f"/api/v1/research/runs/{original['id']}/reproduce", headers=account.headers()
    ).json()

    assert repeat["id"] != original["id"]
    assert repeat["reproduced_from_run_id"] == original["id"]
    assert repeat["reproducibility_key"] == original["reproducibility_key"]
    assert repeat["output_text"] == original["output_text"], (
        "the deterministic provider produced different output for an identical configuration"
    )


def test_a_historical_run_is_labelled_and_constrained(
    client: TestClient, account: Account, demo_agent_id: str
) -> None:
    cutoff = datetime(2023, 6, 30, tzinfo=timezone.utc)
    run = create_run(
        client,
        account,
        agent_id=demo_agent_id,
        question="What is ACME Technologies' most recently reported annual revenue?",
        inputs={"ticker": "ACME"},
        information_cutoff=cutoff,
    )
    detail = client.get(
        f"/api/v1/research/runs/{run['id']}", headers=account.headers()
    ).json()

    assert detail["run"]["information_cutoff"] is not None
    assert detail["task"]["information_cutoff"] is not None
    for item in detail["evidence"]:
        assert item["publication_timestamp"] <= cutoff.isoformat()

    # The same question without a cutoff can see more, which is the point of the control.
    live = create_run(
        client,
        account,
        agent_id=demo_agent_id,
        question="What is ACME Technologies' most recently reported annual revenue?",
        inputs={"ticker": "ACME"},
    )
    assert live["evidence_count"] >= run["evidence_count"]


def test_a_backtest_runs_and_reports_its_assumptions(
    client: TestClient, account: Account
) -> None:
    created = client.post(
        "/api/v1/backtests",
        headers=account.headers(),
        json={
            "name": "Demo momentum",
            "universe": ["ACME", "BLTA", "CRUX", "DELP", "EVRG"],
            "start_date": "2021-01-04",
            "end_date": "2023-12-29",
            "lookback_days": 126,
            "top_n": 2,
            "transaction_cost_bps": 10.0,
            "slippage_bps": 5.0,
            "signal_lag_days": 1,
        },
    ).json()
    body = client.post(
        f"/api/v1/backtests/{created['id']}/run", headers=account.headers()
    ).json()

    by_split = {split["split"]: split for split in body["runs"]}
    assert {"train", "validation", "test"} <= set(by_split)
    for split in body["runs"]:
        assert split["is_valid"]
        assert split["is_demo_data"] is True, "seeded prices must be labelled as demo data"
        assert split["trade_count"] > 0
        assert split["equity_curve"]
        metrics = split["metrics"]
        assert {"total_return_pct", "sharpe_ratio", "max_drawdown_pct"} <= set(metrics)

    # The out-of-sample window is counted, because reusing it degrades its meaning.
    assert body["test_split_use_count"] >= 1
    assert "not investment advice" in body["disclaimer"]


def test_an_experiment_compares_two_models_honestly(
    client: TestClient, account: Account, demo_agent_id: str, flawed_agent_id: str
) -> None:
    suite_key = client.get(
        "/api/v1/evaluations/suites", headers=account.headers()
    ).json()[0]["key"]

    experiment = client.post(
        "/api/v1/experiments",
        headers=account.headers(),
        json={
            "name": "Sound analyst versus flawed fixture",
            "variable": "agent_version",
            "suite_key": suite_key,
            "hypothesis": "The evidence-grounded agent scores higher than the flawed fixture.",
            "max_cases": 2,
            "arms": [
                {"label": "grounded", "agent_id": demo_agent_id},
                {"label": "flawed", "agent_id": flawed_agent_id},
            ],
        },
    ).json()

    result = client.post(
        f"/api/v1/experiments/{experiment['id']}/run", headers=account.headers()
    ).json()
    assert result["status"] == "SUCCEEDED", result
    arms = {arm["arm_label"]: arm for arm in result["arms"]}
    assert arms["grounded"]["overall_score"] > arms["flawed"]["overall_score"]
    assert result["results_summary"]["winner"] == "grounded"
    assert "do not predict investment performance" in result["results_summary"]["caveat"]


def test_a_debate_records_each_role_as_its_own_run(
    client: TestClient, account: Account, demo_agent_id: str
) -> None:
    run = create_run(
        client,
        account,
        agent_id=demo_agent_id,
        question="Is ACME Technologies' software mix shift durable?",
        inputs={"ticker": "ACME"},
    )
    outcome = client.post(
        f"/api/v1/research/runs/{run['id']}/debate",
        headers=account.headers(),
        json={"roles": ["bull", "bear", "judge"]},
    ).json()

    assert set(outcome["run_ids"]) == {"bull", "bear", "judge"}
    assert outcome["parent_run_id"] == run["id"]
    assert "not an investment recommendation" in outcome["disclaimer"]

    # Child runs are hidden from the main list but individually retrievable.
    listed = client.get("/api/v1/research/runs", headers=account.headers()).json()
    assert not any(entry["id"] in outcome["run_ids"].values() for entry in listed)
    for role, run_id in outcome["run_ids"].items():
        child = client.get(
            f"/api/v1/research/runs/{run_id}", headers=account.headers()
        ).json()
        assert child["run"]["debate_role"] == role
