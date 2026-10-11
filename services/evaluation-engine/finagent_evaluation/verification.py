"""Citation verification and hallucination detection.

Pipeline: agent output → claims → cited sources → compare claim with source → verdict.

The comparison is deliberately mechanical:

* every number in the claim must appear in the cited passage within tolerance (unit-aware,
  so ``18%`` and ``18.0%`` match but ``$18M`` does not match ``18%``),
* the claim's content words must overlap the passage enough that the citation is *about* the
  claim rather than merely nearby,
* a citation pointing at a passage the agent never retrieved is a fabricated citation.

No language model is involved, so verdicts are reproducible and cheap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from finagent_core.numeric import NumericMention, Unit, comparable, extract_numbers, values_match
from finagent_core.schemas.enums import ClaimSupport
from finagent_core.schemas.research import EvidenceItem
from finagent_evaluation.claims import ClaimKind, ExtractedClaim

_WORD_RE = re.compile(r"[a-z][a-z0-9\-']+")
_STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for", "from", "has", "have", "in", "into", "is", "it", "its", "of", "on", "or", "over", "per", "that", "the", "their", "there", "these", "this", "those", "to", "was", "were", "will", "with", "within", "year", "years", "quarter", "compared", "than", "versus", "company", "companys", "our", "we", "million", "billion", "approximately", "about"]
)

#: Relative tolerance when matching a claim's number against a source figure.
NUMERIC_TOLERANCE_PCT = 1.0
#: Content-word overlap required for a citation to be considered *about* the claim.
STRONG_OVERLAP = 0.45
WEAK_OVERLAP = 0.20


@dataclass
class ClaimVerdict:
    claim: ExtractedClaim
    support_level: ClaimSupport
    matched_chunk_id: str | None = None
    evidence_quote: str | None = None
    similarity: float = 0.0
    numbers_checked: int = 0
    numbers_matched: int = 0
    explanation: str = ""
    fabricated_citations: list[str] = field(default_factory=list)

    @property
    def is_hallucination(self) -> bool:
        return self.claim.requires_support and self.support_level.counts_as_hallucination


@dataclass
class VerificationReport:
    verdicts: list[ClaimVerdict]
    supported: int = 0
    partially_supported: int = 0
    inferred: int = 0
    unsupported: int = 0
    contradicted: int = 0
    assumptions: int = 0
    unknowns: int = 0
    meta: int = 0
    numeric_claims: int = 0
    numeric_matched: int = 0
    fabricated_citation_count: int = 0
    cutoff_violations: list[str] = field(default_factory=list)

    @property
    def verifiable_total(self) -> int:
        return (
            self.supported + self.partially_supported + self.inferred + self.unsupported + self.contradicted
        )

    @property
    def hallucination_rate(self) -> float:
        """Share of support-requiring claims that no retrieved evidence backs (0–1)."""
        if not self.verifiable_total:
            return 0.0
        return (self.unsupported + self.contradicted) / self.verifiable_total

    @property
    def citation_coverage(self) -> float:
        """Share of support-requiring claims carrying a usable citation (0–1)."""
        if not self.verifiable_total:
            return 0.0
        cited = sum(
            1 for verdict in self.verdicts if verdict.claim.requires_support and verdict.claim.has_citation
        )
        return cited / self.verifiable_total

    @property
    def citation_accuracy(self) -> float:
        """Of the cited claims, the share whose citation actually supports them (0–1)."""
        cited = [
            verdict
            for verdict in self.verdicts
            if verdict.claim.requires_support and verdict.claim.has_citation
        ]
        if not cited:
            return 0.0
        good = sum(
            1
            for verdict in cited
            if verdict.support_level
            in (ClaimSupport.DIRECTLY_SUPPORTED, ClaimSupport.PARTIALLY_SUPPORTED)
        )
        return good / len(cited)

    @property
    def numeric_accuracy(self) -> float:
        if not self.numeric_claims:
            return 0.0
        return self.numeric_matched / self.numeric_claims

    def as_dict(self) -> dict[str, object]:
        return {
            "supported": self.supported,
            "partially_supported": self.partially_supported,
            "inferred": self.inferred,
            "unsupported": self.unsupported,
            "contradicted": self.contradicted,
            "assumptions": self.assumptions,
            "unknowns": self.unknowns,
            "meta": self.meta,
            "verifiable_total": self.verifiable_total,
            "hallucination_rate": round(self.hallucination_rate, 4),
            "citation_coverage": round(self.citation_coverage, 4),
            "citation_accuracy": round(self.citation_accuracy, 4),
            "numeric_claims": self.numeric_claims,
            "numeric_matched": self.numeric_matched,
            "numeric_accuracy": round(self.numeric_accuracy, 4),
            "fabricated_citation_count": self.fabricated_citation_count,
            "cutoff_violations": self.cutoff_violations,
        }


def _content_words(text: str) -> set[str]:
    return {word for word in _WORD_RE.findall((text or "").lower()) if word not in _STOPWORDS}


def overlap_score(claim_text: str, evidence_text: str) -> float:
    """Containment of the claim's content words in the evidence (0–1)."""
    claim_words = _content_words(claim_text)
    if not claim_words:
        return 0.0
    return len(claim_words & _content_words(evidence_text)) / len(claim_words)


