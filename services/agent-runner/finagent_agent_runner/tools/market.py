"""Market data and financial statement tools."""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Any

from finagent_core.data.schemas import Periodicity, ProviderCapability
from finagent_core.errors import ProviderUnavailableError, ValidationFailedError
from finagent_core.numeric import safe_div

from finagent_agent_runner.context import ToolContext
from finagent_agent_runner.tools.base import Tool, ToolPermission, ToolResult

MAX_BARS_RETURNED = 30


def parse_date(value: Any, fallback: date) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError as exc:
            raise ValidationFailedError(f"invalid date: {value}") from exc
    return fallback


class MarketDataTool(Tool):
    name = "MARKET_DATA"
    description = (
        "Retrieve price history, return statistics, market capitalisation or dividends for a "
        "symbol. Returns summary statistics plus the most recent bars, never the full series, so "
        "the agent reasons on aggregates rather than raw noise."
    )
    required_permissions = (ToolPermission.READ_MARKET_DATA,)
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "metric": {
                "type": "string",
                "enum": ["prices", "returns", "market_cap", "dividends"],
                "default": "returns",
            },
            "start_date": {"type": "string", "description": "ISO date. Defaults to one year back."},
            "end_date": {"type": "string", "description": "ISO date. Defaults to the cutoff or today."},
        },
        "required": ["symbol"],
    }

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        if context.data_registry is None:
            raise ProviderUnavailableError("no market data provider is configured")
        symbol = str(arguments["symbol"]).upper()
        metric = str(arguments.get("metric") or "returns")

        capability = {
            "prices": ProviderCapability.PRICES,
            "returns": ProviderCapability.PRICES,
            "market_cap": ProviderCapability.MARKET_CAP,
            "dividends": ProviderCapability.DIVIDENDS,
        }[metric]
        provider = context.data_registry.resolve(
            capability, preferred=context.preferred_data_providers, allow_demo=context.allow_demo_data
        )
        cutoff_date = context.as_of.cutoff.date() if context.as_of.cutoff else date.today()
        end = min(parse_date(arguments.get("end_date"), cutoff_date), cutoff_date)
        start = parse_date(arguments.get("start_date"), end - timedelta(days=365))
        context.record_usage("DATA_API_CALL", 1.0, provider=provider.key, capability=capability.value)

        warnings = ["Market data comes from the labelled DEMO provider."] if provider.is_demo else []

        if metric == "market_cap":
            point = provider.get_market_cap(symbol, as_of=context.as_of)
            return ToolResult(
                payload={
                    "symbol": symbol,
                    "provider": provider.key,
                    "as_of_date": point.as_of_date.isoformat(),
                    "market_cap": round(point.market_cap, 2),
                    "shares_outstanding": point.shares_outstanding,
                    "is_demo": point.is_demo,
                },
                warnings=warnings,
            )

        if metric == "dividends":
            events = provider.get_dividends(symbol, start=start, end=end, as_of=context.as_of)
            return ToolResult(
                payload={
                    "symbol": symbol,
                    "provider": provider.key,
                    "count": len(events),
                    "dividends": [
                        {
                            "ex_date": event.ex_date.isoformat(),
                            "amount_per_share": event.amount_per_share,
                            "frequency": event.frequency,
                            "is_demo": event.is_demo,
                        }
                        for event in events
                    ],
                },
                warnings=warnings,
            )

        bars = provider.get_prices(symbol, start=start, end=end, as_of=context.as_of)
        if not bars:
            return ToolResult(
                payload={
                    "symbol": symbol,
                    "provider": provider.key,
                    "count": 0,
                    "note": "No price bars are admissible for this window under the information cutoff.",
                    "information_cutoff": context.as_of.describe(),
                },
                warnings=warnings + ["No admissible price data in the requested window."],
            )

        closes = [bar.adj_close for bar in bars]
        daily_returns = [
            closes[index] / closes[index - 1] - 1.0
            for index in range(1, len(closes))
            if closes[index - 1]
        ]
        volatility = (
            statistics.stdev(daily_returns) * (252**0.5) * 100.0 if len(daily_returns) > 1 else 0.0
        )
        payload: dict[str, Any] = {
            "symbol": symbol,
            "provider": provider.key,
            "is_demo": bars[0].is_demo,
            "information_cutoff": context.as_of.describe(),
            "summary": {
                "first_date": bars[0].bar_date.isoformat(),
                "last_date": bars[-1].bar_date.isoformat(),
                "first_close": round(closes[0], 4),
                "last_close": round(closes[-1], 4),
                "total_return_pct": round((closes[-1] / closes[0] - 1.0) * 100.0, 4) if closes[0] else None,
                "annualised_volatility_pct": round(volatility, 4),
                "max_close": round(max(closes), 4),
                "min_close": round(min(closes), 4),
                "mean_volume": round(statistics.fmean(bar.volume for bar in bars), 1),
                "bar_count": len(bars),
            },
        }
        if metric == "prices":
            payload["recent_bars"] = [
                {
                    "date": bar.bar_date.isoformat(),
                    "close": round(bar.close, 4),
                    "adj_close": round(bar.adj_close, 4),
                    "volume": bar.volume,
                }
                for bar in bars[-MAX_BARS_RETURNED:]
            ]
        return ToolResult(payload=payload, warnings=warnings)


