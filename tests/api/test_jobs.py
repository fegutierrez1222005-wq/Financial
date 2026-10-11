"""Background job behaviour.

The queue is the seam that lets the same code run inline in development and on a Celery
worker in production. These tests pin the two properties that make that substitution safe:
the submission result is backend-independent, and a job that fails says so on the row it
owns instead of leaving it queued forever.
"""

from __future__ import annotations

from datetime import UTC

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Account, create_run


class TestJobQueue:
    def test_every_registered_job_is_callable(self) -> None:
        from finagent_api.jobs import registered_jobs

        jobs = registered_jobs()
        assert {"research.execute_run", "evaluation.run_suite", "backtest.execute"} <= set(jobs)
        assert all(callable(job) for job in jobs.values())

    def test_an_unknown_job_is_refused(self) -> None:
        from finagent_api.jobs import get_queue

        with pytest.raises(KeyError):
            get_queue().submit("not.a.real.job")

    def test_a_failing_job_reports_rather_than_raising_into_the_transport(self) -> None:
        """The caller gets a handle describing the failure; the request does not 500."""
        from finagent_api.jobs import get_queue

        handle = get_queue().submit("research.execute_run", run_id="does-not-exist")
        assert handle.completed is True
        assert handle.error


class TestFailureRecording:
    def test_a_failed_evaluation_is_marked_failed_not_left_queued(
        self, account: Account, db
    ) -> None:
        """A job's own transaction rolls back when it raises, taking the status it wrote
        with it. Without a second session the row would sit in QUEUED indefinitely."""
        from finagent_api.db.models import Evaluation
        from finagent_api.jobs import get_queue
        from finagent_api.services import evaluation_service

        # An evaluation of kind "run" with nothing to score is the simplest genuine
        # failure the job can hit.
        evaluation = evaluation_service.create_evaluation(
            db,
            organization_id=account.organization_id,
            workspace_id=account.workspace_id,
            kind="run",
            run_id=None,
            user_id=account.user_id,
        )
        evaluation_id = evaluation.id
        db.commit()

        handle = get_queue().submit("evaluation.evaluate_run", evaluation_id=evaluation_id)
        assert handle.error, "the job should have failed"

        db.expire_all()
        row = db.get(Evaluation, evaluation_id)
        assert row is not None
        assert row.status == "FAILED", "a failed job must not leave the row queued"
        assert row.error_code == "VALIDATION_FAILED"
        assert row.error_message
        assert "Traceback" not in row.error_message

    def test_maintenance_expires_runs_that_never_reported(
        self, client: TestClient, account: Account, demo_agent_id: str, db
    ) -> None:
        """A worker can be killed mid-run. Without the sweep the run would sit in RUNNING
        forever and the dashboard would overstate activity."""
        from datetime import datetime, timedelta

        from finagent_api.db.models import ResearchRun
        from finagent_api.jobs.tasks import expire_stuck_runs

        created = client.post(
            "/api/v1/research/runs",
            headers=account.headers(),
            json={
                "agent_id": demo_agent_id,
                "run_now": False,
                "task": {"template": "custom", "question": "A question that never finishes."},
            },
        )
        assert created.status_code == 201, created.text
        stuck_id = created.json()["id"]

        db.expire_all()
        stuck = db.get(ResearchRun, stuck_id)
        stuck.created_at = datetime.now(UTC) - timedelta(hours=4)
        db.commit()

        assert expire_stuck_runs(older_than_seconds=3600)["expired"] >= 1

        db.expire_all()
        row = db.get(ResearchRun, stuck_id)
        assert row.status == "FAILED"
        assert row.error_code == "AGENT_TIMEOUT"
        assert row.finished_at is not None

    def test_a_run_evaluation_reports_no_case_count(
        self, client: TestClient, account: Account, demo_agent_id: str
    ) -> None:
        """A run scored outside a golden-dataset case has no cases. Reporting 0 of 0 would
        read as a failure rather than as "not applicable"."""
        run = create_run(
            client, account, agent_id=demo_agent_id, question="What drove FY2023 revenue?"
        )
        evaluation = client.post(
            "/api/v1/evaluations/runs",
            headers=account.headers(),
            json={"run_id": run["id"]},
        ).json()

        assert evaluation["status"] == "SUCCEEDED"
        assert evaluation["case_count"] is None
        assert evaluation["passed_count"] is None
        assert evaluation["overall_score"] is not None
