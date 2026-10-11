"""Portable column types.

PostgreSQL is the production database, but the test suite runs on SQLite so correctness
tests need no infrastructure. These decorators keep one set of models working on both:
``Vector`` becomes ``pgvector.Vector`` on PostgreSQL and JSON on SQLite (where similarity is
computed in NumPy), and ``UTCDateTime`` guarantees timezone-aware values on every dialect.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import UTC
from typing import Any

from sqlalchemy import JSON, DateTime, String, TypeDecorator
from sqlalchemy.dialects import postgresql


class GUID(TypeDecorator):
    """UUID stored as a 36-character string on every dialect."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        return None if value is None else str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        return None if value is None else str(value)


def new_uuid() -> str:
    return str(uuid.uuid4())


def _json_safe(value: Any) -> Any:
    """Replace non-finite floats with ``None``.

    ``NaN`` and ``Infinity`` are not JSON. Python's encoder emits them anyway and SQLite
    accepts the result, but PostgreSQL rejects it — so a metric like a profit factor with
    no losing trades would persist in development and fail in production. Dropping to
    ``None`` is also the honest reading: the value is undefined, not enormous.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class JSONB(TypeDecorator):
    """JSONB on PostgreSQL, JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.JSONB())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        return _json_safe(value)


def _pgvector_type(dimensions: int) -> Any | None:
    try:
        from pgvector.sqlalchemy import Vector as PgVector
    except ImportError:  # pragma: no cover - pgvector is a declared dependency
        return None
    return PgVector(dimensions)


class Vector(TypeDecorator):
    """Embedding column: ``vector(dim)`` on PostgreSQL, JSON list elsewhere."""

    impl = JSON
    cache_ok = True

    class Comparator(TypeDecorator.Comparator):
        """Exposes pgvector's distance operators through the decorator.

        A ``TypeDecorator`` does not inherit the wrapped type's ``comparator_factory``, so
        without this the column has no ``cosine_distance`` and every similarity query
        falls back to an in-process scan — correct, but a sequential read of the whole
        workspace that never touches the HNSW index.
        """

        def cosine_distance(self, other: Any) -> Any:
            return self._distance("<=>", other)

        def l2_distance(self, other: Any) -> Any:
            return self._distance("<->", other)

        def max_inner_product(self, other: Any) -> Any:
            return self._distance("<#>", other)

        def _distance(self, operator: str, other: Any) -> Any:
            from sqlalchemy import Float, cast, literal

            dimensions = getattr(self.type, "dimensions", 1536)
            target = _pgvector_type(dimensions)
            if target is None:  # pragma: no cover - pgvector is a declared dependency
                raise NotImplementedError("pgvector is required for vector distance operators")
            # pgvector parses its own text form, so the operand is bound as a parameter and
            # cast, rather than interpolated into the statement.
            rendered = "[" + ",".join(format(float(value), ".9g") for value in other) + "]"
            return self.expr.op(operator, return_type=Float())(cast(literal(rendered), target))

    comparator_factory = Comparator

    def __init__(self, dimensions: int = 1536) -> None:
        self.dimensions = dimensions
        super().__init__()

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            target = _pgvector_type(self.dimensions)
            if target is not None:
                return dialect.type_descriptor(target)
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        return None if value is None else [float(item) for item in value]

    def process_result_value(self, value: Any, dialect: Any) -> Any:
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

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if getattr(value, "tzinfo", None) is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if getattr(value, "tzinfo", None) is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
