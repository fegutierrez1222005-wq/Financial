"""Unit tests for the evaluation engine.

These assert the properties that stop the score from being gameable: a generous judge
cannot carry a bad answer, a fabricated citation is detected, unmeasured dimensions are
excluded rather than scored zero, and a claim with no evidence behind it is not treated as
supported just because it sounds plausible.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from finagent_core.schemas.enums import ClaimSupport, EvaluationDimension
from finagent_core.schemas.research import EvidenceItem, RunResult
from finagent_evaluation.claims import ClaimKind, extract_claims_from_markdown
from finagent_evaluation.evaluators.base import (
    DimensionScore,
    EvaluatorKind,
    EvaluatorOutcome,
)
from finagent_evaluation.scoring import Scorer
from finagent_evaluation.verification import verify_claims

FY2023_TEXT = (
    "ACME Technologies reported fiscal 2023 revenue of $4,820.0 million, an increase of "
    "18.0% over fiscal 2022 revenue of $4,084.7 million."
)


def evidence(chunk_id: str = "chunk-1", text: str = FY2023_TEXT, **kwargs) -> EvidenceItem:
    return EvidenceItem(
        chunk_id=chunk_id,
        document_id="doc-1",
        document_name="ACME FY2023 10-K",
        page_number=1,
        text=text,
        similarity=0.9,
        publication_timestamp=datetime(2024, 2, 14, tzinfo=timezone.utc),
        source="demo",
        is_demo=True,
        **kwargs,
    )


class TestClaimExtraction:
    def test_separates_facts_assumptions_and_unknowns(self) -> None:
        claims = extract_claims_from_markdown(
            "### Findings\n\n"
            "- Revenue grew 18.0% in fiscal 2023. [Source: ACME FY2023 10-K, page 1 | chunk:chunk-1]\n\n"
            "### Assumptions\n\n"
            "- No restatement has occurred after the fiscal year end.\n\n"
            "### Unknowns\n\n"
            "- Fiscal 2025 guidance is not covered by the evidence.\n"
        )
        kinds = {claim.section.lower(): claim.kind for claim in claims}
        assert kinds["findings"] == ClaimKind.FACTUAL
        assert kinds["assumptions"] == ClaimKind.ASSUMPTION
        assert kinds["unknowns"] == ClaimKind.UNKNOWN

    def test_citation_markers_are_parsed_not_counted_as_content(self) -> None:
        claims = extract_claims_from_markdown(
            "### Findings\n\n"
            "- Fiscal 2023 revenue was $4,820.0 million in total. "
            "[Source: ACME FY2023 10-K, page 1 | chunk:chunk-1]\n"
        )
        claim = claims[0]
        assert claim.cited_chunk_ids == ["chunk-1"]
        assert "chunk:" not in claim.text, "the marker must not pollute the claim text"
        # The page number from the marker must not be mistaken for a reported figure.
        assert 4_820_000_000.0 in {mention.value for mention in claim.numbers}
        assert 1 not in {mention.value for mention in claim.numbers}, (
            "the page number inside the citation marker must not become a reported figure"
        )

    def test_forward_looking_statements_are_typed_separately(self) -> None:
        claims = extract_claims_from_markdown(
            "### Findings\n\n- Revenue will grow 20% next year.\n"
        )
        assert claims[0].kind == ClaimKind.FORWARD_LOOKING
        assert claims[0].requires_support


class TestVerification:
    def test_a_cited_and_supported_claim_is_directly_supported(self) -> None:
        claims = extract_claims_from_markdown(
            "### Findings\n\n- Fiscal 2023 revenue was $4,820.0 million, up 18.0%. "
            "[Source: ACME FY2023 10-K, page 1 | chunk:chunk-1]\n"
        )
        report = verify_claims(claims, [evidence()])
        assert report.verdicts[0].support_level in (
            ClaimSupport.DIRECTLY_SUPPORTED,
            ClaimSupport.PARTIALLY_SUPPORTED,
        )
        assert report.hallucination_rate == 0.0

    def test_an_unsupported_claim_is_caught(self) -> None:
        claims = extract_claims_from_markdown(
            "### Findings\n\n- Revenue grew 42.0% year over year, the fastest in company history.\n"
        )
        report = verify_claims(claims, [evidence()])
        assert report.verdicts[0].support_level in (
            ClaimSupport.UNSUPPORTED,
            ClaimSupport.CONTRADICTED,
        )
        assert report.hallucination_rate > 0.0

    def test_a_fabricated_citation_is_detected(self) -> None:
        claims = extract_claims_from_markdown(
            "### Findings\n\n- Revenue grew 42.0% year over year, the fastest ever. "
            "[Source: ACME FY2023 10-K, page 1 | chunk:does-not-exist]\n"
        )
        report = verify_claims(claims, [evidence()])
        assert report.fabricated_citation_count == 1

    def test_a_correct_but_uncited_claim_is_inferred_not_supported(self) -> None:
        """Getting the number right without pointing at the source is a citation failure,
        not a factual one; the two must not be conflated."""
        claims = extract_claims_from_markdown(
            "### Findings\n\n- Fiscal 2023 revenue was $4,820.0 million, up 18.0% over fiscal 2022.\n"
        )
        report = verify_claims(claims, [evidence()])
        assert report.verdicts[0].support_level == ClaimSupport.INFERRED

    def test_assumptions_are_not_counted_as_hallucinations(self) -> None:
        claims = extract_claims_from_markdown(
            "### Assumptions\n\n- No restatement has occurred after the cutoff.\n"
        )
        report = verify_claims(claims, [evidence()])
        assert report.assumptions == 1
        assert report.hallucination_rate == 0.0

    def test_evidence_published_after_the_cutoff_is_reported(self) -> None:
        claims = extract_claims_from_markdown(
            "### Findings\n\n- Fiscal 2023 revenue was $4,820.0 million. "
            "[Source: ACME FY2023 10-K, page 1 | chunk:chunk-1]\n"
        )
        report = verify_claims(claims, [evidence()], cutoff_iso="2023-06-30T00:00:00+00:00")
        assert report.cutoff_violations, (
            "citing a document filed after the cutoff must be reported, not silently accepted"
        )


class TestScoring:
    def _outcome(self, dimension, score, kind) -> EvaluatorOutcome:  # noqa: ANN001
        return EvaluatorOutcome(
            scores=[
                DimensionScore(dimension=dimension, score=score, evaluator="test", kind=kind)
            ]
        )

    def test_a_generous_judge_cannot_outvote_a_deterministic_check(self) -> None:
        """An LLM judge is weighted far below a deterministic result for the same dimension."""
        result = Scorer().score(
            [
                self._outcome(
                    EvaluationDimension.FACTUAL_ACCURACY, 0.0, EvaluatorKind.DETERMINISTIC
                ),
                self._outcome(
                    EvaluationDimension.FACTUAL_ACCURACY, 100.0, EvaluatorKind.LLM_JUDGE
                ),
            ]
        )
        factual = next(
            item
            for item in result.dimensions
            if item.dimension == EvaluationDimension.FACTUAL_ACCURACY
        )
        assert factual.score < 30.0, (
            f"a judge scoring 100 pulled a deterministic 0 up to {factual.score}"
        )

    def test_unmeasured_dimensions_are_excluded_and_weights_renormalised(self) -> None:
        result = Scorer().score(
            [self._outcome(EvaluationDimension.FACTUAL_ACCURACY, 80.0, EvaluatorKind.DETERMINISTIC)]
        )
        assert result.dimensions[0].weight == pytest.approx(1.0)
        assert result.overall == pytest.approx(80.0)
        assert EvaluationDimension.CITATION_ACCURACY.value in result.excluded_dimensions

    def test_weights_can_be_overridden_per_suite(self) -> None:
        outcomes = [
            self._outcome(
                EvaluationDimension.FACTUAL_ACCURACY, 100.0, EvaluatorKind.DETERMINISTIC
            ),
            self._outcome(
                EvaluationDimension.COST_EFFICIENCY, 0.0, EvaluatorKind.PROGRAMMATIC
            ),
        ]
        balanced = Scorer({"factual_accuracy": 0.5, "cost_efficiency": 0.5}).score(outcomes)
        accuracy_led = Scorer({"factual_accuracy": 0.9, "cost_efficiency": 0.1}).score(outcomes)
        assert balanced.overall == pytest.approx(50.0)
        assert accuracy_led.overall == pytest.approx(90.0)

    def test_the_disclaimer_is_attached_to_every_score(self) -> None:
        result = Scorer().score(
            [self._outcome(EvaluationDimension.FACTUAL_ACCURACY, 80.0, EvaluatorKind.DETERMINISTIC)]
        )
        assert "does not predict investment returns" in result.disclaimer


class TestEngineEndToEnd:
    def test_a_grounded_answer_outscores_a_fabricated_one(self) -> None:
        from finagent_evaluation.engine import EvaluationEngine

        engine = EvaluationEngine()
        grounded = RunResult(
            output_text=(
                "### Findings\n\n- Fiscal 2023 revenue was $4,820.0 million, up 18.0% over "
                "fiscal 2022. [Source: ACME FY2023 10-K, page 1 | chunk:chunk-1]\n\n"
                "### Assumptions\n\n- Reported figures are accurate as filed.\n"
            ),
            evidence=[evidence()],
        )
        fabricated = RunResult(
            output_text=(
                "### Findings\n\n- Revenue grew 42.0% year over year, the fastest in company "
                "history.\n"
            ),
            evidence=[evidence()],
        )

        good = engine.evaluate(grounded)
        bad = engine.evaluate(fabricated)

        assert good.overall > bad.overall
        assert good.verification.hallucination_rate == 0.0
        assert bad.verification.hallucination_rate > 0.0
        assert bad.failures, "a fabricated claim must produce an explicit failure"

    def test_the_golden_dataset_is_well_formed(self) -> None:
        from finagent_evaluation.cases import FINANCIAL_RESEARCH_BASIC_V1

        suite = FINANCIAL_RESEARCH_BASIC_V1
        assert len(suite.cases) >= 25
        keys = [case.key for case in suite.cases]
        assert len(keys) == len(set(keys)), "case keys must be unique"
        assert sum(suite.weights.values()) == pytest.approx(1.0, abs=0.01)

        historical = [case for case in suite.cases if case.information_cutoff]
        assert historical, "the suite must exercise the information cutoff"
        for case in historical:
            assert case.forbidden_sources, (
                f"{case.key} sets a cutoff but names no source the agent must not use"
            )

        unanswerable = [
            case for case in suite.cases if "unknowable" in case.key.lower() or not case.expected_value
        ]
        assert unanswerable, "the suite must include a question that cannot be answered"
