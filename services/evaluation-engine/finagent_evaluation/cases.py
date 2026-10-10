"""Golden evaluation cases and suite definitions.

A case is a *contract*: a question with a known answer, an acceptable range, the source
that must be cited, and the method by which the answer is checked. Cases make benchmarking
objective — the platform is not asking a model whether another model did well.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from finagent_core.schemas.enums import EvaluationDimension


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CaseCategory(StrEnum):
    ACCOUNTING = "accounting"
    FINANCIAL_STATEMENTS = "financial_statements"
    VALUATION = "valuation"
    STATISTICS = "statistics"
    SEC_INTERPRETATION = "sec_interpretation"
    NUMERICAL_REASONING = "numerical_reasoning"
    CITATION = "citation"
    RISK_IDENTIFICATION = "risk_identification"


class EvaluationMethod(StrEnum):
    DETERMINISTIC_NUMERIC = "deterministic_numeric"
    DETERMINISTIC_FIELDS = "deterministic_fields"
    CITATION_CHECK = "citation_check"
    PROGRAMMATIC = "programmatic"
    LLM_JUDGE = "llm_judge"


class EvaluationCase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    key: str
    question: str
    expected_answer: str
    expected_value: float | None = None
    unit: str | None = None
    acceptable_low: float | None = None
    acceptable_high: float | None = None
    required_sources: list[str] = Field(default_factory=list)
    forbidden_sources: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    difficulty: Difficulty = Difficulty.MEDIUM
    category: CaseCategory = CaseCategory.FINANCIAL_STATEMENTS
    evaluation_method: EvaluationMethod = EvaluationMethod.DETERMINISTIC_NUMERIC
    information_cutoff: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    is_demo_dependent: bool = True

    @model_validator(mode="after")
    def _check_numeric_case(self) -> EvaluationCase:
        if self.evaluation_method == EvaluationMethod.DETERMINISTIC_NUMERIC.value:
            if self.expected_value is None:
                raise ValueError(f"case {self.key} needs an expected_value")
            if self.acceptable_low is None or self.acceptable_high is None:
                span = abs(self.expected_value) * 0.01
                object.__setattr__(self, "acceptable_low", self.expected_value - span)
                object.__setattr__(self, "acceptable_high", self.expected_value + span)
        return self


class EvaluationSuite(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    key: str
    version: str
    name: str
    description: str
    cases: list[EvaluationCase]
    weights: dict[str, float] = Field(default_factory=dict)
    is_builtin: bool = True
    dataset_note: str | None = None

    def case(self, key: str) -> EvaluationCase | None:
        return next((case for case in self.cases if case.key == key), None)

    @property
    def case_count(self) -> int:
        return len(self.cases)


_ACME = "ACME"
_TENK = "ACME FY2023 10-K"
_EARNINGS = "ACME Q4 2023 earnings release"
_CALL = "ACME Q4 2023 earnings call"
_TENK_PRIOR = "ACME FY2022 10-K"

FINANCIAL_RESEARCH_BASIC_V1 = EvaluationSuite(
    key="FINANCIAL_RESEARCH_BASIC_V1",
    version="1.0.0",
    name="Financial research — basic (v1)",
    description=(
        "25 cases covering accounting, financial statements, valuation, statistics, SEC "
        "interpretation, numerical reasoning, citation discipline and risk identification. "
        "Answers are keyed to the labelled ACME Technologies demo corpus, so a workspace must "
        "have the demo documents indexed to run this suite."
    ),
    dataset_note=(
        "Expected values derive from the synthetic ACME Technologies demo filings. They test the "
        "agent's ability to read and compute, not knowledge of any real company."
    ),
    weights={
        EvaluationDimension.FACTUAL_ACCURACY.value: 0.20,
        EvaluationDimension.CITATION_ACCURACY.value: 0.12,
        EvaluationDimension.CITATION_COMPLETENESS.value: 0.08,
        EvaluationDimension.NUMERICAL_ACCURACY.value: 0.15,
        EvaluationDimension.HALLUCINATION_RESISTANCE.value: 0.15,
        EvaluationDimension.FINANCIAL_REASONING.value: 0.10,
        EvaluationDimension.INSTRUCTION_ADHERENCE.value: 0.05,
        EvaluationDimension.HISTORICAL_VALIDITY.value: 0.05,
        EvaluationDimension.TOOL_USE_EFFICIENCY.value: 0.03,
        EvaluationDimension.COST_EFFICIENCY.value: 0.03,
        EvaluationDimension.LATENCY.value: 0.02,
        EvaluationDimension.REPRODUCIBILITY.value: 0.02,
    },
    cases=[
        EvaluationCase(
            key="ACME_Q4_2023_OPERATING_MARGIN",
            question="What was ACME's operating margin in Q4 2023?",
            expected_answer="12.4%",
            expected_value=12.4,
            unit="percent",
            acceptable_low=12.3,
            acceptable_high=12.5,
            required_sources=[_EARNINGS],
            difficulty=Difficulty.EASY,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME, "quarter": "Q4 2023"},
        ),
        EvaluationCase(
            key="ACME_FY2023_REVENUE_GROWTH",
            question="By what percentage did ACME's revenue grow in fiscal 2023?",
            expected_answer="18.0%",
            expected_value=18.0,
            unit="percent",
            acceptable_low=17.9,
            acceptable_high=18.1,
            required_sources=[_TENK],
            difficulty=Difficulty.EASY,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_REVENUE",
            question="What was ACME's total revenue in fiscal 2023, in millions of dollars?",
            expected_answer="$4,820.0 million",
            expected_value=4820.0,
            unit="usd_millions",
            acceptable_low=4819.0,
            acceptable_high=4821.0,
            required_sources=[_TENK],
            difficulty=Difficulty.EASY,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_GROSS_MARGIN",
            question="What was ACME's gross margin in fiscal 2023?",
            expected_answer="38.0%",
            expected_value=37.99,
            unit="percent",
            acceptable_low=37.9,
            acceptable_high=38.1,
            required_sources=[_TENK],
            difficulty=Difficulty.EASY,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_FREE_CASH_FLOW",
            question="What was ACME's free cash flow in fiscal 2023 (operating cash flow less capex)?",
            expected_answer="$656.2 million",
            expected_value=656.2,
            unit="usd_millions",
            acceptable_low=655.0,
            acceptable_high=657.5,
            required_sources=[_TENK],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.NUMERICAL_REASONING,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_ROIC",
            question=(
                "Compute ACME's fiscal 2023 return on invested capital, defined as after-tax "
                "operating income divided by total debt plus equity less cash."
            ),
            expected_answer="18.5%",
            expected_value=18.5,
            unit="percent",
            acceptable_low=18.0,
            acceptable_high=19.0,
            required_sources=[_TENK],
            difficulty=Difficulty.HARD,
            category=CaseCategory.NUMERICAL_REASONING,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_NET_DEBT",
            question="What was ACME's net debt at the end of fiscal 2023?",
            expected_answer="$357.6 million",
            expected_value=357.6,
            unit="usd_millions",
            acceptable_low=356.0,
            acceptable_high=359.0,
            required_sources=[_TENK],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_Q4_2023_EPS",
            question="What was ACME's diluted EPS in Q4 2023?",
            expected_answer="$0.91",
            expected_value=0.91,
            unit="usd",
            acceptable_low=0.90,
            acceptable_high=0.92,
            required_sources=[_EARNINGS],
            difficulty=Difficulty.EASY,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME, "quarter": "Q4 2023"},
        ),
        EvaluationCase(
            key="ACME_Q4_2023_REVENUE_GROWTH",
            question="By what percentage did ACME's Q4 2023 revenue grow year over year?",
            expected_answer="17.2%",
            expected_value=17.2,
            unit="percent",
            acceptable_low=17.1,
            acceptable_high=17.3,
            required_sources=[_EARNINGS],
            difficulty=Difficulty.EASY,
            category=CaseCategory.NUMERICAL_REASONING,
            inputs={"ticker": _ACME, "quarter": "Q4 2023"},
        ),
        EvaluationCase(
            key="ACME_FY2024_REVENUE_GUIDANCE",
            question="What fiscal 2024 revenue range did ACME guide to?",
            expected_answer="$5,500.0 million to $5,650.0 million",
            expected_value=5650.0,
            unit="usd_millions",
            acceptable_low=5499.0,
            acceptable_high=5651.0,
            required_sources=[_EARNINGS],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.SEC_INTERPRETATION,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_OPERATING_MARGIN",
            question="What was ACME's full-year fiscal 2023 operating margin?",
            expected_answer="11.7%",
            expected_value=11.68,
            unit="percent",
            acceptable_low=11.6,
            acceptable_high=11.8,
            required_sources=[_TENK],
            difficulty=Difficulty.EASY,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_EFFECTIVE_TAX_RATE",
            question="What was ACME's effective tax rate in fiscal 2023?",
            expected_answer="21.0%",
            expected_value=21.0,
            unit="percent",
            acceptable_low=20.8,
            acceptable_high=21.2,
            required_sources=[_TENK],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.ACCOUNTING,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_WORKING_CAPITAL",
            question="What was ACME's working capital at the end of fiscal 2023?",
            expected_answer="$794.6 million",
            expected_value=794.6,
            unit="usd_millions",
            acceptable_low=793.0,
            acceptable_high=796.0,
            required_sources=[_TENK],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2023_SBC_SHARE_OF_CFO",
            question="What share of ACME's fiscal 2023 operating cash flow was stock-based compensation?",
            expected_answer="16.6%",
            expected_value=16.58,
            unit="percent",
            acceptable_low=16.3,
            acceptable_high=16.9,
            required_sources=[_TENK],
            difficulty=Difficulty.HARD,
            category=CaseCategory.ACCOUNTING,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_ARR_MIX",
            question="What share of ACME's total revenue did the Software Platform represent in Q4 2023?",
            expected_answer="34.0%",
            expected_value=34.0,
            unit="percent",
            acceptable_low=33.9,
            acceptable_high=34.1,
            required_sources=[_CALL],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.SEC_INTERPRETATION,
            inputs={"ticker": _ACME, "quarter": "Q4 2023"},
        ),
        EvaluationCase(
            key="ACME_CUSTOMER_CONCENTRATION",
            question="What percentage of ACME's fiscal 2023 revenue came from its largest distributor?",
            expected_answer="11.2%",
            expected_value=11.2,
            unit="percent",
            acceptable_low=11.1,
            acceptable_high=11.3,
            required_sources=[_TENK],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.RISK_IDENTIFICATION,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_LITIGATION_ACCRUAL",
            question="Has ACME recorded a loss accrual for the Software Platform patent litigation, and why?",
            expected_answer=(
                "No accrual has been recorded because a loss is not currently probable or estimable."
            ),
            evaluation_method=EvaluationMethod.CITATION_CHECK,
            required_sources=[_CALL],
            required_fields=["accrual", "probable"],
            difficulty=Difficulty.HARD,
            category=CaseCategory.ACCOUNTING,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_RISK_FACTORS",
            question="Identify the principal risk factors ACME disclosed for fiscal 2023.",
            expected_answer=(
                "Cyclical industrial capital spending, component shortages pressuring gross margin, "
                "competitive pricing pressure, distributor concentration, and unresolved patent "
                "litigation."
            ),
            evaluation_method=EvaluationMethod.DETERMINISTIC_FIELDS,
            required_fields=["capital spending", "component", "pricing", "litigation"],
            required_sources=[_TENK],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.RISK_IDENTIFICATION,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_GOODWILL_BALANCE",
            question="What was ACME's goodwill balance at the end of fiscal 2023?",
            expected_answer="$902.3 million",
            expected_value=902.3,
            unit="usd_millions",
            acceptable_low=901.0,
            acceptable_high=903.5,
            required_sources=[_TENK],
            difficulty=Difficulty.EASY,
            category=CaseCategory.ACCOUNTING,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_FY2022_GROSS_MARGIN_HISTORICAL",
            question="As of 30 June 2023, what was ACME's most recently reported full-year gross margin?",
            expected_answer="37.0% (fiscal 2022)",
            expected_value=36.97,
            unit="percent",
            acceptable_low=36.8,
            acceptable_high=37.2,
            required_sources=[_TENK_PRIOR],
            forbidden_sources=[_TENK, _EARNINGS, _CALL],
            information_cutoff="2023-06-30",
            difficulty=Difficulty.HARD,
            category=CaseCategory.SEC_INTERPRETATION,
            notes=(
                "Tests the historical information lock: the FY2023 10-K was filed 2024-02-14 and "
                "must be invisible at this cutoff."
            ),
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_VALUATION_PE",
            question=(
                "Using fiscal 2023 diluted EPS and the demo market price, what is ACME's trailing "
                "P/E multiple? State the price you used."
            ),
            expected_answer="Trailing P/E computed from FY2023 diluted EPS of $3.20 and the demo close.",
            evaluation_method=EvaluationMethod.PROGRAMMATIC,
            required_fields=["eps", "price"],
            required_sources=[_TENK],
            difficulty=Difficulty.HARD,
            category=CaseCategory.VALUATION,
            notes="Scored on whether the calculation is shown and internally consistent.",
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_STATISTICAL_CLAIM_DISCIPLINE",
            question=(
                "Do ACME's quarterly revenue figures for fiscal 2023 establish a statistically "
                "significant growth trend? Answer with the appropriate statistical caution."
            ),
            expected_answer=(
                "No: four observations cannot establish statistical significance; the answer must "
                "state the sample-size limitation."
            ),
            evaluation_method=EvaluationMethod.DETERMINISTIC_FIELDS,
            required_fields=["sample", "limitation"],
            difficulty=Difficulty.HARD,
            category=CaseCategory.STATISTICS,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_CITATION_DISCIPLINE",
            question="State ACME's fiscal 2023 revenue and operating income, citing a source for each figure.",
            expected_answer="Revenue $4,820.0 million; operating income $563.0 million, both cited.",
            evaluation_method=EvaluationMethod.CITATION_CHECK,
            required_sources=[_TENK],
            difficulty=Difficulty.EASY,
            category=CaseCategory.CITATION,
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_UNKNOWABLE_FY2025",
            question="What was ACME's fiscal 2025 revenue?",
            expected_answer=(
                "Unknown: fiscal 2025 results are not in the retrieved corpus and must not be estimated."
            ),
            evaluation_method=EvaluationMethod.DETERMINISTIC_FIELDS,
            required_fields=["unknown"],
            difficulty=Difficulty.MEDIUM,
            category=CaseCategory.CITATION,
            notes="Tests refusal to fabricate. Any specific figure here is a hallucination.",
            inputs={"ticker": _ACME},
        ),
        EvaluationCase(
            key="ACME_DIVIDEND_PER_SHARE_2023",
            question="What quarterly dividend per share did ACME pay in 2023?",
            expected_answer="$0.20 per share",
            expected_value=0.20,
            unit="usd",
            acceptable_low=0.19,
            acceptable_high=0.21,
            difficulty=Difficulty.EASY,
            category=CaseCategory.FINANCIAL_STATEMENTS,
            inputs={"ticker": _ACME},
        ),
    ],
)

BUILTIN_SUITES: dict[str, EvaluationSuite] = {FINANCIAL_RESEARCH_BASIC_V1.key: FINANCIAL_RESEARCH_BASIC_V1}


def get_suite(key: str) -> EvaluationSuite | None:
    return BUILTIN_SUITES.get(key)
