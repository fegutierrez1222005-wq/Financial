"""Market-data providers: Alpha Vantage, Polygon, and user-uploaded CSV.

Thin, replaceable adapters over the shared :class:`FinancialDataProvider` interface.
Without credentials they report ``unavailable``; they never fall back to synthetic data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx

from finagent_core.cutoff import AsOfContext
from finagent_core.data.base import FinancialDataProvider
from finagent_core.data.schemas import (
    CompanyProfile,
    FinancialStatement,
    Periodicity,
    PriceBar,
    ProviderCapability,
    StatementType,
)
from finagent_core.errors import NotFoundError, ProviderError, ValidationFailedError
from finagent_core.logging import get_logger

logger = get_logger(__name__)


class AlphaVantageProvider(FinancialDataProvider):
    key = "alpha_vantage"
    display_name = "Alpha Vantage"
    docs_url = "https://www.alphavantage.co/documentation/"
    capabilities = (
        ProviderCapability.COMPANY_PROFILE,
        ProviderCapability.PRICES,
        ProviderCapability.INCOME_STATEMENT,
    )

    def __init__(self, *, api_key: str | None = None, timeout: float = 30.0) -> None:
        super().__init__(api_key=api_key, base_url="https://www.alphavantage.co/query", timeout=timeout)

    def _call(self, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = httpx.get(
                self._base_url, params={**params, "apikey": self._api_key or ""}, timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"alpha vantage transport failure: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(f"alpha vantage returned {response.status_code}")
        payload = response.json()
        if "Note" in payload or "Information" in payload:
            raise ProviderError("alpha vantage rate limit or entitlement message returned")
        if "Error Message" in payload:
            raise NotFoundError(str(payload["Error Message"]))
        return payload

    def get_company_profile(self, ticker: str, *, as_of: AsOfContext | None = None) -> CompanyProfile:
        self._require(ProviderCapability.COMPANY_PROFILE)
        payload = self._call({"function": "OVERVIEW", "symbol": ticker.upper()})
        return CompanyProfile(
            ticker=ticker.upper(),
            name=payload.get("Name") or ticker.upper(),
            sector=payload.get("Sector"),
            industry=payload.get("Industry"),
            description=payload.get("Description"),
            exchange=payload.get("Exchange"),
            currency=payload.get("Currency", "USD"),
            source=self.key,
            publication_timestamp=datetime.now(UTC),
        )

    def get_prices(
        self, symbol: str, *, start: date, end: date, as_of: AsOfContext | None = None
    ) -> list[PriceBar]:
        self._require(ProviderCapability.PRICES)
        series = self._call(
            {"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol.upper(), "outputsize": "full"}
        ).get("Time Series (Daily)") or {}
        bars: list[PriceBar] = []
        for day_key, row in series.items():
            bar_date = date.fromisoformat(day_key)
            if bar_date < start or bar_date > end:
                continue
            bars.append(
                PriceBar(
                    symbol=symbol.upper(),
                    bar_date=bar_date,
                    open=float(row["1. open"]),
                    high=float(row["2. high"]),
                    low=float(row["3. low"]),
                    close=float(row["4. close"]),
                    adj_close=float(row.get("5. adjusted close", row["4. close"])),
                    volume=float(row.get("6. volume", 0.0)),
                    source=self.key,
                    publication_timestamp=datetime(
                        bar_date.year, bar_date.month, bar_date.day, 21, tzinfo=UTC
                    ),
                )
            )
        bars.sort(key=lambda bar: bar.bar_date)
        return self._enforce_cutoff(bars, as_of, subject=f"{symbol} prices")

    def get_income_statement(
        self,
        ticker: str,
        *,
        periodicity: Periodicity = Periodicity.ANNUAL,
        limit: int = 5,
        as_of: AsOfContext | None = None,
    ) -> list[FinancialStatement]:
        self._require(ProviderCapability.INCOME_STATEMENT)
        payload = self._call({"function": "INCOME_STATEMENT", "symbol": ticker.upper()})
        key = "annualReports" if periodicity is Periodicity.ANNUAL else "quarterlyReports"
        mapping = {
            "totalRevenue": "revenue",
            "costOfRevenue": "cost_of_revenue",
            "grossProfit": "gross_profit",
            "operatingExpenses": "operating_expenses",
            "operatingIncome": "operating_income",
            "incomeBeforeTax": "pretax_income",
            "incomeTaxExpense": "income_tax_expense",
            "netIncome": "net_income",
        }
        statements: list[FinancialStatement] = []
        for report in payload.get(key, [])[: limit * 2]:
            period_end = date.fromisoformat(report["fiscalDateEnding"])
            statements.append(
                FinancialStatement(
                    ticker=ticker.upper(),
                    statement_type=StatementType.INCOME_STATEMENT,
                    periodicity=periodicity,
                    period_label=(
                        f"FY{period_end.year}"
                        if periodicity is Periodicity.ANNUAL
                        else f"Q{(period_end.month - 1) // 3 + 1} {period_end.year}"
                    ),
                    period_end=period_end,
                    fiscal_year=period_end.year,
                    fiscal_quarter=None
                    if periodicity is Periodicity.ANNUAL
                    else (period_end.month - 1) // 3 + 1,
                    currency=report.get("reportedCurrency", "USD"),
                    values={
                        canonical: value
                        for source_key, canonical in mapping.items()
                        if (value := _to_float(report.get(source_key))) is not None
                    },
                    source=self.key,
                    # Alpha Vantage exposes no filing timestamp; unknown provenance is
                    # inadmissible under a historical cutoff by design.
                    publication_timestamp=None,
                )
            )
        statements.sort(key=lambda item: item.period_end, reverse=True)
        return statements[:limit]


class PolygonProvider(FinancialDataProvider):
    key = "polygon"
    display_name = "Polygon.io"
    docs_url = "https://polygon.io/docs"
    capabilities = (ProviderCapability.PRICES, ProviderCapability.COMPANY_PROFILE)

    def __init__(self, *, api_key: str | None = None, timeout: float = 30.0) -> None:
        super().__init__(api_key=api_key, base_url="https://api.polygon.io", timeout=timeout)

    def _call(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = httpx.get(
                f"{self._base_url}{path}",
                params={**(params or {}), "apiKey": self._api_key or ""},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"polygon transport failure: {exc}") from exc
        if response.status_code == 404:
            raise NotFoundError(f"polygon resource not found: {path}")
        if response.status_code >= 400:
            raise ProviderError(f"polygon returned {response.status_code}")
        return response.json()

    def get_company_profile(self, ticker: str, *, as_of: AsOfContext | None = None) -> CompanyProfile:
        self._require(ProviderCapability.COMPANY_PROFILE)
        payload = self._call(f"/v3/reference/tickers/{ticker.upper()}").get("results") or {}
        return CompanyProfile(
            ticker=ticker.upper(),
            name=payload.get("name") or ticker.upper(),
            sector=payload.get("sic_description"),
            industry=payload.get("sic_description"),
            description=payload.get("description"),
            exchange=payload.get("primary_exchange"),
            currency=str(payload.get("currency_name", "USD")).upper(),
            source=self.key,
            publication_timestamp=datetime.now(UTC),
        )

    def get_prices(
        self, symbol: str, *, start: date, end: date, as_of: AsOfContext | None = None
    ) -> list[PriceBar]:
        self._require(ProviderCapability.PRICES)
        payload = self._call(
            f"/v2/aggs/ticker/{symbol.upper()}/range/1/day/{start.isoformat()}/{end.isoformat()}",
            {"adjusted": "true", "sort": "asc", "limit": 50_000},
        )
        bars = [
            PriceBar(
                symbol=symbol.upper(),
                bar_date=(bar_date := datetime.fromtimestamp(row["t"] / 1000, tz=UTC).date()),
                open=float(row["o"]),
                high=float(row["h"]),
                low=float(row["l"]),
                close=float(row["c"]),
                adj_close=float(row["c"]),
                volume=float(row.get("v", 0.0)),
                source=self.key,
                publication_timestamp=datetime(
                    bar_date.year, bar_date.month, bar_date.day, 21, tzinfo=UTC
                ),
            )
            for row in payload.get("results") or []
        ]
        return self._enforce_cutoff(bars, as_of, subject=f"{symbol} prices")


class UploadedCsvPriceProvider(FinancialDataProvider):
    """Prices from a user-uploaded CSV/XLSX dataset.

    Rows need ``symbol``, ``date`` and ``close``; ``open/high/low/volume`` and ``adj_close``
    are optional. ``is_adjusted`` reflects the presence of an ``adj_close`` column, so the
    backtest validator can warn about corporate actions.
    """

    key = "uploaded_csv"
    display_name = "Uploaded price file"
    requires_credentials = False
    capabilities = (ProviderCapability.PRICES,)

    def __init__(self, rows: list[dict[str, Any]], *, dataset_name: str = "uploaded") -> None:
        super().__init__()
        self.dataset_name = dataset_name
        self._bars = self._parse(rows)

    def _parse(self, rows: list[dict[str, Any]]) -> list[PriceBar]:
        bars: list[PriceBar] = []
        for index, row in enumerate(rows):
            try:
                symbol = str(row["symbol"]).upper()
                raw_date = row.get("date") or row.get("bar_date")
                bar_date = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date)[:10])
                close = float(row["close"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValidationFailedError(
                    f"row {index + 1} is missing symbol/date/close", details={"row": index + 1}
                ) from exc
            bars.append(
                PriceBar(
                    symbol=symbol,
                    bar_date=bar_date,
                    open=float(row.get("open") or close),
                    high=float(row.get("high") or close),
                    low=float(row.get("low") or close),
                    close=close,
                    adj_close=float(row.get("adj_close") or close),
                    volume=float(row.get("volume") or 0.0),
                    is_adjusted="adj_close" in row,
                    source=f"{self.key}:{self.dataset_name}",
                    publication_timestamp=datetime(
                        bar_date.year, bar_date.month, bar_date.day, 21, tzinfo=UTC
                    ),
                )
            )
        bars.sort(key=lambda bar: (bar.symbol, bar.bar_date))
        return bars

    @property
    def symbols(self) -> list[str]:
        return sorted({bar.symbol for bar in self._bars})

    def get_prices(
        self, symbol: str, *, start: date, end: date, as_of: AsOfContext | None = None
    ) -> list[PriceBar]:
        self._require(ProviderCapability.PRICES)
        selected = [
            bar for bar in self._bars if bar.symbol == symbol.upper() and start <= bar.bar_date <= end
        ]
        return self._enforce_cutoff(selected, as_of, subject=f"{symbol} prices")


def _to_float(value: Any) -> float | None:
    if value in (None, "", "None", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
