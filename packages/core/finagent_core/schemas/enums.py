"""Shared enumerations. Stored as strings so adding a value never needs a DB type change."""

from __future__ import annotations

from enum import StrEnum


class WorkspaceRole(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    RESEARCHER = "RESEARCHER"
    VIEWER = "VIEWER"

    @property
    def rank(self) -> int:
        return {"VIEWER": 0, "RESEARCHER": 1, "ADMIN": 2, "OWNER": 3}[self.value]

    def at_least(self, other: WorkspaceRole) -> bool:
        return self.rank >= other.rank


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def terminal(self) -> bool:
        return self in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED)


class ClaimSupport(StrEnum):
    """How well a claim is supported by retrieved evidence."""

    DIRECTLY_SUPPORTED = "DIRECTLY_SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"

    @property
    def is_verified(self) -> bool:
        return self is ClaimSupport.DIRECTLY_SUPPORTED

    @property
    def counts_as_hallucination(self) -> bool:
        return self in (ClaimSupport.UNSUPPORTED, ClaimSupport.CONTRADICTED)


class EvaluationDimension(StrEnum):
    FACTUAL_ACCURACY = "factual_accuracy"
    CITATION_ACCURACY = "citation_accuracy"
    CITATION_COMPLETENESS = "citation_completeness"
    FINANCIAL_REASONING = "financial_reasoning"
    NUMERICAL_ACCURACY = "numerical_accuracy"
    STATISTICAL_VALIDITY = "statistical_validity"
    HALLUCINATION_RESISTANCE = "hallucination_resistance"
    INSTRUCTION_ADHERENCE = "instruction_adherence"
    REPRODUCIBILITY = "reproducibility"
    ROBUSTNESS = "robustness"
    HISTORICAL_VALIDITY = "historical_validity"
    OVERFITTING_RISK = "overfitting_risk"
    TOOL_USE_EFFICIENCY = "tool_use_efficiency"
    COST_EFFICIENCY = "cost_efficiency"
    LATENCY = "latency"
    INVESTMENT_USEFULNESS = "investment_usefulness"


class TaskTemplate(StrEnum):
    EARNINGS_ANALYSIS = "earnings_analysis"
    COMPANY_DEEP_DIVE = "company_deep_dive"
    INVESTMENT_THESIS = "investment_thesis"
    FINANCIAL_STATEMENT_ANALYSIS = "financial_statement_analysis"
    QUANT_RESEARCH = "quant_research"
    CUSTOM = "custom"


class ToolName(StrEnum):
    SEC_SEARCH = "SEC_SEARCH"
    DOCUMENT_SEARCH = "DOCUMENT_SEARCH"
    MARKET_DATA = "MARKET_DATA"
    FINANCIAL_STATEMENTS = "FINANCIAL_STATEMENTS"
    CALCULATOR = "CALCULATOR"
    PYTHON = "PYTHON"
    BACKTEST = "BACKTEST"
    PORTFOLIO_ANALYSIS = "PORTFOLIO_ANALYSIS"


class OutputFormat(StrEnum):
    MARKDOWN = "markdown"
    INVESTMENT_THESIS = "investment_thesis"
    JSON = "json"


class ResearchStepKind(StrEnum):
    PLAN = "plan"
    RETRIEVE = "retrieve"
    CALCULATE = "calculate"
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    HYPOTHESIS = "hypothesis"
    CHALLENGE = "challenge"
    CONCLUDE = "conclude"
    ERROR = "error"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class BacktestSplit(StrEnum):
    FULL = "full"
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class RebalanceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class UsageKind(StrEnum):
    RESEARCH_RUN = "RESEARCH_RUN"
    EVALUATION_RUN = "EVALUATION_RUN"
    BACKTEST_RUN = "BACKTEST_RUN"
    MODEL_TOKENS = "MODEL_TOKENS"
    PYTHON_SECONDS = "PYTHON_SECONDS"
    DATA_API_CALL = "DATA_API_CALL"
    DOCUMENT_PAGES = "DOCUMENT_PAGES"
    EMBEDDING_TOKENS = "EMBEDDING_TOKENS"


class AlertSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
