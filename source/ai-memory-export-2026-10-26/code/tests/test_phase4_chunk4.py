"""Phase-4 chunk-4 tests: sentinel, immune, echolocation, episodic,
shards, agent (ears/mind/mouth), calibration wiring, janitor
amendments, storage v0.6 migration.

Run:  python3 tests/test_phase4_chunk4.py   (from the repo root)
"""

import os
import sys
import tempfile
import time
from datetime import datetime

sys.path.insert(0, ".")

from mm.reflect import MemoryRecord, Provenance
from mm.storage import SQLiteStore, record_from_dict, record_to_dict
from mm.janitor import Janitor, ARCHIVE_PRUNE_ELIGIBLE_S
from mm.sentinel import Sentinel, PRECISION_FLOOR
from mm.immune import ImmuneMemory, ThreatPattern, CanaryDrill
from mm.echolocation import SelfProber, CANARY_ALARM_AFTER
from mm.episodic import episode_for, recall_episodes
from mm.shards import Shard, Core
from mm.agent import MemoryAgent, HARD_GATES
from mm.decision import Candidate, Preference

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


def rec(**kw):
    base = dict(id="r1", text="Kappa was frozen at 0.25 for Phase 2.",
                content="Kappa was frozen at 0.25 for Phase 2.",
                timestamp=datetime(2026, 10, 16), type="decision",
                epistemic_tier="observed", explicit=True, owner="council",
                gathered_how="bench", salience=0.8)
    base.update(kw)
    return MemoryRecord(**base)


def fresh_store():
    path = tempfile.mktemp(suffix=".db")
    store = SQLiteStore(path)
    return store, path


# ---------------------------------------------------------------------------
# sentinel: P-wave channels, prospective scoring, wolf-muting
# ---------------------------------------------------------------------------

s = Sentinel()
base_t = 1792500000.0
# feed a quiet baseline
for i in range(20):
    s.observe("gate_rejection_rate", 0.0, at=base_t + i)
# burst trips the threshold
alert = s.observe("gate_rejection_rate", 5.0, at=base_t + 100,
                  detail="burst")
check("sentinel-burst-alert", alert is not None and alert.channel == "gate_rejection_rate",
      "no alert on burst")

# prospective scoring: mark 10 alerts as false alarms -> muted.
# Bursts are spaced beyond the 3600s window so each sees a fresh baseline.
s.mark_outcome(alert.id, False)
for i in range(9):
    t0 = base_t + 10000 * (i + 1)
    for j in range(5):
        s.observe("gate_rejection_rate", 0.0, at=t0 + j)
    a = s.observe("gate_rejection_rate", 8.0, at=t0 + 10)
    assert a is not None, f"burst {i} did not fire"
    s.mark_outcome(a.id, False)
st = s.status()["gate_rejection_rate"]
check("sentinel-wolf-muted", st["muted"] is True and st["precision"] == 0.0,
      f"muted={st['muted']} precision={st['precision']}")
# finding 8: the judge is recorded on the alert - auditable trail
judged = [a for a in s._state["gate_rejection_rate"].alerts
          if a.outcome is not None]
check("sentinel-judge-field", all(hasattr(a, "judge") for a in judged),
      "judge not recorded")

# muted channel stays quiet, rearm re-enables
a2 = s.observe("gate_rejection_rate", 9.0, at=base_t + 400)
check("sentinel-muted-quiet", a2 is None, "muted channel fired")
check("sentinel-rearm", s.rearm("gate_rejection_rate") is True
      and s.status()["gate_rejection_rate"]["muted"] is False)

# true alerts keep precision up: a fresh sentinel, real outcomes
s2 = Sentinel()
ids = []
for i in range(10):
    t0 = base_t + 20000 * (i + 1)
    for j in range(5):
        s2.observe("gate_queue_rate", 0.0, at=t0 + j)
    a = s2.observe("gate_queue_rate", 8.0, at=t0 + 10)
    assert a is not None, f"real burst {i} did not fire"
    ids.append(a.id)
for aid in ids:
    s2.mark_outcome(aid, True)
p = s2.precision("gate_queue_rate")
check("sentinel-precision-real", p is not None and p >= 0.9,
      f"precision={p}")
