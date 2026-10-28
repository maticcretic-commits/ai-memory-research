"""janitor_live - the Janitor wired to the REAL store (Phase-3 chunk 3).

What "live" means here, honestly:
- The store is the production SQLite store (mm.storage.SQLiteStore) at
  data/memory.db - the same file every future run uses. It is seeded
  ONCE (only when empty) with genuine records OF THIS PROJECT, written
  through the write gate like any other memory: the milestone's own
  decisions and events, with their REAL dates (created_at = when the
  event actually happened, Oct 13-20 2026). Nothing is backdated beyond
  its real event date, so lifecycle outcomes are whatever the rules
  produce on real ages - mostly decay ops at this project's age.
- Access events are REAL retrieval events: this harness runs actual
  searches against the store and logs every returned record as an
  access, exactly as a retrieval layer would. No synthetic history is
  manufactured to force a half-life number.
- Half-life therefore reports what the estimator honestly says on the
  accumulated log: "insufficient-data" until a ttl_class has >= 30
  inter-access intervals (mm.janitor.MIN_HALFLIFE_SAMPLES). The first
  real numbers ARE the insufficient-data report + n + censored counts -
  the instrumentation is live and counting from today.

Run order (every invocation, idempotent):
  1. seed if empty (through the gate; outcomes printed)
  2. retrieval probe pass (real searches -> real access events)
  3. Janitor DRY-RUN against the store (report only, nothing mutates)
  4. Janitor LIVE run (metadata persisted via the whitelist)
  5. half-life report from the PERSISTED access log (fresh Janitor)

Intended schedule (documented, installed by the parent via the existing
cron system - this harness is the wired entry point):
  hourly: python3 -m evals.janitor_live   (from the repo root)

Run:  python3 -m evals.janitor_live [--db PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from mm.janitor import Janitor
from mm.reflect import MemoryRecord, Provenance
from mm.storage import SQLiteStore

DEFAULT_DB = "/home/hatch/workspace/ai-memory-milestone/data/memory.db"
OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")


def _ts(y: int, mo: int, d: int, h: int = 10) -> float:
    return datetime(y, mo, d, h, tzinfo=timezone.utc).timestamp()


def _rec(rid: str, text: str, rtype: str, tier_ep: str, ttl: str,
         when: float, conf: float = 0.9, source: str = "project-record",
         explicit: bool = True, supersedes: list[str] | None = None
         ) -> MemoryRecord:
    return MemoryRecord(
        id=rid, text=text, content=text,
        timestamp=datetime.fromtimestamp(when, tz=timezone.utc),
        source=source, type=rtype, epistemic_tier=tier_ep,
        explicit=explicit, owner="ai-memory-milestone",
        gathered_how="project implementation records",
        consent_scope="project", created_at=when, last_accessed=when,
        ttl_class=ttl,
        provenance=Provenance(confidence=conf,
                              supersedes=supersedes or [],
                              recorded_at=datetime.fromtimestamp(
                                  when, tz=timezone.utc)))


# The project's own memories - real events, real dates, from the
# implementation records (phase2-gate-results.md, phase3 records).
SEED_RECORDS = [
    _rec("dec-20261013-architecture",
         "Milestone architecture adopted: memory -> conclusion (reflect), "
         "not memory -> context; confidence via DDM accumulation.",
         "decision", "observed", "verified-no-ttl", _ts(2026, 10, 13, 19)),
    _rec("dec-20261016-controller-freeze",
         "Phase-2 controller frozen: kappa=0.25 (conflict penalty), "
         "lambda=2.5 (bound raise), T=2.0 temperature.",
         "decision", "observed", "verified-no-ttl", _ts(2026, 10, 16, 2),
         supersedes=[]),
    _rec("fact-20261016-gate-d",
         "Gate (d) PASSED: 12,000 fresh high-stakes conflicting tasks, "
         "candidate accuracy 0.7167 vs baseline 0.2694.",
         "fact", "observed", "verified-no-ttl", _ts(2026, 10, 16, 8)),
    _rec("fact-20261016-gate-b",
         "Gate (b) formal FAIL: Brier interaction +0.09195 outside the "
         "+/-0.02 margin after one temperature fix; accuracy interaction "
         "+0.22092 is synergy, not double-counting.",
         "fact", "observed", "verified-no-ttl", _ts(2026, 10, 16, 9)),
    _rec("learn-20261019-dedup-order",
         "Write-gate order matters: exact dedup runs BEFORE contradiction "
         "checks, so an identical record is a duplicate, not a conflict.",
         "learning", "derived", "verified-no-ttl", _ts(2026, 10, 19, 20)),
    _rec("dec-20261019-schema-freeze",
         "Schema v0.5 FROZEN by head decision under founder delegation: "
         "freeze now, per-M-band refit, exact-only dedup, Janitor "
         "thresholds as-is, consolidation opt-in default off.",
         "decision", "observed", "verified-no-ttl", _ts(2026, 10, 19, 23)),
    _rec("learn-20261020-temperature-form",
         "Temperature scaling is the wrong functional form for the "
         "conflict regime: conflict-band T hit the grid ceiling 6.0 "
         "while ECE stayed at 0.2482 vs the 0.10 target.",
         "learning", "derived", "verified-no-ttl", _ts(2026, 10, 20, 1)),
    _rec("ep-20261013-session-start",
         "Episodic: milestone repo work began; v0.3 pipeline implemented "
         "(valuation, DDM accumulation, metacognitive pass).",
         "episodic", "observed", "session", _ts(2026, 10, 13, 19),
         explicit=False),
    _rec("ep-20261015-partners-wired",
         "Episodic: Groq, OpenRouter and Gemini wired as partner routes; "
         "council voted SEQUENCED on v0.4.",
         "episodic", "observed", "session", _ts(2026, 10, 15, 23),
         explicit=False),
    _rec("ep-20261019-chunk1",
         "Episodic: Phase-3 chunk 1 ran the per-M-band calibration fit; "
         "conflict ECE improved 0.3456 -> 0.2482 but missed target.",
         "episodic", "observed", "session", _ts(2026, 10, 19, 20),
         explicit=False),
    _rec("ep-20261020-chunk2",
         "Episodic: Phase-3 chunk 2 shipped schema v0.5, write gate, "
         "M-bands, Janitor, consolidation daemon; 46/46 tests green.",
         "episodic", "observed", "ephemeral", _ts(2026, 10, 20, 1),
         explicit=False),
    _rec("proc-retrieval-probe",
         "Procedure: retrieval probes log an access event for every "
         "record they return; access recency beats write recency.",
         "procedure", "derived", "unverified-days", _ts(2026, 10, 20, 2)),
]

PROBE_QUERIES = [
    "controller frozen kappa lambda",
    "gate fail brier interaction",
    "schema v0.5 frozen decision",
    "temperature wrong functional form conflict",
    "episodic session partners wired",
    "dedup before contradiction",
]


def seed_if_empty(store: SQLiteStore) -> list[dict]:
    if len(store) > 0:
        return [{"status": "store-not-empty", "n": len(store)}]
    out = []
    for rec in SEED_RECORDS:
        outcome = store.write(rec)
        out.append({"id": rec.id, "verdict": outcome.verdict,
                    "reasons": outcome.reasons})
    return out


def probe_pass(store: SQLiteStore, now: float) -> list[dict]:
    """Real retrievals: search the store, log an access per hit, and
    refresh the hit record's access metadata (whitelist fields only)."""
    hits_log = []
    for q in PROBE_QUERIES:
        hits = store.search(q, limit=5)
        for rec in hits:
            store.log_access(rec.id, now, kind="retrieval")
            store.update_metadata(rec.id, last_accessed=now,
                                  access_count=rec.access_count + 1)
        hits_log.append({"query": q, "hits": [r.id for r in hits]})
    return hits_log


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.db), exist_ok=True)
    store = SQLiteStore(args.db)
    now = time.time()

    seed = seed_if_empty(store)
    probes = probe_pass(store, now)

    janitor = store.load_janitor()
    dry = store.run_janitor(janitor, now, dry_run=True)
    live = store.run_janitor(janitor, now, dry_run=False)

    # Half-life from the persisted log, via a FRESH janitor (restart-proof).
    fresh = store.load_janitor()
    records = store.all_records()
    half_life = fresh.estimate_half_life_for(records)

    report = {
        "harness": "janitor-live-v1",
        "db": args.db,
        "at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "records_in_store": len(store),
        "probe_pass": probes,
        "dry_run_ops": [
            {"op": o.op, "id": o.record_id, "from": o.from_tier,
             "to": o.to_tier, "reason": o.reason} for o in dry.ops],
        "live_ops_applied": [
            {"op": o.op, "id": o.record_id, "from": o.from_tier,
             "to": o.to_tier, "reason": o.reason} for o in live.ops
            if not o.dry_run],
        "access_events_persisted": len(store.access_events()),
        "half_life_by_ttl_class": half_life,
        "honesty_note": (
            "Half-life is reported exactly as the estimator computes it "
            "from the persisted access log. Below 30 inter-access "
            "intervals per class it says insufficient-data - that IS the "
            "first real number; no history was manufactured."),
    }
    path = OUT + "janitor-live-run1.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: report[k] for k in
                      ("records_in_store", "access_events_persisted",
                       "half_life_by_ttl_class")}, indent=2))
    print("dry-run ops:", len(dry.ops), "| live ops:", len(live.ops))
    print("wrote", path)
    store.close()


if __name__ == "__main__":
    main()
