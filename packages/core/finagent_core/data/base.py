"""Unified financial data provider interface.

Providers are interchangeable. Every method takes an :class:`AsOfContext` so a historical
evaluation cannot see data published after its cutoff — enforcement lives here, not in a
prompt.
"""

from __future__ import annotations

import abc
from datetime import date
from typing import Any

from finagent_core.cutoff import AsOfContext
from finagent_core.data.schemas import (
    CompanyProfile,
    DividendEvent,
    FinancialStatement,
    MarketCapPoint,
    Periodicity,
    PriceBar,
    ProviderCapability,
    SecFiling,
    TranscriptSegment,
)
from finagent_core.errors import ProviderUnavailableError
from finagent_core.models.base import ProviderStatus


class FinancialDataProvider(abc.ABC):
    key: str = "abstract"
    display_name: str = "Abstract data provider"
    capabilities: tuple[ProviderCapability, ...] = ()
    is_demo: bool = False
    requires_credentials: bool = True
    docs_url: str | None = None

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 30.0
    ) -> None:
        self._api_key = api_key or None
        self._base_url = base_url
        self._timeout = timeout

    # ------------------------------------------------------------------ metadata

    def status(self) -> ProviderStatus:
        if self.is_demo:
            return ProviderStatus.MOCK
        if self.requires_credentials and not self._api_key:
            return ProviderStatus.UNAVAILABLE
        return ProviderStatus.AVAILABLE

    @property
    def available(self) -> bool:
        return self.status() in (ProviderStatus.AVAILABLE, ProviderStatus.MOCK)

    def supports(self, capability: ProviderCapability) -> bool:
        return capability in self.capabilities

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "status": self.status().value,
            "is_demo": self.is_demo,
            "capabilities": [capability.value for capability in self.capabilities],
            "requires_credentials": self.requires_credentials,
            "docs_url": self.docs_url,
        }

    def _require(self, capability: ProviderCapability) -> None:
        if not self.available:
            raise ProviderUnavailableError(
                f"{self.key} is not configured",
                details={"provider": self.key, "capability": capability.value},
            )
        if not self.supports(capability):
            raise ProviderUnavailableError(
                f"{self.key} does not support {capability.value}",
                details={"provider": self.key, "capability": capability.value},
            )

    # ------------------------------------------------------------------- queries
    # Defaults raise PROVIDER_UNAVAILABLE so partial providers are safe.

    def get_company_profile(self, ticker: str, *, as_of: AsOfContext | None = None) -> CompanyProfile:
        self._require(ProviderCapability.COMPANY_PROFILE)
        raise ProviderUnavailableError(f"{self.key}.get_company_profile not implemented")

    def get_income_statement(
        self,
        ticker: str,
        *,
        periodicity: Periodicity = Periodicity.ANNUAL,
        limit: int = 5,
        as_of: AsOfContext | None = None,
    ) -> list[FinancialStatement]:
        self._require(ProviderCapability.INCOME_STATEMENT)
        raise ProviderUnavailableError(f"{self.key}.get_income_statement not implemented")

    def get_balance_sheet(
        self,
        ticker: str,
        *,
        periodicity: Periodicity = Periodicity.ANNUAL,
        limit: int = 5,
        as_of: AsOfContext | None = None,
    ) -> list[FinancialStatement]:
        self._require(ProviderCapability.BALANCE_SHEET)
        raise ProviderUnavailableError(f"{self.key}.get_balance_sheet not implemented")

    def get_cash_flow(
        self,
        ticker: str,
        *,
        periodicity: Periodicity = Periodicity.ANNUAL,
        limit: int = 5,
        as_of: AsOfContext | None = None,
    ) -> list[FinancialStatement]:
        self._require(ProviderCapability.CASH_FLOW)
        raise ProviderUnavailableError(f"{self.key}.get_cash_flow not implemented")

    def get_prices(
        self, symbol: str, *, start: date, end: date, as_of: AsOfContext | None = None
    ) -> list[PriceBar]:
        self._require(ProviderCapability.PRICES)
        raise ProviderUnavailableError(f"{self.key}.get_prices not implemented")

    def get_market_cap(self, symbol: str, *, as_of: AsOfContext | None = None) -> MarketCapPoint:
        self._require(ProviderCapability.MARKET_CAP)
        raise ProviderUnavailableError(f"{self.key}.get_market_cap not implemented")

    def get_dividends(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        as_of: AsOfContext | None = None,
    ) -> list[DividendEvent]:
        self._require(ProviderCapability.DIVIDENDS)
        raise ProviderUnavailableError(f"{self.key}.get_dividends not implemented")

    def get_sec_filings(
        self,
        ticker: str,
        *,
        form_types: tuple[str, ...] = ("10-K", "10-Q"),
        limit: int = 10,
        as_of: AsOfContext | None = None,
    ) -> list[SecFiling]:
        self._require(ProviderCapability.SEC_FILINGS)
        raise ProviderUnavailableError(f"{self.key}.get_sec_filings not implemented")

    def get_transcripts(
        self, ticker: str, *, limit: int = 4, as_of: AsOfContext | None = None
    ) -> list[TranscriptSegment]:
        self._require(ProviderCapability.TRANSCRIPTS)
        raise ProviderUnavailableError(f"{self.key}.get_transcripts not implemented")

    # ------------------------------------------------------------------- helpers

    @staticmethod
    def _enforce_cutoff(records: list[Any], as_of: AsOfContext | None, *, subject: str) -> list[Any]:
        """Drop records the caller may not see; raise when a specific one is demanded."""
        if as_of is None or not as_of.is_historical:
            return records
        visible = [
            record for record in records if as_of.allows(getattr(record, "publication_timestamp", None))
        ]
        if not visible and records:
            as_of.check(getattr(records[0], "publication_timestamp", None), subject=subject)
        return visible
