"""Red-Team Round 5 regression tests (2026-10-21).

Pins the Round-5 defences measured by evals/redteam_round1.py
--round5 (preregistration: redteam-round5-preregistration.md):

- Identity binding (mm/identity.py): capability tokens bound
  to a writer identity (owner, source root) or a reader id;
  only hashes are kept; rotation kills the old token. With an
  authority wired, the store refuses writes under a REGISTERED
  identity without a verifying token (before the gate runs)
  and denies authorized reads under a REGISTERED reader id.
  Unregistered identities keep the legacy declared path.
- Canary-by-default (mm/canary.py): bait records seeded
  through the gate; a CanaryWatch wired into the store trips
  on reader-facing reads of a canary; the system snapshot
  path is never noted.
- Retrieval-share circuit breaker (mm/circuit_breaker.py):
  trips on share >= ceiling with distinct-query and
  actually-surfaced conditions; the alert names every
  principal; a wired agent drops tripped identities.
- Shadow longitudinal tracking (mm/source_trust.py): the
  decision log, breakdowns, dispositions, and the
  corroborated / corrected / still-lone join.
"""

import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.access_control import ReaderContext
from mm.agent import MemoryAgent
from mm.canary import CanaryWatch, seed_canaries
from mm.circuit_breaker import RetrievalShareBreaker
from mm.identity import IdentityAuthority
from mm.janitor import AccessEvent
from mm.reflect import MemoryRecord, Provenance
from mm.sentinel import Sentinel
from mm.source_trust import SourceTrustRegistry
from mm.storage import SQLiteStore
from mm.write_gate import WriteGate

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


def tmp_store(**kw):
    path = os.path.join(tempfile.mkdtemp(), "store.db")
    return SQLiteStore(path, **kw), path


CLAIM = ("The Ledger component owns the billing export per ticket "
         "B-09; check runbook RB-2 v1.8 at 09:30 sharp.")

# ---------------------------------------------------------------------------
# IdentityAuthority: issue / verify / rotate / revoke / persistence
# ---------------------------------------------------------------------------

auth = IdentityAuthority()
tok = auth.register_writer("council", "council/decisions")
check("writer-token-verifies-for-its-identity",
      auth.verify_writer(tok, "council", "council/decisions"))
check("writer-token-binds-the-root-not-the-tail",
      auth.verify_writer(tok, "council", "council/other-tail"))
check("writer-token-fails-for-another-owner",
      not auth.verify_writer(tok, "mallory", "council/decisions"))
check("writer-token-fails-for-another-root",
      not auth.verify_writer(tok, "council", "ops/ledger"))
check("unregistered-identity-reports-unregistered",
      not auth.is_writer_registered("mallory", "external/kb"))
check("garbage-and-empty-tokens-fail",
      not auth.verify_writer("nope", "council", "council/decisions")
      and not auth.verify_writer(None, "council",
                                 "council/decisions")
      and not auth.verify_writer("", "council", "council/decisions"))
rtok = auth.register_reader("founder-mouth")
check("reader-token-verifies-only-for-its-reader",
      auth.verify_reader(rtok, "founder-mouth")
      and not auth.verify_reader(rtok, "mallory-reader"))
tok2 = auth.register_writer("council", "council/decisions")
check("rotation-kills-the-old-token",
      not auth.verify_writer(tok, "council", "council/decisions")
      and auth.verify_writer(tok2, "council", "council/decisions"))
check("revoke-reader-works",
      auth.revoke_reader("founder-mouth")
      and not auth.verify_reader(rtok, "founder-mouth")
      and not auth.is_reader_registered("founder-mouth"))

apath = os.path.join(tempfile.mkdtemp(), "auth.json")
auth2 = IdentityAuthority(apath)
ptok = auth2.register_writer("desk", "wire/desk")
saved = open(apath, encoding="utf-8").read()
check("sidecar-persists-hashes-never-tokens",
      ptok not in saved and "wire" in saved)
auth3 = IdentityAuthority(apath)
check("authority-reloads-and-still-verifies",
      auth3.verify_writer(ptok, "desk", "wire/desk"))

# ---------------------------------------------------------------------------
# Store write binding
# ---------------------------------------------------------------------------

auth = IdentityAuthority()
store, _ = tmp_store(identity_authority=auth)
ctok = auth.register_writer("council", "council/decisions")
out = store.write(rec(id="w1", source="council/decisions",
                      text=CLAIM, content=CLAIM))
check("registered-write-without-token-refused",
      out.verdict == "rejected" and "w1" not in store)
check("identity-refusal-is-gate-logged",
      any(e["verdict"] == "rejected"
          and "identity binding" in " ".join(e["reasons"])
          for e in store.gate_log()))
