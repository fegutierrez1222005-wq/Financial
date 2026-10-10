"""Research task and run orchestration.

Responsibilities: create tasks from templates with validated inputs; create a durable
``research_runs`` row before any work starts; execute a run through :class:`AgentRunner`
with a tenant-scoped tool context; persist the complete trace (steps, messages, tool calls,
model calls, evidence, usage); and support "Reproduce run" by re-executing the recorded spec.

Execution is deliberately synchronous inside these functions; concurrency is the job
queue's concern, which keeps persistence identical in the API, the worker and tests.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from finagent_agent_runner.context import ToolContext
from finagent_agent_runner.multi_agent import DebateOrchestrator
from finagent_agent_runner.runner import AgentRunner
from finagent_api.db.models import (
    Agent,
    AgentMessage,
    AgentTrace,
    AgentTraceStep,
    AgentVersion,
    ModelRun,
    ResearchRun,
    ResearchStep,
    ResearchTask,
    RunEvidence,
    ToolCall,
)
from finagent_api.services import agent_service
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.services.price_loader import DbPriceLoader
from finagent_api.services.providers import build_sandbox, data_registry, model_registry, tool_registry
from finagent_api.services.retrieval import DbDocumentRetriever
from finagent_api.services.usage_service import enforce_quota, record_usage
from finagent_api.settings import get_settings
from finagent_core.errors import FinagentError, NotFoundError, ValidationFailedError
from finagent_core.logging import get_logger, log_context
from finagent_core.schemas.enums import OutputFormat, RunStatus, TaskTemplate, UsageKind
from finagent_core.schemas.research import AgentRunSpec, RunResult, TaskSpec
from finagent_core.schemas.templates import get_template

logger = get_logger(__name__)


@dataclass
class TaskDraft:
    template: str = TaskTemplate.CUSTOM.value
    title: str | None = None
    question: str | None = None
    inputs: dict[str, Any] | None = None
    output_format: str | None = None
    information_cutoff: datetime | None = None
    evaluation_case_key: str | None = None
    evaluation_suite_key: str | None = None


def create_task(
    db: DbSession, *, organization_id: str, workspace_id: str, draft: TaskDraft, user_id: str | None
) -> ResearchTask:
    template = get_template(draft.template)
    inputs = dict(draft.inputs or {})
    if draft.question:
        inputs.setdefault("question", draft.question)

    missing = template.validate_inputs(inputs)
    if missing:
        raise ValidationFailedError(
            f"missing required inputs for {template.name}: {', '.join(missing)}",
            details={"required_inputs": list(template.required_inputs), "missing": missing},
        )

    question = draft.question or template.build_question(inputs)
    title = draft.title or (
        f"{template.name}: {inputs.get('ticker') or inputs.get('hypothesis') or question[:60]}"
    )

    task = ResearchTask(
        organization_id=organization_id,
        workspace_id=workspace_id,
        template_key=template.key.value,
        title=title[:300],
        question=question,
        inputs=inputs,
        required_output_fields=list(template.required_output_fields),
        output_format=(draft.output_format or template.default_output_format.value),
        information_cutoff=draft.information_cutoff,
        evaluation_case_key=draft.evaluation_case_key,
        evaluation_suite_key=draft.evaluation_suite_key,
        created_by_user_id=user_id,
    )
    db.add(task)
    db.flush()
    return task


def create_run(
    db: DbSession,
    *,
    organization_id: str,
    workspace_id: str,
    task: ResearchTask,
    agent: Agent,
    version: AgentVersion,
    user_id: str | None = None,
    api_key_id: str | None = None,
    model_override: str | None = None,
    experiment_run_id: str | None = None,
    parent_run_id: str | None = None,
    debate_role: str | None = None,
    reproduced_from_run_id: str | None = None,
) -> ResearchRun:
    enforce_quota(db, organization_id=organization_id, kind=UsageKind.RESEARCH_RUN)

    spec = agent_service.build_run_spec(
        db,
        agent=agent,
        version=version,
        information_cutoff=task.information_cutoff,
        model_override=model_override,
    )
    run = ResearchRun(
        organization_id=organization_id,
        workspace_id=workspace_id,
        task_id=task.id,
        agent_id=agent.id,
        agent_version_id=version.id,
        prompt_version_id=version.prompt_version_id,
        experiment_run_id=experiment_run_id,
        parent_run_id=parent_run_id,
        debate_role=debate_role,
        model=spec.model,
        status=RunStatus.QUEUED.value,
        information_cutoff=task.information_cutoff,
        reproducibility_key=spec.reproducibility_key(),
        reproduced_from_run_id=reproduced_from_run_id,
        document_ids=spec.document_ids,
        dataset_snapshot_ids=[],
        triggered_by_user_id=user_id,
        triggered_by_api_key_id=api_key_id,
    )
    db.add(run)
    db.flush()
    record_audit(
        db,
        action=AuditAction.RESEARCH_RUN_STARTED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        api_key_id=api_key_id,
        resource_type="research_run",
        resource_id=run.id,
        metadata={
            "agent_id": agent.id,
            "agent_version": version.version_number,
            "model": spec.model,
            "task_template": task.template_key,
            "information_cutoff": (
                task.information_cutoff.isoformat() if task.information_cutoff else None
            ),
        },
    )
    return run


def build_tool_context(db: DbSession, *, run: ResearchRun, spec: AgentRunSpec, settings=None) -> ToolContext:
    settings = settings or get_settings()
    return ToolContext(
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        run_id=run.id,
        retriever=DbDocumentRetriever(
            db, workspace_id=run.workspace_id, organization_id=run.organization_id
        ),
        data_registry=data_registry(),
        price_loader=DbPriceLoader(db, workspace_id=run.workspace_id),
        sandbox=build_sandbox(settings),
        document_ids=list(spec.document_ids),
        dataset_ids=list(spec.dataset_ids),
        allow_demo_data=settings.enable_demo_providers,
        risk_constraints=spec.risk_constraints,
    )


def _task_spec(task: ResearchTask, cutoff: datetime | None) -> TaskSpec:
    return TaskSpec(
        id=task.id,
        template=TaskTemplate(task.template_key),
        title=task.title,
        question=task.question,
        inputs=task.inputs or {},
        output_format=OutputFormat(task.output_format),
        information_cutoff=cutoff,
        required_output_fields=list(task.required_output_fields or []),
    )


def execute_run(db: DbSession, run_id: str) -> ResearchRun:
    """Execute a queued run and persist everything it produced."""
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise NotFoundError("research run not found")
    if run.status not in (RunStatus.QUEUED.value, RunStatus.RUNNING.value):
        return run

    task = db.get(ResearchTask, run.task_id)
    agent = db.get(Agent, run.agent_id)
    version = db.get(AgentVersion, run.agent_version_id)
    if task is None or agent is None or version is None:
        raise NotFoundError("run is missing its task, agent or version")

    cutoff = run.information_cutoff or task.information_cutoff
    spec = agent_service.build_run_spec(
        db, agent=agent, version=version, information_cutoff=cutoff, model_override=run.model
    )

    run.status = RunStatus.RUNNING.value
    run.started_at = datetime.now(timezone.utc)
    db.flush()

    started = time.perf_counter()
    with log_context(run_id=run.id, workspace_id=run.workspace_id, organization_id=run.organization_id):
        context = build_tool_context(db, run=run, spec=spec)
        runner = AgentRunner(model_registry=model_registry(), tool_registry=tool_registry())
        try:
            result = runner.run(spec, _task_spec(task, cutoff), context)
        except FinagentError as error:
            run.status = RunStatus.FAILED.value
            run.error_code = error.code.value
            run.error_message = error.user_message
            run.finished_at = datetime.now(timezone.utc)
            run.duration_ms = int((time.perf_counter() - started) * 1000)
            db.flush()
            record_audit(
                db,
                action=AuditAction.RESEARCH_RUN_FAILED,
                organization_id=run.organization_id,
                workspace_id=run.workspace_id,
                user_id=run.triggered_by_user_id,
                resource_type="research_run",
                resource_id=run.id,
                outcome="FAILURE",
                metadata={"error_code": error.code.value},
            )
            raise

    persist_run_result(db, run=run, result=result)
    return run


def persist_run_result(db: DbSession, *, run: ResearchRun, result: RunResult) -> ResearchRun:
    """Write the run's outputs, trace, evidence and usage records."""
    run.status = result.status if isinstance(result.status, str) else result.status.value
    run.started_at = result.started_at
    run.finished_at = result.finished_at or datetime.now(timezone.utc)
    run.duration_ms = result.usage.duration_ms
    run.input_tokens = result.usage.input_tokens
    run.output_tokens = result.usage.output_tokens
    run.model_calls = result.usage.model_calls
    run.tool_call_count = result.usage.tool_calls
    run.python_seconds = result.usage.python_seconds
    run.data_api_calls = result.usage.data_api_calls
    run.estimated_cost_usd = result.usage.estimated_cost_usd
    run.output_text = result.output_text
    run.thesis = result.thesis.model_dump(mode="json") if result.thesis else None
    run.confidence = result.confidence
    run.evidence_count = len(result.evidence)
    run.used_mock_model = result.used_mock_model
    run.used_demo_data = any(item.is_demo for item in result.evidence)
    run.warnings = result.warnings
    run.error_code = result.error_code
    run.error_message = result.error_message
    if result.spec is not None:
        run.reproducibility_key = result.spec.reproducibility_key()

    trace = AgentTrace(
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        run_id=run.id,
        step_count=len(result.trace),
        tool_call_count=len(result.tool_calls),
        model_call_count=result.usage.model_calls,
        error_count=sum(1 for step in result.trace if step.error_code),
        total_latency_ms=sum(step.latency_ms for step in result.trace),
    )
    db.add(trace)
    db.flush()

    for step in result.trace:
        db.add(
            AgentTraceStep(
                organization_id=run.organization_id,
                workspace_id=run.workspace_id,
                trace_id=trace.id,
                run_id=run.id,
                sequence=step.sequence,
                kind=str(step.kind),
                action=step.action[:400],
                input_json=_jsonable(step.input),
                output_json=_jsonable(step.output),
                tool_name=step.tool_name,
                model=step.model,
                latency_ms=step.latency_ms,
                input_tokens=step.input_tokens,
                output_tokens=step.output_tokens,
                estimated_cost_usd=step.estimated_cost_usd,
                error_code=step.error_code,
                error_message=step.error_message,
                started_at=step.started_at,
            )
        )
        if str(step.kind) == "model_call" and step.model:
            db.add(
                ModelRun(
                    organization_id=run.organization_id,
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                    provider=_provider_for_model(step.model),
                    model=step.model,
                    purpose="research",
                    input_tokens=step.input_tokens,
                    output_tokens=step.output_tokens,
                    latency_ms=step.latency_ms,
                    estimated_cost_usd=step.estimated_cost_usd,
                    is_mock=bool((step.output or {}).get("is_mock"))
                    if isinstance(step.output, dict)
                    else False,
                )
            )

    for index, message in enumerate(result.messages):
        db.add(
            AgentMessage(
                organization_id=run.organization_id,
                workspace_id=run.workspace_id,
                run_id=run.id,
                sequence=index,
                role=str(message.get("role", "user")),
                content=(message.get("content") or "")[:100_000],
                tool_name=message.get("name"),
                tool_call_id=message.get("tool_call_id"),
                token_estimate=len(message.get("content") or "") // 4,
            )
        )

    for call in result.tool_calls:
        db.add(
            ToolCall(
                organization_id=run.organization_id,
                workspace_id=run.workspace_id,
                run_id=run.id,
                tool_name=call.tool_name,
                arguments=_jsonable(call.arguments) or {},
                result=_jsonable(call.result),
                status=call.status,
                latency_ms=call.latency_ms,
                error_code=call.error_code,
                error_message=call.error_message,
            )
        )

    for item in result.evidence:
        db.add(
            RunEvidence(
                organization_id=run.organization_id,
                workspace_id=run.workspace_id,
                run_id=run.id,
                chunk_ref=item.chunk_id[:200],
                chunk_id=item.chunk_id if _looks_like_uuid(item.chunk_id) else None,
                document_id=item.document_id,
                document_name=item.document_name,
                page_number=item.page_number,
                text=item.text,
                similarity=item.similarity,
                publication_timestamp=item.publication_timestamp,
                source=item.source,
                is_demo=item.is_demo,
            )
        )

    for index, step in enumerate(_plan_steps(result)):
        db.add(
            ResearchStep(
                organization_id=run.organization_id,
                workspace_id=run.workspace_id,
                run_id=run.id,
                step_index=index,
                kind=step["kind"],
                title=step["title"][:300],
                status=step["status"],
                detail=step.get("detail", {}),
            )
        )

    record_usage(
        db,
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        user_id=run.triggered_by_user_id,
        kind=UsageKind.RESEARCH_RUN,
        cost_usd=run.estimated_cost_usd,
        run_id=run.id,
        model=run.model,
        detail={"status": run.status, "tool_calls": run.tool_call_count},
    )
    if run.input_tokens or run.output_tokens:
        record_usage(
            db,
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            user_id=run.triggered_by_user_id,
            kind=UsageKind.MODEL_TOKENS,
            quantity=float(run.input_tokens + run.output_tokens),
            unit="tokens",
            cost_usd=run.estimated_cost_usd,
            run_id=run.id,
            model=run.model,
        )
    if run.python_seconds:
        record_usage(
            db,
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            kind=UsageKind.PYTHON_SECONDS,
            quantity=run.python_seconds,
            unit="seconds",
            run_id=run.id,
        )
    if run.data_api_calls:
        record_usage(
            db,
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            kind=UsageKind.DATA_API_CALL,
            quantity=float(run.data_api_calls),
            run_id=run.id,
        )

    db.flush()
    record_audit(
        db,
        action=(
            AuditAction.RESEARCH_RUN_COMPLETED
            if run.status == RunStatus.SUCCEEDED.value
            else AuditAction.RESEARCH_RUN_FAILED
        ),
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        user_id=run.triggered_by_user_id,
        resource_type="research_run",
        resource_id=run.id,
        outcome="SUCCESS" if run.status == RunStatus.SUCCEEDED.value else "FAILURE",
        metadata={
            "duration_ms": run.duration_ms,
            "tokens": run.input_tokens + run.output_tokens,
            "cost_usd": run.estimated_cost_usd,
            "evidence_count": run.evidence_count,
        },
    )
    return run


