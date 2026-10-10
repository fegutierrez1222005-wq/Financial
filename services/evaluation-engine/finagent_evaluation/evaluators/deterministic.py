"""Deterministic evaluators.

These decide pass/fail without judgement: the expected number is either present within
tolerance or it is not; the required source is either cited or it is not. They are the
backbone of objective benchmarking.
"""

from __future__ import annotations

import re

from finagent_core.numeric import NumericMention, Unit, comparable, extract_numbers, values_match
from finagent_core.schemas.enums import ClaimSupport, EvaluationDimension

from finagent_evaluation.cases import EvaluationMethod
from finagent_evaluation.evaluators.base import (
    EvaluationContext,
    Evaluator,
    EvaluatorKind,
    EvaluatorOutcome,
    Failure,
    FailureSeverity,
)

_SOURCE_MARKER_RE = re.compile(r"\[\s*source\s*:[^\]]*\]", re.IGNORECASE)

_UNIT_MAP = {
    "percent": Unit.PERCENT,
    "usd": Unit.USD,
    "usd_millions": Unit.USD,
    "ratio": Unit.RATIO,
    "bps": Unit.BPS,
    "count": Unit.COUNT,
    None: Unit.NUMBER,
}


class ExpectedValueEvaluator(Evaluator):
    """Checks the golden numeric answer against the numbers the agent asserted."""

    key = "expected_value"
    kind = EvaluatorKind.DETERMINISTIC
    dimensions = (EvaluationDimension.FACTUAL_ACCURACY, EvaluationDimension.NUMERICAL_ACCURACY)
    requires_case = True

    def applicable(self, context: EvaluationContext) -> bool:
        return (
            context.case is not None
            and context.case.evaluation_method == EvaluationMethod.DETERMINISTIC_NUMERIC.value
            and context.case.expected_value is not None
        )

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        case = context.case
        assert case is not None  # guarded by applicable()
        expected = float(case.expected_value)
        low = case.acceptable_low if case.acceptable_low is not None else expected * 0.99
        high = case.acceptable_high if case.acceptable_high is not None else expected * 1.01
        expected_unit = _UNIT_MAP.get(case.unit, Unit.NUMBER)

        # Citation markers contain page numbers; they are locators, not asserted values.
        mentions = extract_numbers(_SOURCE_MARKER_RE.sub(" ", context.output_text))
        # "in millions" answers may be written as $4,820.0 million (=4.82e9) or as 4820.0.
        scale_variants = [1.0] + ([1e-6] if case.unit == "usd_millions" else [])

        best_match: float | None = None
        for mention in mentions:
            if expected_unit is not Unit.NUMBER and not comparable(mention, _dummy(expected_unit)):
                continue
            for scale in scale_variants:
                candidate = mention.value * scale
                if low <= candidate <= high or values_match(candidate, expected, tolerance_pct=0.5):
                    best_match = candidate
                    break
            if best_match is not None:
                break

        passed = best_match is not None
        nearest = _nearest(mentions, expected, scale_variants)
        score = 100.0 if passed else 0.0
        outcome = EvaluatorOutcome(
            passed=passed,
            scores=[
                self.score_for(
                    EvaluationDimension.FACTUAL_ACCURACY,
                    score,
                    expected=expected,
                    matched=best_match,
                    acceptable_range=[low, high],
                ),
                self.score_for(
                    EvaluationDimension.NUMERICAL_ACCURACY, score, expected=expected, matched=best_match
                ),
            ],
        )
        if not passed:
            outcome.failures.append(
                Failure(
                    code="EXPECTED_VALUE_NOT_FOUND",
                    title=f"Expected answer not found: {case.expected_answer}",
                    message=(
                        f"The answer should contain {case.expected_answer} "
                        f"(acceptable {low:g}–{high:g} {case.unit or ''}). "
                        + (
                            f"The closest figure in the output was {nearest:g}."
                            if nearest is not None
                            else "The output contained no comparable figure."
                        )
                    ),
                    severity=FailureSeverity.CRITICAL,
                    expected=case.expected_answer,
                    actual=f"{nearest:g}" if nearest is not None else "(no comparable figure)",
                    source=", ".join(case.required_sources) or None,
                    dimension=EvaluationDimension.FACTUAL_ACCURACY,
                    case_key=case.key,
                    evaluator=self.key,
                )
            )
        return outcome


def _dummy(unit: Unit) -> NumericMention:
    return NumericMention(raw="", value=0.0, unit=unit, start=0, end=0)