def _match_numbers(claim_numbers: list[NumericMention], evidence_text: str) -> tuple[int, int, list[float]]:
    """Return (checked, matched, unmatched claim values)."""
    evidence_numbers = extract_numbers(evidence_text)
    matched = 0
    unmatched: list[float] = []
    for mention in claim_numbers:
        candidates = [other for other in evidence_numbers if comparable(mention, other)]
        if any(
            values_match(
                mention.value,
                other.value,
                tolerance_pct=NUMERIC_TOLERANCE_PCT,
                absolute_tolerance=0.05 if mention.unit is Unit.PERCENT else None,
            )
            for other in candidates
        ):
            matched += 1
        else:
            unmatched.append(mention.value)
    return len(claim_numbers), matched, unmatched


def _score_against(
    claim: ExtractedClaim, evidence: EvidenceItem
) -> tuple[ClaimSupport, float, int, int, str]:
    overlap = overlap_score(claim.text, evidence.text)
    checked, matched, unmatched = _match_numbers(claim.numbers, evidence.text)

    if checked:
        if matched == checked and overlap >= WEAK_OVERLAP:
            return (
                ClaimSupport.DIRECTLY_SUPPORTED,
                overlap,
                checked,
                matched,
                "all figures and wording match the cited passage",
            )
        if matched == checked:
            return (
                ClaimSupport.PARTIALLY_SUPPORTED,
                overlap,
                checked,
                matched,
                "figures match but the passage discusses a different subject",
            )
        if matched > 0:
            return (
                ClaimSupport.PARTIALLY_SUPPORTED,
                overlap,
                checked,
                matched,
                f"{matched} of {checked} figures found in the cited passage",
            )
        # No figure matched: a comparable figure in the passage means contradiction;
        # no comparable figure means the citation is simply irrelevant.
        evidence_numbers = extract_numbers(evidence.text)
        if any(comparable(mention, other) for mention in claim.numbers for other in evidence_numbers):
            return (
                ClaimSupport.CONTRADICTED,
                overlap,
                checked,
                matched,
                f"cited passage reports different values (claim: {unmatched})",
            )
        return (
            ClaimSupport.UNSUPPORTED,
            overlap,
            checked,
            matched,
            "cited passage contains none of the claimed figures",
        )

    if overlap >= STRONG_OVERLAP:
        return ClaimSupport.DIRECTLY_SUPPORTED, overlap, 0, 0, "wording is supported by the cited passage"
    if overlap >= WEAK_OVERLAP:
        return ClaimSupport.PARTIALLY_SUPPORTED, overlap, 0, 0, "only partially reflected in the passage"
    return ClaimSupport.UNSUPPORTED, overlap, 0, 0, "cited passage does not discuss this claim"


