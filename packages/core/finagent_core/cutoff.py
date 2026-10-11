"""Historical information lock.

The most important integrity control in the platform: when research is evaluated *as of* a
historical date, nothing published after that date may reach the agent.

Enforcement is structural rather than instructional. Retrieval, financial data providers and
the backtester all take an :class:`AsOfContext` and filter (or raise) on it. Prompting a
model to "ignore future information" is not considered enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from finagent_core.errors import ErrorCode, FinagentError


class LookAheadViolation(FinagentError):
    """Raised when future-dated information is requested under an active cutoff."""

    code = ErrorCode.LOOK_AHEAD_VIOLATION


def ensure_utc(value: datetime | date | str) -> datetime:
    """Coerce a date/datetime/ISO string into a timezone-aware UTC datetime."""
    if isinstance(value, str):
        return ensure_utc(datetime.fromisoformat(value.strip().replace("Z", "+00:00")))
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    raise TypeError(f"unsupported timestamp type: {type(value)!r}")


@dataclass(frozen=True)
class AsOfContext:
    """Information availability window for a research run.

    Attributes:
        cutoff: latest publication timestamp an agent may observe; ``None`` means live.
        label: human-readable description used in traces and UI badges.
        strict: when ``True`` a future-dated request raises :class:`LookAheadViolation`;
            when ``False`` violating records are filtered out and counted.
    """

    cutoff: datetime | None = None
    label: str = "live"
    strict: bool = True
    _filtered: list[str] = field(default_factory=list, compare=False, repr=False)

    @classmethod
    def live(cls) -> AsOfContext:
        return cls(cutoff=None, label="live")

    @classmethod
    def at(cls, value: datetime | date | str, *, strict: bool = True) -> AsOfContext:
        cutoff = ensure_utc(value)
        return cls(cutoff=cutoff, label=f"as-of {cutoff.date().isoformat()}", strict=strict)

    @property
    def is_historical(self) -> bool:
        return self.cutoff is not None

    def allows(self, published_at: datetime | date | str | None) -> bool:
        """Whether a record is visible.

        Records with an unknown publication timestamp are **not** visible in a historical
        context: unknown provenance cannot be proven to precede the cutoff.
        """
        if self.cutoff is None:
            return True
        if published_at is None:
            return False
        return ensure_utc(published_at) <= self.cutoff

    def check(self, published_at: datetime | date | str | None, *, subject: str = "record") -> bool:
        """Validate visibility. Raises in strict mode, records a filter otherwise."""
        if self.allows(published_at):
            return True
        if self.strict:
            raise LookAheadViolation(
                f"{subject} published {published_at} is after cutoff {self.cutoff}",
                details={
                    "subject": subject,
                    "published_at": str(published_at),
                    "cutoff": self.cutoff.isoformat() if self.cutoff else None,
                },
            )
        self._filtered.append(subject)
        return False

    def filter_records(
        self, records: list[dict[str, Any]], *, timestamp_key: str = "publication_timestamp"
    ) -> list[dict[str, Any]]:
        if self.cutoff is None:
            return list(records)
        return [record for record in records if self.allows(record.get(timestamp_key))]

    @property
    def filtered_subjects(self) -> list[str]:
        return list(self._filtered)

    def describe(self) -> dict[str, Any]:
        return {
            "cutoff": self.cutoff.isoformat() if self.cutoff else None,
            "label": self.label,
            "strict": self.strict,
            "is_historical": self.is_historical,
        }
