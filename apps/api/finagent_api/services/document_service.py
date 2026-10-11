"""Document upload, ingestion and lifecycle."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from finagent_api.db.base import utcnow
from finagent_api.db.models import Dataset, Document, DocumentChunk
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.services.providers import embedding_provider
from finagent_api.services.usage_service import record_usage
from finagent_api.settings import get_settings
from finagent_core.errors import FinagentError, NotFoundError
from finagent_core.logging import get_logger
from finagent_core.schemas.enums import DocumentStatus, UsageKind
from finagent_ingestion import assess_rows, ingest_document

logger = get_logger(__name__)


def _storage_path(workspace_id: str, document_id: str, filename: str) -> str:
    directory = os.path.join(get_settings().storage_dir, workspace_id)
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{document_id}__{filename}")


def upload_document(
    db: DbSession,
    *,
    organization_id: str,
    workspace_id: str,
    payload: bytes,
    filename: str,
    user_id: str | None,
    publication_timestamp: datetime | None = None,
    source_label: str | None = None,
    document_type: str | None = None,
    ticker: str | None = None,
    title: str | None = None,
    is_demo: bool = False,
    persist_file: bool = True,
    request_id: str | None = None,
) -> Document:
    """Run the full ingestion pipeline and persist the document with its chunks.

    Failures are recorded on the document row with the stage that failed, so the UI can show
    *why* a file could not be indexed rather than a generic error.
    """
    settings = get_settings()
    provider = embedding_provider(settings)

    document = Document(
        organization_id=organization_id,
        workspace_id=workspace_id,
        filename=filename[:300],
        title=(title or filename)[:400],
        mime_type="application/octet-stream",
        extension=(filename.rsplit(".", 1)[-1].lower() if "." in filename else ""),
        size_bytes=len(payload),
        sha256="",
        status=DocumentStatus.VALIDATING.value,
        publication_timestamp=publication_timestamp,
        source_label=source_label or title or filename,
        document_type=document_type,
        ticker=(ticker or "").upper() or None,
        is_demo=is_demo,
        uploaded_by_user_id=user_id,
    )
    db.add(document)
    db.flush()

    try:
        result = ingest_document(
            payload,
            filename,
            embedding_provider=provider,
            publication_timestamp=publication_timestamp,
            max_bytes=settings.max_upload_bytes,
        )
    except FinagentError as error:
        document.status = DocumentStatus.FAILED.value
        document.error_code = error.code.value
        document.error_message = error.user_message
        db.flush()
        logger.warning(
            "document_ingestion_failed",
            extra={"document_id": document.id, "error_code": error.code.value},
        )
        raise

    document.mime_type = result.upload.mime_type
    document.extension = result.upload.extension
    document.sha256 = result.upload.sha256
    document.page_count = result.document.page_count
    document.chunk_count = result.chunk_count
    document.token_count = result.token_count
    document.embedding_model = result.embedding_model
    document.embedding_provider = result.embedding_provider
    document.embedding_is_mock = result.embedding_is_mock
    document.warnings = result.warnings
    document.malware_scan_status = (
        "clean" if result.upload.scan.scanned and result.upload.scan.clean else "not_scanned"
    )
    document.status = DocumentStatus.INDEXED.value

    # strict: one vector per chunk is an invariant of the ingestion result. A silent
    # mismatch would leave part of the document unretrievable with no error anywhere.
    for chunk, vector in zip(result.chunks, result.embeddings, strict=True):
        db.add(
            DocumentChunk(
                organization_id=organization_id,
                workspace_id=workspace_id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
                token_count=chunk.token_count,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                publication_timestamp=publication_timestamp,
                source_label=document.source_label,
                is_demo=is_demo,
                embedding=vector,
                embedding_model=result.embedding_model,
                metadata_json=chunk.metadata,
            )
        )

    if persist_file:
        try:
            path = _storage_path(workspace_id, document.id, result.upload.filename)
            with open(path, "wb") as handle:
                handle.write(payload)
            document.storage_uri = path
        except OSError as exc:
            logger.warning(
                "document_persist_failed",
                extra={"document_id": document.id, "detail": str(exc)[:160]},
            )
            document.warnings = [
                *document.warnings,
                "The original file could not be stored; only the extracted text is retained.",
            ]

    # Tabular uploads also become a dataset with a quality report.
    if result.document.tabular_rows:
        report = assess_rows(
            result.document.tabular_rows,
            date_column=_guess_date_column(result.document.tabular_rows[0]),
        )
        db.add(
            Dataset(
                organization_id=organization_id,
                workspace_id=workspace_id,
                name=document.title or document.filename,
                description=f"Derived from uploaded file {document.filename}",
                kind="table",
                source="upload",
                document_id=document.id,
                schema_json={"columns": report.detail.get("columns", [])},
                row_count=report.row_count,
                coverage_start=report.coverage_start,
                coverage_end=report.coverage_end,
                quality_score=report.quality_score,
                quality_report=report.model_dump(mode="json"),
                is_demo=is_demo,
                created_by_user_id=user_id,
            )
        )

    db.flush()
    record_usage(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        kind=UsageKind.DOCUMENT_PAGES,
        quantity=float(document.page_count),
        unit="pages",
        detail={"document_id": document.id, "chunks": document.chunk_count},
    )
    record_usage(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        kind=UsageKind.EMBEDDING_TOKENS,
        quantity=float(result.detail.get("embedding_tokens", 0)),
        unit="tokens",
        model=result.embedding_model,
    )
    record_audit(
        db,
        action=AuditAction.DOCUMENT_UPLOADED,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=user_id,
        resource_type="document",
        resource_id=document.id,
        request_id=request_id,
        metadata={
            "filename": document.filename,
            "pages": document.page_count,
            "chunks": document.chunk_count,
            "is_demo": is_demo,
            "publication_timestamp": (
                publication_timestamp.isoformat() if publication_timestamp else None
            ),
        },
    )
    logger.info(
        "document_indexed",
        extra={
            "document_id": document.id,
            "chunks": document.chunk_count,
            "embedding_model": result.embedding_model,
        },
    )
    return document


def _guess_date_column(row: dict[str, Any]) -> str | None:
    return next(
        (
            candidate
            for candidate in ("date", "Date", "as_of", "period_end", "timestamp")
            if candidate in row
        ),
        None,
    )


def get_document(db: DbSession, *, workspace_id: str, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id or document.deleted_at is not None:
        raise NotFoundError("document not found")
    return document


def list_documents(
    db: DbSession, *, workspace_id: str, limit: int = 100, offset: int = 0, status: str | None = None
) -> list[Document]:
    query = select(Document).where(Document.workspace_id == workspace_id, Document.deleted_at.is_(None))
    if status:
        query = query.where(Document.status == status)
    return list(
        db.scalars(query.order_by(Document.created_at.desc()).limit(min(limit, 200)).offset(offset))
    )


def delete_document(db: DbSession, *, document: Document, user_id: str | None) -> None:
    """Soft delete. Retrieval filters ``deleted_at IS NULL``, so the content is immediately
    unreachable by agents while the audit trail and past traces remain intact."""
    document.deleted_at = utcnow()
    document.status = DocumentStatus.DELETED.value
    db.flush()
    record_audit(
        db,
        action=AuditAction.DOCUMENT_DELETED,
        organization_id=document.organization_id,
        workspace_id=document.workspace_id,
        user_id=user_id,
        resource_type="document",
        resource_id=document.id,
        metadata={"filename": document.filename},
    )


def document_stats(db: DbSession, *, workspace_id: str) -> dict[str, Any]:
    total, pages, chunks = db.execute(
        select(
            func.count(Document.id),
            func.coalesce(func.sum(Document.page_count), 0),
            func.coalesce(func.sum(Document.chunk_count), 0),
        ).where(Document.workspace_id == workspace_id, Document.deleted_at.is_(None))
    ).one()
    without_timestamp = int(
        db.scalar(
            select(func.count(Document.id)).where(
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
                Document.publication_timestamp.is_(None),
            )
        )
        or 0
    )
    return {
        "documents": int(total or 0),
        "pages": int(pages or 0),
        "chunks": int(chunks or 0),
        "missing_publication_timestamp": without_timestamp,
    }