def load_run_result(db: DbSession, run: ResearchRun) -> RunResult:
    """Rebuild a :class:`RunResult` from persisted rows, for evaluation and comparison."""
    from finagent_core.schemas.research import EvidenceItem, ToolCallRecord, TraceStep, UsageSummary
    from finagent_core.schemas.thesis import InvestmentThesis

    agent = db.get(Agent, run.agent_id)
    version = db.get(AgentVersion, run.agent_version_id)
    task = db.get(ResearchTask, run.task_id)
    spec = (
        agent_service.build_run_spec(
            db, agent=agent, version=version, information_cutoff=run.information_cutoff
        )
        if agent and version
        else None
    )

    evidence = [
        EvidenceItem(
            chunk_id=row.chunk_ref,
            document_id=row.document_id,
            document_name=row.document_name,
            page_number=row.page_number,
            text=row.text,
            similarity=row.similarity,
            publication_timestamp=row.publication_timestamp,
            source=row.source,
            is_demo=row.is_demo,
        )
        for row in db.scalars(select(RunEvidence).where(RunEvidence.run_id == run.id))
    ]
    trace_rows = list(
        db.scalars(
            select(AgentTraceStep).where(AgentTraceStep.run_id == run.id).order_by(AgentTraceStep.sequence)
        )
    )
    tool_rows = list(db.scalars(select(ToolCall).where(ToolCall.run_id == run.id)))

    return RunResult(
        run_id=run.id,
        status=RunStatus(run.status),
        spec=spec,
        task=_task_spec(task, task.information_cutoff) if task else None,
        output_text=run.output_text or "",
        thesis=InvestmentThesis.model_validate(run.thesis) if run.thesis else None,
        evidence=evidence,
        trace=[
            TraceStep(
                sequence=row.sequence,
                kind=row.kind,
                action=row.action,
                input=row.input_json,
                output=row.output_json,
                tool_name=row.tool_name,
                model=row.model,
                latency_ms=row.latency_ms,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                estimated_cost_usd=row.estimated_cost_usd,
                error_code=row.error_code,
                error_message=row.error_message,
            )
            for row in trace_rows
        ],
        tool_calls=[
            ToolCallRecord(
                id=row.id,
                tool_name=row.tool_name,
                arguments=row.arguments or {},
                result=row.result,
                status=row.status,
                error_code=row.error_code,
                error_message=row.error_message,
                latency_ms=row.latency_ms,
            )
            for row in tool_rows
        ],
        usage=UsageSummary(
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            model_calls=run.model_calls,
            tool_calls=run.tool_call_count,
            python_seconds=run.python_seconds,
            data_api_calls=run.data_api_calls,
            estimated_cost_usd=run.estimated_cost_usd,
            duration_ms=run.duration_ms,
        ),
        confidence=run.confidence,
        error_code=run.error_code,
        error_message=run.error_message,
        warnings=list(run.warnings or []),
        started_at=run.started_at or run.created_at,
        finished_at=run.finished_at,
        used_mock_model=run.used_mock_model,
        information_cutoff=run.information_cutoff,
    )


