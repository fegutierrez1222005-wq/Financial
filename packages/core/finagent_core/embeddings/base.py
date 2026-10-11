"""Embedding provider interface.

The dimension is fixed platform-wide (``EMBEDDING_DIM``) because it is part of the
`document_chunks.embedding` column type. Providers that natively emit a different dimension
must project or truncate deterministically and declare it.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

import numpy as np

from finagent_core.models.base import ProviderStatus

#: Platform-wide embedding dimension (matches the pgvector column).
EMBEDDING_DIM = 1536


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    provider: str
    dimension: int
    input_tokens: int = 0
    is_mock: bool = False
    latency_ms: int = 0
    detail: dict[str, str] = field(default_factory=dict)


class EmbeddingProvider(abc.ABC):
    key: str = "abstract"
    display_name: str = "Abstract embedding provider"
    model: str = "abstract"
    dimension: int = EMBEDDING_DIM
    requires_credentials: bool = True

    def __init__(self, *, api_key: str | None = None, timeout: float = 60.0) -> None:
        self._api_key = api_key or None
        self._timeout = timeout

    def status(self) -> ProviderStatus:
        if not self.requires_credentials:
            return ProviderStatus.MOCK
        return ProviderStatus.AVAILABLE if self._api_key else ProviderStatus.UNAVAILABLE

    @property
    def available(self) -> bool:
        return self.status() in (ProviderStatus.AVAILABLE, ProviderStatus.MOCK)

    @property
    def is_mock(self) -> bool:
        return self.status() is ProviderStatus.MOCK

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Embed a batch of texts. Output order matches the input."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text]).vectors[0]

    def describe(self) -> dict[str, object]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "model": self.model,
            "dimension": self.dimension,
            "status": self.status().value,
            "is_mock": self.is_mock,
        }


def cosine_similarity(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    left = np.asarray(a, dtype=np.float32)
    right = np.asarray(b, dtype=np.float32)
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(left, right) / denominator)
