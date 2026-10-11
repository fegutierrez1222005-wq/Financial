"""Controlled tool registry.

Agents never get ambient access to the system. Every capability is a registered tool with a
declared schema and required permissions, and the registry refuses to execute anything that
is not in the agent version's allow-list — even if the model asks for it by name.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from finagent_agent_runner.context import ToolContext
from finagent_core.errors import (
    FinagentError,
    ToolFailedError,
    ToolNotPermittedError,
    ValidationFailedError,
)
from finagent_core.logging import get_logger
from finagent_core.models.base import ToolSpec

logger = get_logger(__name__)


class ToolPermission(StrEnum):
    READ_DOCUMENTS = "read:documents"
    READ_MARKET_DATA = "read:market_data"
    READ_FILINGS = "read:filings"
    READ_DATASETS = "read:datasets"
    EXECUTE_CODE = "execute:code"
    RUN_BACKTEST = "run:backtest"
    COMPUTE = "compute"


@dataclass
class ToolResult:
    """Uniform tool return value. ``payload`` is what the model sees."""

    payload: Any
    latency_ms: int = 0
    evidence_count: int = 0
    warnings: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


class Tool(abc.ABC):
    name: str = "ABSTRACT"
    description: str = ""
    parameters: dict[str, Any] = {"type": "object", "properties": {}}
    required_permissions: tuple[ToolPermission, ...] = ()
    idempotent: bool = True

    def to_spec(self) -> ToolSpec:
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)

    def validate_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate against the declared JSON schema (required keys, types, enums, bounds)."""
        schema = self.parameters or {}
        properties: dict[str, Any] = schema.get("properties", {})
        required: list[str] = schema.get("required", [])

        missing = [key for key in required if arguments.get(key) in (None, "")]
        if missing:
            raise ValidationFailedError(
                f"{self.name} is missing required arguments: {', '.join(missing)}",
                details={"tool": self.name, "missing": missing},
            )

        cleaned: dict[str, Any] = {}
        for key, value in arguments.items():
            if key not in properties:
                continue  # ignore unknown keys rather than failing the whole run
            coerced = _coerce(value, properties[key].get("type"))
            enum_values = properties[key].get("enum")
            if enum_values and coerced not in enum_values:
                raise ValidationFailedError(
                    f"{self.name}.{key} must be one of {enum_values}",
                    details={"tool": self.name, "argument": key},
                )
            minimum, maximum = properties[key].get("minimum"), properties[key].get("maximum")
            if isinstance(coerced, (int, float)) and not isinstance(coerced, bool):
                if minimum is not None and coerced < minimum:
                    coerced = minimum
                if maximum is not None and coerced > maximum:
                    coerced = maximum
            cleaned[key] = coerced
        return cleaned

    @abc.abstractmethod
    def run(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute the tool. Must raise a :class:`FinagentError` on failure."""


def _coerce(value: Any, expected: str | None) -> Any:
    if expected is None or value is None:
        return value
    try:
        if expected == "integer" and not isinstance(value, bool):
            return int(value)
        if expected == "number" and not isinstance(value, bool):
            return float(value)
        if expected == "string":
            return str(value)
        if expected == "boolean":
            return value.strip().lower() in {"true", "1", "yes"} if isinstance(value, str) else bool(value)
        if expected == "array" and isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
    except (TypeError, ValueError) as exc:
        raise ValidationFailedError(f"could not coerce value to {expected}") from exc
    return value


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolFailedError(f"unknown tool: {name}", details={"tool": name})
        return tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "permissions": [permission.value for permission in tool.required_permissions],
            }
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def specs_for(self, names: list[str]) -> list[ToolSpec]:
        return [self._tools[name].to_spec() for name in names if name in self._tools]

    def execute(self, name: str, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        """Permission-checked execution: the only path a tool may be invoked through."""
        if name not in context.allowed_tools:
            logger.warning(
                "tool_not_permitted",
                extra={"tool": name, "run_id": context.run_id, "allowed": sorted(context.allowed_tools)},
            )
            raise ToolNotPermittedError(
                f"tool {name} is not enabled for this agent version",
                details={"tool": name, "allowed": sorted(context.allowed_tools)},
            )
        tool = self.get(name)
        cleaned = tool.validate_arguments(arguments or {})
        started = time.perf_counter()
        try:
            result = tool.run(cleaned, context)
        except FinagentError:
            raise
        except Exception as exc:  # unexpected tool bug: never leak the raw error upward
            logger.exception("tool_crashed", extra={"tool": name, "run_id": context.run_id})
            raise ToolFailedError(f"{name} raised {type(exc).__name__}", details={"tool": name}) from exc
        result.latency_ms = result.latency_ms or int((time.perf_counter() - started) * 1000)
        logger.info(
            "tool_executed",
            extra={
                "tool": name,
                "run_id": context.run_id,
                "latency_ms": result.latency_ms,
                "evidence_count": result.evidence_count,
            },
        )
        return result
