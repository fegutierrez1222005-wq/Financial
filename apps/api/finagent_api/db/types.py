"""Portable column types.

PostgreSQL is the production database, but the test suite runs on SQLite so correctness
tests need no infrastructure. These decorators keep one set of models working on both:
``Vector`` becomes ``pgvector.Vector`` on PostgreSQL and JSON on SQLite (where similarity is
computed in NumPy), and ``UTCDateTime`` guarantees timezone-aware values on every dialect.
"""

from __future__ import annotations

import json
import uuid
from datetime import timezone
from typing import Any

from sqlalchemy import JSON, DateTime, String, TypeDecorator
from sqlalchemy.dialects import postgresql


class GUID(TypeDecorator):
    """UUID stored as a 36-character string on every dialect."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:  # noqa: ARG002
        return None if value is None else str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:  # noqa: ARG002
        return None if value is None else str(value)


def new_uuid() -> str:
    return str(uuid.uuid4())


class JSONB(TypeDecorator):
    """JSONB on PostgreSQL, JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.JSONB())
        return dialect.type_descriptor(JSON())


class Vector(TypeDecorator):
    """Embedding column: ``vector(dim)`` on PostgreSQL, JSON list elsewhere."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions
        super().__init__()

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector as PgVector
            except ImportError:  # pragma: no cover - pgvector is a declared dependency
                return dialect.type_descriptor(JSON())
            return dialect.type_descriptor(PgVector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:  # noqa: ARG002
        return None if value is None else [float(item) for item in value]

    def process_result_value(self, value: Any, dialect: Any) -> Any:  # noqa: ARG002
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return list(value)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetime on every dialect.

    PostgreSQL preserves the offset; SQLite does not, so values are normalised to UTC on the
    way in and re-tagged on the way out. Without this, comparing a stored timestamp with
    ``datetime.now(timezone.utc)`` raises on SQLite — exactly the kind of bug that silently
    breaks a session-expiry check.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:  # noqa: ARG002
        if value is None:
            return None
        if getattr(value, "tzinfo", None) is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: Any, dialect: Any) -> Any:  # noqa: ARG002
        if value is None:
            return None
        if getattr(value, "tzinfo", None) is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
