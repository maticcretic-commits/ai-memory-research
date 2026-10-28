"""retrieval — the retriever interface for recall evals + a harness baseline.

HONESTY NOTE: mm.temporal.score is still a v0.1 stub (interface only).
This module's `BaselineRetriever` is the HARNESS's own deterministic
retriever (TF-IDF cosine + recency + salience fusion), used so the recall
protocol, metrics, and reports are exercised end-to-end today. It is NOT
mm/temporal and its numbers measure the baseline, not the milestone's
memory. When mm.temporal is implemented, it plugs in via `Retriever`
below and this baseline becomes the "beat me" reference.

Fusion (documented priors, tunable):
  score = 0.55 * tfidf_cosine + 0.25 * recency + 0.20 * salience
Recency decays exponentially with a 30-day half-life against the
question date; salience is the record's salience field (default 0.5).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime

from mm.episodic import valid_at_day, valid_at_instant
from mm.reflect import MemoryRecord
from mm.temporal import RankedEvidence

_TOKEN = re.compile(r"[a-z0-9']+")

W_LEX, W_REC, W_SAL = 0.55, 0.25, 0.20
RECENCY_HALFLIFE_DAYS = 30.0


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _tfidf_matrix(docs: list[list[str]]) -> tuple[list[dict[str, float]], dict[str, float]]:
    """Return (doc tf-idf vectors, idf map). Small-corpus, in-memory."""
    df: Counter[str] = Counter()
    tf_vecs: list[Counter[str]] = []
    for toks in docs:
        c = Counter(toks)
        tf_vecs.append(c)
        for t in c:
            df[t] += 1
    n = len(docs)
    idf = {t: math.log((1 + n) / (1 + f)) + 1.0 for t, f in df.items()}
    vecs = []
    for c in tf_vecs:
        total = sum(c.values()) or 1
        vecs.append({t: (f / total) * idf[t] for t, f in c.items()})
    return vecs, idf


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    num = sum(a[t] * b.get(t, 0.0) for t in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return num / (na * nb)


def parse_lmeval_date(s: str) -> datetime:
    """Parse LongMemEval date strings like '2023/05/30 (Tue) 23:40'."""
    m = re.match(r"(\d{4})/(\d{2})/(\d{2}).*?(\d{2}):(\d{2})", s)
    if not m:
        raise ValueError(f"unparseable date {s!r}")
    y, mo, d, h, mi = map(int, m.groups())
    return datetime(y, mo, d, h, mi)


class Retriever:
    """Interface the recall runner uses. mm.temporal plugs in here."""

    name = "interface"

    def rank(self, records: list[MemoryRecord], query: str,
             now: datetime | None = None) -> list[RankedEvidence]:
        raise NotImplementedError


_TURN_START = re.compile(r"(?m)^\[.*?\]\s")


def _turn_chunks(text: str, window: int = 3) -> list[str]:
    """Split a session text into turn-window chunks.

    Session texts are turns rendered as '[role] content' lines. A
    chunk is up to `window` consecutive turns. Text without turn
    markers falls back to paragraph chunks; a short text is one chunk.
    """
    starts = [m.start() for m in _TURN_START.finditer(text)]
    if len(starts) < 2:
        paras = [p for p in text.split("\n\n") if p.strip()]
        return paras or [text]
    turns = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        turns.append(text[s:e].strip())
    return ["\n".join(turns[i:i + window])
            for i in range(0, len(turns), window)]


class ChunkedRetriever(Retriever):
    """Turn-window chunked TF-IDF (benchmark wave B1, voted 2026-10-20).

    Same fusion weights as BaselineRetriever; the ONLY change is
    granularity: TF-IDF runs over turn-window chunks and a record's
    lexical score is its best chunk's cosine. Isolates whether
    session-level indexing is the recall ceiling. Harness reference,
    not mm.temporal.
    """

    name = "chunked-tfidf-w3"

    def rank(self, records: list[MemoryRecord], query: str,
             now: datetime | None = None) -> list[RankedEvidence]:
        now = now or datetime.utcnow()
        chunks: list[list[str]] = []
        owners: list[int] = []
        for ri, rec in enumerate(records):
            for ch in _turn_chunks(rec.text):
                chunks.append(_tokens(ch))
                owners.append(ri)
        vecs, idf = _tfidf_matrix(chunks)
        q = _tokens(query)
        qc = Counter(q)
        qtotal = sum(qc.values()) or 1
        qvec = {t: (f / qtotal) * idf.get(t, math.log(2 + len(chunks)))
                for t, f in qc.items()}
        best: dict[int, float] = {}
        for ci, vec in enumerate(vecs):
            lex = _cosine(qvec, vec)
            ri = owners[ci]
            if lex > best.get(ri, -1.0):
                best[ri] = lex
        out: list[RankedEvidence] = []
        for ri, rec in enumerate(records):
            lex = best.get(ri, 0.0)
            age_days = max(0.0, (now - rec.timestamp).total_seconds()
                           / 86400.0)
            recency = 0.5 ** (age_days / RECENCY_HALFLIFE_DAYS)
            sal = max(0.0, min(1.0, rec.salience))
            score = W_LEX * lex + W_REC * recency + W_SAL * sal
            out.append(RankedEvidence(
                record=rec, score=score,
                signals={"lexical": lex, "recency": recency,
                         "salience": sal,
                         "fusion": {"lexical": W_LEX, "recency": W_REC,
                                    "salience": W_SAL}},
            ))
        out.sort(key=lambda e: e.score, reverse=True)
        return out


class ValidWindowRetriever(Retriever):
    """B2 measurement wrapper (Benchmark Wave 2): chunked TF-IDF
    over only the records IN FORCE at the query instant
    (mm.episodic.valid_at_instant - the one window rule).

    A record whose validity window excludes `now` never
    surfaces: a superseded fact stops answering after its
    invalid_at, and a record dated after the question (future
    leakage) cannot win on recency. Ranking itself is delegated
    unchanged to ChunkedRetriever, so any delta against plain
    chunked is the window filter alone. n_filtered accumulates
    across rank() calls for the run report."""

    name = "chunked-tfidf-w3-instantwindow"

    def __init__(self, inner: ChunkedRetriever | None = None) -> None:
        self.inner = inner or ChunkedRetriever()
        self.n_filtered = 0

    def rank(self, records: list[MemoryRecord], query: str,
             now: datetime | None = None) -> list[RankedEvidence]:
        now = now or datetime.utcnow()
        kept = [r for r in records if valid_at_instant(r, now)]
        self.n_filtered += len(records) - len(kept)
        return self.inner.rank(kept, query, now=now)


class DayWindowRetriever(Retriever):
    """B2 granularity follow-up: the valid-window chunked
    retriever read at DAY precision (mm.episodic.valid_at_day).
    Same wrapper shape as ValidWindowRetriever - ranking is
    delegated unchanged to ChunkedRetriever, so any delta
    against the instant window is the precision alone. Exists
    because the Wave 2 correction measured the instant rule
    taxing a day-granular corpus (74 gold sessions filtered,
    temporal R@10 -0.143); a record valid TOMORROW is still
    excluded - only same-day later-hour records change
    treatment. n_filtered accumulates across rank() calls."""

    name = "chunked-tfidf-w3-daywindow"

    def __init__(self, inner: ChunkedRetriever | None = None) -> None:
        self.inner = inner or ChunkedRetriever()
        self.n_filtered = 0

    def rank(self, records: list[MemoryRecord], query: str,
             now: datetime | None = None) -> list[RankedEvidence]:
        now = now or datetime.utcnow()
        kept = [r for r in records if valid_at_day(r, now)]
        self.n_filtered += len(records) - len(kept)
        return self.inner.rank(kept, query, now=now)


class BaselineRetriever(Retriever):
    """Deterministic harness baseline: TF-IDF + recency + salience fusion.

    Documented reference only — see module docstring. Numbers from this
    retriever are the floor mm.temporal must beat once implemented.
    """

    name = "baseline-tfidf"

    def rank(self, records: list[MemoryRecord], query: str,
             now: datetime | None = None) -> list[RankedEvidence]:
        now = now or datetime.utcnow()
        doc_toks = [_tokens(r.text) for r in records]
        vecs, idf = _tfidf_matrix(doc_toks)
        q = _tokens(query)
        qc = Counter(q)
        qtotal = sum(qc.values()) or 1
        qvec = {t: (f / qtotal) * idf.get(t, math.log(2 + len(records))) for t, f in qc.items()}

        out: list[RankedEvidence] = []
        for rec, vec in zip(records, vecs):
            lex = _cosine(qvec, vec)
            age_days = max(0.0, (now - rec.timestamp).total_seconds() / 86400.0)
            recency = 0.5 ** (age_days / RECENCY_HALFLIFE_DAYS)
            sal = max(0.0, min(1.0, rec.salience))
            score = W_LEX * lex + W_REC * recency + W_SAL * sal
            out.append(RankedEvidence(
                record=rec, score=score,
                signals={"lexical": lex, "recency": recency, "salience": sal,
                         "fusion": {"lexical": W_LEX, "recency": W_REC,
                                    "salience": W_SAL}},
            ))
        out.sort(key=lambda e: e.score, reverse=True)
        return out