def reproduce_run(db: DbSession, *, run: ResearchRun, user_id: str | None) -> ResearchRun:
    """Re-execute a run with the same version, prompt, model, tools and cutoff."""
    task = db.get(ResearchTask, run.task_id)
    agent = db.get(Agent, run.agent_id)
    version = db.get(AgentVersion, run.agent_version_id)
    if task is None or agent is None or version is None:
        raise NotFoundError("original run is incomplete and cannot be reproduced")

    new_run = create_run(
        db,
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        task=task,
        agent=agent,
        version=version,
        user_id=user_id,
        model_override=run.model,
        reproduced_from_run_id=run.id,
    )
    record_audit(
        db,
        action=AuditAction.RESEARCH_RUN_REPRODUCED,
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        user_id=user_id,
        resource_type="research_run",
        resource_id=new_run.id,
        metadata={"source_run_id": run.id, "reproducibility_key": run.reproducibility_key},
    )
    return new_run


def run_debate(
    db: DbSession, *, run: ResearchRun, roles: tuple[str, ...] = ("bull", "bear", "skeptic", "judge")
) -> dict[str, Any]:
    """Execute a bull/bear/skeptic/judge debate anchored on an existing run's task."""
    task = db.get(ResearchTask, run.task_id)
    agent = db.get(Agent, run.agent_id)
    version = db.get(AgentVersion, run.agent_version_id)
    if task is None or agent is None or version is None:
        raise NotFoundError("run is missing its task, agent or version")

    spec = agent_service.build_run_spec(
        db, agent=agent, version=version, information_cutoff=run.information_cutoff
    )
    role_runs: dict[str, ResearchRun] = {}

    def context_factory(role: str) -> ToolContext:
        child = create_run(
            db,
            organization_id=run.organization_id,
            workspace_id=run.workspace_id,
            task=task,
            agent=agent,
            version=version,
            user_id=run.triggered_by_user_id,
            parent_run_id=run.id,
            debate_role=role,
        )
        child.status = RunStatus.RUNNING.value
        child.started_at = datetime.now(timezone.utc)
        db.flush()
        role_runs[role] = child
        return build_tool_context(db, run=child, spec=spec)

    orchestrator = DebateOrchestrator(
        AgentRunner(model_registry=model_registry(), tool_registry=tool_registry())
    )
    outcome = orchestrator.run(
        spec, _task_spec(task, run.information_cutoff), context_factory=context_factory, roles=roles
    )

    for role, role_outcome in outcome.outcomes.items():
        child = role_runs.get(role)
        if child is not None:
            persist_run_result(db, run=child, result=role_outcome.result)

    record_audit(
        db,
        action=AuditAction.DEBATE_STARTED,
        organization_id=run.organization_id,
        workspace_id=run.workspace_id,
        user_id=run.triggered_by_user_id,
        resource_type="research_run",
        resource_id=run.id,
        metadata={"roles": list(outcome.outcomes), "verdict": outcome.verdict.better_supported_side},
    )
    payload = outcome.as_dict()
    payload["run_ids"] = {role: child.id for role, child in role_runs.items()}
    payload["parent_run_id"] = run.id
    return payload


