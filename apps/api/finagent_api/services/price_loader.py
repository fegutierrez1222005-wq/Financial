"""Price panel loader for backtests and the portfolio tool.

Resolves prices from configured providers honouring the run's information cutoff. Symbols
with no admissible data are omitted and reported by the backtest validator rather than
silently filled.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy.orm import Session as DbSession

from finagent_api.services.providers import data_registry
from finagent_backtesting.dataset import PriceDataset
from finagent_core.cutoff import AsOfContext
from finagent_core.data.demo_dataset import DEMO_UNIVERSE, demo_fundamental_factors
from finagent_core.data.schemas import PriceBar, ProviderCapability
from finagent_core.errors import ProviderUnavailableError
from finagent_core.logging import get_logger

logger = get_logger(__name__)


class DbPriceLoader:
    """Implements :class:`finagent_agent_runner.context.PriceDataProvider`."""

    def __init__(
        self,
        db: DbSession | None = None,
        *,
        workspace_id: str | None = None,
        preferred_providers: list[str] | None = None,
        allow_demo: bool = True,
    ) -> None:
        self.db = db
        self.workspace_id = workspace_id
        self.preferred_providers = preferred_providers or []
        self.allow_demo = allow_demo

    def load(
        self,
        symbols: Sequence[str],
        *,
        start: date,
        end: date,
        as_of: AsOfContext | None = None,
    ) -> PriceDataset:
        provider = data_registry().resolve(
            ProviderCapability.PRICES,
            preferred=self.preferred_providers,
            allow_demo=self.allow_demo,
        )
        bars_by_symbol: dict[str, list[PriceBar]] = {}
        missing: list[str] = []
        for symbol in symbols:
            upper = str(symbol).upper()
            try:
                bars = provider.get_prices(upper, start=start, end=end, as_of=as_of)
            except ProviderUnavailableError:
                raise
            except Exception as exc:  # noqa: BLE001 - one bad symbol must not fail the panel
                logger.warning(
                    "price_load_failed",
                    extra={"symbol": upper, "provider": provider.key, "detail": str(exc)[:160]},
                )
                missing.append(upper)
                continue
            if bars:
                bars_by_symbol[upper] = bars
            else:
                missing.append(upper)

        factor_rows = (
            demo_fundamental_factors()
            if provider.is_demo and any(symbol in DEMO_UNIVERSE for symbol in bars_by_symbol)
            else None
        )
        if missing:
            logger.info("price_symbols_unavailable", extra={"symbols": missing, "provider": provider.key})
        return PriceDataset.from_price_bars(bars_by_symbol, factor_rows=factor_rows)

    def provider_key(self) -> str:
        return data_registry().resolve(
            ProviderCapability.PRICES,
            preferred=self.preferred_providers,
            allow_demo=self.allow_demo,
        ).key
