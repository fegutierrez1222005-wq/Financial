"""Claim extraction.

Before anything can be verified, the agent's output has to be decomposed into atomic
assertions. Extraction is deterministic (no model involved) so the same output always
yields the same claim set — a prerequisite for reproducible scoring.

Claims are typed, because different kinds carry different obligations:

* ``FACTUAL`` — must be supported by cited evidence.
* ``FORWARD_LOOKING`` — a projection; the *basis* must be cited, the outcome cannot be.
* ``ASSUMPTION`` — explicitly labelled as an assumption; must not be presented as fact.
* ``UNKNOWN`` — an explicit admission of missing evidence.
* ``META`` — a statement about the research process itself, not about the world.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from finagent_core.numeric import NumericMention, extract_numbers
from finagent_core.schemas.research import RunResult
from finagent_core.schemas.thesis import InvestmentThesis

_CITATION_RE = re.compile(r"chunk:\s*([A-Za-z0-9_\-:.]+)")
_SOURCE_MARKER_RE = re.compile(r"\[\s*source\s*:([^\]]*)\]", re.IGNORECASE)
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s*(.+?)\s*#*\s*$")
_BULLET_RE = re.compile(r"^\s*([-*+]|\d+\.)\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(`$])")
_CODE_FENCE_RE = re.compile(r"^\s*```")

_FORWARD_TOKENS = (
    "expects", "expect", "guidance", "forecast", "we project", "projected", "outlook",
    "will likely", "should grow", "anticipates", "target of", "by 2025", "by 2026",
    "next quarter", "next year",
)
_META_TOKENS = (
    "retrieved evidence", "retrieved set", "no evidence", "not established", "not asserted",
    "no admissible", "was not performed", "not performed", "insufficient evidence",
    "produced by the deterministic", "absence of evidence", "this analysis",
    "recomputed with the calculator", "cite a source", "demo data",
)
_ASSUMPTION_SECTIONS = ("assumption", "assumptions")
_UNKNOWN_SECTIONS = ("unknown", "unknowns", "open questions")
_META_SECTIONS = ("methodology", "method", "limitations", "notes")


class ClaimKind(StrEnum):
    FACTUAL = "FACTUAL"
    FORWARD_LOOKING = "FORWARD_LOOKING"
    ASSUMPTION = "ASSUMPTION"
    UNKNOWN = "UNKNOWN"
    META = "META"


@dataclass
class ExtractedClaim:
    text: str
    kind: ClaimKind
    section: str
    cited_chunk_ids: list[str] = field(default_factory=list)
    source_labels: list[str] = field(default_factory=list)
    numbers: list[NumericMention] = field(default_factory=list)
    order: int = 0

    @property
    def has_citation(self) -> bool:
        return bool(self.cited_chunk_ids)

    @property
    def requires_support(self) -> bool:
        return self.kind in (ClaimKind.FACTUAL, ClaimKind.FORWARD_LOOKING)


def _strip_markers(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _SOURCE_MARKER_RE.sub("", text)).strip(" -*\t")


def _classify(text: str, section: str) -> ClaimKind:
    lowered = text.lower()
    section_lower = (section or "").lower()
    if any(token in section_lower for token in _ASSUMPTION_SECTIONS):
        return ClaimKind.ASSUMPTION
    if any(token in section_lower for token in _UNKNOWN_SECTIONS):
        return ClaimKind.UNKNOWN
    if any(token in lowered for token in _META_TOKENS):
        return ClaimKind.META
    if any(token in section_lower for token in _META_SECTIONS):
        return ClaimKind.META
    if lowered.startswith(("we assume", "assuming", "assumes ")):
        return ClaimKind.ASSUMPTION
    if any(token in lowered for token in _FORWARD_TOKENS):
        return ClaimKind.FORWARD_LOOKING
    return ClaimKind.FACTUAL


def _make_claim(raw: str, section: str, order: int) -> ExtractedClaim | None:
    citations = _CITATION_RE.findall(raw)
    labels = [part.split("|")[0].strip() for part in _SOURCE_MARKER_RE.findall(raw) if part.strip()]
    text = _strip_markers(raw)
    # Sentence fragments and single words are not assertions.
    if len(text) < 25 or len(text.split()) < 5:
        return None
    return ExtractedClaim(
        text=text,
        kind=_classify(text, section),
        section=section,
        cited_chunk_ids=list(dict.fromkeys(citations)),
        source_labels=list(dict.fromkeys(labels)),
        numbers=extract_numbers(text),
        order=order,
    )


def extract_claims_from_markdown(markdown: str) -> list[ExtractedClaim]:
    claims: list[ExtractedClaim] = []
    section = ""
    in_code_block = False

    for line in (markdown or "").splitlines():
        if _CODE_FENCE_RE.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            section = heading.group(2).strip()
            continue
        if stripped.startswith("_") and stripped.endswith("_"):
            continue  # italic platform note, not a claim
        if stripped.startswith("|") or set(stripped) <= {"-", "|", " ", ":"}:
            continue  # table markup

        body = _BULLET_RE.sub("", stripped)
        # A bullet may contain several sentences; each is judged separately.
        for sentence in _SENTENCE_SPLIT.split(body):
            claim = _make_claim(sentence, section, len(claims))
            if claim is not None:
                claims.append(claim)
    return claims


def extract_claims_from_thesis(thesis: InvestmentThesis) -> list[ExtractedClaim]:
    claims: list[ExtractedClaim] = []
    sections: list[tuple[str, list[str]]] = [
        ("thesis", [thesis.thesis] if thesis.thesis else []),
        ("bull_case", thesis.bull_case),
        ("base_case", thesis.base_case),
        ("bear_case", thesis.bear_case),
        ("catalysts", thesis.catalysts),
        ("risks", thesis.risks),
        ("assumptions", thesis.assumptions),
        ("disconfirming_evidence", thesis.disconfirming_evidence),
        ("unknowns", thesis.unknowns),
    ]
    for section, entries in sections:
        for entry in entries:
            claim = _make_claim(str(entry), section, len(claims))
            if claim is not None:
                claims.append(claim)
    if thesis.valuation and thesis.valuation.note:
        claim = _make_claim(thesis.valuation.note, "valuation", len(claims))
        if claim is not None:
            claims.append(claim)
    return claims


def extract_claims(result: RunResult) -> list[ExtractedClaim]:
    """Extract claims from whichever output form the run produced."""
    if result.thesis is not None:
        claims = extract_claims_from_thesis(result.thesis)
        if claims:
            return claims
    return extract_claims_from_markdown(result.output_text)


def claim_statistics(claims: list[ExtractedClaim]) -> dict[str, int]:
    stats = {kind.value: 0 for kind in ClaimKind}
    for claim in claims:
        stats[claim.kind.value] += 1
    stats["total"] = len(claims)
    stats["cited"] = sum(1 for claim in claims if claim.has_citation)
    stats["requiring_support"] = sum(1 for claim in claims if claim.requires_support)
    stats["numeric"] = sum(1 for claim in claims if claim.numbers)
    return stats
