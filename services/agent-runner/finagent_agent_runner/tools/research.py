"""Evidence-gathering tools: workspace document search and SEC filing search."""

from __future__ import annotations

from typing import Any

from finagent_agent_runner.context import ToolContext
from finagent_agent_runner.tools.base import Tool, ToolPermission, ToolResult
from finagent_core.data.schemas import ProviderCapability
from finagent_core.errors import ProviderUnavailableError, ToolFailedError
from finagent_core.schemas.research import EvidenceItem

MAX_EXCERPT_CHARS = 1800


class DocumentSearchTool(Tool):
    name = "DOCUMENT_SEARCH"
    description = (
        "Search the workspace's indexed documents (filings, memos, uploaded research) and return "
        "the most relevant passages with document name and page number. Every passage carries a "
        "chunk id that must be used when citing it."
    )
    required_permissions = (ToolPermission.READ_DOCUMENTS,)
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural-language search query."},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 6},
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional subset of document ids to search.",
            },
        },
        "required": ["query"],
    }

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        if context.retriever is None:
            raise ToolFailedError(
                "document search is unavailable: no document index is attached to this run"
            )
        items = context.retriever.search(
            str(arguments["query"]),
            top_k=int(arguments.get("top_k") or 6),
            as_of=context.as_of,
            document_ids=arguments.get("document_ids") or context.document_ids or None,
        )
        context.record_evidence(items)

        warnings: list[str] = []
        if not items:
            warnings.append(
                "No admissible passages were found. Either nothing relevant is indexed, or "
                "everything relevant was published after the information cutoff."
            )
        if any(item.is_demo for item in items):
            warnings.append("Some passages come from clearly labelled DEMO documents.")

        return ToolResult(
            payload={
                "query": arguments["query"],
                "count": len(items),
                "information_cutoff": context.as_of.describe(),
                "results": [
                    {
                        "chunk_id": item.chunk_id,
                        "document_id": item.document_id,
                        "document_name": item.document_name,
                        "page_number": item.page_number,
                        "similarity": round(item.similarity, 4),
                        "publication_timestamp": (
                            item.publication_timestamp.isoformat()
                            if item.publication_timestamp
                            else None
                        ),
                        "is_demo": item.is_demo,
                        "text": item.text[:MAX_EXCERPT_CHARS],
                    }
                    for item in items
                ],
                "citation_instructions": (
                    "Cite a passage as [Source: <document_name>, page <page_number> | chunk:<chunk_id>]."
                ),
            },
            evidence_count=len(items),
            warnings=warnings,
        )


class SecSearchTool(Tool):
    name = "SEC_SEARCH"
    description = (
        "List SEC filings for an issuer (form type, filing date, period, URL) from the configured "
        "filings provider, restricted to filings published on or before the information cutoff."
    )
    required_permissions = (ToolPermission.READ_FILINGS,)
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string"},
            "form_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "e.g. ['10-K','10-Q','8-K']. Empty means all forms.",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
            "include_text_excerpt": {"type": "boolean", "default": True},
        },
        "required": ["ticker"],
    }

    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        if context.data_registry is None:
            raise ProviderUnavailableError("no filings provider is configured for this workspace")
        provider = context.data_registry.resolve(
            ProviderCapability.SEC_FILINGS,
            preferred=context.preferred_data_providers,
            allow_demo=context.allow_demo_data,
        )
        filings = provider.get_sec_filings(
            str(arguments["ticker"]),
            form_types=tuple(arguments.get("form_types") or ()),
            limit=int(arguments.get("limit") or 10),
            as_of=context.as_of,
        )
        context.record_usage("DATA_API_CALL", 1.0, provider=provider.key, capability="sec_filings")

        include_excerpt = bool(arguments.get("include_text_excerpt", True))
        evidence: list[EvidenceItem] = []
        rows: list[dict[str, Any]] = []
        for filing in filings:
            excerpt = (filing.text or "")[:MAX_EXCERPT_CHARS] if include_excerpt else ""
            chunk_id = f"sec:{filing.accession_number or filing.form_type}"
            rows.append(
                {
                    "chunk_id": chunk_id,
                    "form_type": filing.form_type,
                    "filed_at": filing.filed_at.isoformat(),
                    "period_of_report": (
                        filing.period_of_report.isoformat() if filing.period_of_report else None
                    ),
                    "title": filing.title,
                    "url": filing.url,
                    "source": filing.source,
                    "is_demo": filing.is_demo,
                    "text_excerpt": excerpt,
                }
            )
            if excerpt:
                evidence.append(
                    EvidenceItem(
                        chunk_id=chunk_id,
                        document_name=filing.title or f"{filing.ticker} {filing.form_type}",
                        text=excerpt,
                        publication_timestamp=filing.publication_timestamp,
                        source=filing.source,
                        is_demo=filing.is_demo,
                    )
                )
        context.record_evidence(evidence)

        return ToolResult(
            payload={
                "ticker": str(arguments["ticker"]).upper(),
                "provider": provider.key,
                "provider_is_demo": provider.is_demo,
                "information_cutoff": context.as_of.describe(),
                "count": len(rows),
                "filings": rows,
            },
            evidence_count=len(evidence),
            warnings=(["Filing metadata comes from the labelled DEMO provider."] if provider.is_demo else []),
        )
