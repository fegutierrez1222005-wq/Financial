"""Model provider registry.

Providers are resolved by key, and availability is derived from configured credentials, so
the UI can honestly show `unavailable` instead of failing at run time.
"""

from __future__ import annotations

from typing import Any

from finagent_core.errors import ModelUnavailableError
from finagent_core.models.anthropic_provider import AnthropicProvider
from finagent_core.models.base import ModelProvider, ProviderStatus
from finagent_core.models.catalog import MODEL_CATALOG
from finagent_core.models.google_provider import GoogleProvider
from finagent_core.models.mock_provider import MockModelProvider
from finagent_core.models.openai_provider import OpenAIProvider


class ModelRegistry:
    def __init__(self, providers: dict[str, ModelProvider] | None = None) -> None:
        self._providers: dict[str, ModelProvider] = providers or {}

    def register(self, provider: ModelProvider) -> None:
        self._providers[provider.key] = provider

    def provider(self, key: str) -> ModelProvider | None:
        """Raw lookup without an availability check (for status reporting)."""
        return self._providers.get(key)

    def get(self, key: str) -> ModelProvider:
        provider = self._providers.get(key)
        if provider is None:
            raise ModelUnavailableError(f"unknown model provider: {key}")
        if not provider.available:
            raise ModelUnavailableError(f"provider {key} is not configured")
        return provider

    def provider_for_model(self, model_key: str) -> ModelProvider:
        info = MODEL_CATALOG.get(model_key)
        if info is None:
            raise ModelUnavailableError(f"unknown model: {model_key}")
        return self.get(info.provider)

    def status(self) -> dict[str, ProviderStatus]:
        return {key: provider.status() for key, provider in self._providers.items()}

    def describe(self) -> list[dict[str, Any]]:
        return [provider.describe() for provider in self._providers.values()]

    def available_models(self) -> list[str]:
        return [
            model_key
            for model_key, info in MODEL_CATALOG.items()
            if (provider := self._providers.get(info.provider)) is not None and provider.available
        ]

    def fallback_model(self) -> str:
        """Best available model, preferring real providers over the mock."""
        for model_key in self.available_models():
            if MODEL_CATALOG[model_key].provider != "mock":
                return model_key
        return "mock-analyst-v1"


def build_default_registry(
    *,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
    google_api_key: str | None = None,
    enable_mock: bool = True,
) -> ModelRegistry:
    registry = ModelRegistry()
    registry.register(OpenAIProvider(api_key=openai_api_key))
    registry.register(AnthropicProvider(api_key=anthropic_api_key))
    registry.register(GoogleProvider(api_key=google_api_key))
    if enable_mock:
        registry.register(MockModelProvider())
    return registry