out = store.write(rec(id="w2", source="council/decisions",
                      text=CLAIM, content=CLAIM),
                  token="attacker-guess")
check("registered-write-with-wrong-token-refused",
      out.verdict == "rejected" and "w2" not in store)
out = store.write(rec(id="w3", source="council/decisions",
                      text=CLAIM, content=CLAIM),
                  token=ctok)
check("registered-write-with-its-token-admitted",
      out.verdict == "admitted" and "w3" in store)
out = store.write(rec(id="w4", owner="walk-in", source="blog/x",
                      text=CLAIM, content=CLAIM))
check("unregistered-write-keeps-legacy-path",
      out.verdict == "admitted")
store.close()

# ---------------------------------------------------------------------------
# Store read binding
# ---------------------------------------------------------------------------

auth = IdentityAuthority()
store, _ = tmp_store(identity_authority=auth)
ctok = auth.register_writer("council", "council/decisions")
store.write(rec(id="sec-1", source="council/decisions",
                text=CLAIM, content=CLAIM), token=ctok)
mouth_tok = auth.register_reader("founder-mouth")
mouth = ReaderContext(reader_id="founder-mouth", owner="council")
check("registered-reader-without-token-denied",
      store.get_for(mouth, "sec-1") is None
      and store.search_for(mouth, "billing export") == []
      and store.all_records_for(mouth) == {})
check("registered-reader-with-its-token-reads",
      store.get_for(mouth, "sec-1", token=mouth_tok) is not None)
other_tok = auth.register_reader("mallory-reader")
check("another-readers-token-does-not-bind",
      store.get_for(mouth, "sec-1", token=other_tok) is None)
free = ReaderContext(reader_id="walk-in-reader", owner="council")
check("unregistered-reader-keeps-legacy-path",
      store.get_for(free, "sec-1") is not None)
sysr = ReaderContext(reader_id="system", system=True)
check("system-reader-is-not-token-bound",
      store.get_for(sysr, "sec-1") is not None)
store.close()

# ---------------------------------------------------------------------------
# Canary: seeding, trips, the system path, sentinel feed
# ---------------------------------------------------------------------------

sentinel = Sentinel()
watch = CanaryWatch(sentinel=sentinel)
store, _ = tmp_store(canary_watch=watch)
seeded = seed_canaries(store, count=3, watch=watch)
check("canaries-seed-through-the-gate",
      len(seeded) == 3 and all(r.id in store for r in seeded)
      and watch.canary_ids() == sorted(r.id for r in seeded))
check("canary-seeding-is-idempotent",
      len(seed_canaries(store, count=3, watch=watch)) == 3
      and len(store) == 3)
store.write(rec(id="real-1", text=CLAIM, content=CLAIM))
_ = store.snapshot()
check("system-snapshot-path-never-trips", watch.trip_count == 0)
_ = store.search("contingency reserve protocol", limit=5)
check("reader-facing-search-trips-the-canary",
      watch.trip_count == 2
      and all(t.actor == "raw" for t in watch.trips),
      f"trips={watch.trips}")
_ = store.get(watch.canary_ids()[1])
check("raw-get-trips-with-actor", watch.trip_count == 3)
_ = store.search("escalation protocol", limit=5)
st = sentinel.status()["canary_trip"]
check("sentinel-feeds-on-trips",
      st["samples"] == 5 and st["alerts"] == 1
      and watch.trip_count == 5,
      f"status={st} trips={watch.trip_count}")
store.close()

store2, _ = tmp_store(canaries=2)
check("constructor-seeds-and-auto-wires",
      store2.canary_watch is not None
      and len(store2.canary_watch.canary_ids()) == 2
      and len(store2) == 2)
store2.close()
store3 = SQLiteStore(store2.path, canary_watch=CanaryWatch())
check("reopened-store-re-registers-its-canaries",
      len(store3.canary_watch.canary_ids()) == 2)
store3.close()

# ---------------------------------------------------------------------------
# Access events carry the query (migration v4 included)
# ---------------------------------------------------------------------------

store, path = tmp_store()
store.log_access("real-1", 1790000000.0, actor="agent",
                 query="billing export owner")
ev = store.access_events()[0]
check("access-event-carries-query",
      ev.query == "billing export owner" and ev.actor == "agent")
store.close()
raw = sqlite3.connect(path)
cols = {r[1] for r in raw.execute("PRAGMA table_info(access_events)")}
raw.close()
check("v4-query-column-present", "query" in cols)

