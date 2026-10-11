"""Unified model interface.

Nothing in the platform depends on a specific LLM vendor. Adapters translate this interface
to a provider API; the agent runner and the LLM judge only ever see these types.
"""

from __future__ import annotations

import abc
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ProviderStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"  # no credentials configured
    ERROR = "error"  # credentials present but provider failing
    MOCK = "mock"  # deterministic local provider, not a real model


class ToolCallRequest(BaseModel):
    """A model's request to invoke a tool."""

    id: str = Field(default_factory=lambda: f"call_{uuid.uuid4().hex[:12]}")
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    role: Role
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(cls, content: str = "", tool_calls: list[ToolCallRequest] | None = None) -> ChatMessage:
        return cls(role=Role.ASSISTANT, content=content, tool_calls=tool_calls or [])

    @classmethod
    def tool(cls, tool_call_id: str, name: str, content: str) -> ChatMessage:
        return cls(role=Role.TOOL, content=content, name=name, tool_call_id=tool_call_id)


class ToolSpec(BaseModel):
    """JSON-schema description of a tool exposed to a model."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class ModelUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: ModelUsage) -> ModelUsage:
        return ModelUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


class ModelResponse(BaseModel):
    """Normalised completion result. Every field here is persisted to ``model_runs``."""

    provider: str
    model: str
    content: str = ""
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    usage: ModelUsage = Field(default_factory=ModelUsage)
    latency_ms: int = 0
    request_id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:16]}")
    finish_reason: str | None = None
    estimated_cost_usd: float = 0.0
    is_mock: bool = False

    @property
    def wants_tool_call(self) -> bool:
        return bool(self.tool_calls)


class ModelProvider(abc.ABC):
    """Base class for all model providers.

    Implementations must never log credentials and must report ``status()`` honestly when
    credentials are missing.
    """

    key: str = "abstract"
    display_name: str = "Abstract provider"
    supported_models: tuple[str, ...] = ()

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None, timeout: float = 120.0
    ) -> None:
        self._api_key = api_key or None
        self._base_url = base_url
        self._timeout = timeout

    def status(self) -> ProviderStatus:
        return ProviderStatus.AVAILABLE if self._api_key else ProviderStatus.UNAVAILABLE

    @property
    def available(self) -> bool:
        return self.status() in (ProviderStatus.AVAILABLE, ProviderStatus.MOCK)

    @property
    def is_mock(self) -> bool:
        return self.status() is ProviderStatus.MOCK

    @abc.abstractmethod
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
        """Produce one completion. Implementations must not retry silently."""

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "display_name": self.display_name,
            "status": self.status().value,
            "is_mock": self.is_mock,
            "models": list(self.supported_models),
        }
