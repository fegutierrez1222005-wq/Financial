"""Tool execution context and the ports the runner depends on.

Ports keep the engine pure: the API supplies database-backed implementations, tests supply
in-memory ones, and neither the runner nor the tools know which they got.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from finagent_backtesting.dataset import PriceDataset
from finagent_core.cutoff import AsOfContext
from finagent_core.data.registry import DataProviderRegistry
from finagent_core.schemas.research import EvidenceItem


@runtime_checkable
class DocumentRetriever(Protocol):
    """Tenant-scoped vector search over indexed documents."""

    def search(
        self,
        query: str,
        *,
        top_k: int = 6,
        as_of: AsOfContext | None = None,
        document_ids: Sequence[str] | None = None,
    ) -> list[EvidenceItem]:
        """Return the most relevant admissible chunks.

        Implementations must enforce tenancy, ``deleted_at IS NULL`` and the ``as_of``
        publication cutoff **in the query**, not in the caller.
        """


@runtime_checkable
class PriceDataProvider(Protocol):
    """Supplies a price panel for the BACKTEST and PORTFOLIO_ANALYSIS tools."""

    def load(
        self, symbols: Sequence[str], *, start: Any, end: Any, as_of: AsOfContext | None = None
    ) -> PriceDataset: ...


@dataclass
class ToolContext:
    """Everything a tool is allowed to touch during one run."""

    organization_id: str
    workspace_id: str
    run_id: str
    as_of: AsOfContext = field(default_factory=AsOfContext.live)
    allowed_tools: frozenset[str] = frozenset()
    retriever: DocumentRetriever | None = None
    data_registry: DataProviderRegistry | None = None
    price_loader: PriceDataProvider | None = None
    sandbox: Any | None = None
    document_ids: list[str] = field(default_factory=list)
    dataset_ids: list[str] = field(default_factory=list)
    preferred_data_providers: list[str] = field(default_factory=list)
    allow_demo_data: bool = True
    #: Called with every EvidenceItem a tool surfaces, so citations can be verified later.
    evidence_sink: Callable[[list[EvidenceItem]], None] | None = None
    #: Called with (kind, quantity, detail) for usage metering.
    usage_sink: Callable[[str, float, dict[str, Any]], None] | None = None
    risk_constraints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def record_evidence(self, items: list[EvidenceItem]) -> None:
        if items and self.evidence_sink is not None:
            self.evidence_sink(items)

    def record_usage(self, kind: str, quantity: float, **detail: Any) -> None:
        if self.usage_sink is not None:
            self.usage_sink(kind, quantity, detail)
