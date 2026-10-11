"""Model catalog and cost estimation.

Prices are **operator-configurable estimates** in USD per 1,000 tokens, used for cost
observability. They are not billing-grade and are labelled as estimates wherever they
surface. Override with ``FINAGENT_MODEL_PRICES`` (JSON) to match a negotiated rate card.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    key: str
    provider: str
    display_name: str
    context_window: int
    input_cost_per_1k: float
    output_cost_per_1k: float
    supports_tools: bool = True
    notes: str = ""


MODEL_CATALOG: dict[str, ModelInfo] = {
    info.key: info
    for info in [
        ModelInfo("gpt-4o", "openai", "GPT-4o", 128_000, 0.0025, 0.01),
        ModelInfo("gpt-4o-mini", "openai", "GPT-4o mini", 128_000, 0.00015, 0.0006),
        ModelInfo("gpt-4.1", "openai", "GPT-4.1", 1_000_000, 0.002, 0.008),
        ModelInfo("o4-mini", "openai", "o4-mini (reasoning)", 200_000, 0.0011, 0.0044),
        ModelInfo("claude-sonnet-4", "anthropic", "Claude Sonnet 4", 200_000, 0.003, 0.015),
        ModelInfo("claude-opus-4", "anthropic", "Claude Opus 4", 200_000, 0.015, 0.075),
        ModelInfo("claude-3-5-haiku", "anthropic", "Claude 3.5 Haiku", 200_000, 0.0008, 0.004),
        ModelInfo("gemini-2.5-pro", "google", "Gemini 2.5 Pro", 1_000_000, 0.00125, 0.01),
        ModelInfo("gemini-2.5-flash", "google", "Gemini 2.5 Flash", 1_000_000, 0.0003, 0.0025),
        ModelInfo(
            "mock-analyst-v1",
            "mock",
            "Deterministic Analyst (mock)",
            32_000,
            0.0,
            0.0,
            notes=(
                "Deterministic local provider. Produces evidence-grounded output from tool "
                "results only. Not a language model; used for demos, tests and offline work."
            ),
        ),
        ModelInfo(
            "mock-analyst-weak",
            "mock",
            "Deterministic Analyst — flawed fixture (mock)",
            32_000,
            0.0,
            0.0,
            notes=(
                "Deterministic local provider, deliberately flawed: omits citations and asserts "
                "an unsupported growth figure. Exists so evaluators can be proven to catch "
                "failures. Never use it for research."
            ),
        ),
        ModelInfo(
            "mock-judge-v1",
            "mock",
            "Deterministic Judge (mock)",
            32_000,
            0.0,
            0.0,
            notes="Deterministic rubric scorer used when no LLM judge credentials exist.",
        ),
    ]
}


def _price_overrides() -> dict[str, dict[str, float]]:
    raw = os.getenv("FINAGENT_MODEL_PRICES")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def find_model(key: str) -> ModelInfo | None:
    return MODEL_CATALOG.get(key)


def models_for_provider(provider: str) -> list[ModelInfo]:
    return [info for info in MODEL_CATALOG.values() if info.provider == provider]


def estimate_cost(model_key: str, input_tokens: int, output_tokens: int) -> float:
    """Estimated USD cost of a call. Unknown models cost 0 and are flagged upstream."""
    info = MODEL_CATALOG.get(model_key)
    overrides = _price_overrides().get(model_key, {})
    input_rate = float(overrides.get("input_cost_per_1k", info.input_cost_per_1k if info else 0.0))
    output_rate = float(overrides.get("output_cost_per_1k", info.output_cost_per_1k if info else 0.0))
    return round(input_tokens / 1000.0 * input_rate + output_tokens / 1000.0 * output_rate, 6)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters/token) for providers that omit usage."""
    if not text:
        return 0
    return max(1, len(text) // 4)
