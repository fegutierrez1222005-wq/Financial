"""Tenant-scoped vector retrieval with structural cutoff enforcement.

This class is the only path an agent has to workspace documents, and it applies three
non-negotiable filters *in the query*:

1. ``workspace_id`` / ``organization_id`` — cross-tenant retrieval is impossible, not
   merely unlikely.
2. ``deleted_at IS NULL`` — a deleted document cannot be retrieved (critical test #6).
3. ``publication_timestamp <= cutoff`` under a historical context, with NULL timestamps
   excluded because unknown provenance cannot be proven admissible (critical test #2).

On PostgreSQL similarity is computed by pgvector's cosine operator; on SQLite the same
candidate set is scored in NumPy. Both paths apply identical filters.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.models import Document, DocumentChunk
from finagent_api.db.session import is_postgres
from finagent_api.services.providers import embedding_provider
from finagent_core.cutoff import AsOfContext
from finagent_core.embeddings.base import EmbeddingProvider, cosine_similarity
from finagent_core.logging import get_logger
from finagent_core.schemas.research import EvidenceItem

logger = get_logger(__name__)

#: Candidates scored in Python when the database cannot rank vectors itself.
FALLBACK_CANDIDATE_LIMIT = 2_000


class DbDocumentRetriever:
    """Implements :class:`finagent_agent_runner.context.DocumentRetriever`."""

    def __init__(
        self,
        db: DbSession,
        *,
        workspace_id: str,
        organization_id: str,
        provider: EmbeddingProvider | None = None,
    ) -> None:
        self.db = db
        self.workspace_id = workspace_id
        self.organization_id = organization_id
        self.provider = provider or embedding_provider()

    def _base_query(self, as_of: AsOfContext | None, document_ids: Sequence[str] | None):
        query = (
            select(DocumentChunk, Document)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.workspace_id == self.workspace_id,
                DocumentChunk.organization_id == self.organization_id,
                Document.deleted_at.is_(None),
                Document.status == "INDEXED",
            )
        )
        if document_ids:
            query = query.where(DocumentChunk.document_id.in_(list(document_ids)))
        if as_of is not None and as_of.cutoff is not None:
            query = query.where(
                DocumentChunk.publication_timestamp.is_not(None),
                DocumentChunk.publication_timestamp <= as_of.cutoff,
            )
        return query

    def search(
        self,
        query: str,
        *,
        top_k: int = 6,
        as_of: AsOfContext | None = None,
        document_ids: Sequence[str] | None = None,
    ) -> list[EvidenceItem]:
        if not query.strip():
            return []
        embedding = self.provider.embed_one(query)
        statement = self._base_query(as_of, document_ids)

        if is_postgres():
            try:
                rows = list(
                    self.db.execute(
                        statement.order_by(DocumentChunk.embedding.cosine_distance(embedding)).limit(top_k)
                    )
                )
                return [self._to_evidence(chunk, document, similarity=None) for chunk, document in rows]
            except Exception as exc:  # noqa: BLE001 - fall back rather than fail a run
                logger.warning(
                    "pgvector_search_failed", extra={"detail": str(exc)[:200], "fallback": "numpy"}
                )

        rows = list(self.db.execute(statement.limit(FALLBACK_CANDIDATE_LIMIT)))
        if not rows:
            return []
        query_vector = np.asarray(embedding, dtype=np.float32)
        scored = [
            (cosine_similarity(query_vector, chunk.embedding), chunk, document)
            for chunk, document in rows
            if chunk.embedding
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            self._to_evidence(chunk, document, similarity=score)
            for score, chunk, document in scored[:top_k]
        ]

    def _to_evidence(
        self, chunk: DocumentChunk, document: Document, *, similarity: float | None
    ) -> EvidenceItem:
        return EvidenceItem(
            chunk_id=chunk.id,
            document_id=document.id,
            document_name=document.source_label or document.title or document.filename,
            page_number=chunk.page_number,
            text=chunk.text,
            similarity=round(float(similarity), 4) if similarity is not None else 0.0,
            publication_timestamp=chunk.publication_timestamp,
            source=document.document_type or "document",
            is_demo=bool(document.is_demo or chunk.is_demo),
        )

    def count_indexed_chunks(self, as_of: AsOfContext | None = None) -> int:
        return len(list(self.db.execute(self._base_query(as_of, None))))
