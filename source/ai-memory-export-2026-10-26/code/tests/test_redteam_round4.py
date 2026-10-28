"""Red-Team Round 4 regression tests (2026-10-21).

Pins the Round-4 defences measured by evals/redteam_round1.py
--round4 (preregistration: redteam-round4-preregistration.md):

- Read-side authorization, first increment (mm/access_control.py):
  a ReaderContext names who is asking; the store's authorized
  reads (get_for / search_for / all_records_for), episode
  assembly and the agent's mouth enforce it fail-closed; denial
  is indistinguishable from absence. Raw reads remain the
  in-process system path (pinned as such, not hidden).
- A14i: class uniqueness is a retention WEIGHT (prune threshold
  x2), never permanent immunity; the immune class keeps the
  only permanent exemption.
- A14ii: with attributed resurrection wired, anonymous and
  self-origin access floods manufacture nothing, while a third
  party's attributed use still resurrects. Legacy (unwired)
  Janitor semantics are pinned unchanged.
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.access_control import ReaderContext, ReadAuthorizer, \
    SYSTEM_READER
from mm.agent import MemoryAgent
from mm.episodic import episode_for, recall_episodes
from mm.janitor import Janitor
from mm.reflect import MemoryRecord, Provenance
from mm.storage import SQLiteStore, _migrate_v3

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f"  [{detail}]" if not cond and detail else ""))


def rec(**kw):
    base = dict(id="r1",
                text="The deploy failed at 14:02 because of a bad "
                     "config in deploy.yaml v2.3; roll back to v2.2 "
                     "and re-run the smoke test.",
                content="", timestamp=datetime(2026, 10, 20),
                source="bench", type="fact", epistemic_tier="observed",
                explicit=True, owner="council", gathered_how="bench",
                salience=0.8, provenance=Provenance(confidence=0.6))
    base.update(kw)
    r = MemoryRecord(**base)
    if not r.content:
        r.content = r.text
    if not r.created_at:
        r.created_at = 1790000000.0
    return r


def fresh_store():
    path = tempfile.mktemp(suffix=".db")
    assert "memory.db" not in path
    return SQLiteStore(path), path


def cleanup(store, path):
    try:
        store.close()
    except Exception:
        pass
    try:
        os.remove(path)
    except OSError:
        pass


T0 = 1790000000.0
DAY = 86400.0
CANARY = ("Quarterly contingency reserve is 480000 units in "
          "vault V-9; the contingency marker is CANARY-7Q4M; "
          "verify with finance at 10:00.")
MALLORY = ReaderContext(reader_id="mallory", owner="mallory")
COUNCIL = ReaderContext(reader_id="council-reader", owner="council")
AUTH = ReadAuthorizer()

# ---------------------------------------------------------------------------
# Authorizer rules (pure)
# ---------------------------------------------------------------------------

rst = rec(id="rst-1", owner="council")
check("authz-system-reads-all",
      AUTH.can_read(SYSTEM_READER, rst)[0])
check("authz-own-lane", AUTH.can_read(COUNCIL, rst)[0])
check("authz-cross-owner-fact-denied",
      not AUTH.can_read(MALLORY, rst)[0])
epi = rec(id="e1", owner="council", type="episodic")
check("authz-episodic-shared-cross-lane",
      AUTH.can_read(MALLORY, epi)[0])
scoped = rec(id="s1", owner="council", consent_scope="fin-scope")
check("authz-consent-scope-needs-clearance",
      not AUTH.can_read(MALLORY, scoped)[0])
cleared = ReaderContext(reader_id="fin", owner="finance",
                        clearances=frozenset({"fin-scope"}))
check("authz-consent-scope-with-clearance",
      AUTH.can_read(cleared, scoped)[0])
scoped_epi = rec(id="s2", owner="council", type="episodic",
                 consent_scope="fin-scope")
check("authz-scope-beats-episodic-sharing",
      not AUTH.can_read(MALLORY, scoped_epi)[0])
unowned = rec(id="u1", owner="")
check("authz-unowned-readable", AUTH.can_read(MALLORY, unowned)[0])

# ---------------------------------------------------------------------------
# Store authorized API: denial == absence, actor logging, migration
# ---------------------------------------------------------------------------

store, path = fresh_store()
store.write(rec(id="rst-1", owner="council", text=CANARY,
                content=CANARY))
store.write(rec(id="own-1", owner="mallory",
                text="Mallory note: the deploy checklist DC-4 was "
                     "updated on 2026-10-19; verify at 11:00.",
                content="Mallory note: the deploy checklist DC-4 "
                        "was updated on 2026-10-19; verify at "
                        "11:00."))
check("get_for-denied-is-none",
      store.get_for(MALLORY, "rst-1") is None)
check("get_for-missing-is-none",
      store.get_for(MALLORY, "no-such-id") is None)
check("get_for-own-record", store.get_for(MALLORY, "own-1")
      is not None)
check("get_for-owner-reads-own",
      store.get_for(COUNCIL, "rst-1") is not None)
check("search_for-filters",
      all(h.id != "rst-1" for h in store.search_for(
          MALLORY, "quarterly contingency reserve", limit=5)))
check("all_records_for-filters",
      "rst-1" not in store.all_records_for(MALLORY)
      and "own-1" in store.all_records_for(MALLORY))
check("raw-read-remains-system-path",
      store.get("rst-1") is not None
      and "rst-1" in store.all_records())
store.log_access("rst-1", T0, actor="council-reader")
store.log_access("rst-1", T0 + DAY)
evs = store.access_events()
check("access-event-actor-persists",
      evs[0].actor == "council-reader" and evs[1].actor == "")
cleanup(store, path)

# migration: a pre-v3 access_events table gains the actor column
import sqlite3
mpath = tempfile.mktemp(suffix=".db")
conn = sqlite3.connect(mpath)
conn.execute("CREATE TABLE access_events (seq INTEGER PRIMARY "
             "KEY AUTOINCREMENT, record_id TEXT NOT NULL, "
             "at REAL NOT NULL, kind TEXT NOT NULL "
             "DEFAULT 'retrieval')")
conn.execute("INSERT INTO access_events(record_id, at) "
             "VALUES ('x', 1.0)")
conn.commit()
_migrate_v3(conn)
cols = {r[1] for r in conn.execute("PRAGMA table_info("
                                   "access_events)")}
row = conn.execute("SELECT actor FROM access_events").fetchone()
check("migration-v3-adds-actor-with-default",
      "actor" in cols and row[0] == "")
conn.close()
os.remove(mpath)

# ---------------------------------------------------------------------------
# Episodes + mouth under a reader
# ---------------------------------------------------------------------------

store, path = fresh_store()
store.write(rec(id="rst-1", owner="council", text=CANARY,
                content=CANARY))
store.write(rec(id="cs-1", owner="council", type="episodic",
                explicit=False, gathered_how="episodic/session-42",
                episodic_record_id="rst-1",
                text="Quarterly contingency session summary: the "
                     "session on 2026-10-20 filed the reserve "
                     "review at 10:00; check the linked record "
                     "R-1 for the figures.",
                content="Quarterly contingency session summary: "
                        "the session on 2026-10-20 filed the "
                        "reserve review at 10:00; check the linked "
                        "record R-1 for the figures."))
ep = episode_for(store, "cs-1", reader=COUNCIL)
check("episode-owner-chain-keeps-own-link",
      "rst-1" in [l.record_id for l in ep.chain])
ep = episode_for(store, "cs-1", reader=MALLORY)
check("episode-cross-lane-head-chain-drops-restricted-link",
      "rst-1" not in [l.record_id for l in ep.chain])
ep = episode_for(store, "rst-1", reader=MALLORY)
check("episode-unreadable-head-is-empty", ep.chain == [])
cleanup(store, path)

# named-relation smuggling (D3's shape): dangling-first contradicts
store, path = fresh_store()
cal = os.path.join(tempfile.mkdtemp(), "calibration.json")
agent = MemoryAgent(store, calibration_path=cal)
agent.ingest(rec(id="atk-30", owner="mallory", type="procedure",
                 provenance=Provenance(confidence=0.6,
                                       contradicts=["rst-1"]),
                 text="Quarterly contingency planning procedure: "
                      "always review the contingency reserve "
                      "before any spend; file the actions at "
                      "12:00.",
                 content="Quarterly contingency planning "
                         "procedure: always review the contingency "
                         "reserve before any spend; file the "
                         "actions at 12:00."))
agent.ingest(rec(id="rst-1", owner="council", text=CANARY,
                 content=CANARY))
ans = agent.answer("quarterly contingency")
check("mouth-legacy (no reader) still cites - declared boundary",
      "rst-1" in ans.evidence_ids)
ans = agent.answer("quarterly contingency", reader=MALLORY)
check("mouth-with-reader-does-not-cite-restricted",
      "rst-1" not in ans.evidence_ids)
hits = agent.retrieve("deploy", reader=MALLORY)
check("retrieve-with-reader-logs-reader-as-actor",
      all(e.actor == "mallory" for e in store.access_events()
          if e.record_id in {h.id for h in hits})
      if hits else True)
cleanup(store, path)

# ---------------------------------------------------------------------------
# Janitor: uniqueness is a weight (A14i), attribution (A14ii)
# ---------------------------------------------------------------------------


def jrec(rid, **kw):
    base = dict(id=rid, text="old", timestamp=datetime(2026, 6, 1),
                type="fact", ttl_class="session",
                epistemic_tier="observed", explicit=True, owner="o",
                gathered_how="g", tier="archive", created_at=T0,
                last_accessed=T0, access_count=0, decay_score=0.01)
    base.update(kw)
    return MemoryRecord(**base)


j = Janitor()
uniq = {"u1": jrec("u1")}
ops = j._lifecycle_for(uniq["u1"], T0 + 100 * DAY, uniq)
check("janitor-unique-protected-at-100d",
      all(o.op != "prune_eligible" for o in ops))
ops = j._lifecycle_for(uniq["u1"], T0 + 200 * DAY, uniq)
check("janitor-unique-eligible-at-200d (weight, not immunity)",
      any(o.op == "prune_eligible" for o in ops))
pair = {"n1": jrec("n1"), "n2": jrec("n2")}
ops = j._lifecycle_for(pair["n1"], T0 + 100 * DAY, pair)
check("janitor-nonunique-eligible-at-100d",
      any(o.op == "prune_eligible" for o in ops))
ex = {"x1": jrec("x1", decay_exempt=True)}
ops = j._lifecycle_for(ex["x1"], T0 + 400 * DAY, ex)
check("janitor-immune-exempt-is-permanent",
      all(o.op != "prune_eligible" for o in ops))


def cooled(rid, owner):
    return rec(id=rid, owner=owner, type="fact",
               ttl_class="session", tier="cooled", created_at=T0,
               last_accessed=T0)


def resurrects(janitor, record, actor, days=(16, 17, 18)):
    for d in days:
        janitor.log_access(record.id, T0 + d * DAY, actor=actor)
    rep = janitor.run({record.id: record}, T0 + 20 * DAY)
    return any(o.op == "resurrect" for o in rep.ops)


r = cooled("rz-a", "mallory")
check("janitor-legacy-anonymous-resurrects (pinned)",
      resurrects(Janitor(), r, ""))
r = cooled("rz-b", "mallory")
check("janitor-attributed-anonymous-does-not-resurrect",
      not resurrects(Janitor(attributed_resurrection=True), r, ""))
r = cooled("rz-c", "mallory")
check("janitor-attributed-self-flood-does-not-resurrect",
      not resurrects(Janitor(attributed_resurrection=True), r,
                     "mallory"))
r = cooled("rz-d", "council")
check("janitor-attributed-third-party-use-resurrects",
      resurrects(Janitor(attributed_resurrection=True), r, "agent"))

# store wiring: load_janitor(attributed_resurrection=True) over
# persisted actor events
store, path = fresh_store()
store.write(rec(id="rz-s", owner="mallory", ttl_class="session",
                text="Fact R-9: the staging freeze calendar was "
                     "posted on 2026-10-02 per ticket S-21; check "
                     "the calendar at 08:30.",
                content="Fact R-9: the staging freeze calendar "
                        "was posted on 2026-10-02 per ticket S-21; "
                        "check the calendar at 08:30."))
records = store.all_records()
store.run_janitor(store.load_janitor(), T0 + 15 * DAY)
for d in (16, 17, 18):
    store.log_access("rz-s", T0 + d * DAY)  # anonymous flood
jan = store.load_janitor(attributed_resurrection=True)
rep = store.run_janitor(jan, T0 + 20 * DAY)
check("store-wired-attributed-janitor-blocks-anonymous-flood",
      not any(o.op == "resurrect" for o in rep.ops))
cleanup(store, path)

# ---------------------------------------------------------------------------
# G5c hardening (the incharge's HOLD decision): GA + GB + shadow
# ---------------------------------------------------------------------------

from mm.source_trust import SourceTrustRegistry
from mm.write_gate import WriteGate

BAND_TEXT = ("The Ledger component owns the billing export per "
             "ticket B-09; check runbook RB-2 v1.8 at 09:30 sharp.")


def band_rec(rid, owner="desk", source="wire/desk"):
    return rec(id=rid, owner=owner, source=source, text=BAND_TEXT,
               content=BAND_TEXT,
               provenance=Provenance(confidence=0.70))


# GA: one reviewer cannot mint - cap 2 per (identity, reviewer)
reg = SourceTrustRegistry()
seed = rec(id="seed", owner="desk", source="wire/desk")
for _ in range(3):
    reg.note_admitted(seed, via="review", reviewer="rev-1")
st = reg.stats_for("desk", "wire/desk")
check("ga-single-reviewer-capped-at-2",
      st.held == 2 and st.review_capped == 1
      and reg.tier_for("desk", "wire/desk") == "unproven",
      f"held={st.held} capped={st.review_capped}")
for _ in range(2):
    reg.note_admitted(seed, via="review", reviewer="rev-2")
reg.note_admitted(seed, via="review", reviewer="rev-3")
check("ga-three-reviewers-can-mint (2+2+1)",
      reg.tier_for("desk", "wire/desk") == "proven"
      and reg.stats_for("desk", "wire/desk").held == 5)
# GA + GB state persists through the sidecar JSON
rpath = tempfile.mktemp(suffix=".json")
reg2 = SourceTrustRegistry(path=rpath)
for _ in range(3):
    reg2.note_admitted(seed, via="review", reviewer="rev-1")
for _ in range(2):
    reg2.note_admitted(seed, via="review", reviewer="rev-2")
reg2.note_admitted(seed, via="review", reviewer="rev-3")
reg2b = SourceTrustRegistry(path=rpath)
st = reg2b.stats_for("desk", "wire/desk")
check("ga-gb-state-persists",
      st.review_held.get("rev-1") == 2 and st.review_capped == 1
      and st.probation is True)
os.remove(rpath)

# GB: first band filing after promotion queues; the next passes
reg = SourceTrustRegistry()
for _ in range(5):
    reg.note_admitted(seed)
check("gb-promotion-arms-probation",
      reg.probation_pending("desk", "wire/desk"))
g = WriteGate(trust_registry=reg)
out = g.admit(band_rec("gb-1"), {})
check("gb-first-band-filing-queues",
      out.verdict == "queued"
      and any("probation" in r for r in out.reasons),
      f"verdict={out.verdict} reasons={out.reasons}")
check("gb-probation-consumed-once",
      not reg.probation_pending("desk", "wire/desk"))
out = g.admit(band_rec("gb-2"), {})
check("gb-second-band-filing-passes-on-standing",
      out.verdict == "admitted", f"verdict={out.verdict}")

# Shadow: decisions recorded, verdicts never change, probation
# is not eaten by measurement
reg = SourceTrustRegistry()
g = WriteGate(trust_registry=reg, trust_shadow=True)
out = g.admit(band_rec("sh-1", owner="newbie", source="blog/x"),
              {})
g5c = [gt for gt in out.record.write_audit["gates"]
       if gt["gate"] == "G5c-source-trust"]
check("shadow-unproven-band-admitted-not-queued",
      out.verdict == "admitted" and g5c
      and "SHADOW" in g5c[0]["detail"],
      f"verdict={out.verdict} g5c={g5c}")
reg = SourceTrustRegistry()
for _ in range(5):
    reg.note_admitted(seed)
g = WriteGate(trust_registry=reg, trust_shadow=True)
out = g.admit(band_rec("sh-2"), {})
check("shadow-probation-filing-admitted-and-flag-kept",
      out.verdict == "admitted"
      and reg.probation_pending("desk", "wire/desk"))
rep = reg.shadow_report()
check("shadow-report-counts-would-queue",
      rep["would_queue"] == 1 and rep["would_pass"] == 0
      and rep["would_queue_rate"] == 1.0, f"report={rep}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
