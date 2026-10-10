"""Deterministic local model provider.

This is **not** a language model. It is a rule-based analyst simulator that lets the whole
platform — agent loop, tool calls, tracing, citation verification, evaluation, scoring — run
end to end without vendor credentials.

Honesty rules enforced here:

* ``ProviderStatus.MOCK`` is reported, never ``AVAILABLE``.
* ``ModelResponse.is_mock`` is ``True``; the API and UI badge every artefact as ``MOCK``.
* Output is composed **only** from tool results the agent actually retrieved; the provider
  never invents financial figures in ``standard`` quality.
* ``weak`` quality is a deliberately flawed fixture (no citations plus one fabricated growth
  number) whose only purpose is to prove the evaluators catch failures.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from finagent_core.models.base import (
    ChatMessage,
    ModelProvider,
    ModelResponse,
    ModelUsage,
    ProviderStatus,
    Role,
    ToolCallRequest,
    ToolSpec,
)
from finagent_core.models.catalog import estimate_tokens
from finagent_core.numeric import Unit, extract_numbers, format_value

#: Fabricated figure used exclusively by the ``weak`` fixture.
FABRICATED_GROWTH_CLAIM = "Revenue grew 42.0% year over year, the fastest in company history."

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

#: Question words that carry no discriminating signal when ranking evidence sentences.
_COMMON_TERMS = frozenset(
    {
        "what", "which", "have", "does", "with", "from", "their", "that", "this", "were",
        "into", "about", "using", "state", "report", "analyse", "analyze", "compute", "identify",
    }
)

_POSITIVE_TOKENS = ("increase", "increased", "growth", "grew", "expanded", "record", "improv", "up ")
_NEGATIVE_TOKENS = (
    "decrease", "declined", "decline", "risk", "loss", "headwind", "pressure", "litigation", "down ",
)


class MockModelProvider(ModelProvider):
    key = "mock"
    display_name = "Deterministic local provider (mock)"

    def __init__(self, *, quality: str = "standard", model: str = "mock-analyst-v1") -> None:
        super().__init__(api_key=None)
        self.quality = quality
        self.default_model = model
        self.supported_models = ("mock-analyst-v1", "mock-analyst-weak", "mock-judge-v1")

    def status(self) -> ProviderStatus:
        return ProviderStatus.MOCK

    # ------------------------------------------------------------------ public API

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        response_format: str | None = None,
    ) -> ModelResponse:
        started = time.perf_counter()
        model_key = model or self.default_model
        quality = "weak" if model_key == "mock-analyst-weak" else self.quality
        prompt_tokens = sum(estimate_tokens(message.content) for message in messages)

        if model_key == "mock-judge-v1" or quality == "judge":
            content, calls = self._judge(messages), []
        else:
            content, calls = self._analyst_step(messages, tools or [], quality=quality)

        return ModelResponse(
            provider=self.key,
            model=model_key,
            content=content,
            tool_calls=calls,
            usage=ModelUsage(input_tokens=prompt_tokens, output_tokens=estimate_tokens(content)),
            latency_ms=max(1, int((time.perf_counter() - started) * 1000)),
            finish_reason="tool_calls" if calls else "stop",
            estimated_cost_usd=0.0,
            is_mock=True,
        )

    # ------------------------------------------------------- analyst state machine

    def _analyst_step(
        self, messages: list[ChatMessage], tools: list[ToolSpec], *, quality: str
    ) -> tuple[str, list[ToolCallRequest]]:
        task = self._task_payload(messages)
        available = {tool.name for tool in tools}
        called = self._called_tools(messages)
        results = self._tool_results(messages)

        question = str(task.get("question") or task.get("title") or "Financial research request")
        ticker = str(task.get("ticker") or task.get("symbol") or "").upper()

        if "DOCUMENT_SEARCH" in available and "DOCUMENT_SEARCH" not in called:
            return "Searching the workspace document index for primary-source evidence.", [
                ToolCallRequest(name="DOCUMENT_SEARCH", arguments={"query": question, "top_k": 6})
            ]

        if ticker and "FINANCIAL_STATEMENTS" in available and "FINANCIAL_STATEMENTS" not in called:
            return "Retrieving reported financial statements for cross-checking.", [
                ToolCallRequest(
                    name="FINANCIAL_STATEMENTS",
                    arguments={"ticker": ticker, "statement": "income_statement", "periods": 4},
                )
            ]

        growth_inputs = self._growth_inputs(results)
        if growth_inputs and "CALCULATOR" in available and "CALCULATOR" not in called:
            current, prior = growth_inputs
            return "Recomputing period-over-period growth from reported figures.", [
                ToolCallRequest(
                    name="CALCULATOR",
                    arguments={
                        "operation": "percent_change",
                        "new_value": current,
                        "old_value": prior,
                        "label": "revenue_growth_pct",
                    },
                )
            ]

        return self._final_answer(task, results, quality=quality), []

    # ---------------------------------------------------------------- composition

    def _final_answer(self, task: dict[str, Any], results: dict[str, Any], *, quality: str) -> str:
        evidence = self._evidence(results)
        computed = self._computed_metrics(results)
        output_format = str(task.get("output_format") or "markdown")
        question = str(task.get("question") or task.get("title") or "Research request")

        findings = self._findings(evidence, question, cite=quality != "weak")
        if quality == "weak":
            findings.append(FABRICATED_GROWTH_CLAIM)

        required = [str(field) for field in (task.get("required_output_fields") or [])]
        if output_format == "investment_thesis":
            return self._thesis_json(question, evidence, computed, findings, quality=quality)
        return self._markdown(
            question, evidence, computed, findings, required=required, quality=quality
        )

    def _markdown(
        self,
        question: str,
        evidence: list[dict[str, Any]],
        computed: dict[str, float],
        findings: list[str],
        *,
        required: list[str],
        quality: str,
    ) -> str:
        lines = [f"## Analysis: {question}", ""]
        if not evidence:
            return "\n".join(
                lines
                + [
                    "No admissible evidence was retrieved for this task under the active "
                    "information cutoff, so no factual conclusion is asserted.",
                    "",
                    "**Confidence: 10%** (no supporting evidence)",
                ]
            )

        lines += ["### Findings", ""]
        lines += [f"- {finding}" for finding in findings]
        lines.append("")

        if required and quality != "weak":
            lines += ["### Requested coverage", ""]
            lines += self._coverage(required, evidence)
            lines.append("")

        if computed:
            lines += ["### Calculations", ""]
            for name, value in computed.items():
                unit = Unit.PERCENT if name.endswith("_pct") else Unit.NUMBER
                lines.append(
                    f"- `{name}` = {format_value(value, unit)} (recomputed with the CALCULATOR tool)"
                )
            lines.append("")

        lines += [
            "### Assumptions",
            "",
            "- Reported figures in the retrieved filings are accurate as filed.",
            "- No restatement has occurred after the information cutoff.",
            "",
            "### Unknowns",
            "",
            "- Forward guidance beyond the retrieved period is not covered by the retrieved evidence.",
            "",
        ]

        if quality == "weak":
            lines += ["### Risks", "", "- Not assessed.", ""]
        else:
            lines += ["### Risks", ""]
            lines += [f"- {item}" for item in self._risks(evidence)]
            lines += ["", "### Disconfirming evidence", ""]
            lines += [f"- {item}" for item in self._disconfirming(evidence)]
            lines.append("")

        lines.append(f"**Confidence: {self._confidence(evidence, computed, quality=quality):.0f}%**")
        lines.append("")
        lines.append(
            "_Produced by the deterministic mock provider: statements above are copied from "
            "retrieved source text, not generated prose._"
            if quality != "weak"
            else "_Produced by the flawed `mock-analyst-weak` fixture. Do not treat as research._"
        )
        return "\n".join(lines)

    def _thesis_json(
        self,
        question: str,
        evidence: list[dict[str, Any]],
        computed: dict[str, float],
        findings: list[str],
        *,
        quality: str,
    ) -> str:
        bull = [item for item in findings if any(token in item.lower() for token in _POSITIVE_TOKENS)]
        bear = [item for item in findings if any(token in item.lower() for token in _NEGATIVE_TOKENS)]
        payload = {
            "thesis": findings[0] if findings else "Insufficient evidence to state a thesis.",
            "bull_case": bull or ["Insufficient retrieved evidence to construct a bull case."],
            "base_case": findings[:3] or ["Insufficient retrieved evidence to construct a base case."],
            "bear_case": bear or ["Insufficient retrieved evidence to construct a bear case."],
            "catalysts": ["Next scheduled earnings release (date not established by evidence)."],
            "risks": self._risks(evidence) if quality != "weak" else [],
            "assumptions": [
                "Reported figures in retrieved filings are accurate as filed.",
                "No restatement occurred after the information cutoff.",
            ],
            "disconfirming_evidence": self._disconfirming(evidence) if quality != "weak" else [],
            "valuation": {
                "method": "not_performed",
                "note": "No valuation asserted: retrieved evidence lacked peer or DCF inputs.",
            },
            "financial_metrics": computed,
            "confidence": round(self._confidence(evidence, computed, quality=quality) / 100.0, 2),
            "sources": [self._citation_marker(item) for item in evidence] if quality != "weak" else [],
        }
        return "```json\n" + json.dumps(payload, indent=2) + "\n```"

    # ------------------------------------------------------------------- helpers

    def _findings(self, evidence: list[dict[str, Any]], question: str, *, cite: bool) -> list[str]:
        """One finding per distinct statement.

        Two documents frequently repeat the same sentence — a 10-Q and the earnings release
        that accompanied it, for example. Listing it twice would inflate the apparent
        weight of evidence behind it, so each statement is kept once.
        """
        findings: list[str] = []
        seen: set[str] = set()
        for item in evidence[:8]:
            sentence = self._informative_sentence(str(item.get("text", "")), question)
            if not sentence:
                continue
            key = re.sub(r"[^a-z0-9]+", "", sentence.lower())
            if key in seen:
                continue
            seen.add(key)
            findings.append(f"{sentence} {self._citation_marker(item)}" if cite else sentence)
            if len(findings) >= 6:
                break
        return findings

    def _coverage(self, required: list[str], evidence: list[dict[str, Any]]) -> list[str]:
        """Address each requested output field explicitly.

        A field the retrieved evidence does not establish is reported as not established.
        Saying so is the correct answer; inventing a value to satisfy the contract is not.
        """
        lines: list[str] = []
        for field in required:
            label = field.replace("_", " ")
            terms = {token for token in re.findall(r"[a-z]{4,}", label.lower())}
            best: tuple[int, str, dict[str, Any]] | None = None
            for item in evidence:
                sentence = self._informative_sentence(str(item.get("text", "")), label)
                if not sentence:
                    continue
                overlap = len(terms & set(re.findall(r"[a-z]{4,}", sentence.lower())))
                if overlap and (best is None or overlap > best[0]):
                    best = (overlap, sentence, item)
            if best is None:
                lines.append(
                    f"- **{label}**: not established by the retrieved evidence under this "
                    "information cutoff."
                )
            else:
                lines.append(f"- **{label}**: {best[1]} {self._citation_marker(best[2])}")
        return lines

    def _informative_sentence(self, text: str, question: str = "") -> str:
        """Pick a quotable sentence: prose, reasonable length, ideally containing a figure.

        Headings, disclaimers and dumped tables are skipped — citing them would produce a
        reference a human reviewer could not check against a readable claim.
        """
        raw = [part.strip() for part in _SENTENCE_SPLIT.split((text or "").strip()) if part.strip()]
        candidates = [
            sentence.replace("\n", " ")
            for sentence in raw
            if 40 <= len(sentence) <= 400 and "DEMO DATA" not in sentence and "|" not in sentence
        ]
        if not candidates:
            return ""
        question_terms = {
            token for token in re.findall(r"[a-z]{4,}", question.lower()) if token not in _COMMON_TERMS
        }

        def relevance(sentence: str) -> tuple[int, int]:
            terms = set(re.findall(r"[a-z]{4,}", sentence.lower()))
            return (len(question_terms & terms), 1 if extract_numbers(sentence) else 0)

        best = (
            max(candidates, key=relevance)
            if question_terms
            else next((sentence for sentence in candidates if extract_numbers(sentence)), candidates[0])
        )
        return best if best.endswith(".") else best + "."

    def _risks(self, evidence: list[dict[str, Any]]) -> list[str]:
        risks = []
        for item in evidence:
            text = str(item.get("text", ""))
            if any(token in text.lower() for token in _NEGATIVE_TOKENS):
                sentence = self._informative_sentence(text, "risk decline pressure litigation")
                if sentence:
                    risks.append(f"{sentence} {self._citation_marker(item)}")
        return risks[:4] or ["No risk factors were present in the retrieved evidence set."]

    def _disconfirming(self, evidence: list[dict[str, Any]]) -> list[str]:
        items = [
            f"{self._informative_sentence(str(item.get('text', '')), 'risk decline pressure')} "
            f"{self._citation_marker(item)}"
            for item in evidence
            if any(token in str(item.get("text", "")).lower() for token in _NEGATIVE_TOKENS)
        ]
        return items[:3] or [
            "No disconfirming evidence was found in the retrieved set; absence of evidence is not "
            "evidence of absence and retrieval was limited to this workspace."
        ]

    def _confidence(
        self, evidence: list[dict[str, Any]], computed: dict[str, float], *, quality: str
    ) -> float:
        """Deterministic heuristic, not a probability estimate."""
        if quality == "weak":
            return 95.0
        score = 40.0 + 6.0 * min(len(evidence), 6)
        if computed:
            score += 8.0
        return min(score, 88.0)

    def _citation_marker(self, item: dict[str, Any]) -> str:
        label = item.get("document_name") or item.get("source") or "source"
        page = item.get("page_number")
        chunk_id = item.get("chunk_id") or item.get("id") or ""
        page_part = f", page {page}" if page else ""
        return f"[Source: {label}{page_part} | chunk:{chunk_id}]"

    def _task_payload(self, messages: list[ChatMessage]) -> dict[str, Any]:
        for message in reversed(messages):
            role = message.role.value if hasattr(message.role, "value") else str(message.role)
            if role != Role.USER.value:
                continue
            match = re.search(r"```json\s*(\{.*?\})\s*```", message.content, re.DOTALL)
            raw = match.group(1) if match else message.content
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}

    def _called_tools(self, messages: list[ChatMessage]) -> set[str]:
        called: set[str] = set()
        for message in messages:
            for call in message.tool_calls:
                called.add(call.name)
            role = message.role.value if hasattr(message.role, "value") else str(message.role)
            if role == Role.TOOL.value and message.name:
                called.add(message.name)
        return called

    def _tool_results(self, messages: list[ChatMessage]) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for message in messages:
            role = message.role.value if hasattr(message.role, "value") else str(message.role)
            if role != Role.TOOL.value or not message.name:
                continue
            try:
                results[message.name] = json.loads(message.content)
            except json.JSONDecodeError:
                results[message.name] = {"text": message.content}
        return results

    def _evidence(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        payload = results.get("DOCUMENT_SEARCH") or {}
        matches = payload.get("results") if isinstance(payload, dict) else None
        return [item for item in (matches or []) if isinstance(item, dict)]

    def _computed_metrics(self, results: dict[str, Any]) -> dict[str, float]:
        computed: dict[str, float] = {}
        calc = results.get("CALCULATOR")
        if isinstance(calc, dict) and isinstance(calc.get("value"), (int, float)):
            computed[str(calc.get("label") or "computed_value")] = round(float(calc["value"]), 4)
        python_result = results.get("PYTHON")
        if isinstance(python_result, dict):
            for key, value in (python_result.get("results") or {}).items():
                if isinstance(value, (int, float)):
                    computed[str(key)] = round(float(value), 4)
        return computed

    def _growth_inputs(self, results: dict[str, Any]) -> tuple[float, float] | None:
        statements = results.get("FINANCIAL_STATEMENTS")
        if not isinstance(statements, dict):
            return None
        periods = statements.get("periods") or statements.get("rows") or []
        values = [
            float(period["revenue"])
            for period in periods
            if isinstance(period, dict) and isinstance(period.get("revenue"), (int, float))
        ]
        if len(values) < 2:
            return None
        return values[0], values[1]

    # --------------------------------------------------------------------- judge

    def _judge(self, messages: list[ChatMessage]) -> str:
        """Deterministic rubric scorer (structure heuristics, not semantic judgement)."""
        answer = ""
        for message in reversed(messages):
            role = message.role.value if hasattr(message.role, "value") else str(message.role)
            if role == Role.USER.value:
                answer = message.content
                break
        lowered = answer.lower()
        has_citation = "chunk:" in lowered or "[source:" in lowered
        has_assumptions = "assumption" in lowered
        has_risks = "risk" in lowered
        has_numbers = bool(extract_numbers(answer))
        has_disconfirming = "disconfirming" in lowered
        length_ok = len(answer) > 400

        payload = {
            "reasoning_quality": min(
                40 + 15 * has_citation + 10 * has_assumptions + 10 * has_numbers + 10 * length_ok, 95
            ),
            "completeness": min(
                35 + 15 * has_risks + 15 * has_assumptions + 15 * has_disconfirming + 10 * length_ok, 95
            ),
            "relevance": min(55 + 20 * has_numbers + 15 * has_citation, 95),
            "rationale": (
                f"Deterministic rubric: citations {'present' if has_citation else 'absent'}, "
                f"assumptions {'stated' if has_assumptions else 'missing'}, risks "
                f"{'stated' if has_risks else 'missing'}, disconfirming evidence "
                f"{'stated' if has_disconfirming else 'missing'}."
            ),
            "judge": "deterministic-mock",
        }
        return json.dumps(payload)