legacydb = os.path.join(tempfile.mkdtemp(), "legacy.db")
conn = sqlite3.connect(legacydb)
conn.execute("CREATE TABLE access_events (seq INTEGER PRIMARY KEY "
             "AUTOINCREMENT, record_id TEXT NOT NULL, at REAL NOT "
             "NULL, kind TEXT NOT NULL DEFAULT 'retrieval', actor "
             "TEXT NOT NULL DEFAULT '')")
conn.execute("INSERT INTO access_events(record_id, at) VALUES "
             "('x', 1.0)")
conn.commit()
conn.close()
store = SQLiteStore(legacydb)
evs = store.access_events()
check("pre-v4-db-migrates-and-reads",
      len(evs) == 1 and evs[0].query == "" and evs[0].actor == "")
store.close()

# ---------------------------------------------------------------------------
# Circuit breaker: conditions, alert shape, suppression
# ---------------------------------------------------------------------------

def _events(spec, start=1790000000.0):
    """spec: list of (record_id, n_events, n_distinct_queries)."""
    out = []
    t = start
    for rid, n, nq in spec:
        for i in range(n):
            out.append(AccessEvent(record_id=rid, at=t,
                                   actor="agent",
                                   query=f"q-{rid}-{i % nq}"))
            t += 1.0
    return out


records = {f"p-{i}": rec(id=f"p-{i}", owner="mallory",
                         source="spam/seo") for i in range(4)}
records.update({f"l-{i}": rec(id=f"l-{i}", owner="council",
                              source="council/decisions")
                for i in range(4)})
brk = RetrievalShareBreaker()
evs = _events([("p-0", 15, 6), ("p-1", 15, 6),
               ("l-0", 10, 6), ("l-1", 10, 6)])
check("breaker-quiet-below-min-events",
      brk.evaluate(_events([("p-0", 10, 6)]), records) == [])
alerts = brk.evaluate(evs, records)
check("breaker-trips-on-dominance-with-distinct-queries",
      len(alerts) == 1
      and alerts[0].identity == ("mallory", "spam")
      and abs(alerts[0].share - 0.6) < 1e-9
      and alerts[0].distinct_queries == 12,
      f"alerts={alerts}")
evs_same_q = _events([("p-0", 40, 1), ("l-0", 10, 6)])
check("one-repeated-query-is-not-amplification",
      brk.evaluate(evs_same_q, records) == [])
evs_cross = []
t = 1790000000.0
for i in range(30):
    evs_cross.append(AccessEvent(
        record_id="p-0", at=t + i,
        actor="agent" if i % 2 else "ops-reader",
        query=f"cross-{i % 7}"))
for i in range(10):
    evs_cross.append(AccessEvent(
        record_id="l-0", at=t + 40 + i, actor="agent",
        query=f"legit-{i % 6}"))
alerts = brk.evaluate(evs_cross, records)
check("alert-names-every-principal-cross-principal",
      len(alerts) == 1 and alerts[0].cross_principal
      and alerts[0].principals == ["agent", "ops-reader"],
      f"alerts={alerts}")
check("suppressed-identities-match-alerts",
      brk.suppressed_identities(evs_cross, records)
      == {("mallory", "spam")})
rep = brk.share_report(evs_cross, records)
check("share-report-shows-sub-ceiling-popularity",
      rep["per_identity"]["council|council"]["share"] == 0.25)

# Agent-level suppression (the mouth drops a tripped identity).
store, _ = tmp_store()
cal = os.path.join(tempfile.mkdtemp(), "calibration.json")
agent = MemoryAgent(store, calibration_path=cal)
agent.ingest(rec(id="pz-1", owner="mallory", source="spam/seo",
                 type="decision",
                 text="Decision D-1: vector harbor lantern plan "
                      "p1 was approved; update the routing table "
                      "RT-1 and check gate G-1 at 08:00.",
                 content="Decision D-1: vector harbor lantern "
                         "plan p1 was approved; update the "
                         "routing table RT-1 and check gate G-1 "
                         "at 08:00."))
agent.ingest(rec(id="lg-1", owner="council",
                 source="council/decisions", type="fact",
                 text="Note L-1: vector harbor briefing l1 was "
                      "filed; update the briefing index BI-1 and "
                      "check entry E-1 at 09:00.",
                 content="Note L-1: vector harbor briefing l1 "
                         "was filed; update the briefing index "
                         "BI-1 and check entry E-1 at 09:00."))
for i in range(25):
    store.log_access("pz-1", 1790000000.0 + i, actor="agent",
                     query=f"amp-{i % 6}")
hits = agent.retrieve("vector harbor lantern", limit=5,
                      breaker=RetrievalShareBreaker())
check("wired-mouth-drops-the-tripped-identity",
      all(r.id != "pz-1" for r in hits) and len(hits) >= 1,
      f"hits={[r.id for r in hits]}")
