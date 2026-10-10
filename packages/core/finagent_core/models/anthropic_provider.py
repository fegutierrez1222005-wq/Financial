"""Anthropic messages adapter."""

from __future__ import annotations

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
_API_VERSION = "2023-06-01"


class AnthropicProvider(ModelProvider):
    key = "anthropic"
    display_name = "Anthropic"

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 120.0
    ) -> None:
        super().__init__(
            api_key=api_key, base_url=base_url or "https://api.anthropic.com/v1", timeout=timeout
        )
        self.supported_models = tuple(info.key for info in models_for_provider("anthropic"))

    def _split_messages(self, messages: list[ChatMessage]) -> tuple[str, list[dict[str, Any]]]:
        system_parts: list[str] = []
        converted: list[dict[str, Any]] = []
        for message in messages:
            role = message.role.value if hasattr(message.role, "value") else str(message.role)
            if role == Role.SYSTEM.value:
                system_parts.append(message.content)
            elif role == Role.TOOL.value:
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message.tool_call_id,
                                "content": message.content,
                            }
                        ],
                    }
                )
            elif role == Role.ASSISTANT.value and message.tool_calls:
                blocks: list[dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                blocks.extend(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                    for call in message.tool_calls
                )
                converted.append({"role": "assistant", "content": blocks})
            else:
                converted.append({"role": role, "content": [{"type": "text", "text": message.content}]})
        return "\n\n".join(part for part in system_parts if part), converted

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
            raise ModelUnavailableError("ANTHROPIC_API_KEY is not configured")

        system_prompt, converted = self._split_messages(messages)
        body: dict[str, Any] = {
            "model": model,
            "messages": converted,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            body["tools"] = [
                {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}
                for tool in tools
            ]

        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self._base_url}/messages",
                json=body,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": _API_VERSION,
                    "content-type": "application/json",
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"anthropic transport failure: {exc}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code >= 400:
            logger.warning("anthropic_error", extra={"status": response.status_code})
            raise ProviderError(f"anthropic returned {response.status_code}")

        data = response.json()
        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for block in data.get("content") or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCallRequest(
                        id=block.get("id", ""), name=block.get("name", ""), arguments=block.get("input") or {}
                    )
                )
        usage_data = data.get("usage") or {}
        usage = ModelUsage(
            input_tokens=int(usage_data.get("input_tokens", 0)),
            output_tokens=int(usage_data.get("output_tokens", 0)),
        )
        return ModelResponse(
            provider=self.key,
            model=model,
            content="\n".join(text_parts),
            tool_calls=tool_calls,
            usage=usage,
            latency_ms=latency_ms,
            request_id=data.get("id", ""),
            finish_reason=data.get("stop_reason"),
            estimated_cost_usd=estimate_cost(model, usage.input_tokens, usage.output_tokens),
        )
