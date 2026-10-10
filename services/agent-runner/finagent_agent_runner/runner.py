"""The agent execution loop.

Design commitments:

* Every model call, tool call, retrieval and error becomes a trace step. The trace is the
  product, not a debug log.
* Tool access is permission-checked on every call against the agent *version's* allow-list.
* Failures degrade into a ``FAILED`` :class:`RunResult` that still carries its trace, so a
  failed run remains diagnosable.
* Nothing here is provider-specific.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from finagent_core.cutoff import AsOfContext
from finagent_core.errors import AgentStepLimitError, AgentTimeoutError, ErrorCode, FinagentError
from finagent_core.logging import get_logger, log_context
from finagent_core.models.base import ChatMessage, ModelProvider
from finagent_core.models.registry import ModelRegistry
from finagent_core.schemas.enums import OutputFormat, ResearchStepKind, RunStatus
from finagent_core.schemas.research import (
    AgentRunSpec,
    EvidenceItem,
    RunResult,
    TaskSpec,
    ToolCallRecord,
    TraceStep,
    UsageSummary,
)
from finagent_core.schemas.thesis import InvestmentThesis

from finagent_agent_runner.context import ToolContext
from finagent_agent_runner.prompts import build_system_prompt, build_task_message
from finagent_agent_runner.tools.base import ToolRegistry

logger = get_logger(__name__)

_CONFIDENCE_RE = re.compile(r"confidence[^0-9]{0,20}(\d{1,3}(?:\.\d+)?)\s*%", re.IGNORECASE)
_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_MAX_TOOL_PAYLOAD_CHARS = 12_000


@dataclass
class RunnerHooks:
    """Optional callbacks so callers can stream progress into their own store."""

    on_trace_step: Any = None
    on_tool_call: Any = None
    on_model_call: Any = None


@dataclass
class _RunState:
    trace: list[TraceStep] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    evidence: dict[str, EvidenceItem] = field(default_factory=dict)
    usage: UsageSummary = field(default_factory=UsageSummary)
    warnings: list[str] = field(default_factory=list)
    sequence: int = 0

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence


class AgentRunner:
    def __init__(
        self,
        *,
        model_registry: ModelRegistry,
        tool_registry: ToolRegistry,
        hooks: RunnerHooks | None = None,
    ) -> None:
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.hooks = hooks or RunnerHooks()

    # ------------------------------------------------------------------ public API

    def run(
        self,
        spec: AgentRunSpec,
        task: TaskSpec,
        context: ToolContext,
        *,
        role: str | None = None,
        seed_messages: list[ChatMessage] | None = None,
        extra_task_context: dict[str, Any] | None = None,
    ) -> RunResult:
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        state = _RunState()

        cutoff = spec.information_cutoff or task.information_cutoff
        as_of = AsOfContext.at(cutoff, strict=False) if cutoff else AsOfContext.live()
        context.as_of = as_of
        context.allowed_tools = frozenset(spec.tools)
        context.evidence_sink = lambda items: self._absorb_evidence(state, items)
        context.usage_sink = lambda kind, quantity, detail: self._absorb_usage(state, kind, quantity)

        tool_specs = self.tool_registry.specs_for(list(spec.tools))
        messages: list[ChatMessage] = [
            ChatMessage.system(
                build_system_prompt(spec, as_of=as_of, tool_names=list(spec.tools), role=role)
            )
        ]
        messages.extend(seed_messages or [])
        messages.append(ChatMessage.user(build_task_message(task, extra=extra_task_context)))

        self._record(
            state,
            ResearchStepKind.PLAN,
            action="Received research task",
            input_payload={
                "task": task.title,
                "template": str(task.template),
                "tools": list(spec.tools),
            },
            output_payload={"information_cutoff": as_of.describe()},
        )

        result = RunResult(
            run_id=context.run_id, spec=spec, task=task, started_at=started_at, information_cutoff=cutoff
        )

        with log_context(run_id=context.run_id, agent_version_id=spec.agent_version_id):
            try:
                provider = self.model_registry.provider_for_model(spec.model)
                final_content = self._loop(
                    provider=provider,
                    spec=spec,
                    context=context,
                    messages=messages,
                    tool_specs=tool_specs,
                    state=state,
                    started=started,
                )
                result.status = RunStatus.SUCCEEDED
                result.output_text = final_content
                result.used_mock_model = provider.is_mock
                self._finalise_output(result, spec, final_content, state)
            except FinagentError as error:
                result.status = RunStatus.FAILED
                result.error_code = error.code.value
                result.error_message = error.user_message
                self._record(
                    state,
                    ResearchStepKind.ERROR,
                    action=f"Run failed: {error.code.value}",
                    output_payload={"detail": error.details},
                    error_code=error.code.value,
                    error_message=error.user_message,
                )
                logger.warning(
                    "agent_run_failed",
                    extra={"run_id": context.run_id, "error_code": error.code.value},
                )
            except Exception as exc:  # unexpected: log with stack, return a safe code
                result.status = RunStatus.FAILED
                result.error_code = ErrorCode.INTERNAL_ERROR.value
                result.error_message = "An unexpected error occurred during the agent run."
                logger.exception("agent_run_crashed", extra={"run_id": context.run_id})
                self._record(
                    state,
                    ResearchStepKind.ERROR,
                    action=f"Unexpected error: {type(exc).__name__}",
                    error_code=ErrorCode.INTERNAL_ERROR.value,
                )

        state.usage.duration_ms = int((time.perf_counter() - started) * 1000)
        result.trace = state.trace
        result.tool_calls = state.tool_calls
        result.evidence = list(state.evidence.values())
        result.usage = state.usage
        result.warnings = state.warnings
        result.messages = [message.model_dump() for message in messages]
        result.finished_at = datetime.now(timezone.utc)
        logger.info(
            "agent_run_finished",
            extra={
                "run_id": context.run_id,
                "status": result.status,
                "steps": len(result.trace),
                "tool_calls": len(result.tool_calls),
                "tokens": state.usage.total_tokens,
                "cost_usd": round(state.usage.estimated_cost_usd, 6),
            },
        )
        return result

    # ----------------------------------------------------------------- inner loop

    def _loop(
        self,
        *,
        provider: ModelProvider,
        spec: AgentRunSpec,
        context: ToolContext,
        messages: list[ChatMessage],
        tool_specs: list[Any],
        state: _RunState,
        started: float,
    ) -> str:
        for _ in range(max(1, spec.max_steps)):
            elapsed = time.perf_counter() - started
            if elapsed > spec.timeout_seconds:
                raise AgentTimeoutError(
                    f"run exceeded {spec.timeout_seconds}s",
                    details={"elapsed_seconds": round(elapsed, 2)},
                )

            response = provider.complete(
                messages,
                model=spec.model,
                tools=tool_specs or None,
                temperature=spec.temperature,
                max_tokens=spec.max_tokens,
                response_format="json" if OutputFormat(spec.output_format) is OutputFormat.JSON else None,
            )
            state.usage.model_calls += 1
            state.usage.input_tokens += response.usage.input_tokens
            state.usage.output_tokens += response.usage.output_tokens
            state.usage.estimated_cost_usd += response.estimated_cost_usd
            self._record(
                state,
                ResearchStepKind.MODEL_CALL,
                action=f"Model call ({response.model})",
                input_payload={"messages": len(messages), "tools_offered": len(tool_specs)},
                output_payload={
                    "content_preview": response.content[:400],
                    "tool_calls": [call.name for call in response.tool_calls],
                    "finish_reason": response.finish_reason,
                    "is_mock": response.is_mock,
                },
                model=response.model,
                latency_ms=response.latency_ms,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost=response.estimated_cost_usd,
            )
            if self.hooks.on_model_call:
                self.hooks.on_model_call(response)

            if not response.tool_calls:
                return response.content

            messages.append(ChatMessage.assistant(response.content, response.tool_calls))
            for call in response.tool_calls:
                payload, record = self._execute_tool(call, context, state)
                messages.append(ChatMessage.tool(call.id, call.name, payload))
                if self.hooks.on_tool_call:
                    self.hooks.on_tool_call(record)

        raise AgentStepLimitError(
            f"agent did not converge within {spec.max_steps} steps", details={"max_steps": spec.max_steps}
        )

    def _execute_tool(
        self, call: Any, context: ToolContext, state: _RunState
    ) -> tuple[str, ToolCallRecord]:
        record = ToolCallRecord(id=call.id, tool_name=call.name, arguments=call.arguments)
        try:
            result = self.tool_registry.execute(call.name, call.arguments, context)
            record.result = result.payload
            record.latency_ms = result.latency_ms
            state.usage.tool_calls += 1
            state.warnings.extend(result.warnings)
            self._record(
                state,
                ResearchStepKind.RETRIEVE if result.evidence_count else ResearchStepKind.TOOL_CALL,
                action=f"Tool {call.name}",
                input_payload=call.arguments,
                output_payload=_truncate_payload(result.payload),
                tool_name=call.name,
                latency_ms=result.latency_ms,
            )
            payload = json.dumps(result.payload, default=str)[:_MAX_TOOL_PAYLOAD_CHARS]
        except FinagentError as error:
            record.status = "FAILED"
            record.error_code = error.code.value
            record.error_message = error.user_message
            state.warnings.append(f"{call.name}: {error.user_message}")
            self._record(
                state,
                ResearchStepKind.ERROR,
                action=f"Tool {call.name} failed",
                input_payload=call.arguments,
                tool_name=call.name,
                error_code=error.code.value,
                error_message=error.user_message,
            )
            # The failure is fed back to the model so it can adapt rather than crash.
            payload = json.dumps(
                {
                    "error": {"code": error.code.value, "message": error.user_message},
                    "retryable": error.retryable,
                }
            )
        state.tool_calls.append(record)
        return payload, record

    # ------------------------------------------------------------------- helpers

    def _absorb_evidence(self, state: _RunState, items: list[EvidenceItem]) -> None:
        for item in items:
            state.evidence.setdefault(item.chunk_id, item)

    def _absorb_usage(self, state: _RunState, kind: str, quantity: float) -> None:
        if kind == "PYTHON_SECONDS":
            state.usage.python_seconds += quantity
        elif kind == "DATA_API_CALL":
            state.usage.data_api_calls += int(quantity)

    def _record(
        self,
        state: _RunState,
        kind: ResearchStepKind,
        *,
        action: str,
        input_payload: Any = None,
        output_payload: Any = None,
        tool_name: str | None = None,
        model: str | None = None,
        latency_ms: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> TraceStep:
        step = TraceStep(
            sequence=state.next_sequence(),
            kind=kind,
            action=action,
            input=input_payload,
            output=output_payload,
            tool_name=tool_name,
            model=model,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            error_code=error_code,
            error_message=error_message,
        )
        state.trace.append(step)
        if self.hooks.on_trace_step:
            self.hooks.on_trace_step(step)
        return step

    def _finalise_output(
        self, result: RunResult, spec: AgentRunSpec, content: str, state: _RunState
    ) -> None:
        output_format = OutputFormat(spec.output_format)
        if output_format in (OutputFormat.INVESTMENT_THESIS, OutputFormat.JSON):
            payload = _extract_json(content)
            if payload is None:
                state.warnings.append(
                    "The agent was asked for structured output but did not return parseable JSON; "
                    "the raw text was preserved."
                )
            elif output_format is OutputFormat.INVESTMENT_THESIS:
                try:
                    thesis = InvestmentThesis.model_validate(payload)
                    result.thesis = thesis
                    result.confidence = thesis.confidence
                    missing = thesis.missing_sections()
                    if missing:
                        state.warnings.append(
                            "Thesis is missing required sections: " + ", ".join(missing)
                        )
                except Exception:  # noqa: BLE001 - validation detail is not user-facing
                    state.warnings.append("Structured thesis output failed schema validation.")
        if result.confidence is None:
            match = _CONFIDENCE_RE.search(content or "")
            if match:
                result.confidence = min(1.0, max(0.0, float(match.group(1)) / 100.0))

        self._record(
            state,
            ResearchStepKind.CONCLUDE,
            action="Produced conclusion",
            output_payload={
                "characters": len(content or ""),
                "confidence": result.confidence,
                "evidence_items": len(state.evidence),
            },
        )


def _extract_json(content: str) -> dict[str, Any] | None:
    match = _JSON_BLOCK_RE.search(content or "")
    candidate = match.group(1) if match else (content or "").strip()
    if not candidate.startswith("{"):
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _truncate_payload(payload: Any) -> Any:
    """Keep traces readable without losing the shape of a tool result."""
    if isinstance(payload, dict):
        summary: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, list) and len(value) > 5:
                summary[key] = value[:5] + [f"... {len(value) - 5} more"]
            elif isinstance(value, str) and len(value) > 1200:
                summary[key] = value[:1200] + "..."
            else:
                summary[key] = value
        return summary
    if isinstance(payload, str) and len(payload) > 2000:
        return payload[:2000] + "..."
    return payload
