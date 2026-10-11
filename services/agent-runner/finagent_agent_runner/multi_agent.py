"""Multi-agent orchestration: bull, bear, skeptic and judge.

The differentiator is the skeptic: it is pointed at the primary thesis and instructed to
find evidence *against* it. A single agent asked to "consider risks" tends to produce
symmetrical boilerplate; a separate agent whose objective is disconfirmation produces
findings that change decisions.

Each role runs with its own trace, tool context and evidence set, so the platform can
evaluate each participant independently.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from finagent_agent_runner.context import ToolContext
from finagent_agent_runner.runner import AgentRunner
from finagent_core.logging import get_logger
from finagent_core.models.base import ChatMessage
from finagent_core.schemas.enums import OutputFormat, RunStatus
from finagent_core.schemas.research import AgentRunSpec, RunResult, TaskSpec

logger = get_logger(__name__)

DEBATE_ROLES = ("bull", "bear", "skeptic", "judge")


@dataclass
class RoleOutcome:
    role: str
    result: RunResult

    @property
    def succeeded(self) -> bool:
        return self.result.status == RunStatus.SUCCEEDED


@dataclass
class DebateVerdict:
    better_supported_side: str
    key_disagreements: list[str] = field(default_factory=list)
    unresolved_uncertainties: list[str] = field(default_factory=list)
    confidence: float = 0.0
    method: str = "model_judge"
    rationale: str = ""
    evidence_counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "better_supported_side": self.better_supported_side,
            "key_disagreements": self.key_disagreements,
            "unresolved_uncertainties": self.unresolved_uncertainties,
            "confidence": round(self.confidence, 3),
            "method": self.method,
            "rationale": self.rationale,
            "evidence_counts": self.evidence_counts,
        }


@dataclass
class DebateOutcome:
    outcomes: dict[str, RoleOutcome]
    verdict: DebateVerdict

    @property
    def total_cost_usd(self) -> float:
        return sum(item.result.usage.estimated_cost_usd for item in self.outcomes.values())

    @property
    def total_tokens(self) -> int:
        return sum(item.result.usage.total_tokens for item in self.outcomes.values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "roles": {
                role: {
                    "status": item.result.status,
                    "run_id": item.result.run_id,
                    "output_text": item.result.output_text,
                    "confidence": item.result.confidence,
                    "evidence_count": len(item.result.evidence),
                    "tool_calls": item.result.tool_names,
                    "usage": item.result.usage.model_dump(),
                    "error_code": item.result.error_code,
                }
                for role, item in self.outcomes.items()
            },
            "verdict": self.verdict.as_dict(),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": self.total_tokens,
        }


class DebateOrchestrator:
    """Runs a single-round bull/bear/skeptic/judge debate."""

    def __init__(self, runner: AgentRunner) -> None:
        self.runner = runner

    def run(
        self,
        spec: AgentRunSpec,
        task: TaskSpec,
        *,
        context_factory: Callable[[str], ToolContext],
        roles: tuple[str, ...] = DEBATE_ROLES,
    ) -> DebateOutcome:
        outcomes: dict[str, RoleOutcome] = {}

        for role in ("bull", "bear"):
            if role not in roles:
                continue
            role_task = task.model_copy(
                update={
                    "title": f"{task.title} — {role} case",
                    "question": self._role_question(role, task),
                    "output_format": OutputFormat.MARKDOWN,
                }
            )
            outcomes[role] = RoleOutcome(
                role,
                self.runner.run(
                    spec.model_copy(update={"output_format": OutputFormat.MARKDOWN}),
                    role_task,
                    context_factory(role),
                    role=role,
                ),
            )

        if "skeptic" in roles:
            primary = outcomes.get("bull")
            seed = (
                [ChatMessage.user("Thesis to challenge:\n\n" + (primary.result.output_text or "(none)"))]
                if primary
                else []
            )
            skeptic_task = task.model_copy(
                update={
                    "title": f"{task.title} — skeptic review",
                    "question": (
                        "Find evidence that contradicts the thesis you were given. Enumerate each "
                        "claim, mark it supported/uncited/contradicted, and state what evidence "
                        "would change the conclusion."
                    ),
                    "output_format": OutputFormat.MARKDOWN,
                }
            )
            outcomes["skeptic"] = RoleOutcome(
                "skeptic",
                self.runner.run(
                    spec.model_copy(update={"output_format": OutputFormat.MARKDOWN}),
                    skeptic_task,
                    context_factory("skeptic"),
                    role="skeptic",
                    seed_messages=seed,
                ),
            )

        verdict = self._judge(spec, task, outcomes, context_factory, roles)
        logger.info(
            "debate_completed",
            extra={
                "roles": list(outcomes),
                "verdict_side": verdict.better_supported_side,
                "verdict_method": verdict.method,
            },
        )
        return DebateOutcome(outcomes=outcomes, verdict=verdict)

    # ------------------------------------------------------------------- internals

    def _role_question(self, role: str, task: TaskSpec) -> str:
        side = "bull" if role == "bull" else "bear"
        return (
            f"{task.question}\n\nBuild the strongest evidence-based {side} case. Cite every claim. "
            f"If the evidence does not support a {side}ish point, say so."
        )

    def _judge(
        self,
        spec: AgentRunSpec,
        task: TaskSpec,
        outcomes: dict[str, RoleOutcome],
        context_factory: Callable[[str], ToolContext],
        roles: tuple[str, ...],
    ) -> DebateVerdict:
        evidence_counts = {
            role: len(item.result.evidence) for role, item in outcomes.items() if role != "judge"
        }
        if "judge" not in roles or not outcomes:
            return self._programmatic_verdict(outcomes, evidence_counts)

        transcript = "\n\n".join(
            f"### {role.upper()} OUTPUT\n\n{item.result.output_text or '(no output)'}"
            for role, item in outcomes.items()
        )
        judge_task = task.model_copy(
            update={
                "title": f"{task.title} — judgement",
                "question": (
                    "Judge the debate. Return JSON with keys: better_supported_side "
                    "('bull'|'bear'|'neither'), key_disagreements (list), "
                    "unresolved_uncertainties (list), confidence (0-1), rationale (string)."
                ),
                "output_format": OutputFormat.JSON,
            }
        )
        judge_result = self.runner.run(
            # The judge reads the transcript; it does not gather its own evidence.
            spec.model_copy(update={"output_format": OutputFormat.JSON, "tools": []}),
            judge_task,
            context_factory("judge"),
            role="judge",
            seed_messages=[ChatMessage.user(transcript)],
        )
        outcomes["judge"] = RoleOutcome("judge", judge_result)

        payload = _parse_json(judge_result.output_text)
        side = str((payload or {}).get("better_supported_side", "")).lower()
        if payload is None or side not in {"bull", "bear", "neither"}:
            fallback = self._programmatic_verdict(outcomes, evidence_counts)
            fallback.rationale = (
                "The judge model did not return a parseable verdict, so the platform fell back to "
                "a programmatic comparison of cited evidence volume. " + fallback.rationale
            )
            return fallback

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence > 1.0:
            confidence /= 100.0

        return DebateVerdict(
            better_supported_side=side,
            key_disagreements=_as_list(payload.get("key_disagreements")),
            unresolved_uncertainties=_as_list(payload.get("unresolved_uncertainties")),
            confidence=max(0.0, min(1.0, confidence)),
            method="model_judge",
            rationale=str(payload.get("rationale") or ""),
            evidence_counts=evidence_counts,
        )

    def _programmatic_verdict(
        self, outcomes: dict[str, RoleOutcome], evidence_counts: dict[str, int]
    ) -> DebateVerdict:
        """Deterministic fallback: whichever side cited more admissible evidence.

        Explicitly *not* a judgement of argument quality, and labelled as such so a reader
        never mistakes it for one.
        """
        bull = evidence_counts.get("bull", 0)
        bear = evidence_counts.get("bear", 0)
        side = "neither" if bull == bear else ("bull" if bull > bear else "bear")
        uncertainties: list[str] = []
        skeptic = outcomes.get("skeptic")
        if skeptic and skeptic.result.output_text:
            uncertainties.append("See the skeptic's review for claim-level challenges.")
        return DebateVerdict(
            better_supported_side=side,
            key_disagreements=["Verdict derived from evidence volume, not argument content."],
            unresolved_uncertainties=uncertainties,
            confidence=0.3,
            method="programmatic_evidence_count",
            rationale=(
                f"bull cited {bull} passages, bear cited {bear}. This compares evidence volume "
                "only and does not assess reasoning quality."
            ),
            evidence_counts=evidence_counts,
        )


def _parse_json(content: str | None) -> dict[str, Any] | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            return None
        text = text[start : end + 1]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
