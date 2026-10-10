"""Evaluation suites, run scoring, suite execution and the agent scoreboard."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from finagent_api.db.models import EvaluationCase, EvaluationSuite
from finagent_api.deps import Db, WorkspaceContext, expensive_operation_guard, require_permission
from finagent_api.jobs.queue import get_queue
from finagent_api.rbac import Permission
from finagent_api.schemas import (
    EvaluateRunRequest,
    EvaluationCaseResponse,
    EvaluationDetailResponse,
    EvaluationResponse,
    EvaluationSuiteResponse,
    RunSuiteRequest,
    ScoreboardEntry,
)
from finagent_api.services import evaluation_service, research_service
from finagent_core.errors import NotFoundError

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

ReadEval = Annotated[WorkspaceContext, Depends(require_permission(Permission.EVALUATION_READ))]
RunEval = Annotated[WorkspaceContext, Depends(require_permission(Permission.EVALUATION_RUN))]
WriteSuite = Annotated[
    WorkspaceContext, Depends(require_permission(Permission.EVALUATION_SUITE_WRITE))
]
Expensive = Annotated[WorkspaceContext, Depends(expensive_operation_guard)]

#: Attached to every evaluation detail response. The user specification requires that the
#: platform never imply a quality score predicts returns.
SCORE_INTERPRETATION = (
    "This is an agent-quality score measuring evidence grounding, citation accuracy, "
    "numerical correctness and instruction adherence. It does not predict investment "
    "returns and must not be used as a return forecast."
)


@router.get("/suites", response_model=list[EvaluationSuiteResponse], summary="Evaluation suites")
def list_suites(db: Db, context: ReadEval) -> list[EvaluationSuiteResponse]:
    evaluation_service.install_builtin_suites(
        db, organization_id=context.organization_id, workspace_id=context.workspace_id
    )
    rows = db.scalars(
        select(EvaluationSuite)
        .where(EvaluationSuite.workspace_id == context.workspace_id)
        .order_by(EvaluationSuite.key)
    )
    responses: list[EvaluationSuiteResponse] = []
    for row in rows:
        count = db.scalar(
            select(func.count(EvaluationCase.id)).where(EvaluationCase.suite_id == row.id)
        )
        responses.append(
            EvaluationSuiteResponse.model_validate(row).model_copy(
                update={"case_count": int(count or 0)}
            )
        )
    return responses


@router.get(
    "/suites/{suite_key}/cases",
    response_model=list[EvaluationCaseResponse],
    summary="Golden dataset cases in a suite",
)
def list_cases(suite_key: str, db: Db, context: ReadEval) -> list[EvaluationCaseResponse]:
    suite = db.scalar(
        select(EvaluationSuite).where(
            EvaluationSuite.workspace_id == context.workspace_id, EvaluationSuite.key == suite_key
        )
    )
    if suite is None:
        raise NotFoundError("evaluation suite not found")
    rows = db.scalars(
        select(EvaluationCase)
        .where(EvaluationCase.suite_id == suite.id)
        .order_by(EvaluationCase.key)
    )
    return [EvaluationCaseResponse.model_validate(row) for row in rows]


@router.post(
    "/runs",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Score one research run",
)
def evaluate_run(
    payload: EvaluateRunRequest, db: Db, context: RunEval, _guard: Expensive
) -> EvaluationResponse:
    run = research_service.get_run(
        db, workspace_id=context.workspace_id, run_id=payload.run_id
    )
    evaluation = evaluation_service.create_evaluation(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        kind="run",
        run_id=run.id,
        agent_id=run.agent_id,
        agent_version_id=run.agent_version_id,
        weights=payload.weights,
        user_id=context.user_id,
    )
    evaluation_id = evaluation.id
    db.commit()
    get_queue().submit("evaluation.evaluate_run", evaluation_id=evaluation_id)
    db.expire_all()
    return EvaluationResponse.model_validate(
        evaluation_service.get_evaluation(
            db, workspace_id=context.workspace_id, evaluation_id=evaluation_id
        )
    )


@router.post(
    "/suites/run",
    response_model=EvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a whole suite against one agent version",
)
def run_suite(
    payload: RunSuiteRequest, db: Db, context: RunEval, _guard: Expensive
) -> EvaluationResponse:
    """The evaluation row is created here, before the work is queued, so the client always
    receives an id it can poll regardless of which queue backend is configured."""
    suite = evaluation_service.resolve_suite(
        db, workspace_id=context.workspace_id, suite_key=payload.suite_key
    )
    evaluation = evaluation_service.create_evaluation(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        kind="suite",
        suite_key=suite.key,
        agent_id=payload.agent_id,
        agent_version_id=payload.agent_version_id,
        weights=suite.weights,
        user_id=context.user_id,
    )
    evaluation_id = evaluation.id
    db.commit()
    get_queue().submit(
        "evaluation.run_suite",
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        suite_key=payload.suite_key,
        agent_id=payload.agent_id,
        agent_version_id=payload.agent_version_id,
        model_override=payload.model_override,
        user_id=context.user_id,
        max_cases=payload.max_cases,
        evaluation_id=evaluation_id,
    )
    db.expire_all()
    return EvaluationResponse.model_validate(
        evaluation_service.get_evaluation(
            db, workspace_id=context.workspace_id, evaluation_id=evaluation_id
        )
    )


@router.get("", response_model=list[EvaluationResponse], summary="List evaluations")
def list_evaluations(
    db: Db,
    context: ReadEval,
    kind: str | None = None,
    agent_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[EvaluationResponse]:
    rows = evaluation_service.list_evaluations(
        db,
        workspace_id=context.workspace_id,
        kind=kind,
        agent_id=agent_id,
        limit=limit,
        offset=offset,
    )
    return [EvaluationResponse.model_validate(row) for row in rows]


@router.get(
    "/scoreboard", response_model=list[ScoreboardEntry], summary="Latest score per agent version"
)
def scoreboard(db: Db, context: ReadEval, suite_key: str | None = None) -> list[ScoreboardEntry]:
    return [
        ScoreboardEntry.model_validate(entry)
        for entry in evaluation_service.agent_scoreboard(
            db, workspace_id=context.workspace_id, suite_key=suite_key
        )
    ]


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationDetailResponse,
    summary="Scores, per-case results and extracted claims",
)
def get_evaluation(evaluation_id: str, db: Db, context: ReadEval) -> EvaluationDetailResponse:
    evaluation = evaluation_service.get_evaluation(
        db, workspace_id=context.workspace_id, evaluation_id=evaluation_id
    )
    detail = evaluation_service.evaluation_detail(db, evaluation)
    return EvaluationDetailResponse(
        evaluation=EvaluationResponse.model_validate(evaluation),
        scores=detail["scores"],
        results=detail["results"],
        claims=detail["claims"],
        score_interpretation=SCORE_INTERPRETATION,
    )
