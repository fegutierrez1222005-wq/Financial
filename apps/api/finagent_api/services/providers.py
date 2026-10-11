"""Provider wiring.

Registries are built once from settings. Availability is reported honestly: a provider with
no credentials is ``unavailable`` and cannot be selected, rather than silently falling back
to synthetic data.
"""

from __future__ import annotations

import functools
from typing import Any

from finagent_agent_runner.sandbox import PythonSandbox
from finagent_agent_runner.tools import build_default_tool_registry
from finagent_api.settings import Settings, get_settings
from finagent_core.data.registry import DataProviderRegistry, build_default_data_registry
from finagent_core.embeddings.base import EmbeddingProvider
from finagent_core.embeddings.registry import EmbeddingRegistry, build_default_embedding_registry
from finagent_core.errors import ModelUnavailableError
from finagent_core.models.base import ModelProvider
from finagent_core.models.catalog import MODEL_CATALOG
from finagent_core.models.registry import ModelRegistry, build_default_registry


@functools.lru_cache
def model_registry() -> ModelRegistry:
    settings = get_settings()
    return build_default_registry(
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        enable_mock=True,
    )


@functools.lru_cache
def data_registry() -> DataProviderRegistry:
    settings = get_settings()
    return build_default_data_registry(
        sec_user_agent=settings.sec_user_agent,
        alpha_vantage_api_key=settings.alpha_vantage_api_key,
        polygon_api_key=settings.polygon_api_key,
        enable_demo=settings.enable_demo_providers,
    )


@functools.lru_cache
def embedding_registry() -> EmbeddingRegistry:
    return build_default_embedding_registry(openai_api_key=get_settings().openai_api_key)


@functools.lru_cache
def tool_registry():
    return build_default_tool_registry()


def reset_provider_caches() -> None:
    """Clear cached registries. Used by tests that change credentials."""
    model_registry.cache_clear()
    data_registry.cache_clear()
    embedding_registry.cache_clear()
    tool_registry.cache_clear()


def embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    registry = embedding_registry()
    if settings.embedding_provider == "openai":
        return registry.get("openai")
    if settings.embedding_provider == "deterministic":
        return registry.get("deterministic")
    return registry.default()


def build_sandbox(settings: Settings | None = None) -> PythonSandbox:
    settings = settings or get_settings()
    return PythonSandbox(
        timeout_seconds=settings.sandbox_timeout_seconds,
        memory_mb=settings.sandbox_memory_mb,
        cpu_seconds=settings.sandbox_cpu_seconds,
    )


def resolve_model(requested: str | None, *, settings: Settings | None = None) -> str:
    """Pick a usable model key, preferring the caller's choice.

    Raises when the requested model's provider has no credentials, so a run never silently
    executes on a different model than the one recorded on the agent version.
    """
    settings = settings or get_settings()
    registry = model_registry()
    candidate = requested or settings.default_model
    if candidate:
        info = MODEL_CATALOG.get(candidate)
        if info is None:
            raise ModelUnavailableError(f"unknown model: {candidate}", details={"model": candidate})
        provider = registry.provider(info.provider)
        if provider is None or not provider.available:
            raise ModelUnavailableError(
                f"model {candidate} requires the {info.provider} provider, which is not configured",
                details={"model": candidate, "provider": info.provider},
            )
        return candidate
    return registry.fallback_model()


def judge_provider() -> tuple[ModelProvider | None, str | None]:
    """Return the judge provider and model, preferring a real model when configured."""
    settings = get_settings()
    registry = model_registry()
    if settings.judge_model:
        info = MODEL_CATALOG.get(settings.judge_model)
        if info:
            provider = registry.provider(info.provider)
            if provider is not None and provider.available:
                return provider, settings.judge_model
    for model_key in registry.available_models():
        info = MODEL_CATALOG[model_key]
        if info.provider != "mock":
            return registry.provider(info.provider), model_key
    return registry.provider("mock"), "mock-judge-v1"


def provider_overview() -> dict[str, Any]:
    """Everything the UI needs to show provider availability. Never includes secrets."""
    settings = get_settings()
    models = model_registry()
    available = models.available_models()
    return {
        "models": models.describe(),
        "available_models": [
            {
                "key": key,
                "provider": MODEL_CATALOG[key].provider,
                "display_name": MODEL_CATALOG[key].display_name,
                "context_window": MODEL_CATALOG[key].context_window,
                "input_cost_per_1k": MODEL_CATALOG[key].input_cost_per_1k,
                "output_cost_per_1k": MODEL_CATALOG[key].output_cost_per_1k,
                "is_mock": MODEL_CATALOG[key].provider == "mock",
                "notes": MODEL_CATALOG[key].notes,
            }
            for key in available
        ],
        "unavailable_models": [
            {
                "key": key,
                "provider": info.provider,
                "display_name": info.display_name,
                "reason": f"{info.provider} credentials are not configured",
            }
            for key, info in MODEL_CATALOG.items()
            if key not in available
        ],
        "data_providers": data_registry().describe(),
        "embeddings": embedding_registry().describe(),
        "credentials_configured": settings.provider_status_summary(),
        "tools": tool_registry().describe(),
        "sandbox": build_sandbox(settings).describe(),
    }
