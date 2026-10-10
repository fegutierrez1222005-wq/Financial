"""Embedding provider abstraction."""

from finagent_core.embeddings.base import (
    EMBEDDING_DIM,
    EmbeddingProvider,
    EmbeddingResult,
    cosine_similarity,
)
from finagent_core.embeddings.deterministic import DeterministicEmbeddingProvider
from finagent_core.embeddings.openai_embeddings import OpenAIEmbeddingProvider
from finagent_core.embeddings.registry import EmbeddingRegistry, build_default_embedding_registry

__all__ = [
    "EMBEDDING_DIM",
    "EmbeddingProvider",
    "EmbeddingResult",
    "cosine_similarity",
    "DeterministicEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "EmbeddingRegistry",
    "build_default_embedding_registry",
]