def _nearest(mentions: list[NumericMention], expected: float, scales: list[float]) -> float | None:
    candidates = [mention.value * scale for mention in mentions for scale in scales]
    return min(candidates, key=lambda value: abs(value - expected)) if candidates else None


class RequiredFieldsEvaluator(Evaluator):
    """Checks that required content is present (task template fields or case keywords)."""

    key = "required_fields"
    kind = EvaluatorKind.DETERMINISTIC
    dimensions = (EvaluationDimension.INSTRUCTION_ADHERENCE,)

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        required: list[str] = []
        if context.case and context.case.required_fields:
            required.extend(context.case.required_fields)
        if context.run.task and context.run.task.required_output_fields:
            required.extend(context.run.task.required_output_fields)
        required = list(dict.fromkeys(required))

        outcome = EvaluatorOutcome()
        if not required:
            outcome.warnings.append(
                "No required output fields were declared, so instruction adherence was not checked "
                "against a contract."
            )
            return outcome

        haystack = context.output_text.lower()
        if context.run.thesis is not None:
            haystack += " " + context.run.thesis.model_dump_json().lower()

        missing = [
            field
            for field in required
            if field.lower() not in haystack and field.replace("_", " ").lower() not in haystack
        ]
        present = len(required) - len(missing)
        outcome.passed = not missing
        outcome.scores = [
            self.score_for(
                EvaluationDimension.INSTRUCTION_ADHERENCE,
                present / len(required) * 100.0,
                required=required,
                missing=missing,
            )
        ]
        if missing:
            outcome.failures.append(
                Failure(
                    code="REQUIRED_FIELDS_MISSING",
                    title=f"{len(missing)} required output field(s) missing",
                    message="The output does not address: " + ", ".join(missing),
                    severity=FailureSeverity.WARNING,
                    expected=", ".join(required),
                    actual=f"{present}/{len(required)} present",
                    dimension=EvaluationDimension.INSTRUCTION_ADHERENCE,
                    case_key=context.case.key if context.case else None,
                    evaluator=self.key,
                )
            )
        return outcome


class SourceRequirementEvaluator(Evaluator):
    """Enforces required and forbidden sources.

    Forbidden sources are how look-ahead is caught at the answer level: a historical case
    lists the future filings that must not appear.
    """

    key = "source_requirements"
    kind = EvaluatorKind.DETERMINISTIC
    dimensions = (EvaluationDimension.CITATION_ACCURACY, EvaluationDimension.HISTORICAL_VALIDITY)
    requires_case = True

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        case = context.case
        assert case is not None
        outcome = EvaluatorOutcome()
        if not case.required_sources and not case.forbidden_sources:
            return outcome

        used_labels = {
            (item.document_name or "").lower() for item in context.run.evidence if item.document_name
        }
        used_labels.update(label.lower() for claim in context.claims for label in claim.source_labels)
        cited_chunk_ids = {chunk_id for claim in context.claims for chunk_id in claim.cited_chunk_ids}
        cited_labels = {
            (item.document_name or "").lower()
            for item in context.run.evidence
            if item.chunk_id in cited_chunk_ids and item.document_name
        }

        missing = [
            source
            for source in case.required_sources
            if not any(source.lower() in label for label in cited_labels | used_labels)
        ]
        forbidden_used = [
            source
            for source in case.forbidden_sources
            if any(source.lower() in label for label in used_labels)
        ]

        citation_score = (
            (len(case.required_sources) - len(missing)) / len(case.required_sources) * 100.0
            if case.required_sources
            else 100.0
        )
        outcome.passed = not missing and not forbidden_used
        outcome.scores = [
            self.score_for(
                EvaluationDimension.CITATION_ACCURACY,
                citation_score,
                required_sources=case.required_sources,
                missing=missing,
            )
        ]
        if case.forbidden_sources:
            outcome.scores.append(
                self.score_for(
                    EvaluationDimension.HISTORICAL_VALIDITY,
                    0.0 if forbidden_used else 100.0,
                    forbidden_sources=case.forbidden_sources,
                    used=forbidden_used,
                )
            )
        if missing:
            outcome.failures.append(
                Failure(
                    code="REQUIRED_SOURCE_NOT_CITED",
                    title="Required source not cited",
                    message="The answer does not cite: " + ", ".join(missing),
                    severity=FailureSeverity.CRITICAL,
                    expected=", ".join(case.required_sources),
                    actual=", ".join(sorted(cited_labels)) or "(nothing cited)",
                    dimension=EvaluationDimension.CITATION_ACCURACY,
                    case_key=case.key,
                    evaluator=self.key,
                )
            )
        if forbidden_used:
            outcome.failures.append(
                Failure(
                    code="FORBIDDEN_SOURCE_USED",
                    title="Look-ahead: forbidden source used",
                    message=(
                        "The run used sources that were not public at the case's information "
                        "cutoff: " + ", ".join(forbidden_used)
                    ),
                    severity=FailureSeverity.CRITICAL,
                    expected="no post-cutoff sources",
                    actual=", ".join(forbidden_used),
                    dimension=EvaluationDimension.HISTORICAL_VALIDITY,
                    case_key=case.key,
                    evaluator=self.key,
                )
            )
        return outcome


