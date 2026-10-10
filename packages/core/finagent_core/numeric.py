"""Financial number parsing, normalisation and comparison.

Used by claim extraction, citation verification, numeric-accuracy evaluation and the
calculator tool. Financial text expresses the same quantity many ways (``$1.2 billion``,
``1,200.0`` under an "in millions" caption, ``(3.2)%``), so everything is normalised to a
canonical (value, unit) pair before comparison.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum


class Unit(StrEnum):
    PERCENT = "percent"
    USD = "usd"
    RATIO = "ratio"  # "2.1x"
    BPS = "bps"
    COUNT = "count"
    NUMBER = "number"


_SCALES: dict[str, float] = {
    "k": 1e3, "thousand": 1e3, "thousands": 1e3,
    "m": 1e6, "mm": 1e6, "million": 1e6, "millions": 1e6,
    "bn": 1e9, "b": 1e9, "billion": 1e9, "billions": 1e9,
    "tn": 1e12, "t": 1e12, "trillion": 1e12, "trillions": 1e12,
}

_NUMBER_RE = re.compile(
    r"""
    (?P<open_paren>\()?
    (?P<currency>[$€£])?\s*
    (?P<sign>[-+])?
    (?P<digits>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    \s*
    (?P<scale>k|mm|m|bn|b|tn|t|thousands?|millions?|billions?|trillions?)?
    \s*
    (?P<suffix>%|x|bps|basis\ points|percent|percentage\ points?)?
    (?P<close_paren>\))?
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class NumericMention:
    """A number found in text, normalised to a canonical unit."""

    raw: str
    value: float
    unit: Unit
    start: int
    end: int

    def as_dict(self) -> dict[str, object]:
        return {"raw": self.raw, "value": self.value, "unit": self.unit.value}


def extract_numbers(text: str, *, table_scale: float = 1.0) -> list[NumericMention]:
    """Extract every numeric mention from ``text``.

    ``table_scale`` multiplies bare currency figures, for text lifted from a table captioned
    "in millions" (``table_scale=1e6``).
    """
    mentions: list[NumericMention] = []
    for match in _NUMBER_RE.finditer(text or ""):
        digits = match.group("digits")
        if digits is None:
            continue
        value = float(digits.replace(",", ""))
        suffix = (match.group("suffix") or "").lower().strip()
        scale_token = (match.group("scale") or "").lower().strip()
        currency = match.group("currency")
        negative = match.group("sign") == "-" or (
            bool(match.group("open_paren")) and bool(match.group("close_paren"))
        )

        if scale_token:
            value *= _SCALES[scale_token]

        if suffix in {"%", "percent", "percentage point", "percentage points"}:
            unit = Unit.PERCENT
        elif suffix == "x":
            unit = Unit.RATIO
        elif suffix in {"bps", "basis points"}:
            unit = Unit.BPS
        elif currency:
            unit = Unit.USD
            if not scale_token:
                value *= table_scale
        else:
            unit = Unit.NUMBER

        if negative:
            value = -value

        mentions.append(
            NumericMention(
                raw=match.group(0).strip(), value=value, unit=unit, start=match.start(), end=match.end()
            )
        )
    return mentions


def parse_number(text: str) -> NumericMention | None:
    mentions = extract_numbers(text)
    return mentions[0] if mentions else None


def values_match(
    actual: float,
    expected: float,
    *,
    tolerance_pct: float = 1.0,
    absolute_tolerance: float | None = None,
) -> bool:
    """Compare two numbers with a relative (and optional absolute) tolerance."""
    if actual is None or expected is None:  # pragma: no cover - defensive
        return False
    if math.isnan(actual) or math.isnan(expected):
        return False
    if absolute_tolerance is not None and abs(actual - expected) <= absolute_tolerance:
        return True
    if expected == 0:
        return abs(actual) <= (absolute_tolerance or 1e-9)
    return abs(actual - expected) / abs(expected) * 100.0 <= tolerance_pct


def in_range(value: float, low: float | None, high: float | None) -> bool:
    if low is not None and value < low:
        return False
    if high is not None and value > high:
        return False
    return True


def comparable(a: NumericMention, b: NumericMention) -> bool:
    """Whether two mentions describe the same kind of quantity.

    ``NUMBER`` is compatible with anything because financial prose routinely drops the unit
    ("revenue grew 18" vs "18%").
    """
    if a.unit == b.unit:
        return True
    flexible = {Unit.NUMBER, Unit.COUNT}
    return a.unit in flexible or b.unit in flexible


def percent_change(new: float, old: float) -> float:
    """Percentage change from ``old`` to ``new`` (a percent, not a fraction)."""
    if old == 0:
        raise ValueError("percent_change undefined for a zero base")
    return (new - old) / abs(old) * 100.0


def cagr(begin_value: float, end_value: float, years: float) -> float:
    """Compound annual growth rate as a percent."""
    if begin_value <= 0 or years <= 0:
        raise ValueError("CAGR requires a positive starting value and horizon")
    return ((end_value / begin_value) ** (1.0 / years) - 1.0) * 100.0


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator not in (0, 0.0, None) else default


def format_value(value: float, unit: Unit | str) -> str:
    """Render a normalised value the way an analyst would write it."""
    unit = Unit(unit) if isinstance(unit, str) else unit
    if unit is Unit.PERCENT:
        return f"{value:.1f}%"
    if unit is Unit.BPS:
        return f"{value:.0f}bps"
    if unit is Unit.RATIO:
        return f"{value:.1f}x"
    if unit is Unit.USD:
        magnitude = abs(value)
        if magnitude >= 1e9:
            return f"${value / 1e9:,.2f}B"
        if magnitude >= 1e6:
            return f"${value / 1e6:,.1f}M"
        if magnitude >= 1e3:
            return f"${value / 1e3:,.1f}K"
        return f"${value:,.2f}"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"
