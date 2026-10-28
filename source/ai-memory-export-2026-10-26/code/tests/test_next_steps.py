"""Next-steps build queue tests (2026-10-20, ChatGPT incharge order
2,1,5,4,3; record: implementation/next-steps-record.md).

Item 2 - real calibration pairs: decide() registers a pending
decision; note_decision_outcome() resolves it with the OBSERVED
outcome and lands the real (stated confidence, outcome, M) pair in
data/calibration.json - persisted, reloadable, isotonic-consumable.
The caller supplies only the outcome; the confidence is the one
decide() stated. Nothing lands before an outcome is observed.

Run:  python3 tests/test_next_steps.py   (from the repo root)
"""

import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, ".")

from mm.agent import MemoryAgent
from mm.confidence import CalibrationLog
from mm.decision import Candidate, Preference
from mm.storage import SQLiteStore

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


CANDS = [Candidate(id="c1", description="keep building"),
         Candidate(id="c2", description="stop and report")]
CLEAR = [Preference(candidate_id="c1", kind="better", weight=1.0,
                    source_module="test")]


def fresh_agent():
    tdir = tempfile.mkdtemp()
    store = SQLiteStore(os.path.join(tdir, "memory.db"))
    cal = os.path.join(tdir, "calibration.json")
    return MemoryAgent(store, calibration_path=cal), cal


# --- item 2: pending registry + outcome resolution --------------------
# Call-site update (2026-10-21, gate-(a) remediation lane, R-C
# ruling): note_decision_outcome now REQUIRES a named independent
# resolution_source - the resolutions below are observed outcomes,
# so they pass one explicitly. Every assertion is unchanged.

agent, cal_path = fresh_agent()
r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, CLEAR)
check("i2-decide-has-key", bool(r.get("decision_key")),
      f"result keys: {sorted(r)}")
check("i2-no-pair-before-outcome", agent.calibration.pairs == [],
      f"pairs={agent.calibration.pairs}")
pend = agent.pending_decisions()
check("i2-pending-registered", len(pend) == 1
      and pend[0]["decision_key"] == r["decision_key"]
      and pend[0]["confidence"] == r["confidence"],
      f"pending={pend}")

ok = agent.note_decision_outcome(
    r["decision_key"], True,
    resolution_source="observed-outcome", resolved_by="test-suite")
check("i2-resolve-returns-true", ok is True)
check("i2-pair-landed", agent.calibration.pairs == [(r["confidence"], True)],
      f"pairs={agent.calibration.pairs}")
check("i2-pair-has-m", agent.calibration.m_values == [r["conflict_score"]],
      f"m_values={agent.calibration.m_values}")
check("i2-pending-drained", agent.pending_decisions() == [])
check("i2-double-resolve-refused",
      agent.note_decision_outcome(
          r["decision_key"], True,
          resolution_source="observed-outcome") is False
      and len(agent.calibration.pairs) == 1)
check("i2-unknown-key-refused",
      agent.note_decision_outcome(
          "decision-key-99999", False,
          resolution_source="observed-outcome") is False)

# persistence: the pair is on disk and a fresh agent over the same
# paths reloads it; isotonic triples() can consume it (HD-2 shape).
check("i2-calibration-file-on-disk", os.path.exists(cal_path))
with open(cal_path, encoding="utf-8") as f:
    log = CalibrationLog.load_json(f.read())
check("i2-reload-pairs", log.pairs == [(r["confidence"], True)],
      f"reloaded={log.pairs}")
check("i2-triples-consumable",
      log.triples() == [(r["confidence"], True, r["conflict_score"])],
      f"triples={log.triples()}")

# keyed dedup: two DISTINCT decisions with identical stated confidence
# and outcome are two real pairs, not one (legacy unkeyed dedup would
# collapse them - the pending registry exists to prevent exactly that).
agent2, _ = fresh_agent()
keys = []
for _ in range(2):
    rr = agent2.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                       CANDS, CLEAR)
    keys.append(rr["decision_key"])
confs = [p["confidence"] for p in agent2.pending_decisions()]
check("i2-same-confidence-setup", confs[0] == confs[1],
      f"confs={confs}")
for k in keys:
    agent2.note_decision_outcome(
        k, True, resolution_source="observed-outcome",
        resolved_by="test-suite")
check("i2-keyed-pairs-not-collapsed", len(agent2.calibration.pairs) == 2,
      f"pairs={agent2.calibration.pairs}")

