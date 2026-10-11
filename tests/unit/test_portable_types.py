"""The portable column types.

These are the seam that lets one set of models run on SQLite in tests and on
PostgreSQL + pgvector in production. A regression here does not announce itself: the
application keeps working and quietly gets slower or subtly wrong, which is exactly what
happened when ``cosine_distance`` went missing and every similarity query degraded to a
sequential scan with only a warning in the log.

The statements are compiled rather than executed, so the PostgreSQL behaviour is asserted
without a PostgreSQL server.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite

from finagent_api.db.models import DocumentChunk


def compile_pg(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def compile_sqlite(statement) -> str:
    return str(statement.compile(dialect=sqlite.dialect()))


def render_type(column_type, dialect) -> str:
    """The DDL the dialect would emit for a column of this type."""
    return dialect.type_compiler_instance.process(column_type.load_dialect_impl(dialect)).upper()


class TestVectorColumn:
    def test_embedding_is_a_native_vector_on_postgres(self) -> None:
        from finagent_api.db.models.data import EMBEDDING_DIM
        from finagent_api.db.types import Vector

        rendered = render_type(Vector(EMBEDDING_DIM), postgresql.dialect())
        assert rendered == f"VECTOR({EMBEDDING_DIM})", (
            f"the embedding column must map to pgvector, not JSON, on PostgreSQL: {rendered}"
        )

    def test_embedding_is_json_on_sqlite(self) -> None:
        from finagent_api.db.types import Vector

        assert render_type(Vector(8), sqlite.dialect()) == "JSON"

    def test_cosine_distance_compiles_to_the_pgvector_operator(self) -> None:
        """Without this the column silently has no distance operator and retrieval falls
        back to reading the whole workspace."""
        statement = select(DocumentChunk.id).order_by(
            DocumentChunk.embedding.cosine_distance([0.1, 0.2, 0.3])
        )
        sql = compile_pg(statement)
        assert "<=>" in sql, f"cosine distance did not compile to pgvector's operator: {sql}"
        assert "AS VECTOR" in sql.upper(), "the operand must be cast to vector"

    def test_the_operand_is_bound_not_interpolated(self) -> None:
        statement = select(DocumentChunk.id).order_by(
            DocumentChunk.embedding.cosine_distance([0.125, 0.25])
        )
        sql = compile_pg(statement)
        assert "0.125" not in sql, "the vector must be a bound parameter, not inlined SQL"

    @pytest.mark.parametrize(
        ("method", "operator"),
        [("cosine_distance", "<=>"), ("l2_distance", "<->"), ("max_inner_product", "<#>")],
    )
    def test_every_distance_operator_is_available(self, method: str, operator: str) -> None:
        expression = getattr(DocumentChunk.embedding, method)([0.1, 0.2])
        assert operator in compile_pg(select(DocumentChunk.id).order_by(expression))


class TestUTCDateTime:
    def test_a_naive_value_is_stored_as_utc(self) -> None:
        from finagent_api.db.types import UTCDateTime

        column = UTCDateTime()
        naive = datetime(2023, 6, 30, 12, 0)  # noqa: DTZ001 - a naive value is the case under test
        stored = column.process_bind_param(naive, sqlite.dialect())
        assert stored.tzinfo is UTC

    def test_an_offset_value_is_normalised_not_truncated(self) -> None:
        from finagent_api.db.types import UTCDateTime

        column = UTCDateTime()
        tokyo = datetime(2023, 6, 30, 21, 0, tzinfo=UTC) + timedelta(hours=9)
        stored = column.process_bind_param(tokyo, sqlite.dialect())
        assert stored.tzinfo is UTC
        assert stored.hour == 6, "the instant must be preserved when converting to UTC"

    def test_a_value_read_back_is_always_aware(self) -> None:
        """SQLite returns naive datetimes; comparing one against an aware ``now()`` raises,
        which is how a session-expiry check breaks silently."""
        from finagent_api.db.types import UTCDateTime

        column = UTCDateTime()
        naive = datetime(2023, 6, 30, 12, 0)  # noqa: DTZ001 - SQLite returns naive values
        loaded = column.process_result_value(naive, sqlite.dialect())
        assert loaded.tzinfo is UTC
        assert loaded < datetime.now(UTC)


class TestGuidAndJsonb:
    def test_guid_round_trips_as_a_string_on_every_dialect(self) -> None:
        import uuid

        from finagent_api.db.types import GUID

        column = GUID()
        value = uuid.uuid4()
        for dialect in (postgresql.dialect(), sqlite.dialect()):
            stored = column.process_bind_param(value, dialect)
            assert stored == str(value)
            assert column.process_result_value(stored, dialect) == str(value)

    def test_jsonb_is_used_on_postgres_and_json_elsewhere(self) -> None:
        from finagent_api.db.types import JSONB

        assert render_type(JSONB(), postgresql.dialect()) == "JSONB"
        assert render_type(JSONB(), sqlite.dialect()) == "JSON"


class TestRetrievalQuery:
    """The filters that make retrieval safe must be in the SQL, on both dialects."""

    def _statement(self, *, with_cutoff: bool):
        from finagent_api.services.retrieval import DbDocumentRetriever
        from finagent_core.cutoff import AsOfContext

        retriever = DbDocumentRetriever.__new__(DbDocumentRetriever)
        retriever.workspace_id = "ws-1"
        retriever.organization_id = "org-1"
        as_of = AsOfContext(cutoff=datetime(2023, 6, 30, tzinfo=UTC)) if with_cutoff else None
        return retriever._base_query(as_of, None)

    def test_tenancy_and_deletion_filters_are_in_the_query(self) -> None:
        sql = compile_pg(self._statement(with_cutoff=False)).lower()
        assert "document_chunks.workspace_id" in sql
        assert "document_chunks.organization_id" in sql
        assert "documents.deleted_at is null" in sql

    def test_a_cutoff_excludes_unknown_publication_dates_in_sql(self) -> None:
        sql = compile_pg(self._statement(with_cutoff=True)).lower()
        assert "publication_timestamp is not null" in sql, (
            "evidence of unknown provenance must be excluded by the query, not by the caller"
        )
        assert "publication_timestamp <=" in sql

    def test_the_same_filters_apply_on_sqlite(self) -> None:
        sql = compile_sqlite(self._statement(with_cutoff=True)).lower()
        assert "document_chunks.workspace_id" in sql
        assert "documents.deleted_at is null" in sql
        assert "publication_timestamp is not null" in sql
