"""Documents, retrieval, datasets, data-source connections and provider status."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import select

from finagent_api.db.models import DataConnector, Dataset, DataSource
from finagent_api.deps import Db, WorkspaceContext, require_permission
from finagent_api.rbac import Permission
from finagent_api.schemas import (
    DatasetResponse,
    DataSourceCreateRequest,
    DataSourceResponse,
    DocumentResponse,
    EvidenceResponse,
    Message,
    ProviderStatusResponse,
    SearchRequest,
)
from finagent_api.security.crypto import encrypt_secret, mask_secret
from finagent_api.services import document_service
from finagent_api.services.audit import AuditAction, record_audit
from finagent_api.services.providers import (
    data_registry,
    embedding_provider,
    judge_provider,
    provider_overview,
)
from finagent_api.services.retrieval import DbDocumentRetriever
from finagent_api.settings import get_settings
from finagent_core.cutoff import AsOfContext
from finagent_core.errors import FileTooLargeError, NotFoundError

router = APIRouter(tags=["data"])

ReadDocs = Annotated[WorkspaceContext, Depends(require_permission(Permission.DOCUMENT_READ))]
UploadDocs = Annotated[WorkspaceContext, Depends(require_permission(Permission.DOCUMENT_UPLOAD))]
DeleteDocs = Annotated[WorkspaceContext, Depends(require_permission(Permission.DOCUMENT_DELETE))]
ReadSources = Annotated[
    WorkspaceContext, Depends(require_permission(Permission.DATA_SOURCE_READ))
]
WriteSources = Annotated[
    WorkspaceContext, Depends(require_permission(Permission.DATA_SOURCE_WRITE))
]
ReadDatasets = Annotated[WorkspaceContext, Depends(require_permission(Permission.DATASET_READ))]


# ---------------------------------------------------------------------- documents


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a document",
)
async def upload_document(
    db: Db,
    context: UploadDocs,
    file: Annotated[UploadFile, File(description="PDF, HTML, TXT, MD, CSV or XLSX.")],
    title: Annotated[str | None, Form()] = None,
    publication_timestamp: Annotated[datetime | None, Form()] = None,
    source_label: Annotated[str | None, Form()] = None,
    document_type: Annotated[str | None, Form()] = None,
    ticker: Annotated[str | None, Form()] = None,
) -> DocumentResponse:
    """The publication timestamp is the control that makes historical research honest.

    A document without one is still indexed, but it is excluded from any run that carries
    an information cutoff, because its provenance cannot be verified.
    """
    settings = get_settings()
    payload = await file.read()
    if len(payload) > settings.max_upload_bytes:
        raise FileTooLargeError(
            "the file exceeds the upload limit",
            details={"limit_bytes": settings.max_upload_bytes, "size_bytes": len(payload)},
        )

    document = document_service.upload_document(
        db,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        payload=payload,
        filename=file.filename or "upload",
        user_id=context.user_id,
        publication_timestamp=publication_timestamp,
        source_label=source_label,
        document_type=document_type,
        ticker=ticker,
        title=title,
        request_id=context.principal.request_id,
    )
    return DocumentResponse.model_validate(document)


@router.get("/documents", response_model=list[DocumentResponse], summary="List documents")
def list_documents(
    db: Db,
    context: ReadDocs,
    document_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[DocumentResponse]:
    return [
        DocumentResponse.model_validate(document)
        for document in document_service.list_documents(
            db,
            workspace_id=context.workspace_id,
            limit=limit,
            offset=offset,
            status=document_status,
        )
    ]


@router.get("/documents/stats", summary="Corpus statistics")
def document_stats(db: Db, context: ReadDocs) -> dict[str, Any]:
    return document_service.document_stats(db, workspace_id=context.workspace_id)


@router.get("/documents/{document_id}", response_model=DocumentResponse, summary="Get a document")
def get_document(document_id: str, db: Db, context: ReadDocs) -> DocumentResponse:
    return DocumentResponse.model_validate(
        document_service.get_document(
            db, workspace_id=context.workspace_id, document_id=document_id
        )
    )


@router.delete("/documents/{document_id}", response_model=Message, summary="Delete a document")
def delete_document(document_id: str, db: Db, context: DeleteDocs) -> Message:
    """Deletion removes the document from every retrieval path immediately.

    The row is retained with ``deleted_at`` set so past runs keep their audit trail, but
    the chunks can no longer be returned as evidence.
    """
    document = document_service.get_document(
        db, workspace_id=context.workspace_id, document_id=document_id
    )
    document_service.delete_document(db, document=document, user_id=context.user_id)
    return Message(
        message="Document deleted and removed from retrieval.",
        detail={"document_id": document_id},
    )


@router.post(
    "/documents/search",
    response_model=list[EvidenceResponse],
    summary="Search the indexed corpus",
)
def search_documents(
    payload: SearchRequest, db: Db, context: ReadDocs
) -> list[EvidenceResponse]:
    retriever = DbDocumentRetriever(
        db,
        workspace_id=context.workspace_id,
        organization_id=context.organization_id,
        provider=embedding_provider(),
    )
    as_of = AsOfContext(cutoff=payload.as_of) if payload.as_of else None
    results = retriever.search(
        payload.query, top_k=payload.top_k, as_of=as_of, document_ids=payload.document_ids
    )
    return [
        EvidenceResponse(
            chunk_ref=item.chunk_id,
            document_id=item.document_id,
            document_name=item.document_name,
            page_number=item.page_number,
            text=item.text,
            similarity=item.similarity,
            publication_timestamp=item.publication_timestamp,
            source=item.source,
            is_demo=item.is_demo,
        )
        for item in results
    ]


# ------------------------------------------------------------------- data sources


@router.get("/data-sources", response_model=list[DataSourceResponse], summary="Data sources")
def list_data_sources(db: Db, context: ReadSources) -> list[DataSourceResponse]:
    rows = db.scalars(
        select(DataSource)
        .where(DataSource.workspace_id == context.workspace_id)
        .order_by(DataSource.provider_key)
    )
    return [DataSourceResponse.model_validate(row) for row in rows]


@router.post(
    "/data-sources",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a data provider",
)
def create_data_source(
    payload: DataSourceCreateRequest, db: Db, context: WriteSources
) -> DataSourceResponse:
    """The credential is encrypted at rest and is never returned by any endpoint.

    Only the last four characters are retained in clear text so an operator can recognise
    which key is installed.
    """
    descriptor = next(
        (
            entry
            for entry in data_registry().describe()
            if entry["key"] == payload.provider_key
        ),
        None,
    )
    if descriptor is None:
        raise NotFoundError("unknown data provider")

    source = db.scalar(
        select(DataSource).where(
            DataSource.workspace_id == context.workspace_id,
            DataSource.provider_key == payload.provider_key,
        )
    )
    if source is None:
        source = DataSource(
            organization_id=context.organization_id,
            workspace_id=context.workspace_id,
            provider_key=payload.provider_key,
            name=payload.name,
            kind=descriptor.get("kind", "market_data"),
            status=descriptor["status"],
            is_demo=descriptor["is_demo"],
            capabilities=descriptor["capabilities"],
            config=payload.config,
            last_checked_at=datetime.now(UTC),
        )
        db.add(source)
        db.flush()
    else:
        source.name = payload.name
        source.config = payload.config
        source.last_checked_at = datetime.now(UTC)

    if payload.credential:
        db.add(
            DataConnector(
                organization_id=context.organization_id,
                data_source_id=source.id,
                name=payload.name,
                secret_encrypted=encrypt_secret(payload.credential),
                secret_last_four=mask_secret(payload.credential)[-4:],
                created_by_user_id=context.user_id,
            )
        )

    record_audit(
        db,
        action=AuditAction.DATA_SOURCE_UPDATED,
        organization_id=context.organization_id,
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        resource_type="data_source",
        resource_id=source.id,
        metadata={"provider_key": payload.provider_key, "credential_supplied": bool(payload.credential)},
    )
    db.flush()
    return DataSourceResponse.model_validate(source)


@router.get("/datasets", response_model=list[DatasetResponse], summary="Datasets")
def list_datasets(db: Db, context: ReadDatasets) -> list[DatasetResponse]:
    rows = db.scalars(
        select(Dataset)
        .where(Dataset.workspace_id == context.workspace_id, Dataset.deleted_at.is_(None))
        .order_by(Dataset.created_at.desc())
    )
    return [DatasetResponse.model_validate(row) for row in rows]


@router.get(
    "/providers/status",
    response_model=ProviderStatusResponse,
    summary="Which providers are available (never credentials)",
)
def provider_status() -> ProviderStatusResponse:
    overview = provider_overview()
    _judge, judge_model = judge_provider()
    embeddings = embedding_provider()
    return ProviderStatusResponse(
        **overview,
        judge={
            "model": judge_model,
            "is_mock": (judge_model or "").startswith("mock"),
            "note": (
                "LLM-judge scores are weighted below deterministic and programmatic checks "
                "and never decide a result on their own."
            ),
        },
        notice=(
            "Providers reported as unavailable have no credentials configured in this "
            f"deployment. Embeddings currently use '{embeddings.key}'"
            + (" (deterministic local provider, not a trained model)." if embeddings.is_mock else ".")
        ),
    )