def get_run(db: DbSession, *, workspace_id: str, run_id: str) -> ResearchRun:
    run = db.get(ResearchRun, run_id)
    if run is None or run.workspace_id != workspace_id:
        raise NotFoundError("research run not found")
    return run


def list_runs(
    db: DbSession,
    *,
    workspace_id: str,
    agent_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    include_debate_children: bool = False,
) -> list[ResearchRun]:
    query = select(ResearchRun).where(ResearchRun.workspace_id == workspace_id)
    if agent_id:
        query = query.where(ResearchRun.agent_id == agent_id)
    if status:
        query = query.where(ResearchRun.status == status)
    if not include_debate_children:
        query = query.where(ResearchRun.parent_run_id.is_(None))
    return list(
        db.scalars(query.order_by(ResearchRun.created_at.desc()).limit(min(limit, 200)).offset(offset))
    )


def run_counts(db: DbSession, *, workspace_id: str) -> dict[str, int]:
    return {
        status: int(count)
        for status, count in db.execute(
            select(ResearchRun.status, func.count(ResearchRun.id))
            .where(ResearchRun.workspace_id == workspace_id)
            .group_by(ResearchRun.status)
        )
    }


def run_detail(db: DbSession, run: ResearchRun) -> dict[str, Any]:
    """Everything the run-detail view shows: plan, trace, evidence, citations, cost."""
    from finagent_api.db.models import Citation, Evaluation

    plan = [
        {
            "step_index": step.step_index,
            "kind": step.kind,
            "title": step.title,
            "status": step.status,
            "detail": step.detail,
        }
        for step in db.scalars(
            select(ResearchStep)
            .where(ResearchStep.run_id == run.id)
            .order_by(ResearchStep.step_index)
        )
    ]
    trace = list(
        db.scalars(
            select(AgentTraceStep)
            .where(AgentTraceStep.run_id == run.id)
            .order_by(AgentTraceStep.sequence)
        )
    )
    evidence = list(
        db.scalars(select(RunEvidence).where(RunEvidence.run_id == run.id).order_by(RunEvidence.id))
    )
    citations = list(db.scalars(select(Citation).where(Citation.run_id == run.id)))
    messages = [
        {
            "sequence": message.sequence,
            "role": message.role,
            "content": message.content,
            "tool_name": message.tool_name,
        }
        for message in db.scalars(
            select(AgentMessage).where(AgentMessage.run_id == run.id).order_by(AgentMessage.sequence)
        )
    ]
    tool_calls = [
        {
            "tool_name": call.tool_name,
            "arguments": call.arguments,
            "status": call.status,
            "latency_ms": call.latency_ms,
            "error_code": call.error_code,
            "error_message": call.error_message,
        }
        for call in db.scalars(select(ToolCall).where(ToolCall.run_id == run.id))
    ]
    model_runs = [
        {
            "provider": model_run.provider,
            "model": model_run.model,
            "purpose": model_run.purpose,
            "input_tokens": model_run.input_tokens,
            "output_tokens": model_run.output_tokens,
            "latency_ms": model_run.latency_ms,
            "estimated_cost_usd": model_run.estimated_cost_usd,
            "is_mock": model_run.is_mock,
        }
        for model_run in db.scalars(select(ModelRun).where(ModelRun.run_id == run.id))
    ]
    evaluations = [
        {
            "id": evaluation.id,
            "kind": evaluation.kind,
            "status": evaluation.status,
            "overall_score": evaluation.overall_score,
            "hallucination_rate": evaluation.hallucination_rate,
            "citation_coverage": evaluation.citation_coverage,
            "created_at": evaluation.created_at,
        }
        for evaluation in db.scalars(
            select(Evaluation)
            .where(Evaluation.run_id == run.id)
            .order_by(Evaluation.created_at.desc())
        )
    ]
    return {
        "task": db.get(ResearchTask, run.task_id) if run.task_id else None,
        "plan": plan,
        "trace": trace,
        "evidence": evidence,
        "citations": citations,
        "messages": messages,
        "tool_calls": tool_calls,
        "model_runs": model_runs,
        "evaluations": evaluations,
    }