check("sentinel-unknown-channel-raises", True)
try:
    s2.observe("nope", 1.0, at=base_t)
    check("sentinel-unknown-channel-raises", False, "no KeyError")
except KeyError:
    pass

# ---------------------------------------------------------------------------
# immune: pattern memory, tolerance, canary drills, threat records
# ---------------------------------------------------------------------------

im = ImmuneMemory()
pat = ThreatPattern(id="pat-1", reason_class="G0-secrets",
                    source="evil", min_length=0,
                    attack_class="poisoned-rag-injection")
im.bank(pat)
hit = im.match(source="evil", reason_class="G0-secrets", text_length=10)
check("immune-reflex-match", hit is not None and hit.id == "pat-1",
      "no match on known pattern")
miss = im.match(source="good", reason_class="G0-secrets", text_length=10)
check("immune-no-self-match", miss is None, "matched clean write")

# tolerance: enough legit fires -> auto-suspend
for _ in range(10):
    im.patterns["pat-1"].fires += 1
    im.note_legit_fire("pat-1", resolution_ref="review/res-1")
check("immune-tolerance-suspend",
      im.patterns["pat-1"].suspended is True
      and len(im.suspended()) == 1,
      "autoimmune rule did not suspend")
hit2 = im.match(source="evil", reason_class="G0-secrets", text_length=10)
check("immune-suspended-quiet", hit2 is None, "suspended pattern fired")

# legitimacy is never self-certified: no ref -> raises
try:
    im.note_legit_fire("pat-1", resolution_ref="")
    check("immune-legit-needs-ref", False, "no ValueError")
except ValueError:
    check("immune-legit-needs-ref", True)

# match_from_outcome: features come from the gate's own verdict
class FakeOutcome:
    verdict = "rejected"
    reasons = ["G0-secrets: api key pattern"]
im2 = ImmuneMemory()
im2.bank(ThreatPattern(id="p2", reason_class="G0-secrets",
                       attack_class="poisoned-rag-injection"))
r_probe = rec(id="probe-1", source="evil-src")
hit3 = im2.match_from_outcome(r_probe, FakeOutcome())
check("immune-match-from-outcome",
      hit3 is not None and hit3.id == "p2",
      "gate-derived features did not match")

# threat record: max salience + decay_exempt, no content
kw = im.threat_record(pat, "G0-secrets", "threat-1")
check("immune-threat-record-exempt",
      kw["decay_exempt"] is True and kw["salience"] == 1.0,
      "threat class not decay-exempt")

# canary drill
dr = CanaryDrill()
dr.plant("can-1")
check("canary-caught", dr.score("can-1", "rejected") is True)
dr.plant("can-2")
check("canary-missed", dr.score("can-2", "admitted") is False)
check("canary-catch-rate", dr.catch_rate() == 0.5,
      f"rate={dr.catch_rate()}")
check("canary-missed-list", [c.id for c in dr.missed()] == ["can-2"])
check("canary-unknown", dr.score("nope", "rejected") is None)

# threat record persists through the gate, sealed, exempt
store, path = fresh_store()
tr = rec(**kw)
out = store.write(tr)
got = store.get("threat-1")
check("immune-threat-persisted", out.verdict == "admitted"
      and got is not None and got.decay_exempt is True,
      f"verdict={out.verdict}")
store.close(); os.remove(path)

# ---------------------------------------------------------------------------
# canary records are written with the canary owner (isolation)
store, path = fresh_store()
c1 = rec(id="canary-q", owner="canary",
         # G5b (Red-Team Round 2): lone claims at confidence >= 0.80
         # queue without a disjoint-origin corroborator. Fixtures in
         # this file whose subject is NOT the write gate carry
         # confidence 0.6 so they land and exercise their own path.
         provenance=Provenance(confidence=0.6),
         text="the password reset flow requires manager approval per policy v3; "
         "verify the approver list at 09:00",
         content="the password reset flow requires manager approval per policy v3; "
         "verify the approver list at 09:00",
         type="fact")
store.write(c1)
probe = SelfProber()
probe.plant_canary("canary-q", "password reset flow approval")
al = probe.ping_canary(store)
check("echolocation-canary-retrievable", al is None,
      f"unexpected alarm: {al}")
