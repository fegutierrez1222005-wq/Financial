"""Financial data provider registry with capability-aware routing."""

from __future__ import annotations

from typing import Any

from finagent_core.data.base import FinancialDataProvider
from finagent_core.data.demo_provider import DemoDataProvider
from finagent_core.data.market_providers import AlphaVantageProvider, PolygonProvider
from finagent_core.data.schemas import ProviderCapability
from finagent_core.data.sec_edgar import SecEdgarProvider
from finagent_core.errors import ProviderUnavailableError
from finagent_core.models.base import ProviderStatus


class DataProviderRegistry:
    def __init__(self, providers: dict[str, FinancialDataProvider] | None = None) -> None:
        self._providers: dict[str, FinancialDataProvider] = providers or {}

    def register(self, provider: FinancialDataProvider) -> None:
        self._providers[provider.key] = provider

    def get(self, key: str) -> FinancialDataProvider:
        provider = self._providers.get(key)
        if provider is None:
            raise ProviderUnavailableError(f"unknown data provider: {key}")
        if not provider.available:
            raise ProviderUnavailableError(f"provider {key} is not configured", details={"provider": key})
        return provider

    def keys(self) -> list[str]:
        return sorted(self._providers)

    def all(self) -> list[FinancialDataProvider]:
        return list(self._providers.values())

    def describe(self) -> list[dict[str, Any]]:
        return [provider.describe() for provider in self._providers.values()]

    def status(self) -> dict[str, ProviderStatus]:
        return {key: provider.status() for key, provider in self._providers.items()}

    def resolve(
        self,
        capability: ProviderCapability,
        *,
        preferred: list[str] | None = None,
        allow_demo: bool = True,
    ) -> FinancialDataProvider:
        """First available provider supporting ``capability``.

        Real providers win over demo providers, so a workspace with credentials never
        silently receives synthetic data.
        """
        order = [key for key in (preferred or []) if key in self._providers]
        order += [key for key in self.keys() if key not in order]

        demo_candidate: FinancialDataProvider | None = None
        for key in order:
            provider = self._providers[key]
            if not provider.available or not provider.supports(capability):
                continue
            if provider.is_demo:
                demo_candidate = demo_candidate or provider
                continue
            return provider
        if demo_candidate is not None and allow_demo:
            return demo_candidate
        raise ProviderUnavailableError(
            f"no provider available for {capability.value}",
            details={"capability": capability.value, "configured": self.keys()},
        )


def build_default_data_registry(
    *,
    sec_user_agent: str | None = None,
    alpha_vantage_api_key: str | None = None,
    polygon_api_key: str | None = None,
    enable_demo: bool = True,
) -> DataProviderRegistry:
    registry = DataProviderRegistry()
    registry.register(SecEdgarProvider(user_agent=sec_user_agent))
    registry.register(AlphaVantageProvider(api_key=alpha_vantage_api_key))
    registry.register(PolygonProvider(api_key=polygon_api_key))
    if enable_demo:
        registry.register(DemoDataProvider())
    return registry
