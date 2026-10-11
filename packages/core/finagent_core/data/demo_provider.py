"""Demo financial data provider (clearly labelled synthetic data)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from finagent_core.cutoff import AsOfContext
from finagent_core.data.base import FinancialDataProvider
from finagent_core.data.demo_dataset import (
    ACME_ANNUAL_BALANCE,
    ACME_ANNUAL_CASH_FLOW,
    ACME_ANNUAL_INCOME,
    ACME_QUARTERLY_INCOME,
    COMPANY_PROFILES,
    DEMO_DISCLAIMER,
    DEMO_SOURCE,
    MILLION,
    PERIOD_ENDS,
    PERIOD_PUBLICATION,
    demo_documents,
    generate_price_series,
)
from finagent_core.data.schemas import (
    CompanyProfile,
    DividendEvent,
    FinancialStatement,
    MarketCapPoint,
    Periodicity,
    PriceBar,
    ProviderCapability,
    SecFiling,
    StatementType,
    TranscriptSegment,
)
from finagent_core.errors import NotFoundError


class DemoDataProvider(FinancialDataProvider):
    """Synthetic issuer data for ACME Technologies and seven fictional peers.

    Never presented as market data: ``is_demo=True`` on every record and ``status() == MOCK``.
    """

    key = "demo"
    display_name = "Demo dataset (synthetic, labelled)"
    is_demo = True
    requires_credentials = False
    capabilities = (
        ProviderCapability.COMPANY_PROFILE,
        ProviderCapability.INCOME_STATEMENT,
        ProviderCapability.BALANCE_SHEET,
        ProviderCapability.CASH_FLOW,
        ProviderCapability.PRICES,
        ProviderCapability.MARKET_CAP,
        ProviderCapability.DIVIDENDS,
        ProviderCapability.SEC_FILINGS,
        ProviderCapability.TRANSCRIPTS,
    )
    disclaimer = DEMO_DISCLAIMER

    # ------------------------------------------------------------------ profiles

    def get_company_profile(self, ticker: str, *, as_of: AsOfContext | None = None) -> CompanyProfile:
        self._require(ProviderCapability.COMPANY_PROFILE)
        profile = COMPANY_PROFILES.get(ticker.upper())
        if profile is None:
            raise NotFoundError(f"demo provider has no issuer {ticker}")
        return CompanyProfile(
            ticker=ticker.upper(),
            name=profile["name"],
            sector=profile.get("sector"),
            industry=profile.get("industry"),
            description=profile.get("description"),
            cik=profile.get("cik"),
            exchange=profile.get("exchange", "DEMO-EX"),
            employees=profile.get("employees"),
            source=DEMO_SOURCE,
            is_demo=True,
            publication_timestamp=datetime(2018, 1, 1, tzinfo=UTC),
        )

    # --------------------------------------------------------------- statements

    def _statements(
        self,
        ticker: str,
        table: dict[str, dict[str, float]],
        statement_type: StatementType,
        periodicity: Periodicity,
        limit: int,
        as_of: AsOfContext | None,
    ) -> list[FinancialStatement]:
        if ticker.upper() != "ACME":
            raise NotFoundError(
                f"demo statements are only available for ACME (requested {ticker.upper()})"
            )
        statements: list[FinancialStatement] = []
        for period_label, values in table.items():
            quarter = None
            if period_label.startswith("Q"):
                quarter = int(period_label[1])
                fiscal_year = int(period_label.split()[-1])
            else:
                fiscal_year = int(period_label[2:])
            statements.append(
                FinancialStatement(
                    ticker="ACME",
                    statement_type=statement_type,
                    periodicity=periodicity,
                    period_label=period_label,
                    period_end=PERIOD_ENDS[period_label],
                    fiscal_year=fiscal_year,
                    fiscal_quarter=quarter,
                    unit_scale=MILLION,
                    values=dict(values),
                    source=DEMO_SOURCE,
                    is_demo=True,
                    publication_timestamp=PERIOD_PUBLICATION[period_label],
                    filing_type="10-K" if periodicity is Periodicity.ANNUAL else "10-Q",
                )
            )
        statements.sort(key=lambda item: item.period_end, reverse=True)
        visible = self._enforce_cutoff(statements, as_of, subject=f"{ticker} {statement_type.value}")
        return visible[:limit]

    def get_income_statement(
        self,
        ticker: str,
        *,
        periodicity: Periodicity = Periodicity.ANNUAL,
        limit: int = 5,
        as_of: AsOfContext | None = None,
    ) -> list[FinancialStatement]:
        self._require(ProviderCapability.INCOME_STATEMENT)
        table = ACME_ANNUAL_INCOME if periodicity is Periodicity.ANNUAL else ACME_QUARTERLY_INCOME
        return self._statements(
            ticker, table, StatementType.INCOME_STATEMENT, periodicity, limit, as_of
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
        return self._statements(
            ticker, ACME_ANNUAL_BALANCE, StatementType.BALANCE_SHEET, Periodicity.ANNUAL, limit, as_of
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
        return self._statements(
            ticker, ACME_ANNUAL_CASH_FLOW, StatementType.CASH_FLOW, Periodicity.ANNUAL, limit, as_of
        )

    # ------------------------------------------------------------------- prices

    def get_prices(
        self, symbol: str, *, start: date, end: date, as_of: AsOfContext | None = None
    ) -> list[PriceBar]:
        self._require(ProviderCapability.PRICES)
        symbol = symbol.upper()
        if symbol not in COMPANY_PROFILES:
            raise NotFoundError(f"demo provider has no symbol {symbol}")
        effective_end = end
        if as_of is not None and as_of.cutoff is not None:
            effective_end = min(end, as_of.cutoff.date())
        if effective_end < start:
            return []
        bars = [
            PriceBar(
                symbol=row["symbol"],
                bar_date=row["bar_date"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                adj_close=row["adj_close"],
                volume=row["volume"],
                source=DEMO_SOURCE,
                is_demo=True,
                publication_timestamp=row["publication_timestamp"],
            )
            for row in generate_price_series(symbol, start, effective_end)
        ]
        return self._enforce_cutoff(bars, as_of, subject=f"{symbol} prices")

    def get_market_cap(self, symbol: str, *, as_of: AsOfContext | None = None) -> MarketCapPoint:
        self._require(ProviderCapability.MARKET_CAP)
        symbol = symbol.upper()
        profile = COMPANY_PROFILES.get(symbol)
        if profile is None:
            raise NotFoundError(f"demo provider has no symbol {symbol}")
        as_of_date = as_of.cutoff.date() if as_of and as_of.cutoff else date(2024, 12, 31)
        bars = self.get_prices(
            symbol, start=as_of_date - timedelta(days=10), end=as_of_date, as_of=as_of
        )
        if not bars:
            raise NotFoundError(f"no demo prices for {symbol} as of {as_of_date}")
        last = bars[-1]
        shares = float(profile["shares_outstanding"]) * MILLION
        return MarketCapPoint(
            symbol=symbol,
            as_of_date=last.bar_date,
            market_cap=last.close * shares,
            shares_outstanding=shares,
            source=DEMO_SOURCE,
            is_demo=True,
            publication_timestamp=last.publication_timestamp,
        )

    def get_dividends(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        as_of: AsOfContext | None = None,
    ) -> list[DividendEvent]:
        self._require(ProviderCapability.DIVIDENDS)
        symbol = symbol.upper()
        if symbol != "ACME":
            return []
        events: list[DividendEvent] = []
        for year, amount in ((2021, 0.17), (2022, 0.19), (2023, 0.20)):
            for month, day in ((3, 10), (6, 10), (9, 10), (12, 10)):
                ex_date = date(year, month, day)
                if (start and ex_date < start) or (end and ex_date > end):
                    continue
                events.append(
                    DividendEvent(
                        symbol=symbol,
                        ex_date=ex_date,
                        pay_date=ex_date,
                        amount_per_share=amount,
                        frequency="quarterly",
                        source=DEMO_SOURCE,
                        is_demo=True,
                        publication_timestamp=datetime(
                            ex_date.year, ex_date.month, ex_date.day, tzinfo=UTC
                        ),
                    )
                )
        return self._enforce_cutoff(events, as_of, subject=f"{symbol} dividends")

    # ----------------------------------------------------------------- filings

    def get_sec_filings(
        self,
        ticker: str,
        *,
        form_types: tuple[str, ...] = ("10-K", "10-Q"),
        limit: int = 10,
        as_of: AsOfContext | None = None,
    ) -> list[SecFiling]:
        self._require(ProviderCapability.SEC_FILINGS)
        ticker = ticker.upper()
        filings = [
            SecFiling(
                ticker=document.ticker,
                cik=COMPANY_PROFILES.get(document.ticker, {}).get("cik"),
                form_type=document.form_type,
                filed_at=document.filed_at,
                period_of_report=PERIOD_ENDS.get(document.period_label),
                accession_number=f"demo-{document.key.lower()}",
                title=document.title,
                text=document.text,
                page_count=document.page_count,
                source=DEMO_SOURCE,
                is_demo=True,
                publication_timestamp=document.filed_at,
            )
            for document in demo_documents()
            if document.ticker == ticker and (not form_types or document.form_type in form_types)
        ]
        filings.sort(key=lambda item: item.filed_at, reverse=True)
        return self._enforce_cutoff(filings, as_of, subject=f"{ticker} filings")[:limit]

    def get_transcripts(
        self, ticker: str, *, limit: int = 4, as_of: AsOfContext | None = None
    ) -> list[TranscriptSegment]:
        self._require(ProviderCapability.TRANSCRIPTS)
        ticker = ticker.upper()
        segments = [
            TranscriptSegment(
                ticker=ticker,
                event_date=document.filed_at.date(),
                quarter_label=document.period_label,
                speaker="see transcript",
                section="prepared_remarks" if page.page_number == 1 else "qa",
                text=page.text,
                source=DEMO_SOURCE,
                is_demo=True,
                publication_timestamp=document.filed_at,
            )
            for document in demo_documents()
            if document.ticker == ticker and document.form_type == "TRANSCRIPT"
            for page in document.pages
        ]
        return self._enforce_cutoff(segments, as_of, subject=f"{ticker} transcripts")[:limit]
