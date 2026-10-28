"""Retrieval prototype (Nate Herk N6).

Token-overlap retrieval over a synthetic corpus, scored by Jaccard
similarity. Scores are surfaced on every result and are never used as
permission: the caller decides what to do with a result. An empty query
is rejected. The corpus is never mutated. Stdlib only. Synthetic data
only. No network, no sending.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"\w+")


class RetrievalError(Exception):
    """Raised for an empty query."""


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def retrieve(corpus: list[dict], query: str) -> list[dict]:
    """Return every record ranked by Jaccard score, highest first.

    Ties keep corpus order (stable sort). Scores are in [0, 1].
    """
    query_tokens = _tokens(query)
    if not query_tokens:
        raise RetrievalError("empty query")
    scored = []
    for record in corpus:
        record_tokens = _tokens(record["text"])
        overlap = query_tokens & record_tokens
        union = query_tokens | record_tokens
        score = len(overlap) / len(union) if union else 0.0
        scored.append({"id": record["id"], "text": record["text"], "score": score})
    scored.sort(key=lambda r: -r["score"])
    return scored
