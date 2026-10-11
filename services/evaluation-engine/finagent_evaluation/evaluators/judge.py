"""LLM-as-judge evaluator.

Used for the qualities that resist mechanical checking — reasoning quality, completeness,
relevance. Three safeguards apply:

1. Judge scores are down-weighted relative to deterministic and programmatic scores (see
   ``scoring.KIND_WEIGHTS``).
2. The judge sees the *evidence* alongside the answer and is told to score only what the
   evidence supports.
3. With no judge model configured, the dimension is simply not scored by a judge. The
   platform never silently substitutes an opinion for a measurement.
"""

from __future__ import annotations

import json
from typing import Any

from finagent_core.logging import get_logger
from finagent_core.models.base import ChatMessage
from finagent_core.schemas.enums import EvaluationDimension
from finagent_evaluation.evaluators.base import (
    EvaluationContext,
    Evaluator,
    EvaluatorKind,
    EvaluatorOutcome,
    Failure,
    FailureSeverity,
)

logger = get_logger(__name__)

JUDGE_SYSTEM_PROMPT = """
You are an evaluation judge for institutional investment research. You score a research
answer on three axes, using only the evidence provided:

- reasoning_quality (0-100): is the chain from evidence to conclusion sound, and are
  alternative explanations considered?
- completeness (0-100): does it address every part of the question, including risks,
  assumptions and unknowns?
- relevance (0-100): would this answer help an investment professional make a decision?

Rules:
- Do not reward fluency, length or confidence.
- Penalise any claim that the provided evidence does not support.
- If the answer is confident without stated uncertainty, reduce reasoning_quality.

Return only JSON: {"reasoning_quality": n, "completeness": n, "relevance": n,
"rationale": "one paragraph"}.
""".strip()

#: Judge axis → platform dimension.
_DIMENSION_MAP = {
    "reasoning_quality": EvaluationDimension.FINANCIAL_REASONING,
    "completeness": EvaluationDimension.INSTRUCTION_ADHERENCE,
    "relevance": EvaluationDimension.INVESTMENT_USEFULNESS,
}

MAX_ANSWER_CHARS = 12_000
MAX_EVIDENCE_ITEMS = 8
MAX_EVIDENCE_CHARS = 1200


class LlmJudgeEvaluator(Evaluator):
    key = "llm_judge"
    kind = EvaluatorKind.LLM_JUDGE
    dimensions = (
        EvaluationDimension.FINANCIAL_REASONING,
        EvaluationDimension.INSTRUCTION_ADHERENCE,
        EvaluationDimension.INVESTMENT_USEFULNESS,
    )

    def applicable(self, context: EvaluationContext) -> bool:
        return context.judge_provider is not None and bool(context.output_text.strip())

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        outcome = EvaluatorOutcome()
        provider = context.judge_provider
        if provider is None:  # pragma: no cover - guarded by applicable()
            return outcome

        model = context.judge_model or "mock-judge-v1"
        question = context.run.task.question if context.run.task else ""
        evidence_block = "\n\n".join(
            f"[chunk:{item.chunk_id}] {item.document_name or 'source'} p.{item.page_number}: "
            f"{item.text[:MAX_EVIDENCE_CHARS]}"
            for item in context.run.evidence[:MAX_EVIDENCE_ITEMS]
        )
        prompt = (
            f"QUESTION\n{question}\n\nEVIDENCE PROVIDED TO THE AGENT\n{evidence_block or '(none)'}\n\n"
            f"ANSWER TO SCORE\n{context.output_text[:MAX_ANSWER_CHARS]}"
        )

        try:
            response = provider.complete(
                [ChatMessage.system(JUDGE_SYSTEM_PROMPT), ChatMessage.user(prompt)],
                model=model,
                temperature=0.0,
                max_tokens=800,
                response_format="json",
            )
        except Exception as exc:
            logger.warning("judge_failed", extra={"error": type(exc).__name__, "model": model})
            outcome.warnings.append(
                "The LLM judge could not be reached; qualitative dimensions were scored by "
                "programmatic evaluators only."
            )
            return outcome

        payload = _parse(response.content)
        if payload is None:
            outcome.warnings.append("The LLM judge returned unparseable output and was ignored.")
            return outcome

        for axis, dimension in _DIMENSION_MAP.items():
            raw = payload.get(axis)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value <= 1.0:
                value *= 100.0
            outcome.scores.append(
                self.score_for(
                    dimension, value, axis=axis, judge_model=model, judge_is_mock=provider.is_mock
                )
            )

        rationale = str(payload.get("rationale") or "").strip()
        outcome.detail = {
            "judge_model": model,
            "judge_is_mock": provider.is_mock,
            "rationale": rationale,
            "tokens": response.usage.total_tokens,
            "estimated_cost_usd": response.estimated_cost_usd,
        }
        if provider.is_mock:
            outcome.warnings.append(
                "Judged by the deterministic rubric scorer (no judge model configured). Its scores "
                "reflect structure, not semantics."
            )
        for score in [item for item in outcome.scores if item.score < 50.0]:
            outcome.failures.append(
                Failure(
                    code="JUDGE_LOW_SCORE",
                    title=f"Judge scored {score.dimension.value} at {score.score:.0f}",
                    message=rationale or "The judge scored this dimension below the threshold.",
                    severity=FailureSeverity.WARNING,
                    dimension=score.dimension,
                    evaluator=self.key,
                )
            )
        return outcome


def _parse(content: str | None) -> dict[str, Any] | None:
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
