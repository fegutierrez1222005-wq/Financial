"""Embedding provider registry.

Retrieval quality depends on using the *same* provider for indexing and querying, so chunks
record the embedding model they were produced with and the registry can return it.
"""

from __future__ import annotations

from typing import Any

from finagent_core.embeddings.base import EmbeddingProvider
from finagent_core.embeddings.deterministic import DeterministicEmbeddingProvider
from finagent_core.embeddings.openai_embeddings import OpenAIEmbeddingProvider
from finagent_core.errors import ProviderUnavailableError


class EmbeddingRegistry:
    def __init__(self, providers: dict[str, EmbeddingProvider] | None = None) -> None:
        self._providers = providers or {}

    def register(self, provider: EmbeddingProvider) -> None:
        self._providers[provider.key] = provider

    def get(self, key: str) -> EmbeddingProvider:
        provider = self._providers.get(key)
        if provider is None or not provider.available:
            raise ProviderUnavailableError(f"embedding provider unavailable: {key}")
        return provider

    def for_model(self, model: str) -> EmbeddingProvider:
        for provider in self._providers.values():
            if provider.model == model and provider.available:
                return provider
        raise ProviderUnavailableError(f"no available embedding provider for model {model}")

    def default(self) -> EmbeddingProvider:
        """Prefer a real provider; fall back to the labelled deterministic provider."""
        for provider in self._providers.values():
            if provider.available and not provider.is_mock:
                return provider
        for provider in self._providers.values():
            if provider.available:
                return provider
        raise ProviderUnavailableError("no embedding provider configured")

    def describe(self) -> list[dict[str, Any]]:
        return [provider.describe() for provider in self._providers.values()]


def build_default_embedding_registry(*, openai_api_key: str | None = None) -> EmbeddingRegistry:
    registry = EmbeddingRegistry()
    registry.register(OpenAIEmbeddingProvider(api_key=openai_api_key))
    registry.register(DeterministicEmbeddingProvider())
    return registry
