"""Dataset quality assessment.

Research built on a stale or gappy dataset is not trustworthy, so every dataset gets a
quality report and the UI surfaces warnings before a run uses it. The penalty weights are
platform-defined heuristics, documented in ``docs/DATA_PROVIDERS.md``.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

from finagent_core.data.schemas import DataQualityReport


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def assess_rows(
    rows: list[dict[str, Any]],
    *,
    date_column: str | None = None,
    key_columns: tuple[str, ...] = (),
    required_columns: tuple[str, ...] = (),
    stale_after_days: int = 90,
    now: datetime | None = None,
) -> DataQualityReport:
    """Score a tabular dataset 0–100 and list explicit warnings."""
    now = now or datetime.now(UTC)
    warnings: list[str] = []
    if not rows:
        return DataQualityReport(row_count=0, quality_score=0.0, warnings=["Dataset contains no rows."])

    columns = sorted({key for row in rows for key in row})
    missing_required = [column for column in required_columns if column not in columns]
    if missing_required:
        warnings.append(f"Missing required columns: {', '.join(missing_required)}.")

    total_cells = sum(len(row) for row in rows)
    missing_values = sum(
        1 for row in rows for value in row.values() if value in (None, "", "NaN", "nan", "null")
    )

    if key_columns:
        counter = Counter(tuple(str(row.get(column, "")) for column in key_columns) for row in rows)
    else:
        counter = Counter(tuple(sorted(row.items(), key=lambda item: item[0])) for row in rows)
    duplicates = sum(count - 1 for count in counter.values() if count > 1)

    coverage_start: date | None = None
    coverage_end: date | None = None
    unparseable = 0
    if date_column:
        parsed: list[date] = []
        for row in rows:
            value = _parse_date(row.get(date_column))
            if value is None:
                unparseable += 1
            else:
                parsed.append(value)
        if parsed:
            coverage_start, coverage_end = min(parsed), max(parsed)

    stale_days: int | None = None
    if coverage_end:
        stale_days = (now.date() - coverage_end).days
        if stale_days > stale_after_days:
            warnings.append(
                f"Most recent record is {stale_days} days old (stale threshold {stale_after_days} days)."
            )

    missing_ratio = missing_values / total_cells if total_cells else 0.0
    duplicate_ratio = duplicates / len(rows)
    unparseable_ratio = unparseable / len(rows) if date_column else 0.0

    if missing_ratio:
        warnings.append(f"{missing_values} missing values ({missing_ratio:.1%} of cells).")
    if duplicates:
        warnings.append(f"{duplicates} duplicate rows detected.")
    if unparseable:
        warnings.append(f"{unparseable} rows have an unparseable '{date_column}' value.")

    score = 100.0
    score -= min(40.0, missing_ratio * 200.0)
    score -= min(25.0, duplicate_ratio * 150.0)
    score -= min(20.0, unparseable_ratio * 200.0)
    score -= 15.0 if missing_required else 0.0
    if stale_days is not None and stale_days > stale_after_days:
        score -= min(15.0, (stale_days - stale_after_days) / 30.0 * 5.0)

    return DataQualityReport(
        row_count=len(rows),
        missing_values=missing_values,
        duplicate_rows=duplicates,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        stale_days=stale_days,
        inconsistent_timestamps=unparseable,
        quality_score=max(0.0, round(score, 1)),
        warnings=warnings,
        detail={"columns": columns, "total_cells": total_cells},
    )
