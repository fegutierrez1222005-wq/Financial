"""Structured investment thesis.

Structuring the output is what makes research *evaluable*: the platform can check that a
thesis states assumptions, risks and disconfirming evidence, and can score each part
separately instead of judging a wall of prose.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from finagent_core.schemas.enums import ClaimSupport


class ValuationView(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: str = Field(default="not_performed", description="dcf, multiples, not_performed, ...")
    fair_value_per_share: float | None = None
    current_price: float | None = None
    upside_pct: float | None = None
    key_inputs: dict[str, float] = Field(default_factory=dict)
    note: str | None = None


class SupportedStatement(BaseModel):
    """A statement with its evidence pointer and support classification."""

    text: str
    support_level: ClaimSupport = ClaimSupport.UNKNOWN
    chunk_ids: list[str] = Field(default_factory=list)
    source_labels: list[str] = Field(default_factory=list)


class InvestmentThesis(BaseModel):
    """The platform's canonical structured research output."""

    model_config = ConfigDict(extra="allow")

    subject: str | None = Field(default=None, description="Ticker or entity under analysis.")
    thesis: str = ""
    bull_case: list[str] = Field(default_factory=list)
    base_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    disconfirming_evidence: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    valuation: ValuationView = Field(default_factory=ValuationView)
    financial_metrics: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)

    @field_validator(
        "bull_case", "base_case", "bear_case", "catalysts", "risks", "assumptions",
        "disconfirming_evidence", "unknowns", "sources", mode="before",
    )
    @classmethod
    def _coerce_list(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: Any) -> Any:
        """Accept 0–1 fractions or 0–100 percentages; store a fraction."""
        if value is None:
            return 0.0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if numeric > 1.0:
            numeric /= 100.0
        return max(0.0, min(1.0, numeric))

    @property
    def completeness(self) -> float:
        """Fraction of required sections that are populated (0–1)."""
        required = [
            self.thesis, self.bull_case, self.base_case, self.bear_case,
            self.risks, self.assumptions, self.disconfirming_evidence,
        ]
        return sum(1 for section in required if section) / len(required)

    def missing_sections(self) -> list[str]:
        checks = {
            "thesis": self.thesis,
            "bull_case": self.bull_case,
            "base_case": self.base_case,
            "bear_case": self.bear_case,
            "risks": self.risks,
            "assumptions": self.assumptions,
            "disconfirming_evidence": self.disconfirming_evidence,
        }
        return [name for name, value in checks.items() if not value]
