"""temporal — temporal fusion ranker: recency × salience, time-aware.

v0.1 STUB: interface only. Not implemented.

Scores evidence by recency × salience with multi-signal fusion (semantic
similarity + lexical match + entity overlap), so ranking never acts on stale
facts and never ignores a highly salient old memory. This is the retrieval
hygiene every downstream decision depends on.

Pattern update (v0.2): outcome-weighted utility — records whose evidence
helped past decisions get a utility boost in fusion (synthesis-all Tier 2:
hippo-memory/memoripy per-memory outcome feedback). Amygdala salience: every
record carries a salience field set at ingest (prediction-error magnitude,
user emphasis, error cost); decay is salience-dependent — Ebbinghaus curve
with per-record time constants. Two-level forgetting: retrieval decay (fast,
reversible strength loss) vs storage pruning (only after sustained
sub-threshold retrieval across a consolidation cycle) — forgetting as
generalization, not janitor.

Pattern inspiration: mem0 temporal reasoning + parallel fusion; graphiti
time-bounded edges; claude-mem progressive disclosure (cost-aware
retrieval); neuro track §§5, 11 (amygdala tagging; Ebbinghaus/adaptive
forgetting).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mm.reflect import MemoryRecord


@dataclass
class RankedEvidence:
    record: MemoryRecord
    score: float                      # combined recency × salience × signals
    signals: dict                     # per-signal breakdown, e.g. {"semantic": .8, "lexical": .4}


def score(
    records: list[MemoryRecord],
    query: str,
    now: datetime | None = None,
) -> list[RankedEvidence]:
    """Rank records for `query` by recency × salience × multi-signal fusion.

    Returns records ranked descending. Old-but-salient memories must survive;
    fresh-but-trivial ones must not dominate.

    TODO (research): the recency decay curve (exponential? Ebbinghaus-like?
    task-dependent?); fusion weights (learned? fixed? per-query?); where
    progressive disclosure / cost-bounded tiers plug in. See ARCHITECTURE.md §5.
    """
    raise NotImplementedError(
        "v0.1 stub — implement once the decay curve, fusion weights, and "
        "cost-tier policy are defined (ARCHITECTURE.md §5, open questions)."
    )
