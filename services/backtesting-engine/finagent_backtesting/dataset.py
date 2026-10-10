"""Backtest input data container.

Price and factor data are converted once into aligned frames carrying the provenance the
validator needs: whether prices are corporate-action adjusted, whether the data is
synthetic, and when each factor observation actually became public.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd

from finagent_core.data.schemas import PriceBar


@dataclass
class PriceDataset:
    """Aligned price panel plus provenance metadata."""

    prices: pd.DataFrame  # index: date, columns: symbols, values: adjusted close
    is_demo: bool = False
    unadjusted_symbols: list[str] = field(default_factory=list)
    missing_by_symbol: dict[str, int] = field(default_factory=dict)
    first_date_by_symbol: dict[str, date] = field(default_factory=dict)
    last_date_by_symbol: dict[str, date] = field(default_factory=dict)
    sources: set[str] = field(default_factory=set)
    #: factor panel: MultiIndex (available_date, symbol) → factor columns.
    factors: pd.DataFrame | None = None
    factor_publication_lag_days: dict[str, int] = field(default_factory=dict)

    @property
    def symbols(self) -> list[str]:
        return list(self.prices.columns)

    @property
    def dates(self) -> list[date]:
        return list(self.prices.index)

    def window(self, start: date, end: date) -> PriceDataset:
        mask = (self.prices.index >= pd.Timestamp(start)) & (self.prices.index <= pd.Timestamp(end))
        factors = None
        if self.factors is not None and not self.factors.empty:
            level = self.factors.index.get_level_values(0)
            factors = self.factors[(level >= pd.Timestamp(start)) & (level <= pd.Timestamp(end))]
        return PriceDataset(
            prices=self.prices.loc[mask],
            is_demo=self.is_demo,
            unadjusted_symbols=list(self.unadjusted_symbols),
            missing_by_symbol=dict(self.missing_by_symbol),
            first_date_by_symbol=dict(self.first_date_by_symbol),
            last_date_by_symbol=dict(self.last_date_by_symbol),
            sources=set(self.sources),
            factors=factors,
            factor_publication_lag_days=dict(self.factor_publication_lag_days),
        )

    def history_for(self, as_of: pd.Timestamp, lookback: int) -> pd.DataFrame:
        """Price history strictly *before* ``as_of`` — the look-ahead firewall.

        Every strategy signal derives from this method. Because it excludes ``as_of``
        itself, a signal can never be computed from the bar it trades on.
        """
        return self.prices.loc[self.prices.index < as_of].tail(lookback)

    def factors_available_at(self, as_of: pd.Timestamp) -> pd.DataFrame:
        """Latest factor observation per symbol that was public strictly before ``as_of``."""
        if self.factors is None or self.factors.empty:
            return pd.DataFrame()
        visible = self.factors[self.factors.index.get_level_values(0) < as_of]
        if visible.empty:
            return pd.DataFrame()
        return visible.groupby(level="symbol").last()

    def fingerprint(self) -> str:
        """Content hash of the price panel — the data half of a reproducibility key."""
        values = np.nan_to_num(self.prices.to_numpy(dtype=np.float64), nan=-1.0)
        payload = (
            ",".join(self.symbols).encode()
            + b"|"
            + ",".join(str(index.date()) for index in self.prices.index).encode()
            + b"|"
            + values.round(6).tobytes()
        )
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def from_price_bars(
        cls, bars_by_symbol: dict[str, list[PriceBar]], *, factor_rows: list[dict[str, Any]] | None = None
    ) -> PriceDataset:
        series: dict[str, pd.Series] = {}
        unadjusted: list[str] = []
        first_dates: dict[str, date] = {}
        last_dates: dict[str, date] = {}
        sources: set[str] = set()
        is_demo = False

        for symbol, bars in bars_by_symbol.items():
            if not bars:
                continue
            ordered = sorted(bars, key=lambda bar: bar.bar_date)
            index = pd.to_datetime([bar.bar_date for bar in ordered])
            series[symbol] = pd.Series([bar.adj_close for bar in ordered], index=index, name=symbol)
            if any(not bar.is_adjusted for bar in ordered):
                unadjusted.append(symbol)
            first_dates[symbol] = ordered[0].bar_date
            last_dates[symbol] = ordered[-1].bar_date
            sources.update(bar.source for bar in ordered)
            is_demo = is_demo or any(bar.is_demo for bar in ordered)

        prices = pd.DataFrame(series).sort_index() if series else pd.DataFrame()
        missing = (
            {symbol: int(prices[symbol].isna().sum()) for symbol in prices.columns}
            if not prices.empty
            else {}
        )

        factors = None
        lags: dict[str, int] = {}
        if factor_rows:
            records = []
            for row in factor_rows:
                published = row.get("publication_timestamp")
                period_end = row.get("period_end")
                if published is None:
                    # Unknown provenance cannot be proven to precede the trade date.
                    continue
                available = published.date() if isinstance(published, datetime) else published
                if isinstance(period_end, date) and isinstance(available, date):
                    lags[str(row.get("symbol"))] = (available - period_end).days
                record = {
                    key: value
                    for key, value in row.items()
                    if key not in {"publication_timestamp", "period_end", "symbol", "is_demo", "source"}
                }
                record["available_date"] = pd.Timestamp(available)
                record["symbol"] = str(row.get("symbol"))
                records.append(record)
            if records:
                factors = pd.DataFrame(records).set_index(["available_date", "symbol"]).sort_index()

        return cls(
            prices=prices,
            is_demo=is_demo,
            unadjusted_symbols=unadjusted,
            missing_by_symbol=missing,
            first_date_by_symbol=first_dates,
            last_date_by_symbol=last_dates,
            sources=sources,
            factors=factors,
            factor_publication_lag_days=lags,
        )