def _plan_steps(result: RunResult) -> list[dict[str, Any]]:
    """Condense the low-level trace into readable plan steps for the UI."""
    steps: list[dict[str, Any]] = []
    for step in result.trace:
        kind = str(step.kind)
        if kind in ("plan", "conclude", "error"):
            steps.append(
                {
                    "kind": kind,
                    "title": step.action,
                    "status": "FAILED" if step.error_code else "SUCCEEDED",
                    "detail": {"sequence": step.sequence},
                }
            )
        elif kind in ("retrieve", "tool_call") and step.tool_name:
            steps.append(
                {
                    "kind": "retrieve" if kind == "retrieve" else "calculate",
                    "title": f"Used {step.tool_name}",
                    "status": "SUCCEEDED",
                    "detail": {"tool": step.tool_name, "latency_ms": step.latency_ms},
                }
            )
    return steps


def _provider_for_model(model_key: str) -> str:
    from finagent_core.models.catalog import MODEL_CATALOG

    info = MODEL_CATALOG.get(model_key)
    return info.provider if info else "unknown"


def _looks_like_uuid(value: str) -> bool:
    return len(value) == 36 and value.count("-") == 4


def _jsonable(value: Any) -> Any:
    """Coerce arbitrary payloads into something a JSON column accepts."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value[:200_000]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
