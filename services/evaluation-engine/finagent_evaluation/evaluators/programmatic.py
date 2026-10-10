"""Programmatic evaluators: computed from the run's own artefacts.

Nothing here asks a model for an opinion. Numbers are recomputed, timestamps compared, the
trace inspected, and statistical language checked against what the evidence can support.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from finagent_core.numeric import cagr, extract_numbers, percent_change, safe_div, values_match
from finagent_core.schemas.enums import EvaluationDimension

from finagent_evaluation.evaluators.base import (
    EvaluationContext,
    Evaluator,
    EvaluatorKind,
    EvaluatorOutcome,
    Failure,
    FailureSeverity,
)

_STAT_TOKENS = (
    "statistically significant", "significant at", "p-value", "p value", "correlation",
    "correlated", "r-squared", "r2", "regression", "causes", "causal", "drives",
)
_SAMPLE_TOKENS = ("sample", "observations", "n =", "n=", "data points", "periods")
_LIMITATION_TOKENS = ("limitation", "caveat", "cannot establish", "not conclusive", "small sample")
_CAUSAL_TOKENS = ("causes", "caused by", "because of the correlation", "proves that")


class CalculationCorrectnessEvaluator(Evaluator):
    """Re-derives every CALCULATOR result from its own inputs.

    A tool that returns a wrong number is worse than no tool, because the model will trust
    it. This evaluator recomputes rather than trusting the recorded value.
    """

    key = "calculation_correctness"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.NUMERICAL_ACCURACY,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        outcome = EvaluatorOutcome()
        payloads = context.calculator_payloads()
        if not payloads:
            return outcome

        checked = correct = 0
        for payload in payloads:
            operation = str(payload.get("operation") or "")
            inputs = payload.get("inputs") or {}
            reported = payload.get("value")
            expected: float | None = None
            try:
                if operation == "percent_change":
                    expected = percent_change(float(inputs["new_value"]), float(inputs["old_value"]))
                elif operation == "margin":
                    expected = safe_div(float(inputs["numerator"]), float(inputs["denominator"])) * 100.0
                elif operation == "ratio":
                    expected = safe_div(float(inputs["numerator"]), float(inputs["denominator"]))
                elif operation == "cagr":
                    expected = cagr(
                        float(inputs["begin_value"]), float(inputs["end_value"]), float(inputs["years"])
                    )
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                expected = None

            if expected is None or reported is None:
                continue
            checked += 1
            if values_match(float(reported), expected, tolerance_pct=0.01, absolute_tolerance=1e-6):
                correct += 1
            else:
                outcome.failures.append(
                    Failure(
                        code="CALCULATION_INCORRECT",
                        title=f"Recomputation disagrees with the reported {operation}",
                        message=(
                            f"{payload.get('label') or operation}: reported {reported}, independent "
                            f"recomputation gives {expected:.6g} from {inputs}."
                        ),
                        severity=FailureSeverity.CRITICAL,
                        expected=f"{expected:.6g}",
                        actual=str(reported),
                        dimension=EvaluationDimension.NUMERICAL_ACCURACY,
                        evaluator=self.key,
                    )
                )

        if checked:
            outcome.scores.append(
                self.score_for(
                    EvaluationDimension.NUMERICAL_ACCURACY,
                    correct / checked * 100.0,
                    calculations_checked=checked,
                    calculations_correct=correct,
                )
            )
            outcome.detail = {"checked": checked, "correct": correct}
        return outcome


class NumericConsistencyEvaluator(Evaluator):
    """Scores whether the figures asserted in prose exist in the retrieved evidence."""

    key = "numeric_consistency"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.NUMERICAL_ACCURACY,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        report = context.verification
        outcome = EvaluatorOutcome()
        if not report.numeric_claims:
            outcome.warnings.append("The output contained no verifiable numeric claims.")
            return outcome
        outcome.scores.append(
            self.score_for(
                EvaluationDimension.NUMERICAL_ACCURACY,
                report.numeric_accuracy * 100.0,
                numeric_claims=report.numeric_claims,
                numeric_matched=report.numeric_matched,
            )
        )
        return outcome


class StatisticalValidityEvaluator(Evaluator):
    """Checks statistical language against what the evidence supports."""

    key = "statistical_validity"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.STATISTICAL_VALIDITY,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        text = context.output_text.lower()
        outcome = EvaluatorOutcome()
        if not any(token in text for token in _STAT_TOKENS):
            return outcome  # dimension excluded from scoring

        score = 100.0
        mentions_sample = any(token in text for token in _SAMPLE_TOKENS)
        mentions_limitation = any(token in text for token in _LIMITATION_TOKENS)
        asserts_causation = any(token in text for token in _CAUSAL_TOKENS)
        has_python_evidence = any(call.tool_name == "PYTHON" for call in context.run.tool_calls)

        if not mentions_sample:
            score -= 30.0
            outcome.failures.append(
                Failure(
                    code="STATISTICAL_NO_SAMPLE_SIZE",
                    title="Statistical claim without a sample size",
                    message=(
                        "The answer makes a statistical claim but never states the number of "
                        "observations it rests on."
                    ),
                    severity=FailureSeverity.WARNING,
                    dimension=EvaluationDimension.STATISTICAL_VALIDITY,
                    evaluator=self.key,
                )
            )
        if not mentions_limitation:
            score -= 20.0
        if asserts_causation and "correlation" in text:
            score -= 35.0
            outcome.failures.append(
                Failure(
                    code="CAUSATION_FROM_CORRELATION",
                    title="Causal claim drawn from correlation",
                    message="The answer asserts causation while its stated evidence is correlational.",
                    severity=FailureSeverity.CRITICAL,
                    dimension=EvaluationDimension.STATISTICAL_VALIDITY,
                    evaluator=self.key,
                )
            )
        if not has_python_evidence:
            score -= 15.0
            outcome.warnings.append(
                "A statistical claim was made without any computation recorded in the trace."
            )

        outcome.scores.append(
            self.score_for(
                EvaluationDimension.STATISTICAL_VALIDITY,
                score,
                mentions_sample=mentions_sample,
                mentions_limitation=mentions_limitation,
                asserts_causation=asserts_causation,
                computation_in_trace=has_python_evidence,
            )
        )
        return outcome


class HistoricalValidityEvaluator(Evaluator):
    """Verifies that nothing the run used post-dates its information cutoff."""

    key = "historical_validity"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.HISTORICAL_VALIDITY,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        outcome = EvaluatorOutcome()
        cutoff: datetime | None = context.run.information_cutoff
        if cutoff is None:
            return outcome  # live run: dimension not applicable

        violations = [
            item
            for item in context.run.evidence
            if item.publication_timestamp is None or item.publication_timestamp > cutoff
        ]
        unknown_provenance = [item for item in violations if item.publication_timestamp is None]
        future_dated = [item for item in violations if item.publication_timestamp is not None]

        score = 100.0
        if future_dated:
            score = 0.0
            outcome.failures.append(
                Failure(
                    code="LOOK_AHEAD_EVIDENCE",
                    title="Evidence published after the information cutoff was used",
                    message=(
                        f"{len(future_dated)} passage(s) post-date the cutoff {cutoff.isoformat()}: "
                        + ", ".join(sorted({item.document_name or item.chunk_id for item in future_dated}))
                    ),
                    severity=FailureSeverity.CRITICAL,
                    expected=f"publication_timestamp <= {cutoff.isoformat()}",
                    actual=", ".join(
                        sorted(
                            {
                                item.publication_timestamp.isoformat()
                                for item in future_dated
                                if item.publication_timestamp
                            }
                        )
                    ),
                    dimension=EvaluationDimension.HISTORICAL_VALIDITY,
                    evaluator=self.key,
                )
            )
        elif unknown_provenance:
            score = 60.0
            outcome.warnings.append(
                f"{len(unknown_provenance)} passage(s) have no publication timestamp, so their "
                "admissibility under the cutoff cannot be proven."
            )

        outcome.scores.append(
            self.score_for(
                EvaluationDimension.HISTORICAL_VALIDITY,
                score,
                cutoff=cutoff.isoformat(),
                evidence_count=len(context.run.evidence),
                future_dated=len(future_dated),
                unknown_provenance=len(unknown_provenance),
            )
        )
        return outcome


class ToolUseEfficiencyEvaluator(Evaluator):
    key = "tool_use_efficiency"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.TOOL_USE_EFFICIENCY,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        outcome = EvaluatorOutcome()
        calls = context.run.tool_calls
        if not calls:
            outcome.scores.append(
                self.score_for(
                    EvaluationDimension.TOOL_USE_EFFICIENCY,
                    0.0,
                    reason="no tools were used, so no evidence could be gathered",
                )
            )
            return outcome

        failed = [call for call in calls if call.status != "SUCCEEDED"]
        signatures = [(call.tool_name, str(sorted((call.arguments or {}).items()))) for call in calls]
        duplicates = len(signatures) - len(set(signatures))
        evidence_per_retrieval = safe_div(
            len(context.run.evidence),
            sum(1 for call in calls if call.tool_name in {"DOCUMENT_SEARCH", "SEC_SEARCH"}) or 1,
        )

        score = 100.0 - len(failed) / len(calls) * 50.0 - duplicates * 10.0
        if evidence_per_retrieval < 1.0:
            score -= 15.0

        outcome.scores.append(
            self.score_for(
                EvaluationDimension.TOOL_USE_EFFICIENCY,
                score,
                tool_calls=len(calls),
                failed_calls=len(failed),
                duplicate_calls=duplicates,
                evidence_per_retrieval=round(evidence_per_retrieval, 2),
            )
        )
        for call in failed:
            outcome.failures.append(
                Failure(
                    code="TOOL_CALL_FAILED",
                    title=f"Tool call failed: {call.tool_name}",
                    message=call.error_message or "The tool returned an error.",
                    severity=FailureSeverity.WARNING,
                    dimension=EvaluationDimension.TOOL_USE_EFFICIENCY,
                    evaluator=self.key,
                )
            )
        return outcome


class CostLatencyEvaluator(Evaluator):
    """Scores cost and latency against operator-configured reference points."""

    key = "cost_latency"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.COST_EFFICIENCY, EvaluationDimension.LATENCY)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        budget = context.budget
        usage = context.run.usage
        outcome = EvaluatorOutcome()

        cost = usage.estimated_cost_usd
        if context.run.used_mock_model:
            outcome.warnings.append(
                "This run used the deterministic mock provider, so its cost of $0 is not "
                "representative of a real model."
            )
        outcome.scores = [
            self.score_for(
                EvaluationDimension.COST_EFFICIENCY,
                _band_score(cost, budget.target_cost_usd, budget.max_cost_usd),
                estimated_cost_usd=round(cost, 6),
                target=budget.target_cost_usd,
                max=budget.max_cost_usd,
                is_mock=context.run.used_mock_model,
            ),
            self.score_for(
                EvaluationDimension.LATENCY,
                _band_score(usage.duration_ms, budget.target_latency_ms, budget.max_latency_ms),
                duration_ms=usage.duration_ms,
                target_ms=budget.target_latency_ms,
                max_ms=budget.max_latency_ms,
            ),
        ]
        if cost > budget.max_cost_usd:
            outcome.failures.append(
                Failure(
                    code="COST_BUDGET_EXCEEDED",
                    title="Run exceeded its cost budget",
                    message=f"Estimated cost ${cost:.4f} exceeds the ${budget.max_cost_usd:.2f} ceiling.",
                    severity=FailureSeverity.WARNING,
                    dimension=EvaluationDimension.COST_EFFICIENCY,
                    evaluator=self.key,
                )
            )
        return outcome


def _band_score(value: float, target: float, ceiling: float) -> float:
    """100 at or below target, 0 at or above ceiling, linear between."""
    if value <= target:
        return 100.0
    if value >= ceiling:
        return 0.0
    return (1.0 - (value - target) / (ceiling - target)) * 100.0


class ReproducibilityEvaluator(Evaluator):
    """Scores whether this run could be re-executed identically."""

    key = "reproducibility"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.REPRODUCIBILITY,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        outcome = EvaluatorOutcome()
        spec = context.run.spec
        if spec is None:
            outcome.scores.append(
                self.score_for(EvaluationDimension.REPRODUCIBILITY, 0.0, reason="no run spec recorded")
            )
            return outcome

        checks: dict[str, Any] = {
            "agent_version_pinned": bool(spec.agent_version_id),
            "prompt_version_pinned": bool(spec.prompt_version_id),
            "model_pinned": bool(spec.model),
            "tools_recorded": bool(spec.tools),
            "dataset_or_documents_pinned": bool(spec.dataset_ids or spec.document_ids),
            "deterministic_temperature": spec.temperature <= 0.2,
        }
        score = sum(1 for value in checks.values() if value) / len(checks) * 100.0

        if context.repeat_runs:
            baseline = _output_signature(context.run)
            matches = sum(1 for other in context.repeat_runs if _output_signature(other) == baseline)
            agreement = matches / len(context.repeat_runs)
            score = score * 0.5 + agreement * 100.0 * 0.5
            checks["repeat_run_agreement"] = round(agreement, 3)
            if agreement < 1.0:
                outcome.failures.append(
                    Failure(
                        code="NON_REPRODUCIBLE_OUTPUT",
                        title="Repeat runs produced different numeric answers",
                        message=(
                            f"{len(context.repeat_runs) - matches} of {len(context.repeat_runs)} "
                            "repeat runs disagreed with the baseline on at least one figure."
                        ),
                        severity=FailureSeverity.WARNING,
                        dimension=EvaluationDimension.REPRODUCIBILITY,
                        evaluator=self.key,
                    )
                )
        else:
            outcome.warnings.append(
                "Reproducibility was scored from configuration pinning only; no repeat runs were "
                "supplied for output comparison."
            )

        outcome.scores.append(
            self.score_for(
                EvaluationDimension.REPRODUCIBILITY,
                score,
                reproducibility_key=spec.reproducibility_key(),
                **checks,
            )
        )
        return outcome


class RobustnessEvaluator(Evaluator):
    """Robustness requires repeated or perturbed runs; without them it is not scored."""

    key = "robustness"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.ROBUSTNESS,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        outcome = EvaluatorOutcome()
        if not context.repeat_runs:
            outcome.warnings.append(
                "Robustness was not scored: it requires repeat or perturbed runs, which this "
                "evaluation did not include."
            )
            return outcome

        baseline_numbers = _numbers(context.run.output_text)
        agreements: list[float] = []
        for other in context.repeat_runs:
            other_numbers = _numbers(other.output_text)
            if not baseline_numbers:
                agreements.append(1.0 if not other_numbers else 0.0)
            else:
                agreements.append(len(baseline_numbers & other_numbers) / len(baseline_numbers))
        score = sum(agreements) / len(agreements) * 100.0
        outcome.scores.append(
            self.score_for(
                EvaluationDimension.ROBUSTNESS,
                score,
                repeat_runs=len(context.repeat_runs),
                mean_numeric_agreement=round(sum(agreements) / len(agreements), 4),
            )
        )
        if score < 80.0:
            outcome.failures.append(
                Failure(
                    code="UNSTABLE_ACROSS_RUNS",
                    title="Answer is unstable across repeat runs",
                    message=(
                        "Repeat runs of the same configuration produced materially different "
                        "figures, so a single run should not be relied upon."
                    ),
                    severity=FailureSeverity.WARNING,
                    dimension=EvaluationDimension.ROBUSTNESS,
                    evaluator=self.key,
                )
            )
        return outcome


class OverfittingRiskEvaluator(Evaluator):
    """Reads the backtest tool output for split degradation."""

    key = "overfitting_risk"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.OVERFITTING_RISK,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        outcome = EvaluatorOutcome()
        payloads = context.backtest_payloads()
        if not payloads:
            return outcome

        worst = 100.0
        for payload in payloads:
            assessment = payload.get("overfitting")
            if not assessment:
                if payload.get("splits"):
                    continue
                worst = min(worst, 40.0)
                outcome.warnings.append(
                    "A backtest was run without train/validation/out-of-sample splits, so "
                    "overfitting risk could not be assessed."
                )
                continue
            severity = str(assessment.get("severity") or "INFO")
            worst = min(worst, {"INFO": 90.0, "WARNING": 45.0, "CRITICAL": 10.0}.get(severity, 60.0))
            if severity in ("WARNING", "CRITICAL"):
                outcome.failures.append(
                    Failure(
                        code="OVERFITTING_RISK",
                        title=f"Overfitting risk: {severity}",
                        message=str(assessment.get("verdict") or ""),
                        severity=(
                            FailureSeverity.CRITICAL if severity == "CRITICAL" else FailureSeverity.WARNING
                        ),
                        expected="comparable in-sample and out-of-sample performance",
                        actual=(
                            f"train Sharpe {assessment.get('train_sharpe')} vs test Sharpe "
                            f"{assessment.get('test_sharpe')}"
                        ),
                        dimension=EvaluationDimension.OVERFITTING_RISK,
                        evaluator=self.key,
                    )
                )
        outcome.scores.append(
            self.score_for(EvaluationDimension.OVERFITTING_RISK, worst, backtests_examined=len(payloads))
        )
        return outcome


class ReasoningStructureEvaluator(Evaluator):
    """Programmatic component of reasoning and usefulness scoring.

    Checks the structure an institutional reader needs: stated assumptions, risks,
    disconfirming evidence, quantified figures, explicit confidence, and no unhedged
    absolutes.
    """

    key = "reasoning_structure"
    kind = EvaluatorKind.PROGRAMMATIC
    dimensions = (EvaluationDimension.FINANCIAL_REASONING, EvaluationDimension.INVESTMENT_USEFULNESS)

    _ABSOLUTES = ("guaranteed", "certain to", "risk-free", "will definitely", "cannot lose")

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        text = context.output_text.lower()
        thesis = context.run.thesis
        outcome = EvaluatorOutcome()

        components = {
            "states_assumptions": "assumption" in text or bool(thesis and thesis.assumptions),
            "states_risks": "risk" in text or bool(thesis and thesis.risks),
            "states_disconfirming": "disconfirming" in text
            or bool(thesis and thesis.disconfirming_evidence),
            "states_unknowns": "unknown" in text or bool(thesis and thesis.unknowns),
            "quantified": bool(context.verification.numeric_claims),
            "explicit_confidence": context.run.confidence is not None,
            "shows_calculation": bool(context.calculator_payloads())
            or any(call.tool_name == "PYTHON" for call in context.run.tool_calls),
        }
        reasoning_score = sum(1 for value in components.values() if value) / len(components) * 100.0

        usefulness_components = {
            "has_conclusion": bool(text.strip()) and len(text) > 200,
            "has_catalysts_or_drivers": "catalyst" in text
            or "driver" in text
            or bool(thesis and thesis.catalysts),
            "has_risks": components["states_risks"],
            "has_confidence": components["explicit_confidence"],
            "has_cited_evidence": context.verification.citation_coverage > 0.5,
        }
        usefulness_score = (
            sum(1 for value in usefulness_components.values() if value)
            / len(usefulness_components)
            * 100.0
        )

        absolutes = [token for token in self._ABSOLUTES if token in text]
        if absolutes:
            reasoning_score = max(0.0, reasoning_score - 25.0)
            usefulness_score = max(0.0, usefulness_score - 15.0)
            outcome.failures.append(
                Failure(
                    code="UNHEDGED_ABSOLUTE_CLAIM",
                    title="Unhedged absolute language",
                    message="The answer uses absolute language: " + ", ".join(absolutes),
                    severity=FailureSeverity.WARNING,
                    dimension=EvaluationDimension.FINANCIAL_REASONING,
                    evaluator=self.key,
                )
            )
        if not components["states_disconfirming"]:
            outcome.failures.append(
                Failure(
                    code="NO_DISCONFIRMING_EVIDENCE",
                    title="No disconfirming evidence considered",
                    message="The answer never addresses evidence that would weaken its conclusion.",
                    severity=FailureSeverity.WARNING,
                    dimension=EvaluationDimension.FINANCIAL_REASONING,
                    evaluator=self.key,
                )
            )

        outcome.scores = [
            self.score_for(EvaluationDimension.FINANCIAL_REASONING, reasoning_score, **components),
            self.score_for(
                EvaluationDimension.INVESTMENT_USEFULNESS, usefulness_score, **usefulness_components
            ),
        ]
        return outcome


def _numbers(text: str) -> set[float]:
    return {round(mention.value, 4) for mention in extract_numbers(text or "")}


def _output_signature(result: Any) -> tuple[float, ...]:
    return tuple(sorted(_numbers(result.output_text)))
