"""Prompt construction.

The agent's own instructions are user-authored and versioned. The platform *adds* a
non-negotiable research contract (evidence discipline, citation format, cutoff notice,
uncertainty reporting) so every run is evaluable on the same terms regardless of what the
user wrote.
"""

from __future__ import annotations

import json

from finagent_core.cutoff import AsOfContext
from finagent_core.schemas.enums import OutputFormat
from finagent_core.schemas.research import AgentRunSpec, TaskSpec

RESEARCH_CONTRACT = """
## Platform research contract (applies to every response)

1. Evidence before conclusion. Use the tools provided to retrieve evidence before asserting
   any fact. If no evidence supports a statement, say so explicitly.
2. Cite every factual claim inline as: [Source: <document name>, page <page> | chunk:<chunk_id>]
   using the chunk_id returned by the retrieval tools. Uncited figures are treated as
   unsupported and will be scored as such.
3. Distinguish clearly between:
   - fact (directly supported by a cited source),
   - inference (your reasoning from cited facts),
   - assumption (not supported by evidence),
   - unknown (evidence does not exist in the retrieved set).
4. Recompute every derived number with the CALCULATOR or PYTHON tool. Do not perform
   arithmetic mentally.
5. State assumptions, unknowns and disconfirming evidence. A confident answer with no stated
   uncertainty is a failed answer.
6. Never use information published after the information cutoff, and never speculate about
   what happened after it.
7. You are producing institutional research input, not investment advice, and you must not
   place or recommend trades.
""".strip()

THESIS_SCHEMA_HINT = {
    "thesis": "one sentence",
    "bull_case": ["cited statements"],
    "base_case": ["cited statements"],
    "bear_case": ["cited statements"],
    "catalysts": ["..."],
    "risks": ["..."],
    "assumptions": ["..."],
    "disconfirming_evidence": ["..."],
    "unknowns": ["..."],
    "valuation": {"method": "dcf|multiples|not_performed", "note": "..."},
    "financial_metrics": {"metric_name": 0.0},
    "confidence": 0.0,
    "sources": ["chunk ids or source labels"],
}

ROLE_PROMPTS: dict[str, str] = {
    "analyst": (
        "You are an institutional equity research analyst. Analyse the subject using only the "
        "data sources provided. Every factual claim must have a citation. Clearly distinguish "
        "facts from assumptions."
    ),
    "bull": (
        "You are a bull-side analyst. Build the strongest *evidence-based* case that the subject "
        "is attractive. You may not invent evidence: if the retrieved evidence does not support a "
        "bullish point, state that the bull case lacks support on that point."
    ),
    "bear": (
        "You are a bear-side analyst. Build the strongest *evidence-based* case that the subject "
        "is unattractive or over-valued. Use retrieved risk factors, competitive pressures and "
        "financial weaknesses. Do not invent evidence."
    ),
    "skeptic": (
        "You are a skeptic. Your job is to find evidence that *contradicts* the thesis you are "
        "given. Enumerate every claim in the thesis, look for disconfirming evidence in the "
        "retrieved sources, and flag any claim that is uncited, mis-cited, arithmetically wrong "
        "or logically unsupported. Be specific about which claim fails and why."
    ),
    "risk": (
        "You are a risk analyst. Identify the position-level and portfolio-level risks implied by "
        "the thesis: concentration, liquidity, cyclicality, leverage, litigation, key-person and "
        "data-quality risk. Quantify where the evidence allows."
    ),
    "judge": (
        "You are an impartial judge. You are given a bull case, a bear case and a skeptic's "
        "critique. Identify the key points of disagreement, state which side is better supported "
        "by cited evidence, list the unresolved uncertainties, and give a calibrated confidence. "
        "Do not favour the more fluent argument; favour the better-evidenced one."
    ),
    "editor": (
        "You are an editor. Tighten the research into a decision-ready memo without changing any "
        "figure, removing any citation, or strengthening any claim beyond its evidence."
    ),
}


def build_system_prompt(
    spec: AgentRunSpec, *, as_of: AsOfContext, tool_names: list[str], role: str | None = None
) -> str:
    sections: list[str] = []
    instructions = (spec.system_prompt or "").strip()
    if role and role in ROLE_PROMPTS:
        sections.append(ROLE_PROMPTS[role])
    if instructions:
        sections.append(instructions)
    if not sections:
        sections.append(ROLE_PROMPTS["analyst"])

    sections.append(RESEARCH_CONTRACT)

    if as_of.is_historical:
        sections.append(
            f"## Information cutoff\n\nYou are operating as of {as_of.cutoff.isoformat()}. "
            "Retrieval is filtered to sources published on or before that timestamp. Treat "
            "anything later as unknown."
        )
    else:
        sections.append("## Information cutoff\n\nNo historical restriction is active (live mode).")

    if tool_names:
        sections.append("## Tools available\n\n" + "\n".join(f"- {name}" for name in tool_names))
    else:
        sections.append(
            "## Tools available\n\nNone. You have no retrieval capability, so you must state that "
            "no evidence was available rather than answering from memory."
        )

    output_format = OutputFormat(spec.output_format)
    if output_format is OutputFormat.INVESTMENT_THESIS:
        sections.append(
            "## Required output\n\nReturn a single JSON object in a ```json fenced block with this "
            "shape:\n```json\n" + json.dumps(THESIS_SCHEMA_HINT, indent=2) + "\n```"
        )
    elif output_format is OutputFormat.JSON:
        sections.append("## Required output\n\nReturn a single JSON object in a ```json fenced block.")
    else:
        sections.append(
            "## Required output\n\nMarkdown with these sections: Findings, Calculations, "
            "Assumptions, Unknowns, Risks, Disconfirming evidence, and a final line "
            "`**Confidence: N%**`."
        )

    if spec.risk_constraints:
        sections.append(
            "## Risk constraints\n\n"
            + "\n".join(f"- {key}: {value}" for key, value in spec.risk_constraints.items())
        )
    return "\n\n".join(sections)


def build_task_message(task: TaskSpec, *, extra: dict | None = None) -> str:
    payload = task.prompt_payload()
    if extra:
        payload.update(extra)
    return (
        "Complete the following research task.\n\n```json\n"
        + json.dumps(payload, indent=2, default=str)
        + "\n```"
    )