# legacy unkeyed dedup unchanged (finding 14 contract).
agent3, _ = fresh_agent()
agent3.log_decision_pair(0.8, True)
agent3.log_decision_pair(0.8, True)
check("i2-legacy-dedup-intact", agent3.calibration.pairs == [(0.8, True)],
      f"pairs={agent3.calibration.pairs}")

# restart durability: pending decisions survive a fresh agent over the
# same store/calibration paths (sidecar), and still resolve once.
tdir = tempfile.mkdtemp()
store = SQLiteStore(os.path.join(tdir, "memory.db"))
cal = os.path.join(tdir, "calibration.json")
a_first = MemoryAgent(store, calibration_path=cal)
rr = a_first.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                    CANDS, CLEAR)
a_second = MemoryAgent(SQLiteStore(os.path.join(tdir, "memory.db")),
                       calibration_path=cal)
check("i2-pending-survives-restart",
      [p["decision_key"] for p in a_second.pending_decisions()]
      == [rr["decision_key"]],
      f"pending={a_second.pending_decisions()}")
check("i2-resolve-after-restart",
      a_second.note_decision_outcome(
          rr["decision_key"], False,
          resolution_source="observed-outcome",
          resolved_by="test-suite") is True
      and a_second.calibration.pairs == [(rr["confidence"], False)],
      f"pairs={a_second.calibration.pairs}")

# --- item 1: margin-relative tie epsilon -------------------------------
# select() semantics: absolute band is scale-blind; relative band is a
# fraction of the leader's net score. Default in select() stays
# "absolute" (v0.3 primitive); the agent path defaults to "relative"
# (majority adoption vote, tie-lever-run1.json).

from mm.decision import Candidate as DCand, Preference as DPref, select

A = DCand(id="a", description="a")
B = DCand(id="b", description="b")


def nets(wa, wb):
    return [DPref(candidate_id="a", kind="better", weight=wa),
            DPref(candidate_id="b", kind="better", weight=wb)]


# compressed low scores: margin 0.03 - tie under absolute (<=0.05),
# decision under relative (eps = 0.05 * 0.40 = 0.02).
d = select([A, B], nets(0.40, 0.37))
check("i1-absolute-ties-compressed", d.selected_id is None
      and d.impasse.kind == "tie", f"{d}")
d = select([A, B], nets(0.40, 0.37), tie_epsilon_mode="relative")
check("i1-relative-decides-compressed", d.selected_id == "a", f"{d}")
# large accumulated nets: margin 0.20 - decision under absolute,
# tie under relative (eps = 0.05 * 5.0 = 0.25).
d = select([A, B], nets(5.0, 4.8))
check("i1-absolute-decides-large", d.selected_id == "a", f"{d}")
d = select([A, B], nets(5.0, 4.8), tie_epsilon_mode="relative")
check("i1-relative-ties-large", d.selected_id is None
      and d.impasse.kind == "tie", f"{d}")
# an EXACT tie stays a tie in both modes (margin 0 <= any epsilon).
d = select([A, B], nets(0.35, 0.35), tie_epsilon_mode="relative")
check("i1-exact-tie-stays-tie", d.selected_id is None
      and d.impasse.kind == "tie", f"{d}")
# invalid mode is a hard error, never a silent fallback.
try:
    select([A, B], nets(1.0, 0.5), tie_epsilon_mode="bogus")
    check("i1-invalid-mode-raises", False, "no exception")
except ValueError:
    check("i1-invalid-mode-raises", True)
# agent path: default mode is relative now; explicit absolute restores
# the pre-adoption behavior on the same inputs.
agent4, _ = fresh_agent()
rr = agent4.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                   CANDS, CLEAR)
check("i1-agent-default-relative", rr["tie_epsilon_mode"] == "relative",
      f"{rr.get('tie_epsilon_mode')}")
rr = agent4.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                   CANDS, CLEAR, tie_epsilon_mode="absolute")
check("i1-agent-explicit-absolute", rr["tie_epsilon_mode"] == "absolute",
      f"{rr.get('tie_epsilon_mode')}")

# --- item 3: comms D-C2 acceptance-rate auto-tightening + draining ---

from datetime import timedelta, timezone as _tz

_IST = _tz(timedelta(hours=5, minutes=30))
DAY = 86400


def _noon(day_offset):
    return datetime(2026, 10, 21, 12, 0, tzinfo=_IST).timestamp() \
        + day_offset * DAY


HI3 = dict(severity=0.9, confidence=0.9, novelty=0.9)   # score 0.729
MID3 = dict(severity=0.7, confidence=0.7, novelty=0.7)  # score 0.343

