"""OpenAI embeddings adapter."""

from __future__ import annotations

import time

import httpx

from finagent_core.embeddings.base import EMBEDDING_DIM, EmbeddingProvider, EmbeddingResult
from finagent_core.errors import ModelUnavailableError, ProviderError
from finagent_core.logging import get_logger

logger = get_logger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    key = "openai"
    display_name = "OpenAI embeddings"
    model = "text-embedding-3-small"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(api_key=api_key, timeout=timeout)
        self.model = model or self.model
        self.dimension = EMBEDDING_DIM
        self._base_url = base_url or "https://api.openai.com/v1"

    def embed(self, texts: list[str]) -> EmbeddingResult:
        if not self._api_key:
            raise ModelUnavailableError("OPENAI_API_KEY is not configured")
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self._base_url}/embeddings",
                json={"model": self.model, "input": texts, "dimensions": self.dimension},
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"openai embeddings transport failure: {exc}") from exc
        if response.status_code >= 400:
            logger.warning("openai_embedding_error", extra={"status": response.status_code})
            raise ProviderError(f"openai embeddings returned {response.status_code}")
        payload = response.json()
        ordered = sorted(payload.get("data", []), key=lambda item: item.get("index", 0))
        return EmbeddingResult(
            vectors=[item["embedding"] for item in ordered],
            model=self.model,
            provider=self.key,
            dimension=self.dimension,
            input_tokens=int((payload.get("usage") or {}).get("prompt_tokens", 0)),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