# now make it unretrievable: archive it and drain the query path
store.update_metadata("canary-q", tier="archive")
miss_alarm = None
for _ in range(CANARY_ALARM_AFTER + 1):
    miss_alarm = probe.ping_canary(store)
check("echolocation-canary-alarm", miss_alarm is not None
      and miss_alarm.kind == "canary", "no alarm on lost canary")

# staleness: archived record still answering live queries
stale = probe.probe_staleness(store, ["password reset flow approval"])
check("echolocation-staleness", stale is not None
      and "canary-q" in stale.record_ids, "no staleness finding")

# contradiction: open declared dispute
a = rec(id="ca", text="the cap is 30 percent for Q3; raise it to 40 percent "
        "after the audit on 2026-10-20", content="the cap is 30 percent for Q3; "
        "raise it to 40 percent after the audit on 2026-10-20",
        provenance=Provenance(confidence=0.6, contradicts=["cb"]))
b = rec(id="cb", text="the cap is 40 percent for Q3; the audit on 2026-10-20 "
        "set the new limit", content="the cap is 40 percent for Q3; the audit "
        "on 2026-10-20 set the new limit",
        provenance=Provenance(confidence=0.6))
store.write(a); store.write(b)
contra = probe.probe_contradictions(store)
check("echolocation-contradiction", contra is not None
      and "ca" in contra.record_ids, "no contradiction finding")
store.close(); os.remove(path)

# ---------------------------------------------------------------------------
# episodic: full episode assembly with provenance
# ---------------------------------------------------------------------------

store, path = fresh_store()
ep2 = rec(id="ep2", text="council voted sequenced on v0.4 at 10:24 on 2026-10-20 "
          "with 6 partners present",
          content="council voted sequenced on v0.4 at 10:24 on 2026-10-20 "
          "with 6 partners present", owner="council",
          gathered_how="vote-log",
          provenance=Provenance(confidence=0.6))
ep1 = rec(id="ep1", text="v0.4 was sequenced after the 10:24 vote; record the "
          "outcome in the decision log",
          content="v0.4 was sequenced after the 10:24 vote; record the "
          "outcome in the decision log", episodic_record_id="ep2",
          owner="council", gathered_how="vote-log",
          provenance=Provenance(confidence=0.6))
store.write(ep2); store.write(ep1)
ep = episode_for(store, "ep1")
check("episodic-chain", [l.record_id for l in ep.chain[:2]] == ["ep1", "ep2"],
      f"chain={[l.record_id for l in ep.chain]}")
check("episodic-context", "council" in ep.owners
      and "vote-log" in ep.gathered_how, "relational context lost")
check("episodic-unknown", episode_for(store, "nope").chain == [],
      "unknown head not empty")
recs = recall_episodes(store, "sequenced")
check("episodic-recall", len(recs) >= 1 and recs[0].head_id in ("ep1", "ep2"),
      "no episode recalled")
store.close(); os.remove(path)

# ---------------------------------------------------------------------------
# shards: exclusive ownership, deltas, cross-shard conflicts
# ---------------------------------------------------------------------------

sp1, pp1 = fresh_store()
sp2, pp2 = fresh_store()
sh1, sh2 = Shard("research", sp1), Shard("build", sp2)
sa = rec(id="sa", text="X is true per the 10:24 calibration run; verify against "
         "seed 42 before closing the ticket", content="X is true per the 10:24 "
         "calibration run; verify against seed 42 before closing the ticket",
         provenance=Provenance(confidence=0.6, contradicts=["sb"]))
sb = rec(id="sb", text="X is false per the 10:24 calibration run; re-check seed "
         "42 before closing the ticket", content="X is false per the 10:24 "
         "calibration run; re-check seed 42 before closing the ticket",
         provenance=Provenance(confidence=0.6))
sh1.write(sa); sh2.write(sb)
core = Core()
core.add_shard(sh1); core.add_shard(sh2)
d1 = sh1.delta()
check("shard-delta", d1.lane == "research" and d1.records == 1
      and d1.admitted == 1, f"delta={d1}")
xc = core.cross_shard_conflicts()
check("shard-cross-conflict",
      any({"sa", "sb"} == {c["a"], c["b"]}
          for c in xc), f"conflicts={xc}")
