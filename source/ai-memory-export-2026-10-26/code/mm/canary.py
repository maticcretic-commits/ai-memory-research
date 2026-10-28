"""canary - canary memories by default (Red-Team Round 5).

Grok's proposal from the Round-1 sweep (corpus 3363): plant
memories whose ONLY job is to be stolen. A canary record is
bait - plausible, high-interest synthetic content carrying a
per-store unique marker - seeded into the store like any
record. Nobody legitimate ever needs to read one. So a read
of a canary is never a borderline case to adjudicate: it is
the extraction signal itself, the tripwire a real memory
cannot provide (a real record's read might be innocent; a
canary's cannot).

Mechanics:

- seed_canaries(store, count) writes `count` canary records
  through the store's write path (the gate is the only way
  in - canaries are admitted records, owner "canary",
  source "canary/seed", each carrying a marker unique to
  this store: CANARY-<hex>). Seeding is idempotent per store:
  a store that already holds canaries returns them.
- CanaryWatch holds the canary id set. Wired into the store
  (canary_watch=...), it is told about every record the
  reader-facing read methods RETURN (get / search /
  all_records and the authorized get_for / search_for /
  all_records_for), with the actor (reader id, or "raw" for
  the unauthenticated API). The store's internal snapshot
  path - the write gate's input snapshot, the janitor's
  wiring, episode assembly's class-uniqueness scan - is the
  named system path and is NOT noted: system components
  scanning the store are not extractions, and counting them
  would make the tripwire cry wolf on every gate write.
- A noted canary access is a TRIP: recorded on the watch
  (record id, actor, time) and fed to the sentinel's
  canary_trip channel when a sentinel is attached.
- Deployment posture (the "by default" of 3363): stores
  opened for deployment seed canaries - SQLiteStore(...,
  canaries=N) seeds at construction and auto-wires a watch.
  The low-level default stays canaries=0: every existing
  suite's fixture accounting (record counts, gate-log
  lengths) was built against unseeded stores, and flipping
  the constructor default would silently rewrite all of it.
  Disclosed in the Round-5 preregistration, not smuggled.

Honest limits: a trip proves a read happened through a
reader-facing path; it does not identify a human, and an
attacker who never touches the bait topics never trips it -
canaries detect extraction that SAMPLES the store, which is
what bulk extraction (and answer-smuggling) does. A reader
with the system flag is not noted (in-process trust boundary,
declared since Round 1). Canaries seeded while G5c
enforcement is wired would face the band rule like any
unproven source's filings - seed at store creation, before
enforcement wiring, as the factory order does.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime

from mm.reflect import MemoryRecord, Provenance

CANARY_OWNER = "canary"
CANARY_SOURCE = "canary/seed"

# Bait topics: the things an extractor (or a poisoner probing
# the store) goes looking for - reserves, deploy control,
# escalation paths. Each template passes the write gate
# honestly (actionable, concrete, specific) and carries the
# per-store marker.
_TEMPLATES = [
    ("Quarterly contingency reserve protocol: hold {n} units "
     "in reserve vault V-{v}; the release marker is {marker}; "
     "verify the reserve balance with finance at 10:00 and "
     "record the check in ledger L-{v}."),
    ("Production deploy freeze window: deploy freeze starts "
     "at 18:00 on day {v} and the rollback code is RB-{n}; "
     "the freeze marker is {marker}; check the freeze board "
     "before any deploy and record exceptions in log F-{v}."),
    ("Founder escalation protocol: escalation path E-{v} "
     "routes urgent pages to the duty desk at extension {n}; "
     "the escalation marker is {marker}; verify the duty "
     "roster at 08:00 and record the verification in book "
     "E-{v}."),
    ("Vendor payment hold list: hold vendor payments above "
     "{n} units until review R-{v} closes; the hold marker "
     "is {marker}; check the hold list at 09:30 and record "
     "each release in register P-{v}."),
]


@dataclass
class CanaryTrip:
    record_id: str
    actor: str
    at: float


@dataclass
class CanaryWatch:
    """The tripwire registry: which records are canaries, and
    every noted access to one."""

    sentinel: object | None = None
    _canaries: dict[str, str] = field(default_factory=dict)
    trips: list[CanaryTrip] = field(default_factory=list)

    def register(self, record_id: str, marker: str = "") -> None:
        self._canaries[record_id] = marker

    def is_canary(self, record_id: str) -> bool:
        return record_id in self._canaries

    def canary_ids(self) -> list[str]:
        return sorted(self._canaries)

    def note_access(self, record_id: str, actor: str = "raw",
                    at: float | None = None) -> bool:
        """One record was returned by a reader-facing read.
        Returns True if it was a canary (a trip). System reads
        are the store's own business and are never noted by
        the store; a caller passing actor="system" is likewise
        not a trip."""
        if record_id not in self._canaries or actor == "system":
            return False
        when = time.time() if at is None else at
        self.trips.append(CanaryTrip(record_id=record_id,
                                     actor=actor, at=when))
        if self.sentinel is not None:
            self.sentinel.observe(
                "canary_trip", 1.0, when,
                detail=(f"canary {record_id} read by "
                        f"{actor!r} (marker "
                        f"{self._canaries[record_id]})"))
        return True

    @property
    def trip_count(self) -> int:
        return len(self.trips)


def seed_canaries(store, count: int = 3,
                  watch: CanaryWatch | None = None
                  ) -> list[MemoryRecord]:
    """Seed (or return the existing) canary records for a
    store. Records go through store.write - the gate is the
    only way in. If a watch is given, every seeded canary is
    registered on it."""
    existing = [r for r in store.snapshot().values()
                if r.owner == CANARY_OWNER
                and r.source == CANARY_SOURCE]
    if existing:
        if watch is not None:
            for r in existing:
                watch.register(r.id, _marker_of(r))
        return existing
    marker = "CANARY-" + secrets.token_hex(4).upper()
    out: list[MemoryRecord] = []
    for i in range(count):
        tmpl = _TEMPLATES[i % len(_TEMPLATES)]
        text = tmpl.format(n=4200 + 137 * i, v=3 + i, marker=marker)
        rec = MemoryRecord(
            id=f"canary-{i + 1}-{marker[-4:].lower()}",
            text=text, content=text,
            timestamp=datetime(2026, 10, 21),
            source=CANARY_SOURCE, salience=0.6, type="fact",
            epistemic_tier="observed", explicit=False,
            owner=CANARY_OWNER, gathered_how="episodic/canary-seed",
            provenance=Provenance(confidence=0.6))
        outcome = store.write(rec)
        if outcome.verdict == "admitted":
            out.append(rec)
            if watch is not None:
                watch.register(rec.id, marker)
    return out


def _marker_of(record: MemoryRecord) -> str:
    for tok in (record.content or record.text).split():
        if tok.startswith("CANARY-"):
            return tok.rstrip(";.")
    return ""


__all__ = ["CANARY_OWNER", "CANARY_SOURCE", "CanaryTrip",
           "CanaryWatch", "seed_canaries"]