hits = agent.retrieve("vector harbor lantern", limit=5)
check("unwired-mouth-serves-it-as-before",
      any(r.id == "pz-1" for r in hits))
evq = [e.query for e in store.access_events() if e.query]
check("retrieve-logs-the-query-it-served",
      "vector harbor lantern" in evq)
store.close()

# ---------------------------------------------------------------------------
# Shadow longitudinal tracking
# ---------------------------------------------------------------------------

regpath = os.path.join(tempfile.mkdtemp(), "trust.json")
reg = SourceTrustRegistry(regpath)
gate = WriteGate(trust_registry=reg, trust_shadow=True)
lone = rec(id="sh-1", owner="newbie", source="blog/x",
           provenance=Provenance(confidence=0.70),
           text=CLAIM, content=CLAIM)
out = gate.admit(lone, {})
check("shadow-mode-still-admits-and-logs",
      out.verdict == "admitted" and len(reg.shadow_log) == 1
      and reg.shadow_log[0]["would_queue"] is True
      and reg.shadow_log[0]["registry_tier"] == "unproven"
      and reg.shadow_log[0]["confidence"] == 0.70)
prov = rec(id="sh-2", owner="desk", source="wire/desk",
           provenance=Provenance(confidence=0.60),
           text="Desk note DN-4: the wire desk rota was updated "
                "at 07:30; check rota sheet RS-4 before 08:00.",
           content="Desk note DN-4: the wire desk rota was "
                   "updated at 07:30; check rota sheet RS-4 "
                   "before 08:00.")
for _ in range(5):
    reg.note_admitted(prov)
reg.consume_probation("desk", "wire/desk")
out = gate.admit(prov, {})
log = reg.shadow_log
check("shadow-log-records-passes-too",
      len(log) == 2 and log[1]["would_queue"] is False
      and log[1]["registry_tier"] == "proven")
bd = reg.shadow_breakdown()
check("shadow-breakdown-slices",
      bd["decisions"] == 2
      and bd["by_confidence_band"]["0.65-0.79"]["would_queue"] == 1
      and bd["by_confidence_band"]["0.50-0.64"]["would_pass"] == 1
      and bd["by_source"]["newbie|blog"]["would_queue"] == 1
      and bd["by_epistemic_tier"]["observed"]["would_queue"] == 1,
      f"breakdown={bd}")
check("shadow-disposition-annotates",
      reg.note_shadow_disposition("sh-1", "legit-lone-source")
      and reg.shadow_breakdown()["by_disposition"]
          ["legit-lone-source"]["would_queue"] == 1
      and not reg.note_shadow_disposition("nope", "x"))
outs = reg.shadow_outcomes({"sh-1": lone, "sh-2": prov})
check("longitudinal-join-still-lone",
      outs["still_lone"] == 1 and outs["corroborated"] == 0
      and outs["corrected"] == 0, f"outcomes={outs}")
corrob = rec(id="sh-3", owner="other", source="wire/other",
             provenance=Provenance(confidence=0.85),
             text=CLAIM, content=CLAIM)
outs = reg.shadow_outcomes({"sh-1": lone, "sh-3": corrob})
check("longitudinal-join-corroborated",
      outs["corroborated"] == 1, f"outcomes={outs}")
fix = rec(id="sh-4", owner="other", source="wire/other",
          provenance=Provenance(confidence=0.85,
                                supersedes=["sh-1"]),
          text="Correction C-9: the Ledger component owner was "
               "fixed at 11:00 per ticket B-11; update runbook "
               "RB-2 and check the matrix.",
          content="Correction C-9: the Ledger component owner "
                  "was fixed at 11:00 per ticket B-11; update "
                  "runbook RB-2 and check the matrix.")
outs = reg.shadow_outcomes({"sh-1": lone, "sh-3": corrob,
                            "sh-4": fix})
check("longitudinal-join-corrected-beats-corroborated",
      outs["corrected"] == 1, f"outcomes={outs}")
reg2 = SourceTrustRegistry(regpath)
check("shadow-log-persists-across-reload",
      len(reg2.shadow_log) == 2
      and reg2.shadow_log[0]["disposition"] == "legit-lone-source")
oldpath = os.path.join(tempfile.mkdtemp(), "old.json")
with open(oldpath, "w", encoding="utf-8") as f:
    json.dump({"desk\x1fwire": {"held": 3, "disputes": 0,
                                "poison": 0, "queued": 0,
                                "rejected": 0}}, f)
reg3 = SourceTrustRegistry(oldpath)
check("pre-round5-sidecar-loads-unchanged",
      reg3.stats_for("desk", "wire/desk").held == 3
      and reg3.shadow_log == [])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