# finding 2: cross-shard exact-duplicate check (exact-only, never fuzzy)
dup = rec(id="sa2", text="X is true per the 10:24 calibration run; verify against "
      "seed 42 before closing the ticket", content="X is true per the 10:24 "
      "calibration run; verify against seed 42 before closing the ticket")
check("shard-exact-dup-elsewhere",
      core.exact_duplicate_elsewhere(dup, own_lane="build") == "research",
      "cross-shard duplicate not detected")
near = rec(id="sa3", text="X is almost true per the 10:24 run; re-check seed 7 "
       "before closing", content="X is almost true per the 10:24 run; re-check "
       "seed 7 before closing")
check("shard-near-dup-not-flagged",
      core.exact_duplicate_elsewhere(near, own_lane="build") is None,
      "fuzzy match flagged")
core.broadcast_goal("close the arc", lanes=["research"])
d2 = sh2.delta()
check("shard-goal-scoped", d2.records == 1, "goal leaked to wrong shard")
sp1.close(); sp2.close(); os.remove(pp1); os.remove(pp2)

# ---------------------------------------------------------------------------
# agent: ears/mind/mouth, hard gates, calibration wiring
# ---------------------------------------------------------------------------

store, path = fresh_store()
cal_dir = tempfile.mkdtemp()
agent = MemoryAgent(store,
                    calibration_path=os.path.join(cal_dir, "calibration.json"))
# ears: ingest through the gate
ing = agent.ingest(rec(id="in-1", text="the loop closed the arc at 16:41 after "
                       "6 legs; file the synth in watch-log",
                       content="the loop closed the arc at 16:41 after "
                       "6 legs; file the synth in watch-log",
                       provenance=Provenance(confidence=0.6)))
check("agent-ingest", ing["verdict"] == "admitted",
      f"verdict={ing['verdict']}")
# ears: retrieval logs real access events
hits = agent.retrieve("closed the arc")
check("agent-retrieve", len(hits) >= 1 and hits[0].id == "in-1",
      "no retrieval")
check("agent-access-logged", len(store.access_events()) >= 1,
      "access not logged")

# mind: conflict-conditioned decision, persisted with provenance
cands = [Candidate(id="c1", description="keep building"),
         Candidate(id="c2", description="stop and report")]
prefs = [Preference(candidate_id="c1", kind="better", reason="progress")]
ev = [rec(id="ev1", text="build is on track", content="build is on track")]
res = agent.decide("ship or pause?", cands, prefs, ev)
check("agent-decide", res["selected_id"] in ("c1", "c2")
      and 0.0 <= res["confidence"] <= 1.0
      and res["evidence_ids"] == ["ev1"],
      f"result={res.get('selected_id')}")
check("agent-decide-persisted", res.get("record_id") is not None
      and store.get(res["record_id"]) is not None,
      "decision not persisted")

# mind: impasse is fail-closed, never a guess
res2 = agent.decide("empty?", [], [])
check("agent-impasse", res2["selected_id"] is None
      and res2["impasse"] == "no-candidate", "impasse not fail-closed")

# calibration wiring: real pair persists
agent.log_decision_pair(0.8, True)
check("agent-calibration-pair", agent.calibration.pairs == [(0.8, True)],
      "pair not logged")
check("agent-calibration-persisted",
      os.path.exists(agent.calibration_path),
      "calibration file not written")

# mouth: answer carries provenance + confidence
ans = agent.answer("closed the arc")
check("agent-answer", ans.evidence_ids and ans.confidence == 0.5,
      "answer missing provenance/confidence")

# findings 7/17: immune + canary owners never enter answers
im_rec = rec(id="imm-1", owner="immune", source="immune/attack-memory",
             text="threat memory: 3 attack classes "
             "logged on 2026-10-20; review the patterns weekly",
             content="threat memory: 3 attack classes logged on 2026-10-20; "
             "review the patterns weekly", type="pattern")
store.write(im_rec)
ans2 = agent.answer("threat memory")
check("agent-answer-excludes-system",
      all(e != "imm-1" for e in ans2.evidence_ids),
      "immune record leaked into answer")

