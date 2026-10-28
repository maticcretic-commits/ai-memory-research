"""echolocation - active self-probing (instinct 3).

Memory does not wait to be asked; it pings its own store and reads the
echo. evals/consolidation_probe.py is the prototype (fixed probe set,
gains AND regressions measured). This module generalizes it:

- Canary records: known-answer records planted at write time; the mind
  periodically probes for them. A canary that stops being retrievable
  is a store-health alarm (the rehydration test for cold storage).
- Probe kinds: staleness (archived records whose content still answers
  live questions = shadow-index rehydration candidates), contradiction
  (declared-contradiction pairs whose dispute is unresolved), coverage
  (probe queries from the consolidation harness).
- The foraging rule: a probe branch is abandoned when its marginal
  yield drops below the running average - probing can never loop
  forever.
- Findings are written BACK to the memory itself (through the write
  gate, as records) - the agent remembers what its probing found.

Rule-based, zero LLM. Scheduled, never on the reflex path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Foraging rule: abandon a probe branch when marginal yield < k * mean.
FORAGE_K = 0.5
# A canary unretrievable after this many consecutive failed pings alarms.
CANARY_ALARM_AFTER = 3


@dataclass
class ProbeFinding:
    kind: str            # canary | staleness | contradiction | coverage
    record_ids: list[str]
    detail: str
    at: str = ""


@dataclass
class CanaryRecord:
    """A known-answer record planted at write time."""
    record_id: str
    query: str           # the probe query that must retrieve it
    consecutive_misses: int = 0


def _now() -> str:
    return datetime.utcnow().isoformat()


class SelfProber:
    """The echolocation organ. Owns no store; probes the caller's store."""

    def __init__(self, forage_k: float = FORAGE_K) -> None:
        self.forage_k = forage_k
        self.canaries: dict[str, CanaryRecord] = {}
        self._yields: list[float] = []   # marginal yields for the rule

    # -- canaries ------------------------------------------------------------

    def plant_canary(self, record_id: str, query: str) -> CanaryRecord:
        c = CanaryRecord(record_id=record_id, query=query)
        self.canaries[record_id] = c
        return c

    def ping_canary(self, store, sentinel=None) -> ProbeFinding | None:
        """Ping every canary. The live index answers; an archived canary
        is unretrievable by design, so archived hits do not count. Returns
        a finding for the first alarming canary (consecutive misses >=
        CANARY_ALARM_AFTER); sentinel is fed the miss rate regardless."""
        for c in self.canaries.values():
            hits = store.search(c.query, limit=5)
            live = {r.id for r in hits if r.tier != "archive"}
            if c.record_id in live:
                c.consecutive_misses = 0
            else:
                c.consecutive_misses += 1
            if sentinel is not None:
                sentinel.observe(
                    "access_gap_s", float(c.consecutive_misses),
                    at=datetime.utcnow().timestamp(),
                    detail=f"canary {c.record_id} miss")
            if c.consecutive_misses >= CANARY_ALARM_AFTER:
                return ProbeFinding(
                    kind="canary", record_ids=[c.record_id], at=_now(),
                    detail=(f"canary {c.record_id!r} unretrievable for "
                            f"{c.consecutive_misses} pings - store-health "
                            "alarm"))
        return None

    # -- staleness: archived records that still answer live questions --------

    def probe_staleness(self, store, queries: list[str],
                        limit: int = 5) -> ProbeFinding | None:
        """Archived records echoing back through the shadow index are
        rehydration candidates - the cold-storage test. Bounded by the
        foraging rule."""
        archived_hits: list[str] = []
        yields: list[float] = []
        for q in queries:
            hits = store.search(q, limit=limit)
            old = [r.id for r in hits if r.tier == "archive"]
            y = len(old) / max(1, len(hits))
            yields.append(y)
            self._yields.append(y)
            mean = sum(self._yields) / len(self._yields)
            if y < self.forage_k * mean and self._yields:
                break  # foraging rule: abandon this branch
            archived_hits.extend(old)
        if archived_hits:
            return ProbeFinding(
                kind="staleness", record_ids=sorted(set(archived_hits)),
                at=_now(),
                detail=(f"{len(set(archived_hits))} archived records still "
                        "answer live queries - rehydration candidates"))
        return None

    # -- contradiction: declared disputes with no resolution -----------------

    def probe_contradictions(self, store) -> ProbeFinding | None:
        """Declared-contradiction pairs where neither side is superseded
        and the dispute is still open."""
        records = store.all_records()
        open_disputes: list[str] = []
        for r in records.values():
            if not r.provenance.contradicts:
                continue
            for other_id in r.provenance.contradicts:
                other = records.get(other_id)
                if other is None:
                    continue
                if (not r.superseded_with_replacement
                        and not other.superseded_with_replacement):
                    open_disputes.append(r.id)
                    break
        if open_disputes:
            return ProbeFinding(
                kind="contradiction", record_ids=sorted(set(open_disputes)),
                at=_now(),
                detail=(f"{len(set(open_disputes))} records carry unresolved "
                        "declared contradictions"))
        return None

    # -- full scheduled pass -------------------------------------------------

    def run(self, store, queries: list[str] | None = None,
            sentinel=None) -> list[ProbeFinding]:
        """One scheduled echolocation pass. Returns findings (possibly
        empty). Findings are for the caller to write back through the
        gate - the prober never writes."""
        findings: list[ProbeFinding] = []
        canary_alarm = self.ping_canary(store, sentinel=sentinel)
        if canary_alarm is not None:
            findings.append(canary_alarm)
        stale = self.probe_staleness(store, queries or [])
        if stale is not None:
            findings.append(stale)
        contra = self.probe_contradictions(store)
        if contra is not None:
            findings.append(contra)
        return findings