class CitationDisciplineEvaluator(Evaluator):
    """Turns the verification report into citation and hallucination scores."""

    key = "citation_discipline"
    kind = EvaluatorKind.DETERMINISTIC
    dimensions = (
        EvaluationDimension.CITATION_ACCURACY,
        EvaluationDimension.CITATION_COMPLETENESS,
        EvaluationDimension.HALLUCINATION_RESISTANCE,
        EvaluationDimension.FACTUAL_ACCURACY,
    )

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        report = context.verification
        outcome = EvaluatorOutcome()

        if not report.verifiable_total:
            outcome.warnings.append(
                "No support-requiring claims were extracted, so citation and hallucination "
                "dimensions could not be scored."
            )
            return outcome

        supported_share = (
            (report.supported + 0.6 * report.partially_supported + 0.4 * report.inferred)
            / report.verifiable_total
            * 100.0
        )
        outcome.scores = [
            self.score_for(
                EvaluationDimension.CITATION_COMPLETENESS,
                report.citation_coverage * 100.0,
                cited=int(report.citation_coverage * report.verifiable_total),
                total=report.verifiable_total,
            ),
            self.score_for(
                EvaluationDimension.CITATION_ACCURACY,
                report.citation_accuracy * 100.0,
                fabricated_citations=report.fabricated_citation_count,
            ),
            self.score_for(
                EvaluationDimension.HALLUCINATION_RESISTANCE,
                (1.0 - report.hallucination_rate) * 100.0,
                unsupported=report.unsupported,
                contradicted=report.contradicted,
                hallucination_rate=round(report.hallucination_rate, 4),
            ),
            self.score_for(
                EvaluationDimension.FACTUAL_ACCURACY,
                supported_share,
                supported=report.supported,
                partially_supported=report.partially_supported,
                inferred=report.inferred,
            ),
        ]

        for verdict in report.verdicts:
            if verdict.support_level is ClaimSupport.CONTRADICTED:
                outcome.failures.append(
                    Failure(
                        code="CLAIM_CONTRADICTED",
                        title="Claim contradicts its cited source",
                        message=f"{verdict.claim.text} — {verdict.explanation}",
                        severity=FailureSeverity.CRITICAL,
                        expected="figures matching the cited passage",
                        actual=verdict.claim.text,
                        source=verdict.matched_chunk_id,
                        dimension=EvaluationDimension.FACTUAL_ACCURACY,
                        evaluator=self.key,
                    )
                )
            elif verdict.is_hallucination:
                outcome.failures.append(
                    Failure(
                        code="CLAIM_UNSUPPORTED",
                        title="Unsupported claim",
                        message=f"{verdict.claim.text} — {verdict.explanation}",
                        severity=FailureSeverity.CRITICAL,
                        expected="a cited passage supporting the claim",
                        actual="no supporting evidence in the retrieved set",
                        dimension=EvaluationDimension.HALLUCINATION_RESISTANCE,
                        evaluator=self.key,
                    )
                )
            elif verdict.claim.requires_support and not verdict.claim.has_citation:
                outcome.failures.append(
                    Failure(
                        code="CLAIM_UNCITED",
                        title="Factual claim without a citation",
                        message=f"{verdict.claim.text} — {verdict.explanation}",
                        severity=FailureSeverity.WARNING,
                        expected="an inline citation",
                        actual="no citation",
                        dimension=EvaluationDimension.CITATION_COMPLETENESS,
                        evaluator=self.key,
                    )
                )
            if verdict.fabricated_citations:
                outcome.failures.append(
                    Failure(
                        code="FABRICATED_CITATION",
                        title="Citation points to a passage that was never retrieved",
                        message=(
                            f"{verdict.claim.text} cites {', '.join(verdict.fabricated_citations)}, "
                            "which is not in the evidence set for this run."
                        ),
                        severity=FailureSeverity.CRITICAL,
                        dimension=EvaluationDimension.CITATION_ACCURACY,
                        evaluator=self.key,
                    )
                )
        return outcome
