"""SEC EDGAR provider (real HTTP).

EDGAR requires a descriptive ``User-Agent`` identifying the requesting organisation. That
contact string is treated as this provider's credential: without it the provider reports
``unavailable`` rather than sending non-compliant requests.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

import httpx

from finagent_core.cutoff import AsOfContext
from finagent_core.data.base import FinancialDataProvider
from finagent_core.data.schemas import (
    CompanyProfile,
    FinancialStatement,
    Periodicity,
    ProviderCapability,
    SecFiling,
    StatementType,
)
from finagent_core.errors import NotFoundError, ProviderError
from finagent_core.logging import get_logger

logger = get_logger(__name__)

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

_INCOME_CONCEPTS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "Revenues": "revenue",
    "CostOfRevenue": "cost_of_revenue",
    "GrossProfit": "gross_profit",
    "OperatingExpenses": "operating_expenses",
    "OperatingIncomeLoss": "operating_income",
    "IncomeTaxExpenseBenefit": "income_tax_expense",
    "NetIncomeLoss": "net_income",
    "EarningsPerShareDiluted": "diluted_eps",
}
_BALANCE_CONCEPTS = {
    "CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
    "AccountsReceivableNetCurrent": "accounts_receivable",
    "InventoryNet": "inventory",
    "AssetsCurrent": "total_current_assets",
    "Assets": "total_assets",
    "LiabilitiesCurrent": "total_current_liabilities",
    "Liabilities": "total_liabilities",
    "StockholdersEquity": "total_equity",
    "Goodwill": "goodwill",
    "LongTermDebtNoncurrent": "long_term_debt",
}
_CASH_FLOW_CONCEPTS = {
    "NetCashProvidedByUsedInOperatingActivities": "cash_from_operations",
    "NetCashProvidedByUsedInInvestingActivities": "cash_from_investing",
    "NetCashProvidedByUsedInFinancingActivities": "cash_from_financing",
    "PaymentsToAcquirePropertyPlantAndEquipment": "capital_expenditures",
    "DepreciationDepletionAndAmortization": "depreciation_amortization",
    "ShareBasedCompensation": "stock_based_compensation",
}


class SecEdgarProvider(FinancialDataProvider):
    key = "sec_edgar"
    display_name = "SEC EDGAR"
    docs_url = "https://www.sec.gov/os/accessing-edgar-data"
    capabilities = (
        ProviderCapability.COMPANY_PROFILE,
        ProviderCapability.INCOME_STATEMENT,
        ProviderCapability.BALANCE_SHEET,
        ProviderCapability.CASH_FLOW,
        ProviderCapability.SEC_FILINGS,
    )

    def __init__(self, *, user_agent: str | None = None, timeout: float = 30.0) -> None:
        # The EDGAR contact string plays the role of the credential.
        super().__init__(api_key=user_agent, base_url="https://data.sec.gov", timeout=timeout)
        self._user_agent = user_agent
        self._ticker_cache: dict[str, str] = {}

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self._user_agent or "", "Accept-Encoding": "gzip, deflate"}

    def _get_json(self, url: str) -> dict[str, Any]:
        try:
            response = httpx.get(url, headers=self._headers(), timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise ProviderError(f"edgar transport failure: {exc}") from exc
        if response.status_code == 404:
            raise NotFoundError(f"edgar resource not found: {url}")
        if response.status_code >= 400:
            raise ProviderError(f"edgar returned {response.status_code}")
        return response.json()

    def cik_for_ticker(self, ticker: str) -> str:
        ticker = ticker.upper()
        if not self._ticker_cache:
            payload = self._get_json(_TICKER_MAP_URL)
            self._ticker_cache = {
                str(entry["ticker"]).upper(): str(entry["cik_str"]).zfill(10)
                for entry in payload.values()
                if isinstance(entry, dict) and entry.get("ticker")
            }
        cik = self._ticker_cache.get(ticker)
        if cik is None:
            raise NotFoundError(f"no EDGAR CIK for ticker {ticker}")
        return cik

    def get_company_profile(self, ticker: str, *, as_of: AsOfContext | None = None) -> CompanyProfile:
        self._require(ProviderCapability.COMPANY_PROFILE)
        cik = self.cik_for_ticker(ticker)
        payload = self._get_json(f"{self._base_url}/submissions/CIK{cik}.json")
        return CompanyProfile(
            ticker=ticker.upper(),
            name=payload.get("name", ticker.upper()),
            sector=payload.get("sicDescription"),
            industry=payload.get("sicDescription"),
            cik=cik,
            exchange=(payload.get("exchanges") or [None])[0],
            source=self.key,
            publication_timestamp=datetime.now(timezone.utc),
        )

    def _statements_from_facts(
        self,
        ticker: str,
        concepts: dict[str, str],
        statement_type: StatementType,
        periodicity: Periodicity,
        limit: int,
        as_of: AsOfContext | None,
    ) -> list[FinancialStatement]:
        cik = self.cik_for_ticker(ticker)
        facts = self._get_json(
            f"{self._base_url}/api/xbrl/companyfacts/CIK{cik}.json"
        ).get("facts", {}).get("us-gaap", {})
        form_filter = "10-K" if periodicity is Periodicity.ANNUAL else "10-Q"
        buckets: dict[str, dict[str, Any]] = {}

        for concept, canonical in concepts.items():
            for entries in ((facts.get(concept) or {}).get("units", {})).values():
                for entry in entries:
                    if entry.get("form") != form_filter or not entry.get("end"):
                        continue
                    fiscal_year, fiscal_period = entry.get("fy"), entry.get("fp")
                    if fiscal_year is None or fiscal_period is None:
                        continue
                    label = (
                        f"FY{fiscal_year}"
                        if periodicity is Periodicity.ANNUAL
                        else f"{fiscal_period} {fiscal_year}"
                    )
                    filed = entry.get("filed")
                    published = (
                        datetime.fromisoformat(filed).replace(tzinfo=timezone.utc) if filed else None
                    )
                    bucket = buckets.setdefault(
                        label,
                        {
                            "period_end": date.fromisoformat(entry["end"]),
                            "fiscal_year": int(fiscal_year),
                            "fiscal_quarter": None
                            if periodicity is Periodicity.ANNUAL
                            else {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4, "FY": 4}.get(str(fiscal_period)),
                            "values": {},
                            "published": published,
                        },
                    )
                    bucket["values"][canonical] = float(entry.get("val", 0.0))
                    if published and (bucket["published"] is None or published > bucket["published"]):
                        bucket["published"] = published

        statements = [
            FinancialStatement(
                ticker=ticker.upper(),
                statement_type=statement_type,
                periodicity=periodicity,
                period_label=label,
                period_end=bucket["period_end"],
                fiscal_year=bucket["fiscal_year"],
                fiscal_quarter=bucket["fiscal_quarter"],
                values=bucket["values"],
                source=self.key,
                publication_timestamp=bucket["published"],
                filing_type=form_filter,
            )
            for label, bucket in buckets.items()
        ]
        statements.sort(key=lambda item: item.period_end, reverse=True)
        return self._enforce_cutoff(
            statements, as_of, subject=f"{ticker} {statement_type.value}"
        )[:limit]

    def get_income_statement(
        self,
        ticker: str,
        *,
        periodicity: Periodicity = Periodicity.ANNUAL,
        limit: int = 5,
        as_of: AsOfContext | None = None,
    ) -> list[FinancialStatement]:
        self._require(ProviderCapability.INCOME_STATEMENT)
        return self._statements_from_facts(
            ticker, _INCOME_CONCEPTS, StatementType.INCOME_STATEMENT, periodicity, limit, as_of
        )

    def get_balance_sheet(
        self,
        ticker: str,
        *,
        periodicity: Periodicity = Periodicity.ANNUAL,
        limit: int = 5,
        as_of: AsOfContext | None = None,
    ) -> list[FinancialStatement]:
        self._require(ProviderCapability.BALANCE_SHEET)
        return self._statements_from_facts(
            ticker, _BALANCE_CONCEPTS, StatementType.BALANCE_SHEET, periodicity, limit, as_of
        )

    def get_cash_flow(
        self,
        ticker: str,
        *,
        periodicity: Periodicity = Periodicity.ANNUAL,
        limit: int = 5,
        as_of: AsOfContext | None = None,
    ) -> list[FinancialStatement]:
        self._require(ProviderCapability.CASH_FLOW)
        return self._statements_from_facts(
            ticker, _CASH_FLOW_CONCEPTS, StatementType.CASH_FLOW, periodicity, limit, as_of
        )

    def get_sec_filings(
        self,
        ticker: str,
        *,
        form_types: tuple[str, ...] = ("10-K", "10-Q"),
        limit: int = 10,
        as_of: AsOfContext | None = None,
    ) -> list[SecFiling]:
        self._require(ProviderCapability.SEC_FILINGS)
        cik = self.cik_for_ticker(ticker)
        recent = (
            (self._get_json(f"{self._base_url}/submissions/CIK{cik}.json").get("filings") or {})
            .get("recent")
            or {}
        )
        filings: list[SecFiling] = []
        for index, form in enumerate(recent.get("form") or []):
            if form_types and form not in form_types:
                continue
            filed_raw = (recent.get("filingDate") or [None])[index]
            if not filed_raw:
                continue
            filed_at = datetime.fromisoformat(filed_raw).replace(tzinfo=timezone.utc)
            accession = (recent.get("accessionNumber") or [None])[index]
            document = (recent.get("primaryDocument") or [None])[index]
            period = (recent.get("reportDate") or [None])[index]
            filings.append(
                SecFiling(
                    ticker=ticker.upper(),
                    cik=cik,
                    form_type=form,
                    filed_at=filed_at,
                    period_of_report=date.fromisoformat(period) if period else None,
                    accession_number=accession,
                    url=(
                        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                        f"{str(accession).replace('-', '')}/{document}"
                        if accession and document
                        else None
                    ),
                    title=f"{ticker.upper()} {form} filed {filed_raw}",
                    source=self.key,
                    publication_timestamp=filed_at,
                )
            )
        filings.sort(key=lambda item: item.filed_at, reverse=True)
        return self._enforce_cutoff(filings, as_of, subject=f"{ticker} filings")[:limit]

    def fetch_filing_text(self, filing: SecFiling) -> str:
        """Download a filing's primary document as text (HTML tags stripped)."""
        if not filing.url:
            raise NotFoundError("filing has no document url")
        try:
            response = httpx.get(filing.url, headers=self._headers(), timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise ProviderError(f"edgar transport failure: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"edgar returned {response.status_code}")
        return _strip_html(response.text)


def _strip_html(html: str) -> str:
    without_scripts = re.sub(
        r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<[^>]+>", " ", without_scripts)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#8217;", "'")
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()
