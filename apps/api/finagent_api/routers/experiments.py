"""Experiments, benchmarks and the comparison views built on top of them."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from finagent_api.deps import Db, WorkspaceContext, expensive_operation_guard, require_permission
from finagent_api.jobs.queue import get_queue
from finagent_api.rbac import Permission
from finagent_api.schemas import (
    BenchmarkCreateRequest,
    BenchmarkEntryResponse,
    BenchmarkResponse,
    ExperimentCreateRequest,
    ExperimentResponse,
    ExperimentRunResponse,
)
from finagent_api.services import experiment_service

router = APIRouter(tags=["experiments"])

ReadExperiment = Annotated[
    WorkspaceContext, Depends(require_permission(Permission.EXPERIMENT_READ))
]
WriteExperiment = Annotated[
    WorkspaceContext, Depends(require_permission(Permission.EXPERIMENT_WRITE))
]
ReadBenchmark = Annotated[WorkspaceContext, Depends(require_permission(Permission.BENCHMARK_READ))]
WriteBenchmark = Annotated[
    WorkspaceContext, Depends(require_permission(Permission.BENCHMARK_WRITE))
]
Expensive = Annotated[WorkspaceContext, Depends(expensive_operation_guard)]

RANKING_BASIS = (
    "Ranked on agent-quality dimensions — factual accuracy, citation accuracy, numerical "
    "accuracy, hallucination resistance and cost efficiency. Never on investment return."
)


def _experiment_response(db, experiment) -> ExperimentResponse:  # noqa: ANN001
    arms = experiment_service.experiment_arms(db, experiment.id)
    return ExperimentResponse.model_validate(experiment).model_copy(
        update={"arms": [ExperimentRunResponse.model_validate(arm) for arm in arms]}
    )


@router.get("/experiments", response_model=list[ExperimentResponse], summary="List experiments")
def list_experiments(
    db: Db, context: ReadExperiment, limit: int = Query(default=50, ge=1, le=200)
) -> list[ExperimentResponse]:
    return [
        _experiment_response(db, experiment)
        for experiment in experiment_service.list_experiments(
            db, workspace_id=context.workspace_id, limit=limit
        )
    ]


@router.post(
    "/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Define an A/B experiment",
)
def create_experiment(
    payload: ExperimentCreateRequest, db: Db, context: WriteExperiment
) -> ExperimentResponse:
    draft = experiment_service.ExperimentDraft(
        name=payload.name,
        variable=payload.variable,
        suite_key=payload.suite_key,
        arms=[experiment_service.ExperimentArm(**arm.model_dump()) for arm in payload.arms],
        hypothesis=payload.hypothesis,
        description=payload.description,
        max_cases=payload.max_cases,
    )
    experiment = experiment_service.create_experiment(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        draft=draft,
        user_id=context.user_id,
    )
    return _experiment_response(db, experiment)


@router.post(
    "/experiments/{experiment_id}/run",
    response_model=ExperimentResponse,
    summary="Execute every arm against the suite",
)
def run_experiment(
    experiment_id: str, db: Db, context: WriteExperiment, _guard: Expensive
) -> ExperimentResponse:
    experiment_service.get_experiment(
        db, workspace_id=context.workspace_id, experiment_id=experiment_id
    )
    db.commit()
    get_queue().submit("experiment.execute", experiment_id=experiment_id, user_id=context.user_id)
    db.expire_all()
    return _experiment_response(
        db,
        experiment_service.get_experiment(
            db, workspace_id=context.workspace_id, experiment_id=experiment_id
        ),
    )


@router.get(
    "/experiments/{experiment_id}", response_model=ExperimentResponse, summary="Experiment detail"
)
def get_experiment(experiment_id: str, db: Db, context: ReadExperiment) -> ExperimentResponse:
    return _experiment_response(
        db,
        experiment_service.get_experiment(
            db, workspace_id=context.workspace_id, experiment_id=experiment_id
        ),
    )


@router.post(
    "/benchmarks",
    response_model=BenchmarkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Define a benchmark across agent versions",
)
def create_benchmark(
    payload: BenchmarkCreateRequest, db: Db, context: WriteBenchmark
) -> BenchmarkResponse:
    benchmark = experiment_service.create_benchmark(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        name=payload.name,
        suite_key=payload.suite_key,
        agent_version_ids=payload.agent_version_ids,
        ranking_weights=payload.ranking_weights,
        user_id=context.user_id,
    )
    return _benchmark_response(db, benchmark)


@router.post(
    "/benchmarks/{benchmark_id}/run",
    response_model=BenchmarkResponse,
    summary="Execute the benchmark and rank the entries",
)
def run_benchmark(
    benchmark_id: str, db: Db, context: WriteBenchmark, _guard: Expensive
) -> BenchmarkResponse:
    experiment_service.get_benchmark(
        db, workspace_id=context.workspace_id, benchmark_id=benchmark_id
    )
    db.commit()
    get_queue().submit("benchmark.execute", benchmark_id=benchmark_id, user_id=context.user_id)
    db.expire_all()
    return _benchmark_response(
        db,
        experiment_service.get_benchmark(
            db, workspace_id=context.workspace_id, benchmark_id=benchmark_id
        ),
    )


@router.get(
    "/benchmarks/{benchmark_id}", response_model=BenchmarkResponse, summary="Leaderboard"
)
def get_benchmark(benchmark_id: str, db: Db, context: ReadBenchmark) -> BenchmarkResponse:
    return _benchmark_response(
        db,
        experiment_service.get_benchmark(
            db, workspace_id=context.workspace_id, benchmark_id=benchmark_id
        ),
    )


def _benchmark_response(db, benchmark) -> BenchmarkResponse:  # noqa: ANN001
    entries = experiment_service.benchmark_entries(db, benchmark.id)
    return BenchmarkResponse.model_validate(benchmark).model_copy(
        update={
            "entries": [BenchmarkEntryResponse.model_validate(entry) for entry in entries],
            "ranking_basis": RANKING_BASIS,
        }
    )


@router.get(
    "/comparisons/prompts",
    summary="Mean evaluation score per prompt version for one agent",
)
def compare_prompts(agent_id: str, db: Db, context: ReadExperiment) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "rows": experiment_service.prompt_comparison(
            db, workspace_id=context.workspace_id, agent_id=agent_id
        ),
        "note": (
            "Comparing prompt versions is only meaningful when the same suite and model were "
            "used. Rows with few evaluations are noisy."
        ),
    }


@router.get("/comparisons/models", summary="Model comparison across suite evaluations")
def compare_models(
    db: Db, context: ReadExperiment, suite_key: str | None = None
) -> dict[str, Any]:
    return {
        "suite_key": suite_key,
        "rows": experiment_service.model_comparison(
            db, workspace_id=context.workspace_id, suite_key=suite_key
        ),
        "ranking_basis": RANKING_BASIS,
    }
