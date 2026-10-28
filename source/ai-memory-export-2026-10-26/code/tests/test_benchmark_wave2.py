"""Benchmark Wave 2 tests (2026-10-21): B5 benchmark source
registration (mm/source_trust.py + gate G5b/G5c) and B2
bi-temporal validity windows (mm/reflect.py, mm/storage.py,
mm/episodic.py, evals/retrieval.py).

B5 contract (partner vote 2026-10-20, Muse's condition):
registration is harness-side and auditable, never a production
backdoor. These tests pin: names are required; scope is the
exact (owner, source root) identity; registration satisfies
ONLY the corroboration requirements (G5b/G5c) - every quality
gate still applies; production defaults (no registry wired)
are byte-for-byte the legacy behaviour; registration moves no
trust tier and accrues no track record.

B2 contract (Wave 1 record sec. 6 spec): records carry a
validity window [valid_at, invalid_at); ingest stamps
valid_at = timestamp when unset; supersession stamps the
loser's invalid_at through the lifecycle whitelist; as-of
episodic recall never surfaces a record outside its window.

Run: python3 tests/test_benchmark_wave2.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.episodic import (episode_for, recall_episodes, valid_at_day,
                        valid_at_instant)
from mm.reflect import MemoryRecord, Provenance
from mm.source_trust import SourceTrustRegistry
from mm.storage import (SQLiteStore, SealedRecordError,
                        record_from_dict, record_to_dict)
from mm.write_gate import WriteGate
from evals.retrieval import (ChunkedRetriever, DayWindowRetriever,
                             ValidWindowRetriever)

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


CLAIM = ("The deploy failed at 14:02 because of a bad config in "
         "deploy.yaml v2.3; roll back to v2.2 and re-run the "
         "smoke test.")
SECRET = ("Rotate the api_key: hunter2hunter2 value in vault.yaml "
          "v3; deploy the replacement at 14:00 and verify the "
          "login flow.")
VAGUE = "stuff happened and things were done at some point"


def rec(rid="r1", conf=0.95, tier="observed", owner="",
        source="episodic/longmemeval-s", text=CLAIM, **kw):
    base = dict(id=rid, text=text, content=text,
                timestamp=datetime(2026, 1, 1),
                source=source, type="episodic",
                epistemic_tier=tier, explicit=True, owner=owner,
                gathered_how="episodic/capture", salience=0.5,
                provenance=Provenance(confidence=conf))
    base.update(kw)
    return MemoryRecord(**base)


def registered_registry() -> SourceTrustRegistry:
    reg = SourceTrustRegistry()
    reg.register_benchmark_source(
        "", "episodic/longmemeval-s",
        dataset="xiaowu0162/longmemeval-cleaned (pinned), S split",
        harness="tests/test_benchmark_wave2.py")
    return reg


def gate_note(outcome, gate_name: str) -> str:
    for g in outcome.record.write_audit.get("gates", []):
        if g["gate"] == gate_name:
            return str(g["detail"])
    return ""


# --- B5-1: registration requires dataset AND harness names --------
reg = SourceTrustRegistry()
for kw in (dict(dataset="", harness="h"),
           dict(dataset="d", harness=""),
           dict(dataset="  ", harness="h")):
    try:
        reg.register_benchmark_source("", "episodic/x", **kw)
        check(f"b5-anonymous-refused-{sorted(kw)}", False)
    except ValueError:
        check(f"b5-anonymous-refused-{sorted(kw)}", True)

# --- B5-2: registration is exact-identity scoped ------------------
reg = registered_registry()
check("b5-registered-identity-found",
      reg.benchmark_registration_for(
          "", "episodic/longmemeval-s") is not None)
check("b5-same-root-is-same-identity",
      reg.benchmark_registration_for(
          "", "episodic/other-dataset") is not None)
check("b5-other-root-not-registered",
      reg.benchmark_registration_for(
          "", "external/kb-import") is None)
check("b5-other-owner-not-registered",
      reg.benchmark_registration_for(
          "someone", "episodic/longmemeval-s") is None)
check("b5-registration-listed-for-audit",
      len(reg.benchmark_registrations()) == 1
      and reg.benchmark_registrations()[0].dataset.startswith(
          "xiaowu0162/"))

# --- B5-3: registration moves no tier, accrues nothing ------------
check("b5-registration-moves-no-tier",
      reg.tier_for("", "episodic/longmemeval-s") == "unproven"
      and reg.stats_for("", "episodic/longmemeval-s").held == 0)

# --- B5-4: registered source passes G5b, stamped in the audit -----
gate = WriteGate(trust_registry=registered_registry())
out = gate.admit(rec(), {})
check("b5-registered-passes-g5b", out.verdict == "admitted",
      f"verdict={out.verdict} reasons={out.reasons}")
note = gate_note(out, "G5b-corroboration")
check("b5-g5b-note-is-flagged",
      "benchmark-registered" in note
      and "xiaowu0162" in note, note[:80])

# --- B5-5: same record, unregistered identity -> still queues -----
gate = WriteGate(trust_registry=registered_registry())
out = gate.admit(rec(source="external/kb-import"), {})
check("b5-unregistered-still-queues", out.verdict == "queued",
      f"verdict={out.verdict}")

# --- B5-6: registered source passes the G5c band ------------------
gate = WriteGate(trust_registry=registered_registry())
out = gate.admit(rec(conf=0.7, tier="derived"), {})
check("b5-registered-passes-g5c-band", out.verdict == "admitted",
      f"verdict={out.verdict} reasons={out.reasons}")
note = gate_note(out, "G5c-source-trust")
check("b5-g5c-note-is-flagged", "benchmark-registered" in note,
      note[:80])
gate = WriteGate(trust_registry=registered_registry())
out = gate.admit(rec(conf=0.7, tier="derived",
                     source="external/kb-import"), {})
check("b5-unregistered-band-still-queues", out.verdict == "queued",
      f"verdict={out.verdict}")

# --- B5-7: registration waives corroboration ONLY ------------------
gate = WriteGate(trust_registry=registered_registry())
out = gate.admit(rec(text=SECRET), {})
check("b5-registered-secret-still-rejected",
      out.verdict == "rejected", f"verdict={out.verdict}")
gate = WriteGate(trust_registry=registered_registry())
out = gate.admit(rec(text=VAGUE), {})
check("b5-registered-vague-still-rejected",
      out.verdict == "rejected", f"verdict={out.verdict}")

# --- B5-8: production default (no registry) is legacy --------------
gate = WriteGate()
out = gate.admit(rec(), {})
check("b5-default-gate-unchanged", out.verdict == "queued",
      f"verdict={out.verdict}")

# --- B5-9: registration persists in the sidecar --------------------
path = os.path.join(tempfile.mkdtemp(), "trust.json")
reg = SourceTrustRegistry(path)
reg.register_benchmark_source("bench", "episodic/lme", dataset="D",
                              harness="H")
reg2 = SourceTrustRegistry(path)
got = reg2.benchmark_registration_for("bench", "episodic/lme")
check("b5-sidecar-round-trip",
      got is not None and got.dataset == "D" and got.harness == "H")

# --- B2-1: window predicate ----------------------------------------
base = datetime(2026, 1, 10)
r = MemoryRecord(id="w", text="x", timestamp=base,
                 valid_at=base, invalid_at=base + timedelta(days=10))
check("b2-window-before", not valid_at_instant(
    r, base - timedelta(days=1)))
check("b2-window-start-inclusive", valid_at_instant(r, base))
check("b2-window-inside", valid_at_instant(
    r, base + timedelta(days=5)))
check("b2-window-end-exclusive", not valid_at_instant(
    r, base + timedelta(days=10)))
r2 = MemoryRecord(id="w2", text="x", timestamp=base)
check("b2-window-none-falls-back-to-timestamp",
      valid_at_instant(r2, base)
      and not valid_at_instant(r2, base - timedelta(hours=1)))

# --- B2-2: ingest stamps valid_at; supersession stamps invalid_at --
tdir = tempfile.mkdtemp()
store = SQLiteStore(f"{tdir}/m.db")


def srec(rid, text, ts, **kw):
    base = dict(id=rid, text=text, content=text, timestamp=ts,
                source="bench", type="fact", epistemic_tier="derived",
                explicit=True, owner="desk", gathered_how="bench",
                provenance=Provenance(confidence=0.7))
    base.update(kw)
    return MemoryRecord(**base)


t1 = datetime(2026, 1, 1, 10, 0)
t2 = datetime(2026, 1, 2, 10, 0)
out = store.write(srec(
    "a", "Deploy the fix for ticket B-09 at 14:02; update runbook "
         "RB-2 v1.8 and verify the login flow.", t1))
check("b2-fixture-admitted", out.verdict == "admitted",
      f"{out.verdict} {out.reasons}")
got = store.get("a")
check("b2-ingest-stamps-valid-at",
      got.valid_at == t1 and got.invalid_at is None,
      f"valid_at={got.valid_at}")
out = store.write(srec(
    "b", "Deploy the corrected fix for ticket B-09 at 15:30; "
         "update runbook RB-2 v1.9 and verify the login flow.", t2,
    provenance=Provenance(confidence=0.7, supersedes=["a"])))
check("b2-correction-admitted", out.verdict == "admitted",
      f"{out.verdict} {out.reasons}")
loser = store.get("a")
check("b2-supersession-stamps-invalid-at",
      loser.invalid_at == t2
      and loser.superseded_with_replacement is True,
      f"invalid_at={loser.invalid_at}")

# --- B2-3: the whitelist admits invalid_at and nothing more --------
try:
    store.update_metadata("a", invalid_at=t2)
    check("b2-whitelist-allows-invalid-at", True)
except SealedRecordError:
    check("b2-whitelist-allows-invalid-at", False)
try:
    store.update_metadata("a", valid_at=t1)
    check("b2-whitelist-refuses-valid-at", False)
except SealedRecordError:
    check("b2-whitelist-refuses-valid-at", True)
try:
    store.update_metadata("a", text="rewrite history")
    check("b2-whitelist-still-refuses-content", False)
except SealedRecordError:
    check("b2-whitelist-still-refuses-content", True)

# --- B2-4: serialization round-trip --------------------------------
d = record_to_dict(got)
back = record_from_dict(d)
check("b2-dict-round-trip",
      back.valid_at == got.valid_at
      and back.invalid_at == got.invalid_at)

# --- B2-5: episodic as-of assembly ----------------------------------
class FakeStore:
    def __init__(self, records):
        self._records = records

    def all_records(self):
        return dict(self._records)

    def search(self, query, limit=10):
        return list(self._records.values())[:limit]


old = MemoryRecord(id="old", text="the old fact", timestamp=t1,
                   type="episodic", valid_at=t1, invalid_at=t2)
new = MemoryRecord(id="new", text="the new fact", timestamp=t2,
                   type="episodic", valid_at=t2,
                   episodic_record_id="old")
fake = FakeStore({"old": old, "new": new})
ep = episode_for(fake, "new", as_of=t1 + timedelta(hours=1))
check("b2-asof-head-not-yet-valid", ep.chain == [])
ep = episode_for(fake, "new", as_of=t2 + timedelta(hours=1))
check("b2-asof-chain-drops-invalid-link",
      [link.record_id for link in ep.chain] == ["new"],
      str([link.record_id for link in ep.chain]))
ep = episode_for(fake, "old", as_of=t1 + timedelta(hours=1))
check("b2-asof-old-valid-then",
      [link.record_id for link in ep.chain] == ["old"])
eps = recall_episodes(fake, "fact", as_of=t1 + timedelta(hours=1))
check("b2-asof-recall-heads-filtered",
      [e.head_id for e in eps] == ["old"],
      str([e.head_id for e in eps]))

# --- B2-6: the windowed retriever excludes out-of-window records ---
now = datetime(2023, 6, 1)
past = MemoryRecord(
    id="past", timestamp=now - timedelta(days=1), salience=0.5,
    text="[user] My diploma is in Business Administration")
future = MemoryRecord(
    id="future", timestamp=now + timedelta(days=30), salience=0.5,
    text=("[user] What degree did I graduate with? I graduated "
          "with a degree in Computer Science"))
q = "What degree did I graduate with?"
plain = ChunkedRetriever().rank([past, future], q, now=now)
check("b2-fixture-future-wins-unfiltered",
      plain[0].record.id == "future",
      f"top={plain[0].record.id}")
wr = ValidWindowRetriever()
windowed = wr.rank([past, future], q, now=now)
check("b2-windowed-excludes-future",
      [e.record.id for e in windowed] == ["past"]
      and wr.n_filtered == 1,
      f"ids={[e.record.id for e in windowed]} "
      f"filtered={wr.n_filtered}")

# --- B2-7: day-precision window (granularity follow-up) ------------
# Preregistration: b2-granularity-preregistration.md. The pair pins
# the precision difference: same-day later-hour evidence is OUT at
# instant precision, IN at day precision; tomorrow is out at both.
q_day = datetime(2026, 1, 10, 10, 15)
same_day = MemoryRecord(id="sd", text="x",
                        timestamp=datetime(2026, 1, 10, 21, 32))
tomorrow = MemoryRecord(id="tm", text="x",
                        timestamp=datetime(2026, 1, 11, 0, 1))
check("b2g-same-day-admitted-day", valid_at_day(same_day, q_day))
check("b2g-same-day-excluded-instant",
      not valid_at_instant(same_day, q_day))
check("b2g-tomorrow-excluded-day", not valid_at_day(tomorrow, q_day))
check("b2g-tomorrow-excluded-instant",
      not valid_at_instant(tomorrow, q_day))
inv_today = MemoryRecord(
    id="it", text="x", timestamp=datetime(2026, 1, 5, 9, 0),
    invalid_at=datetime(2026, 1, 10, 8, 0))
inv_tomorrow = MemoryRecord(
    id="iw", text="x", timestamp=datetime(2026, 1, 5, 9, 0),
    invalid_at=datetime(2026, 1, 11, 8, 0))
check("b2g-invalid-on-question-day-out",
      not valid_at_day(inv_today, q_day))
check("b2g-invalid-tomorrow-still-in",
      valid_at_day(inv_tomorrow, q_day))
late_none = MemoryRecord(id="ln", text="x",
                         timestamp=datetime(2026, 1, 10, 23, 59))
check("b2g-none-fallback-day-precision",
      valid_at_day(late_none, q_day)
      and not valid_at_day(tomorrow, q_day))
explicit = MemoryRecord(
    id="ex", text="x", timestamp=datetime(2026, 1, 1, 9, 0),
    valid_at=datetime(2026, 1, 10, 18, 0))
check("b2g-explicit-valid-at-governs",
      valid_at_day(explicit, q_day)
      and not valid_at_instant(explicit, q_day))
sd_rec = MemoryRecord(
    id="same-day", timestamp=datetime(2023, 6, 1, 21, 32),
    salience=0.5,
    text="[user] I graduated with a degree in Biology")
dw = DayWindowRetriever()
day_ranked = dw.rank([past, future, sd_rec], q,
                     now=datetime(2023, 6, 1, 10, 15))
day_ids = [e.record.id for e in day_ranked]
check("b2g-daywindow-admits-same-day-excludes-future",
      "same-day" in day_ids and "past" in day_ids
      and "future" not in day_ids and dw.n_filtered == 1,
      f"ids={day_ids} filtered={dw.n_filtered}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
