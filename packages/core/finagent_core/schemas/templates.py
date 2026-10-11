"""Research task templates.

A template declares the *contract* for a task: required inputs, required output fields, and
the tools it needs. Deterministic evaluators check the output against
`required_output_fields`, which is why templates are data rather than prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from finagent_core.schemas.enums import OutputFormat, TaskTemplate, ToolName


@dataclass(frozen=True)
class TaskTemplateDefinition:
    key: TaskTemplate
    name: str
    description: str
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...]
    required_output_fields: tuple[str, ...]
    recommended_tools: tuple[ToolName, ...]
    default_output_format: OutputFormat = OutputFormat.MARKDOWN
    question_template: str = ""
    guidance: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def build_question(self, inputs: dict[str, Any]) -> str:
        try:
            return self.question_template.format(**inputs)
        except KeyError as exc:
            raise ValueError(f"missing template input: {str(exc).strip(chr(39))}") from exc

    def validate_inputs(self, inputs: dict[str, Any]) -> list[str]:
        return [key for key in self.required_inputs if not str(inputs.get(key, "")).strip()]


TASK_TEMPLATES: dict[TaskTemplate, TaskTemplateDefinition] = {
    TaskTemplate.EARNINGS_ANALYSIS: TaskTemplateDefinition(
        key=TaskTemplate.EARNINGS_ANALYSIS,
        name="Earnings analysis",
        description="Analyse a reported quarter against the prior period and guidance.",
        required_inputs=("ticker", "quarter"),
        optional_inputs=("peer_tickers",),
        required_output_fields=(
            "revenue", "eps", "guidance", "margin", "management_commentary", "risks",
            "changes_from_prior_quarter",
        ),
        recommended_tools=(ToolName.DOCUMENT_SEARCH, ToolName.FINANCIAL_STATEMENTS, ToolName.CALCULATOR),
        question_template=(
            "Analyse {ticker}'s {quarter} results. Report revenue, EPS, margins, guidance, "
            "management commentary, risks, and what changed versus the prior quarter. Cite a "
            "source for every figure."
        ),
        guidance="Compare reported figures with the prior period and with any stated guidance.",
    ),
    TaskTemplate.COMPANY_DEEP_DIVE: TaskTemplateDefinition(
        key=TaskTemplate.COMPANY_DEEP_DIVE,
        name="Company deep dive",
        description="Full qualitative and quantitative company review.",
        required_inputs=("ticker",),
        optional_inputs=("focus",),
        required_output_fields=(
            "business_model", "revenue_drivers", "competitive_advantages", "risks",
            "financial_health", "valuation", "catalysts",
        ),
        recommended_tools=(
            ToolName.DOCUMENT_SEARCH, ToolName.FINANCIAL_STATEMENTS, ToolName.MARKET_DATA,
            ToolName.CALCULATOR,
        ),
        question_template=(
            "Produce a deep dive on {ticker}: business model, revenue drivers, competitive "
            "advantages, risks, financial health, valuation and catalysts. Cite every claim."
        ),
    ),
    TaskTemplate.INVESTMENT_THESIS: TaskTemplateDefinition(
        key=TaskTemplate.INVESTMENT_THESIS,
        name="Investment thesis",
        description="Structured bull/base/bear thesis with assumptions and disconfirming evidence.",
        required_inputs=("ticker",),
        optional_inputs=("horizon_months", "position_size_pct"),
        required_output_fields=(
            "thesis", "bull_case", "base_case", "bear_case", "assumptions", "catalysts", "risks",
            "disconfirming_evidence",
        ),
        recommended_tools=(
            ToolName.DOCUMENT_SEARCH, ToolName.FINANCIAL_STATEMENTS, ToolName.MARKET_DATA,
            ToolName.CALCULATOR,
        ),
        default_output_format=OutputFormat.INVESTMENT_THESIS,
        question_template=(
            "Build an investment thesis for {ticker}. State the bull, base and bear cases, the "
            "key assumptions, catalysts, risks, and the evidence that would disconfirm the "
            "thesis. Cite every factual claim."
        ),
        guidance="A thesis without disconfirming evidence is scored as incomplete.",
    ),
    TaskTemplate.FINANCIAL_STATEMENT_ANALYSIS: TaskTemplateDefinition(
        key=TaskTemplate.FINANCIAL_STATEMENT_ANALYSIS,
        name="Financial statement analysis",
        description="Quantitative review of growth, margins, cash generation and balance sheet.",
        required_inputs=("ticker",),
        optional_inputs=("periods",),
        required_output_fields=(
            "revenue_growth", "gross_margin", "operating_margin", "free_cash_flow", "roic", "debt",
            "working_capital",
        ),
        recommended_tools=(
            ToolName.FINANCIAL_STATEMENTS, ToolName.DOCUMENT_SEARCH, ToolName.CALCULATOR,
            ToolName.PYTHON,
        ),
        question_template=(
            "Analyse {ticker}'s financial statements: revenue growth, gross margin, operating "
            "margin, free cash flow, ROIC, debt and working capital. Show each calculation."
        ),
    ),
    TaskTemplate.QUANT_RESEARCH: TaskTemplateDefinition(
        key=TaskTemplate.QUANT_RESEARCH,
        name="Quant research",
        description="Test a hypothesis on a dataset with an explicit methodology and limitations.",
        required_inputs=("hypothesis",),
        optional_inputs=("dataset_id", "universe", "start_date", "end_date"),
        required_output_fields=("methodology", "statistical_test", "results", "limitations", "backtest"),
        recommended_tools=(ToolName.PYTHON, ToolName.BACKTEST, ToolName.MARKET_DATA),
        question_template=(
            "Test this hypothesis: {hypothesis}. State the methodology, the statistical test "
            "used, the results with effect size, the limitations, and an out-of-sample backtest."
        ),
        guidance="In-sample results alone are not an acceptable answer.",
    ),
    TaskTemplate.CUSTOM: TaskTemplateDefinition(
        key=TaskTemplate.CUSTOM,
        name="Custom task",
        description="Free-form research question with citation requirements still enforced.",
        required_inputs=("question",),
        optional_inputs=("ticker",),
        required_output_fields=(),
        recommended_tools=(ToolName.DOCUMENT_SEARCH, ToolName.CALCULATOR),
        question_template="{question}",
    ),
}


def get_template(key: TaskTemplate | str) -> TaskTemplateDefinition:
    return TASK_TEMPLATES[TaskTemplate(key) if isinstance(key, str) else key]
