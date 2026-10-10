"""Deterministic offline embedding provider.

A hashed bag-of-words (unigram + bigram) representation with sub-linear term weighting and
L2 normalisation. It is **lexical, not semantic** — two texts must share words to look
similar.

It exists so ingestion, retrieval, citation verification and the evaluation pipeline work
with no third-party credentials. It is labelled ``deterministic-mock`` everywhere it
surfaces and is never described as a production embedding model.
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from collections import Counter

import numpy as np

from finagent_core.embeddings.base import EMBEDDING_DIM, EmbeddingProvider, EmbeddingResult

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\.\-%$]*")

#: Extremely common words carry no retrieval signal in financial text.
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in is it its of on or that the to was were
    will with we our their this these those which not been but they he she""".split()
)


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall((text or "").lower()) if token not in _STOPWORDS]


def _bucket(token: str, dimension: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimension


class DeterministicEmbeddingProvider(EmbeddingProvider):
    key = "deterministic"
    display_name = "Deterministic hashed embedding (mock)"
    model = "deterministic-mock-v1"
    requires_credentials = False

    def __init__(self, *, dimension: int = EMBEDDING_DIM) -> None:
        super().__init__()
        self.dimension = dimension

    def embed(self, texts: list[str]) -> EmbeddingResult:
        started = time.perf_counter()
        vectors: list[list[float]] = []
        total_tokens = 0
        for text in texts:
            tokens = _tokenize(text)
            total_tokens += len(tokens)
            bigrams = [f"{first}_{second}" for first, second in zip(tokens, tokens[1:])]
            counts = Counter(tokens)
            counts.update(Counter(bigrams))
            vector = np.zeros(self.dimension, dtype=np.float32)
            for term, count in counts.items():
                weight = 1.0 + math.log(count)
                # Two hashes per term reduce collision damage in a fixed-width space.
                vector[_bucket(term, self.dimension)] += weight
                vector[_bucket(term + "#2", self.dimension)] += weight * 0.5
            norm = float(np.linalg.norm(vector))
            if norm > 0:
                vector /= norm
            vectors.append(vector.tolist())
        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            provider=self.key,
            dimension=self.dimension,
            input_tokens=total_tokens,
            is_mock=True,
            latency_ms=max(1, int((time.perf_counter() - started) * 1000)),
            detail={"note": "Lexical hashed embedding for offline operation. Not a semantic model."},
        )