class FinancialStatementsTool(Tool):
    name = "FINANCIAL_STATEMENTS"
    description = (
        "Retrieve as-reported income statement, balance sheet or cash flow figures for an issuer, "
        "with the filing publication timestamp for each period. Values are in base currency units. "
        "Only periods published on or before the information cutoff are returned."
    )
    required_permissions = (ToolPermission.READ_MARKET_DATA,)
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string"},
            "statement": {
                "type": "string",
                "enum": ["income_statement", "balance_sheet", "cash_flow"],
                "default": "income_statement",
            },
            "periodicity": {"type": "string", "enum": ["annual", "quarterly"], "default": "annual"},
            "periods": {"type": "integer", "minimum": 1, "maximum": 12, "default": 4},
        },
        "required": ["ticker"],
    }

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        if context.data_registry is None:
            raise ProviderUnavailableError("no fundamentals provider is configured")
        ticker = str(arguments["ticker"]).upper()
        statement = str(arguments.get("statement") or "income_statement")
        periodicity = Periodicity(str(arguments.get("periodicity") or "annual"))

        capability = {
            "income_statement": ProviderCapability.INCOME_STATEMENT,
            "balance_sheet": ProviderCapability.BALANCE_SHEET,
            "cash_flow": ProviderCapability.CASH_FLOW,
        }[statement]
        provider = context.data_registry.resolve(
            capability, preferred=context.preferred_data_providers, allow_demo=context.allow_demo_data
        )
        method = {
            "income_statement": provider.get_income_statement,
            "balance_sheet": provider.get_balance_sheet,
            "cash_flow": provider.get_cash_flow,
        }[statement]
        statements = method(
            ticker, periodicity=periodicity, limit=int(arguments.get("periods") or 4), as_of=context.as_of
        )
        context.record_usage("DATA_API_CALL", 1.0, provider=provider.key, capability=capability.value)

        periods: list[dict[str, Any]] = []
        for item in statements:
            values = {key: item.value(key) for key in item.values}
            revenue = values.get("revenue")
            derived: dict[str, float] = {}
            if revenue:
                for key, label in (
                    ("gross_profit", "gross_margin_pct"),
                    ("operating_income", "operating_margin_pct"),
                    ("net_income", "net_margin_pct"),
                ):
                    if values.get(key) is not None:
                        derived[label] = round(safe_div(values[key], revenue) * 100.0, 4)
            periods.append(
                {
                    "period_label": item.period_label,
                    "period_end": item.period_end.isoformat(),
                    "fiscal_year": item.fiscal_year,
                    "fiscal_quarter": item.fiscal_quarter,
                    "currency": item.currency,
                    "publication_timestamp": (
                        item.publication_timestamp.isoformat() if item.publication_timestamp else None
                    ),
                    "filing_type": item.filing_type,
                    "is_demo": item.is_demo,
                    **{key: value for key, value in values.items() if value is not None},
                    "derived": derived,
                }
            )

        return ToolResult(
            payload={
                "ticker": ticker,
                "statement": statement,
                "periodicity": periodicity.value,
                "provider": provider.key,
                "unit": "base currency units (not millions)",
                "information_cutoff": context.as_of.describe(),
                "count": len(periods),
                "periods": periods,
            },
            warnings=(["Fundamentals come from the labelled DEMO provider."] if provider.is_demo else []),
        )