# finding 10: archived records are not answers by default
arch = rec(id="arch-1", text="old closed fact from the 2026-10-19 audit; keep for "
      "reference per ticket T-42, do not delete", content="old closed fact from "
      "the 2026-10-19 audit; keep for reference per ticket T-42, do not delete",
      provenance=Provenance(confidence=0.6))
store.write(arch)
store.update_metadata("arch-1", tier="archive")
hits_arch = agent.retrieve("old closed fact")
check("agent-answer-excludes-archive",
      all(r.id != "arch-1" for r in hits_arch),
      "archived record surfaced as answer")
hits_arch_in = agent.retrieve("old closed fact", include_archived=True)
check("agent-archive-opt-in",
      any(r.id == "arch-1" for r in hits_arch_in),
      "explicit archive opt-in not honored")

# mouth: hard gates queue for nitesh, never execute
a_spend = agent.propose_action("buy credits", tags=["spending"])
a_pub = agent.propose_action("publish the report", tags=["publishing"])
a_ok = agent.propose_action("run the probe", tags=["internal"])
check("agent-hardgate-spending",
      a_spend.queued_for_nitesh and not a_spend.executed
      and a_pub.queued_for_nitesh and not a_pub.executed,
      "hard gate executed")
check("agent-internal-executes",
      a_ok.executed and not a_ok.queued_for_nitesh,
      "internal action not executed")
# finding 15: side-effecting actions queue even without a hard-gate tag
a_se = agent.propose_action("send the digest", tags=["notify"],
                            side_effect=True)
check("agent-sideeffect-queues",
      a_se.queued_for_nitesh and not a_se.executed,
      "side-effect action executed without approval")
check("agent-nitesh-queue", len(agent.pending_for_nitesh()) == 3,
      "nitesh queue wrong")

# finding 14: calibration pairs deduplicate
agent.log_decision_pair(0.8, True)   # duplicate of the earlier pair
check("agent-calibration-dedup", agent.calibration.pairs == [(0.8, True)],
      f"pairs={agent.calibration.pairs}")

# loop cycle: runs, reports, never executes hard gates itself
cyc = agent.run_cycle()
check("agent-cycle", cyc["cycle"] == 1
      and "sentinel_status" in cyc and "findings" in cyc,
      f"cycle={cyc}")
store.close(); os.remove(path)

# ---------------------------------------------------------------------------
# janitor amendments: decay_exempt + class-uniqueness
# ---------------------------------------------------------------------------

now = 1792500000.0
old_t = now - 100 * 86400


def jrec(rid, **kw):
    base = dict(id=rid, text="old", timestamp=datetime(2026, 6, 1),
                type="fact", ttl_class="session", epistemic_tier="observed",
                explicit=True, owner="o", gathered_how="g", tier="archive",
                created_at=old_t, last_accessed=old_t, access_count=0,
                decay_score=0.01)
    base.update(kw)
    return MemoryRecord(**base)


j = Janitor()
ops = j._lifecycle_for(jrec("ex", decay_exempt=True), now,
                        {"ex": jrec("ex")})
check("janitor-exempt-no-migrate-prune",
      all(o.op not in ("migrate", "prune_eligible") for o in ops),
      f"ops={[o.op for o in ops]}")
ops = j._lifecycle_for(jrec("u1"), now, {"u1": jrec("u1")})
check("janitor-unique-no-prune",
      all(o.op != "prune_eligible" for o in ops),
      f"ops={[o.op for o in ops]}")
store2 = {"nu1": jrec("nu1"), "nu2": jrec("nu2")}
ops = j._lifecycle_for(store2["nu1"], now, store2)
check("janitor-nonunique-prunes",
      any(o.op == "prune_eligible" for o in ops),
      "non-unique record not prune-eligible")

# storage: v0.6 column persists + migrates
store, path = fresh_store()
r = rec(id="vex", decay_exempt=True, owner="immune",
        source="immune/attack-memory")
store.write(r)
check("storage-decay-exempt", store.get("vex").decay_exempt is True)
rt = record_from_dict(record_to_dict(store.get("vex")))
check("storage-decay-exempt-roundtrip", rt.decay_exempt is True)
store.close(); os.remove(path)

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
