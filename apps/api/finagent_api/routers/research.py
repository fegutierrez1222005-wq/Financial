"""Research tasks, runs, traces, reproduction and multi-agent debate."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from finagent_api.deps import Db, WorkspaceContext, expensive_operation_guard, require_permission
from finagent_api.jobs.queue import get_queue
from finagent_api.rbac import Permission
from finagent_api.schemas import (
    CitationResponse,
    DebateRequest,
    EvidenceResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskTemplateResponse,
    TraceStepResponse,
)
from finagent_api.services import agent_service, research_service
from finagent_core.errors import ValidationFailedError
from finagent_core.schemas.templates import TASK_TEMPLATES

router = APIRouter(tags=["research"])

ReadResearch = Annotated[WorkspaceContext, Depends(require_permission(Permission.RESEARCH_READ))]
CreateResearch = Annotated[
    WorkspaceContext, Depends(require_permission(Permission.RESEARCH_CREATE))
]
RunAgent = Annotated[WorkspaceContext, Depends(require_permission(Permission.AGENT_RUN))]
Expensive = Annotated[WorkspaceContext, Depends(expensive_operation_guard)]


@router.get(
    "/research/templates",
    response_model=list[TaskTemplateResponse],
    summary="Built-in research task templates",
)
def list_templates() -> list[TaskTemplateResponse]:
    return [
        TaskTemplateResponse(
            key=template.key.value,
            name=template.name,
            description=template.description,
            required_inputs=list(template.required_inputs),
            optional_inputs=list(template.optional_inputs),
            required_output_fields=list(template.required_output_fields),
            recommended_tools=[tool.value for tool in template.recommended_tools],
            default_output_format=template.default_output_format.value,
            guidance=template.guidance or None,
        )
        for template in TASK_TEMPLATES.values()
    ]


@router.post(
    "/research/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Define a research task",
)
def create_task(payload: TaskCreateRequest, db: Db, context: CreateResearch) -> TaskResponse:
    task = research_service.create_task(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        draft=_task_draft(payload, context),
        user_id=context.user_id,
    )
    return TaskResponse.model_validate(task)


def _task_draft(payload: TaskCreateRequest, context: WorkspaceContext) -> research_service.TaskDraft:
    cutoff = payload.information_cutoff or context.workspace.default_information_cutoff
    return research_service.TaskDraft(
        template=payload.template.value,
        title=payload.title,
        question=payload.question,
        inputs=payload.inputs,
        output_format=payload.output_format.value if payload.output_format else None,
        information_cutoff=cutoff,
        evaluation_case_key=payload.evaluation_case_key,
        evaluation_suite_key=payload.evaluation_suite_key,
    )


@router.post(
    "/research/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a research run",
)
def create_run(
    payload: RunCreateRequest, db: Db, context: RunAgent, _guard: Expensive
) -> RunResponse:
    if not payload.task_id and payload.task is None:
        raise ValidationFailedError("supply either task_id or an inline task definition")

    if payload.task_id:
        from finagent_api.db.models import ResearchTask

        task = db.get(ResearchTask, payload.task_id)
        if task is None or task.workspace_id != context.workspace_id:
            from finagent_core.errors import NotFoundError

            raise NotFoundError("research task not found")
    else:
        task = research_service.create_task(
            db,
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            draft=_task_draft(payload.task, context),
            user_id=context.user_id,
        )

    agent = agent_service.get_agent(
        db, workspace_id=context.workspace_id, agent_id=payload.agent_id
    )
    version = (
        agent_service.get_version(
            db, workspace_id=context.workspace_id, version_id=payload.agent_version_id
        )
        if payload.agent_version_id
        else agent_service.current_version(db, agent)
    )

    run = research_service.create_run(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        task=task,
        agent=agent,
        version=version,
        user_id=context.user_id,
        api_key_id=context.principal.api_key.id if context.principal.api_key else None,
        model_override=payload.model_override,
    )
    run_id = run.id

    if payload.run_now:
        db.commit()
        get_queue().submit("research.execute_run", run_id=run_id)
        db.expire_all()
        run = research_service.get_run(db, workspace_id=context.workspace_id, run_id=run_id)

    return RunResponse.model_validate(run)


@router.get("/research/runs", response_model=list[RunResponse], summary="List runs")
def list_runs(
    db: Db,
    context: ReadResearch,
    agent_id: str | None = None,
    run_status: str | None = Query(default=None, alias="status"),
    include_debate_children: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[RunResponse]:
    runs = research_service.list_runs(
        db,
        workspace_id=context.workspace_id,
        agent_id=agent_id,
        status=run_status,
        limit=limit,
        offset=offset,
        include_debate_children=include_debate_children,
    )
    return [RunResponse.model_validate(run) for run in runs]


@router.get(
    "/research/runs/{run_id}",
    response_model=RunDetailResponse,
    summary="Full run record: plan, trace, evidence and citations",
)
def get_run(run_id: str, db: Db, context: ReadResearch) -> RunDetailResponse:
    run = research_service.get_run(db, workspace_id=context.workspace_id, run_id=run_id)
    detail = research_service.run_detail(db, run)
    return RunDetailResponse(
        run=RunResponse.model_validate(run),
        task=TaskResponse.model_validate(detail["task"]) if detail["task"] else None,
        plan=detail["plan"],
        trace=[TraceStepResponse.model_validate(step) for step in detail["trace"]],
        evidence=[EvidenceResponse.model_validate(item) for item in detail["evidence"]],
        citations=[CitationResponse.model_validate(item) for item in detail["citations"]],
        messages=detail["messages"],
        tool_calls=detail["tool_calls"],
        model_runs=detail["model_runs"],
        evaluations=detail["evaluations"],
    )


@router.post(
    "/research/runs/{run_id}/execute",
    response_model=RunResponse,
    summary="Execute a queued run",
)
def execute_run(run_id: str, db: Db, context: RunAgent, _guard: Expensive) -> RunResponse:
    research_service.get_run(db, workspace_id=context.workspace_id, run_id=run_id)
    db.commit()
    get_queue().submit("research.execute_run", run_id=run_id)
    db.expire_all()
    return RunResponse.model_validate(
        research_service.get_run(db, workspace_id=context.workspace_id, run_id=run_id)
    )


@router.post(
    "/research/runs/{run_id}/reproduce",
    response_model=RunResponse,
    summary="Re-run the exact recorded configuration",
)
def reproduce_run(run_id: str, db: Db, context: RunAgent, _guard: Expensive) -> RunResponse:
    """Reproducibility check.

    The new run reuses the stored agent version, model and information cutoff. Comparing
    the two outputs is how the reproducibility dimension is measured; a model provider with
    non-zero temperature is not expected to be bit-identical.
    """
    source = research_service.get_run(db, workspace_id=context.workspace_id, run_id=run_id)
    new_run = research_service.reproduce_run(db, run=source, user_id=context.user_id)
    new_run_id = new_run.id
    db.commit()
    get_queue().submit("research.execute_run", run_id=new_run_id)
    db.expire_all()
    return RunResponse.model_validate(
        research_service.get_run(db, workspace_id=context.workspace_id, run_id=new_run_id)
    )


@router.post(
    "/research/runs/{run_id}/debate",
    summary="Run a bull / bear / skeptic / judge debate on this run's task",
)
def debate(
    run_id: str, payload: DebateRequest, db: Db, context: RunAgent, _guard: Expensive
) -> dict[str, Any]:
    run = research_service.get_run(db, workspace_id=context.workspace_id, run_id=run_id)
    outcome = research_service.run_debate(db, run=run, roles=tuple(payload.roles))
    outcome["disclaimer"] = (
        "A debate surfaces disagreement between perspectives. It is an argument-quality "
        "signal, not an investment recommendation."
    )
    return outcome