def verify_claims(
    claims: list[ExtractedClaim], evidence: list[EvidenceItem], *, cutoff_iso: str | None = None
) -> VerificationReport:
    """Classify every claim against the evidence the agent actually retrieved."""
    evidence_by_id = {item.chunk_id: item for item in evidence}
    report = VerificationReport(verdicts=[])

    for claim in claims:
        if claim.kind in (ClaimKind.ASSUMPTION, ClaimKind.UNKNOWN, ClaimKind.META):
            support, explanation, counter = {
                ClaimKind.ASSUMPTION: (
                    ClaimSupport.ASSUMED,
                    "explicitly labelled as an assumption",
                    "assumptions",
                ),
                ClaimKind.UNKNOWN: (
                    ClaimSupport.UNKNOWN,
                    "explicitly labelled as unknown",
                    "unknowns",
                ),
                ClaimKind.META: (
                    ClaimSupport.UNKNOWN,
                    "statement about the research process, not a factual assertion",
                    "meta",
                ),
            }[claim.kind]
            setattr(report, counter, getattr(report, counter) + 1)
            report.verdicts.append(
                ClaimVerdict(claim=claim, support_level=support, explanation=explanation)
            )
            continue

        fabricated = [chunk_id for chunk_id in claim.cited_chunk_ids if chunk_id not in evidence_by_id]
        cited_items = [
            evidence_by_id[chunk_id] for chunk_id in claim.cited_chunk_ids if chunk_id in evidence_by_id
        ]

        best: tuple[ClaimSupport, float, int, int, str, EvidenceItem] | None = None
        for item in cited_items:
            support, similarity, checked, matched, explanation = _score_against(claim, item)
            if (
                best is None
                or _rank(support) > _rank(best[0])
                or (_rank(support) == _rank(best[0]) and similarity > best[1])
            ):
                best = (support, similarity, checked, matched, explanation, item)

        if best is None:
            # Uncited (or only fabricated citations): search all retrieved evidence. A claim
            # the evidence supports but does not cite is INFERRED, not a hallucination.
            for item in evidence:
                support, similarity, checked, matched, _ = _score_against(claim, item)
                if support in (
                    ClaimSupport.DIRECTLY_SUPPORTED,
                    ClaimSupport.PARTIALLY_SUPPORTED,
                ) and (best is None or similarity > best[1]):
                        best = (
                            ClaimSupport.INFERRED,
                            similarity,
                            checked,
                            matched,
                            "supported by retrieved evidence but not cited",
                            item,
                        )

        if best is None:
            verdict = ClaimVerdict(
                claim=claim,
                support_level=ClaimSupport.UNSUPPORTED,
                explanation=(
                    "no retrieved passage supports this claim"
                    if not fabricated
                    else "citation refers to a passage that was never retrieved"
                ),
                fabricated_citations=fabricated,
            )
        else:
            support_level, similarity, checked, matched, explanation, item = best
            verdict = ClaimVerdict(
                claim=claim,
                support_level=support_level,
                matched_chunk_id=item.chunk_id,
                evidence_quote=item.text[:400],
                similarity=round(similarity, 4),
                numbers_checked=checked,
                numbers_matched=matched,
                explanation=explanation,
                fabricated_citations=fabricated,
            )
            report.numeric_claims += 1 if checked else 0
            report.numeric_matched += 1 if checked and matched == checked else 0

        report.fabricated_citation_count += len(fabricated)
        if cutoff_iso and verdict.matched_chunk_id:
            item = evidence_by_id.get(verdict.matched_chunk_id)
            if item and item.publication_timestamp and item.publication_timestamp.isoformat() > cutoff_iso:
                report.cutoff_violations.append(verdict.matched_chunk_id)

        attribute = {
            ClaimSupport.DIRECTLY_SUPPORTED: "supported",
            ClaimSupport.PARTIALLY_SUPPORTED: "partially_supported",
            ClaimSupport.INFERRED: "inferred",
            ClaimSupport.UNSUPPORTED: "unsupported",
            ClaimSupport.CONTRADICTED: "contradicted",
        }.get(verdict.support_level)
        if attribute:
            setattr(report, attribute, getattr(report, attribute) + 1)
        report.verdicts.append(verdict)

    return report


def _rank(support: ClaimSupport) -> int:
    return {
        ClaimSupport.DIRECTLY_SUPPORTED: 5,
        ClaimSupport.PARTIALLY_SUPPORTED: 4,
        ClaimSupport.INFERRED: 3,
        ClaimSupport.UNKNOWN: 2,
        ClaimSupport.ASSUMED: 2,
        ClaimSupport.CONTRADICTED: 1,
        ClaimSupport.UNSUPPORTED: 0,
    }.get(support, 0)
