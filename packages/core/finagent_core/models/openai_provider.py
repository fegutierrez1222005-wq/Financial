"""OpenAI chat-completions adapter."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from finagent_core.errors import ModelUnavailableError, ProviderError
from finagent_core.logging import get_logger
from finagent_core.models.base import (
    ChatMessage,
    ModelProvider,
    ModelResponse,
    ModelUsage,
    Role,
    ToolCallRequest,
    ToolSpec,
)
from finagent_core.models.catalog import estimate_cost, models_for_provider

logger = get_logger(__name__)


class OpenAIProvider(ModelProvider):
    key = "openai"
    display_name = "OpenAI"

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 120.0
    ) -> None:
        super().__init__(
            api_key=api_key, base_url=base_url or "https://api.openai.com/v1", timeout=timeout
        )
        self.supported_models = tuple(info.key for info in models_for_provider("openai"))

    def _payload_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for message in messages:
            role = message.role.value if hasattr(message.role, "value") else str(message.role)
            if role == Role.TOOL.value:
                out.append(
                    {"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content}
                )
                continue
            entry: dict[str, Any] = {"role": role, "content": message.content}
            if message.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    }
                    for call in message.tool_calls
                ]
            out.append(entry)
        return out

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> ModelResponse:
        if not self._api_key:
            raise ModelUnavailableError("OPENAI_API_KEY is not configured")

        body: dict[str, Any] = {
            "model": model,
            "messages": self._payload_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
        if response_format == "json":
            body["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"openai transport failure: {exc}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code >= 400:
            logger.warning("openai_error", extra={"status": response.status_code})
            raise ProviderError(f"openai returned {response.status_code}")

        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = [
            ToolCallRequest(
                id=call.get("id", ""),
                name=(call.get("function") or {}).get("name", ""),
                arguments=_safe_json((call.get("function") or {}).get("arguments")),
            )
            for call in message.get("tool_calls") or []
        ]
        usage_data = data.get("usage") or {}
        usage = ModelUsage(
            input_tokens=int(usage_data.get("prompt_tokens", 0)),
            output_tokens=int(usage_data.get("completion_tokens", 0)),
        )
        return ModelResponse(
            provider=self.key,
            model=model,
            content=message.get("content") or "",
            tool_calls=tool_calls,
            usage=usage,
            latency_ms=latency_ms,
            request_id=data.get("id", ""),
            finish_reason=choice.get("finish_reason"),
            estimated_cost_usd=estimate_cost(model, usage.input_tokens, usage.output_tokens),
        )


def _safe_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"_raw": str(raw)}
    return parsed if isinstance(parsed, dict) else {"value": parsed}
