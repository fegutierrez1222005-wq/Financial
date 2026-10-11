"""Canonical financial data records.

Every record carries `source` and `publication_timestamp` because the historical
information lock and the citation system both depend on provenance, and `is_demo` so
synthetic data can never be mistaken for real market data.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StatementType(StrEnum):
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"


class Periodicity(StrEnum):
    ANNUAL = "annual"
    QUARTERLY = "quarterly"


class ProvenanceMixin(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    source: str = Field(description="Provider key, e.g. 'sec_edgar', 'demo'.")
    publication_timestamp: datetime | None = Field(
        default=None, description="When this became public. Required for historical evaluation."
    )
    is_demo: bool = Field(default=False, description="True for clearly labelled synthetic data.")


class CompanyProfile(ProvenanceMixin):
    ticker: str
    name: str
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    cik: str | None = None
    exchange: str | None = None
    employees: int | None = None
    currency: str = "USD"


class FinancialStatement(ProvenanceMixin):
    ticker: str
    statement_type: StatementType
    periodicity: Periodicity
    period_label: str  # "FY2023", "Q4 2023"
    period_end: date
    fiscal_year: int
    fiscal_quarter: int | None = None
    currency: str = "USD"
    unit_scale: float = Field(default=1.0, description="Multiplier to base currency units.")
    values: dict[str, float] = Field(default_factory=dict)
    filing_url: str | None = None
    filing_type: str | None = None

    def value(self, key: str) -> float | None:
        raw = self.values.get(key)
        return None if raw is None else raw * self.unit_scale


class PriceBar(ProvenanceMixin):
    symbol: str
    bar_date: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: float
    is_adjusted: bool = Field(
        default=True, description="False signals corporate-action risk to the backtester."
    )


class MarketCapPoint(ProvenanceMixin):
    symbol: str
    as_of_date: date
    market_cap: float
    shares_outstanding: float | None = None


class DividendEvent(ProvenanceMixin):
    symbol: str
    ex_date: date
    pay_date: date | None = None
    amount_per_share: float
    frequency: str | None = None


class SecFiling(ProvenanceMixin):
    ticker: str
    cik: str | None = None
    form_type: str
    filed_at: datetime
    period_of_report: date | None = None
    accession_number: str | None = None
    url: str | None = None
    title: str | None = None
    text: str | None = None
    page_count: int | None = None


class TranscriptSegment(ProvenanceMixin):
    ticker: str
    event_date: date
    quarter_label: str
    speaker: str
    role: str | None = None
    section: str = "prepared_remarks"
    text: str = ""


class ProviderCapability(StrEnum):
    COMPANY_PROFILE = "company_profile"
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    PRICES = "prices"
    MARKET_CAP = "market_cap"
    DIVIDENDS = "dividends"
    SEC_FILINGS = "sec_filings"
    TRANSCRIPTS = "transcripts"


class DataQualityReport(BaseModel):
    """Attached to datasets so the UI can warn about quality before research uses them."""

    row_count: int = 0
    missing_values: int = 0
    duplicate_rows: int = 0
    coverage_start: date | None = None
    coverage_end: date | None = None
    stale_days: int | None = None
    inconsistent_timestamps: int = 0
    quality_score: float = Field(default=0.0, ge=0.0, le=100.0)
    warnings: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)