agent5, _ = fresh_agent()
st = agent5.outreach_threshold_state(at=_noon(0))
check("i3-state-baseline", st["opportunity"]["effective_threshold"] == 0.25
      and st["opportunity"]["judged"] == 0
      and st["opportunity"]["acceptance_rate"] is None, f"{st['opportunity']}")

# six opportunity outreaches on six days (daily budget is per-day);
# responses noted afterwards: 5 dismissed, 1 accepted.
opp_ids = []
for k in range(6):
    e = agent5.propose_outreach("opportunity", f"opp {k}", why="test why",
                                reference="rec-1", at=_noon(k), **HI3)
    opp_ids.append(e["id"])
check("i3-proposals-sent", all(
    x["decision"] == "send" for x in agent5.outreach_log
    if x["trigger"] == "opportunity"),
    f"{[(x['id'], x['decision']) for x in agent5.outreach_log]}")
for oid in opp_ids[:5]:
    agent5.note_outreach_response(oid, "dismissed", at=_noon(5))
agent5.note_outreach_response(opp_ids[5], "accepted", at=_noon(5))
e0 = [x for x in agent5.outreach_log if x["id"] == opp_ids[0]][0]
check("i3-response-stamped", e0.get("response_at") == _noon(5),
      f"{e0.get('response_at')}")
st = agent5.outreach_threshold_state(at=_noon(5))
so = st["opportunity"]
check("i3-drift-tightens", so["judged"] == 6
      and abs(so["acceptance_rate"] - 1 / 6) < 1e-9
      and abs(so["acceptance_floor"] - (0.25 + (0.5 - 1 / 6) * 0.5)) < 1e-9
      and so["effective_threshold"] == so["acceptance_floor"]
      and so["effective_threshold"] > 0.375,
      f"{so}")
check("i3-drift-pauses-with-backoff", so["paused"] is True, f"{so}")

# the drifted gate actually bites: a mid score that cleared the old
# 0.25 floor is now suppressed; a high score still sends.
agent5.reenable_outreach_class("opportunity")
e = agent5.propose_outreach("opportunity", "mid after drift",
                            why="test why", reference="rec-1",
                            at=_noon(6), **MID3)
check("i3-gate-bites-mid", e["decision"] == "suppress"
      and any("below threshold" in r for r in e["reasons"]),
      f"{e['decision']} {e['reasons']}")
e = agent5.propose_outreach("opportunity", "hi after drift",
                            why="test why", reference="rec-1",
                            at=_noon(6), **HI3)
check("i3-gate-passes-hi", e["decision"] == "send", f"{e['decision']}")

# tightening only: a fully accepted class never loosens below base.
for k in range(4):
    e = agent5.propose_outreach("briefing", f"brief {k}", why="test why",
                                at=_noon(k), **HI3)
    agent5.note_outreach_response(e["id"], "accepted", at=_noon(k))
sb = agent5.outreach_threshold_state(at=_noon(5))["briefing"]
check("i3-no-loosening", sb["judged"] == 4
      and sb["acceptance_rate"] == 1.0
      and sb["acceptance_floor"] == 0.25
      and sb["effective_threshold"] == 0.25, f"{sb}")

# minimum judged sample: 2 judged outcomes cannot move the floor.
for k in range(2):
    e = agent5.propose_outreach("sentinel_alert", f"alert {k}",
                                why="test why", reference="rec-9",
                                at=_noon(k), **HI3)
    agent5.note_outreach_response(e["id"], "dismissed", at=_noon(1))
ss = agent5.outreach_threshold_state(at=_noon(1))["sentinel_alert"]
check("i3-min-judged", ss["judged"] == 2
      and ss["acceptance_floor"] == 0.25, f"{ss}")

# the window expires: 31 days after the responses, the sample is gone
# and the floor returns to base (tightening is not a ratchet).
st = agent5.outreach_threshold_state(at=_noon(5) + 31 * DAY)
check("i3-window-expiry", st["opportunity"]["judged"] == 0
      and st["opportunity"]["acceptance_floor"] == 0.25,
      f"{st['opportunity']}")

# draining: manual bookkeeping only - stamps, moves, keeps history.
log_len = len(agent5.outreach_log)
out_n = len(agent5.outbox)
drained = agent5.drain_outbox(at=_noon(6))
check("i3-drain-moves", len(drained) == out_n and out_n > 0
      and agent5.outbox == []
      and len(agent5.drained_outreach) == out_n
      and all(x.get("drained_at") == _noon(6) for x in drained)
      and len(agent5.outreach_log) == log_len,
      f"out={out_n} drained={len(drained)}")
check("i3-drain-idempotent", agent5.drain_outbox(at=_noon(6)) == [],
      "second drain must be empty")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
