"""Chunking that preserves citation provenance.

Chunks never span pages: a chunk covering pages 41–42 could not be cited precisely.
Sentence boundaries are respected where possible so a cited quote reads as a whole claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from finagent_ingestion.extraction import ExtractedDocument

_SENTENCE_END = re.compile(r"(?<=[.!?:;])\s+")
_WHITESPACE = re.compile(r"[ \t]+")

DEFAULT_CHUNK_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 150


@dataclass
class Chunk:
    chunk_index: int
    page_number: int
    text: str
    token_count: int
    char_start: int
    char_end: int
    publication_timestamp: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def estimate_tokens(text: str) -> int:
    """Approximate token count (~4 characters/token)."""
    return max(1, len(text) // 4)


def chunk_page(
    text: str, *, chunk_chars: int = DEFAULT_CHUNK_CHARS, overlap_chars: int = DEFAULT_OVERLAP_CHARS
) -> list[tuple[str, int, int]]:
    """Split one page into (text, char_start, char_end) windows."""
    cleaned = _WHITESPACE.sub(" ", text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_chars:
        return [(cleaned, 0, len(cleaned))]

    windows: list[tuple[str, int, int]] = []
    buffer: list[str] = []
    start = 0
    cursor = 0
    for sentence in _SENTENCE_END.split(cleaned):
        candidate_len = sum(len(part) + 1 for part in buffer) + len(sentence)
        if buffer and candidate_len > chunk_chars:
            body = " ".join(buffer)
            windows.append((body, start, start + len(body)))
            # Carry the tail forward so context is not cut mid-argument.
            carry: list[str] = []
            carry_len = 0
            for part in reversed(buffer):
                if carry_len + len(part) > overlap_chars:
                    break
                carry.insert(0, part)
                carry_len += len(part) + 1
            buffer = carry
            start = max(0, cursor - carry_len)
        buffer.append(sentence)
        cursor += len(sentence) + 1
    if buffer:
        body = " ".join(buffer)
        windows.append((body, start, start + len(body)))
    return windows


def chunk_document(
    document: ExtractedDocument,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    publication_timestamp: datetime | None = None,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in document.pages:
        for text, char_start, char_end in chunk_page(
            page.text, chunk_chars=chunk_chars, overlap_chars=overlap_chars
        ):
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    page_number=page.page_number,
                    text=text,
                    token_count=estimate_tokens(text),
                    char_start=char_start,
                    char_end=char_end,
                    publication_timestamp=publication_timestamp,
                    metadata={"pagination": document.pagination},
                )
            )
    return chunks
