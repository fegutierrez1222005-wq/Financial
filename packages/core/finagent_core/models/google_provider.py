"""Google Gemini (generative language API) adapter."""

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
from finagent_core.models.catalog import estimate_cost, estimate_tokens, models_for_provider

logger = get_logger(__name__)


class GoogleProvider(ModelProvider):
    key = "google"
    display_name = "Google"

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 120.0
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url or "https://generativelanguage.googleapis.com/v1beta",
            timeout=timeout,
        )
        self.supported_models = tuple(info.key for info in models_for_provider("google"))

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
            raise ModelUnavailableError("GOOGLE_API_KEY is not configured")

        system_instruction: list[str] = []
        contents: list[dict[str, Any]] = []
        for message in messages:
            role = message.role.value if hasattr(message.role, "value") else str(message.role)
            if role == Role.SYSTEM.value:
                system_instruction.append(message.content)
            elif role == Role.TOOL.value:
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": message.name or "tool",
                                    "response": {"content": message.content},
                                }
                            }
                        ],
                    }
                )
            elif role == Role.ASSISTANT.value:
                parts: list[dict[str, Any]] = []
                if message.content:
                    parts.append({"text": message.content})
                parts.extend(
                    {"functionCall": {"name": call.name, "args": call.arguments}}
                    for call in message.tool_calls
                )
                contents.append({"role": "model", "parts": parts or [{"text": ""}]})
            else:
                contents.append({"role": "user", "parts": [{"text": message.content}]})

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_instruction)}]}
        if tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
                        for tool in tools
                    ]
                }
            ]

        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self._base_url}/models/{model}:generateContent",
                params={"key": self._api_key},
                json=body,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"google transport failure: {exc}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code >= 400:
            logger.warning("google_error", extra={"status": response.status_code})
            raise ProviderError(f"google returned {response.status_code}")

        data = response.json()
        candidate = (data.get("candidates") or [{}])[0]
        text_parts: list[str] = []
        tool_calls: list[ToolCallRequest] = []
        for part in (candidate.get("content") or {}).get("parts") or []:
            if "text" in part:
                text_parts.append(part["text"])
            if "functionCall" in part:
                call = part["functionCall"]
                tool_calls.append(ToolCallRequest(name=call.get("name", ""), arguments=call.get("args") or {}))

        usage_data = data.get("usageMetadata") or {}
        content = "\n".join(text_parts)
        usage = ModelUsage(
            input_tokens=int(usage_data.get("promptTokenCount", 0)),
            output_tokens=int(usage_data.get("candidatesTokenCount", estimate_tokens(content))),
        )
        return ModelResponse(
            provider=self.key,
            model=model,
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=candidate.get("finishReason"),
            estimated_cost_usd=estimate_cost(model, usage.input_tokens, usage.output_tokens),
        )
