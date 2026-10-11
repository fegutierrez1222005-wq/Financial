"""Experiment tracking and benchmarking.

An experiment varies exactly one factor — model, prompt version or agent version — across
arms, runs the same suite for each arm, and records the result. That is what makes "did
prompt v3 actually improve the agent?" an answerable question rather than an opinion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import (
    Agent,
    AgentVersion,
    Benchmark,
    BenchmarkEntry,
    Evaluation,
    EvaluationScore,
    Experiment,
    ExperimentRun,
    ResearchRun,
)
from finagent_api.services import agent_service, evaluation_service
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.services.usage_service import research_efficiency
from finagent_core.errors import NotFoundError, ValidationFailedError
from finagent_core.logging import get_logger
from finagent_core.schemas.enums import RunStatus

logger = get_logger(__name__)

#: Default leaderboard weights. Deliberately excludes any notion of investment return.
DEFAULT_RANKING_WEIGHTS: dict[str, float] = {
    "overall_score": 0.55,
    "pass_rate": 0.20,
    "hallucination_resistance": 0.15,
    "cost_efficiency": 0.05,
    "latency": 0.05,
}


@dataclass
class ExperimentArm:
    label: str
    agent_id: str
    agent_version_id: str | None = None
    prompt_version_id: str | None = None
    model: str | None = None


@dataclass
class ExperimentDraft:
    name: str
    variable: str
    suite_key: str
    arms: list[ExperimentArm]
    hypothesis: str | None = None
    description: str | None = None
    max_cases: int | None = None


def create_experiment(
    db: DbSession, *, organization_id: str, workspace_id: str, draft: ExperimentDraft, user_id: str | None
) -> Experiment:
    if len(draft.arms) < 2:
        raise ValidationFailedError("an experiment needs at least two arms to compare")
    if draft.variable not in {"model", "prompt_version", "agent_version", "tools"}:
        raise ValidationFailedError("variable must be model, prompt_version, agent_version or tools")

    experiment = Experiment(
        organization_id=organization_id,
        workspace_id=workspace_id,
        name=draft.name.strip(),
        hypothesis=draft.hypothesis,
        description=draft.description,
        variable=draft.variable,
        suite_key=draft.suite_key,
        configuration={
            "max_cases": draft.max_cases,
            "arms": [
                {
                    "label": arm.label,
                    "agent_id": arm.agent_id,
                    "agent_version_id": arm.agent_version_id,
                    "prompt_version_id": arm.prompt_version_id,
                    "model": arm.model,
                }
                for arm in draft.arms
            ],
        },
        status=RunStatus.QUEUED.value,
        created_by_user_id=user_id,
    )
    db.add(experiment)
    db.flush()

    for arm in draft.arms:
        db.add(
            ExperimentRun(
                organization_id=organization_id,
                workspace_id=workspace_id,
                experiment_id=experiment.id,
                arm_label=arm.label,
                agent_id=arm.agent_id,
                agent_version_id=arm.agent_version_id,
                prompt_version_id=arm.prompt_version_id,
                model=arm.model,
                suite_key=draft.suite_key,
                status=RunStatus.QUEUED.value,
                parameters={"variable": draft.variable},
            )
        )
    db.flush()
    record_audit(
        db,
        action=AuditAction.EXPERIMENT_CREATED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        resource_type="experiment",
        resource_id=experiment.id,
        metadata={"variable": draft.variable, "arms": len(draft.arms), "suite_key": draft.suite_key},
    )
    return experiment


def execute_experiment(db: DbSession, *, experiment_id: str, user_id: str | None = None) -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if experiment is None or experiment.deleted_at is not None:
        raise NotFoundError("experiment not found")

    experiment.status = RunStatus.RUNNING.value
    experiment.started_at = datetime.now(UTC)
    db.flush()

    max_cases = (experiment.configuration or {}).get("max_cases")
    for arm in db.scalars(select(ExperimentRun).where(ExperimentRun.experiment_id == experiment.id)):
        arm.status = RunStatus.RUNNING.value
        db.flush()
        try:
            evaluation = evaluation_service.run_suite(
                db,
                organization_id=experiment.organization_id,
                workspace_id=experiment.workspace_id,
                suite_key=experiment.suite_key or "FINANCIAL_RESEARCH_BASIC_V1",
                agent_id=arm.agent_id,
                agent_version_id=arm.agent_version_id,
                model_override=arm.model,
                user_id=user_id,
                experiment_run_id=arm.id,
                max_cases=max_cases,
            )
        except Exception as exc:
            arm.status = RunStatus.FAILED.value
            arm.error_code = type(exc).__name__
            arm.error_message = str(exc)[:500]
            db.flush()
            logger.warning(
                "experiment_arm_failed", extra={"experiment_id": experiment.id, "arm": arm.arm_label}
            )
            continue

        run_ids = list((evaluation.summary or {}).get("run_ids", {}).values())
        runs = list(db.scalars(select(ResearchRun).where(ResearchRun.id.in_(run_ids)))) if run_ids else []
        arm.status = RunStatus.SUCCEEDED.value
        arm.evaluation_ids = [evaluation.id]
        arm.research_run_ids = run_ids
        arm.overall_score = evaluation.overall_score
        arm.pass_rate = evaluation.pass_rate
        arm.hallucination_rate = evaluation.hallucination_rate
        arm.citation_coverage = evaluation.citation_coverage
        arm.dimension_scores = (evaluation.summary or {}).get("dimension_means", {})
        arm.total_cost_usd = round(sum(run.estimated_cost_usd for run in runs), 6)
        arm.total_tokens = sum(run.input_tokens + run.output_tokens for run in runs)
        arm.mean_latency_ms = int(sum(run.duration_ms for run in runs) / len(runs)) if runs else 0
        db.flush()

    experiment.status = RunStatus.SUCCEEDED.value
    experiment.finished_at = datetime.now(UTC)
    experiment.results_summary = _summarise_arms(db, experiment)
    experiment.conclusion = experiment.results_summary.get("conclusion")
    db.flush()
    return experiment


def _summarise_arms(db: DbSession, experiment: Experiment) -> dict[str, Any]:
    arms = list(db.scalars(select(ExperimentRun).where(ExperimentRun.experiment_id == experiment.id)))
    scored = sorted(
        [arm for arm in arms if arm.overall_score is not None],
        key=lambda arm: arm.overall_score or 0.0,
        reverse=True,
    )

    if len(scored) < 2:
        conclusion = "Not enough successful arms to draw a comparison."
    else:
        best, second = scored[0], scored[1]
        delta = (best.overall_score or 0.0) - (second.overall_score or 0.0)
        conclusion = (
            (
                f"No material difference: '{best.arm_label}' scored {best.overall_score:.1f} versus "
                f"'{second.arm_label}' at {second.overall_score:.1f}. A gap this small is within "
                "run-to-run noise for a suite of this size; do not treat it as an improvement."
            )
            if delta < 2.0
            else (
                f"'{best.arm_label}' scored {best.overall_score:.1f}, {delta:.1f} points above "
                f"'{second.arm_label}' ({second.overall_score:.1f}) on {experiment.suite_key}."
            )
        )

    return {
        "variable": experiment.variable,
        "suite_key": experiment.suite_key,
        "arms": [
            {
                "arm_label": arm.arm_label,
                "status": arm.status,
                "model": arm.model,
                "agent_version_id": arm.agent_version_id,
                "prompt_version_id": arm.prompt_version_id,
                "overall_score": arm.overall_score,
                "pass_rate": arm.pass_rate,
                "hallucination_rate": arm.hallucination_rate,
                "citation_coverage": arm.citation_coverage,
                "dimension_scores": arm.dimension_scores,
                "total_cost_usd": arm.total_cost_usd,
                "total_tokens": arm.total_tokens,
                "mean_latency_ms": arm.mean_latency_ms,
                "research_efficiency": research_efficiency(
                    mean_score=arm.overall_score or 0.0,
                    mean_cost_usd=(arm.total_cost_usd or 0.0) / max(len(arm.research_run_ids or []), 1),
                    mean_duration_ms=arm.mean_latency_ms,
                ),
            }
            for arm in arms
        ],
        "winner": scored[0].arm_label if scored else None,
        "conclusion": conclusion,
        "caveat": (
            "Scores compare research process quality on a fixed case set. They do not predict "
            "investment performance."
        ),
    }


def get_experiment(db: DbSession, *, workspace_id: str, experiment_id: str) -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if (
        experiment is None
        or experiment.workspace_id != workspace_id
        or experiment.deleted_at is not None
    ):
        raise NotFoundError("experiment not found")
    return experiment


def list_experiments(db: DbSession, *, workspace_id: str, limit: int = 50) -> list[Experiment]:
    return list(
        db.scalars(
            select(Experiment)
            .where(Experiment.workspace_id == workspace_id, Experiment.deleted_at.is_(None))
            .order_by(Experiment.created_at.desc())
            .limit(limit)
        )
    )


def experiment_arms(db: DbSession, experiment_id: str) -> list[ExperimentRun]:
    return list(
        db.scalars(
            select(ExperimentRun)
            .where(ExperimentRun.experiment_id == experiment_id)
            .order_by(ExperimentRun.created_at.asc())
        )
    )


# --------------------------------------------------------------------------- benchmarks


def create_benchmark(
    db: DbSession,
    *,
    organization_id: str,
    workspace_id: str,
    name: str,
    suite_key: str,
    agent_version_ids: list[str],
    ranking_weights: dict[str, float] | None = None,
    user_id: str | None = None,
) -> Benchmark:
    if not agent_version_ids:
        raise ValidationFailedError("select at least one agent version to benchmark")
    benchmark = Benchmark(
        organization_id=organization_id,
        workspace_id=workspace_id,
        name=name.strip(),
        suite_key=suite_key,
        agent_version_ids=agent_version_ids,
        status=RunStatus.QUEUED.value,
        ranking_weights=ranking_weights or DEFAULT_RANKING_WEIGHTS,
        created_by_user_id=user_id,
    )
    db.add(benchmark)
    db.flush()
    record_audit(
        db,
        action=AuditAction.BENCHMARK_CREATED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        resource_type="benchmark",
        resource_id=benchmark.id,
        metadata={"suite_key": suite_key, "agents": len(agent_version_ids)},
    )
    return benchmark


def execute_benchmark(db: DbSession, *, benchmark_id: str, user_id: str | None = None) -> Benchmark:
    benchmark = db.get(Benchmark, benchmark_id)
    if benchmark is None or benchmark.deleted_at is not None:
        raise NotFoundError("benchmark not found")

    benchmark.status = RunStatus.RUNNING.value
    benchmark.started_at = datetime.now(UTC)
    db.flush()

    entries: list[BenchmarkEntry] = []
    for version_id in benchmark.agent_version_ids:
        version = db.get(AgentVersion, version_id)
        if version is None or version.workspace_id != benchmark.workspace_id:
            continue
        agent = db.get(Agent, version.agent_id)
        try:
            evaluation = evaluation_service.run_suite(
                db,
                organization_id=benchmark.organization_id,
                workspace_id=benchmark.workspace_id,
                suite_key=benchmark.suite_key or "FINANCIAL_RESEARCH_BASIC_V1",
                agent_id=version.agent_id,
                agent_version_id=version.id,
                user_id=user_id,
            )
        except Exception:
            logger.warning(
                "benchmark_entry_failed",
                extra={"benchmark_id": benchmark.id, "agent_version_id": version_id},
            )
            continue

        run_ids = list((evaluation.summary or {}).get("run_ids", {}).values())
        runs = list(db.scalars(select(ResearchRun).where(ResearchRun.id.in_(run_ids)))) if run_ids else []
        total_cost = round(sum(run.estimated_cost_usd for run in runs), 6)
        mean_latency = int(sum(run.duration_ms for run in runs) / len(runs)) if runs else 0
        entry = BenchmarkEntry(
            organization_id=benchmark.organization_id,
            workspace_id=benchmark.workspace_id,
            benchmark_id=benchmark.id,
            agent_id=version.agent_id,
            agent_version_id=version.id,
            agent_name=f"{agent.name} v{version.version_number}" if agent else version.id,
            model=version.model,
            overall_score=evaluation.overall_score,
            dimension_scores={
                score.dimension: round(score.score, 2)
                for score in db.scalars(
                    select(EvaluationScore).where(EvaluationScore.evaluation_id == evaluation.id)
                )
            },
            pass_rate=evaluation.pass_rate,
            hallucination_rate=evaluation.hallucination_rate,
            citation_coverage=evaluation.citation_coverage,
            mean_latency_ms=mean_latency,
            total_cost_usd=total_cost,
            research_efficiency=research_efficiency(
                mean_score=evaluation.overall_score or 0.0,
                mean_cost_usd=total_cost / max(len(runs), 1),
                mean_duration_ms=mean_latency,
            )["value"],
            evaluation_ids=[evaluation.id],
        )
        db.add(entry)
        entries.append(entry)
    db.flush()

    ranked = rank_entries(entries, weights=benchmark.ranking_weights or DEFAULT_RANKING_WEIGHTS)
    for rank, entry in enumerate(ranked, start=1):
        entry.rank = rank
    benchmark.status = RunStatus.SUCCEEDED.value
    benchmark.finished_at = datetime.now(UTC)
    benchmark.summary = {
        "suite_key": benchmark.suite_key,
        "entries": len(entries),
        "ranking_weights": benchmark.ranking_weights,
        "leader": ranked[0].agent_name if ranked else None,
        "disclaimer": (
            "Ranking reflects research-process quality under identical conditions. It is not a "
            "ranking by investment return."
        ),
    }
    db.flush()
    return benchmark


def rank_entries(entries: list[BenchmarkEntry], *, weights: dict[str, float]) -> list[BenchmarkEntry]:
    """Configurable composite ranking. Never ranks on investment return."""

    def composite(entry: BenchmarkEntry) -> float:
        components = {
            "overall_score": entry.overall_score or 0.0,
            "pass_rate": entry.pass_rate or 0.0,
            "hallucination_resistance": (1.0 - (entry.hallucination_rate or 0.0)) * 100.0,
            "cost_efficiency": entry.dimension_scores.get("cost_efficiency", 50.0),
            "latency": entry.dimension_scores.get("latency", 50.0),
        }
        total_weight = sum(weights.get(key, 0.0) for key in components) or 1.0
        return sum(value * weights.get(key, 0.0) for key, value in components.items()) / total_weight

    return sorted(entries, key=composite, reverse=True)


def get_benchmark(db: DbSession, *, workspace_id: str, benchmark_id: str) -> Benchmark:
    benchmark = db.get(Benchmark, benchmark_id)
    if benchmark is None or benchmark.workspace_id != workspace_id or benchmark.deleted_at is not None:
        raise NotFoundError("benchmark not found")
    return benchmark


def benchmark_entries(db: DbSession, benchmark_id: str) -> list[BenchmarkEntry]:
    return list(
        db.scalars(
            select(BenchmarkEntry)
            .where(BenchmarkEntry.benchmark_id == benchmark_id)
            .order_by(BenchmarkEntry.rank.asc())
        )
    )


def prompt_comparison(db: DbSession, *, workspace_id: str, agent_id: str) -> list[dict[str, Any]]:
    """Mean evaluation score per prompt version — answers "did v3 actually help?"."""
    rows: list[dict[str, Any]] = []
    for prompt in agent_service.list_prompts(db, agent_id):
        version_ids = [
            version.id
            for version in db.scalars(
                select(AgentVersion).where(
                    AgentVersion.agent_id == agent_id, AgentVersion.prompt_version_id == prompt.id
                )
            )
        ]
        if not version_ids:
            rows.append(
                {
                    "prompt_version": prompt.version_number,
                    "prompt_id": prompt.id,
                    "evaluations": 0,
                    "mean_overall_score": None,
                    "note": "No agent version used this prompt.",
                }
            )
            continue
        evaluations = list(
            db.scalars(
                select(Evaluation).where(
                    Evaluation.workspace_id == workspace_id,
                    Evaluation.agent_version_id.in_(version_ids),
                    Evaluation.overall_score.is_not(None),
                )
            )
        )
        scores = [evaluation.overall_score for evaluation in evaluations if evaluation.overall_score]
        rows.append(
            {
                "prompt_version": prompt.version_number,
                "prompt_id": prompt.id,
                "content_preview": prompt.content[:280],
                "evaluations": len(scores),
                "mean_overall_score": round(sum(scores) / len(scores), 2) if scores else None,
                "mean_pass_rate": (
                    round(
                        sum(evaluation.pass_rate or 0.0 for evaluation in evaluations)
                        / len(evaluations),
                        2,
                    )
                    if evaluations
                    else None
                ),
            }
        )
    rows.sort(key=lambda row: row["prompt_version"])
    return rows


def model_comparison(
    db: DbSession, *, workspace_id: str, suite_key: str | None = None
) -> list[dict[str, Any]]:
    """Normalised comparison of models across suite evaluations in this workspace."""
    query = select(Evaluation).where(
        Evaluation.workspace_id == workspace_id,
        Evaluation.kind == "suite",
        Evaluation.overall_score.is_not(None),
    )
    if suite_key:
        query = query.where(Evaluation.suite_key == suite_key)

    grouped: dict[str, list[Evaluation]] = {}
    for evaluation in db.scalars(query):
        model = (evaluation.summary or {}).get("model")
        if not model and evaluation.agent_version_id:
            version = db.get(AgentVersion, evaluation.agent_version_id)
            model = version.model if version else None
        if model:
            grouped.setdefault(model, []).append(evaluation)

    rows: list[dict[str, Any]] = []
    for model, items in grouped.items():
        run_ids = [
            run_id for item in items for run_id in (item.summary or {}).get("run_ids", {}).values()
        ]
        runs = list(db.scalars(select(ResearchRun).where(ResearchRun.id.in_(run_ids)))) if run_ids else []
        mean_score = sum(item.overall_score or 0.0 for item in items) / len(items)
        mean_cost = (sum(run.estimated_cost_usd for run in runs) / len(runs)) if runs else 0.0
        mean_latency = int(sum(run.duration_ms for run in runs) / len(runs)) if runs else 0
        rows.append(
            {
                "model": model,
                "evaluations": len(items),
                "mean_overall_score": round(mean_score, 2),
                "mean_pass_rate": round(sum(item.pass_rate or 0.0 for item in items) / len(items), 2),
                "mean_hallucination_rate": round(
                    sum(item.hallucination_rate or 0.0 for item in items) / len(items), 4
                ),
                "mean_cost_usd": round(mean_cost, 6),
                "mean_latency_ms": mean_latency,
                "score_per_dollar": round(mean_score / mean_cost, 2) if mean_cost > 0 else None,
                "research_efficiency": research_efficiency(
                    mean_score=mean_score, mean_cost_usd=mean_cost, mean_duration_ms=mean_latency
                ),
                "used_mock_model": any(run.used_mock_model for run in runs),
            }
        )
    rows.sort(key=lambda row: row["mean_overall_score"], reverse=True)
    return rows
