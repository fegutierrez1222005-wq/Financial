"""Evaluation engine: the component that decides whether research can be trusted."""

from finagent_evaluation.cases import (
    BUILTIN_SUITES,
    FINANCIAL_RESEARCH_BASIC_V1,
    CaseCategory,
    Difficulty,
    EvaluationCase,
    EvaluationMethod,
    EvaluationSuite,
    get_suite,
)
from finagent_evaluation.claims import (
    ClaimKind,
    ExtractedClaim,
    claim_statistics,
    extract_claims,
    extract_claims_from_markdown,
    extract_claims_from_thesis,
)
from finagent_evaluation.engine import EvaluationEngine, EvaluationReport, aggregate_suite_reports
from finagent_evaluation.evaluators import EvaluationBudget, default_evaluators
from finagent_evaluation.scoring import DEFAULT_WEIGHTS, KIND_WEIGHTS, ScoreResult, Scorer
from finagent_evaluation.verification import (
    ClaimVerdict,
    VerificationReport,
    overlap_score,
    verify_claims,
)

__all__ = [
    "BUILTIN_SUITES",
    "FINANCIAL_RESEARCH_BASIC_V1",
    "CaseCategory",
    "Difficulty",
    "EvaluationCase",
    "EvaluationMethod",
    "EvaluationSuite",
    "get_suite",
    "ClaimKind",
    "ExtractedClaim",
    "claim_statistics",
    "extract_claims",
    "extract_claims_from_markdown",
    "extract_claims_from_thesis",
    "EvaluationEngine",
    "EvaluationReport",
    "aggregate_suite_reports",
    "EvaluationBudget",
    "default_evaluators",
    "DEFAULT_WEIGHTS",
    "KIND_WEIGHTS",
    "ScoreResult",
    "Scorer",
    "ClaimVerdict",
    "VerificationReport",
    "overlap_score",
    "verify_claims",
]
