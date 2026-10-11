"""Ingestion pipeline: UPLOAD → VALIDATE → EXTRACT → CHUNK → EMBED → (persist by caller).

The pipeline is pure: bytes in, :class:`IngestionResult` out. Persistence, tenancy and
indexing are the API's responsibility, which keeps this testable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from finagent_core.embeddings.base import EmbeddingProvider
from finagent_core.errors import FinagentError
from finagent_core.logging import get_logger
from finagent_ingestion.chunking import Chunk, chunk_document
from finagent_ingestion.extraction import ExtractedDocument, extract_document
from finagent_ingestion.validation import MalwareScanner, ValidatedUpload, validate_upload

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    upload: ValidatedUpload
    document: ExtractedDocument
    chunks: list[Chunk]
    embeddings: list[list[float]]
    embedding_model: str
    embedding_provider: str
    embedding_is_mock: bool
    warnings: list[str] = field(default_factory=list)
    stage: str = "INDEXED"
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def token_count(self) -> int:
        return sum(chunk.token_count for chunk in self.chunks)


def ingest_document(
    payload: bytes,
    filename: str,
    *,
    embedding_provider: EmbeddingProvider,
    publication_timestamp: datetime | None = None,
    scanner: MalwareScanner | None = None,
    max_bytes: int | None = None,
    chunk_chars: int = 1200,
    overlap_chars: int = 150,
    embed_batch_size: int = 64,
) -> IngestionResult:
    """Run the full pipeline for one file.

    Raises a :class:`FinagentError` subclass with a user-safe code on any stage failure; the
    caller records the failing stage on the document row.
    """
    warnings: list[str] = []

    upload = validate_upload(
        payload, filename, scanner=scanner, **({"max_bytes": max_bytes} if max_bytes else {})
    )
    if not upload.scan.scanned:
        warnings.append(upload.scan.detail)

    document = extract_document(payload, upload.extension)
    if document.pagination == "synthetic":
        warnings.append(
            "This format has no intrinsic pages; citation page numbers are synthetic section "
            "numbers assigned during extraction."
        )
    if publication_timestamp is None:
        warnings.append(
            "No publication timestamp was supplied, so this document is excluded from historical "
            "(as-of) research runs."
        )

    chunks = chunk_document(
        document,
        chunk_chars=chunk_chars,
        overlap_chars=overlap_chars,
        publication_timestamp=publication_timestamp,
    )
    if not chunks:
        raise FinagentError("document produced no chunks")

    vectors: list[list[float]] = []
    total_embedding_tokens = 0
    for start in range(0, len(chunks), embed_batch_size):
        batch = chunks[start : start + embed_batch_size]
        result = embedding_provider.embed([chunk.text for chunk in batch])
        vectors.extend(result.vectors)
        total_embedding_tokens += result.input_tokens

    if embedding_provider.is_mock:
        warnings.append(
            "Indexed with the deterministic offline embedding provider (lexical, not semantic). "
            "Configure an embedding provider for production retrieval quality."
        )

    logger.info(
        "document_ingested",
        extra={
            "document_filename": upload.filename,
            "pages": document.page_count,
            "chunks": len(chunks),
            "embedding_model": embedding_provider.model,
        },
    )
    return IngestionResult(
        upload=upload,
        document=document,
        chunks=chunks,
        embeddings=vectors,
        embedding_model=embedding_provider.model,
        embedding_provider=embedding_provider.key,
        embedding_is_mock=embedding_provider.is_mock,
        warnings=warnings,
        detail={
            "embedding_tokens": total_embedding_tokens,
            "extractor": document.metadata.get("extractor"),
            "tabular_rows": len(document.tabular_rows),
        },
    )
