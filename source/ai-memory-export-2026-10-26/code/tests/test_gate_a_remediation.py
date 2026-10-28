"""Gate-(a) remediation tests (2026-10-21; ChatGPT ruling in
implementation/gate-a-agentpath-chatgpt-ruling.txt; record:
gate-a-remediation-record.md).

R-A (ADOPT): user-facing presentation of a decide() result is
BANDED - state + Policy-C zone + the harness-measured accuracy
of the closest slice, labelled SYNTHETIC - and the raw
two-anchor confidence is suppressed unless explicitly opted in.
This suite pins the banding, the slice references (arm A0 of
the characterization: standard 0.7874 n=348, conflict 0.7895
n=76, tie 0.6271 n=59), the suppression, and that an impasse
never carries an accuracy claim.

R-C (AMEND): a pending decision becomes a real calibration
pair ONLY under a named independent resolution source -
acceptance / self-assessment are refused mechanically - every
pair carries outcome provenance, corrections are appended
events (the calibration log is never rewritten), pair
recording has an explicit consent switch, and reaching 30
pairs unlocks EVALUATION only (no automatic fitting: no new
artifact appears, ever).

R-B is design-only in this lane and R-D is no-change; neither
has code to pin here.

Run:  python3 tests/test_gate_a_remediation.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, ".")

from mm.agent import MemoryAgent, present_decision
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
TIE = [Preference(candidate_id="c1", kind="better", weight=1.0,
                  source_module="test"),
       Preference(candidate_id="c2", kind="better", weight=1.0,
                  source_module="test")]
Q = "ship the v2 build on 2026-10-23 per plan P-7?"


def fresh_agent(**kw):
    tdir = tempfile.mkdtemp()
    store = SQLiteStore(os.path.join(tdir, "memory.db"))
    cal = os.path.join(tdir, "calibration.json")
    return MemoryAgent(store, calibration_path=cal, **kw), cal, tdir


def decided_dict(**over):
    d = {"question": "q?", "selected_id": "c1", "impasse": None,
         "conflict_score": 0.1, "policy_score": 0.1,
         "confidence": 0.6835, "conflict_conditioned": False,
         "tie_broken": None, "decision_key": "decision-key-00001"}
    d.update(over)
    return d


# --- R-A: banded presentation ------------------------------------------

p = present_decision(decided_dict())
check("ra-standard-slice", p["state"] == "decided"
      and p["zone"] == "clear" and p["confidence_band"] == "standard"
      and p["harness_accuracy"]["accuracy"] == 0.7874
      and p["harness_accuracy"]["n"] == 348,
      f"{p['harness_accuracy']}")
check("ra-synthetic-label",
      "NOT production calibration" in p["harness_accuracy"]["evidence"]
      and "UNCALIBRATED" in p["calibration_status"]
      and "not a probability" in p["calibration_status"],
      f"{p['harness_accuracy']['evidence']}")
check("ra-raw-suppressed", p["confidence"] is None
      and p["confidence_suppressed"] is True
      and "0.6835" not in json.dumps(p), f"{p}")
p = present_decision(decided_dict(), show_raw=True)
check("ra-show-raw-opt-in", p["confidence"] == 0.6835
      and p["confidence_suppressed"] is False, f"{p}")

p = present_decision(decided_dict(policy_score=0.8, conflict_score=0.8,
                                  conflict_conditioned=True,
                                  confidence=0.61))
check("ra-conflict-slice", p["zone"] == "contested"
      and p["confidence_band"] == "conflict-conditioned"
      and p["harness_accuracy"]["accuracy"] == 0.7895
      and p["harness_accuracy"]["n"] == 76, f"{p}")

p = present_decision(decided_dict(policy_score=0.8,
                                  conflict_conditioned=True,
                                  tie_broken="provenance"))
check("ra-tie-slice-precedence", p["confidence_band"] == "tie-broken"
      and p["harness_accuracy"]["accuracy"] == 0.6271
      and p["harness_accuracy"]["n"] == 59, f"{p}")

p = present_decision(decided_dict(policy_score=0.97))
check("ra-extreme-zone", p["zone"] == "extreme", f"{p['zone']}")

p = present_decision(decided_dict(selected_id=None, impasse="tie",
                                  confidence=0.5))
check("ra-impasse-no-accuracy", p["state"] == "impasse"
      and p["impasse"] == "tie" and p["harness_accuracy"] is None
      and p["confidence_band"] == "impasse", f"{p}")

# integration: the presentation of a real decide() result.
agent, _cal, _td = fresh_agent()
r = agent.decide(Q, CANDS, CLEAR)
p = agent.present(r)
check("ra-integration-decided", p["state"] == "decided"
      and p["zone"] == "clear" and p["confidence"] is None
      and p["decision_key"] == r["decision_key"], f"{p}")
r2 = agent.decide(Q, CANDS, TIE)
p2 = agent.present(r2)
check("ra-integration-impasse", r2["selected_id"] is None
      and p2["state"] == "impasse" and p2["harness_accuracy"] is None,
      f"{p2}")

# --- R-C: provenance-gated pair accumulation ---------------------------

agent, cal_path, tdir = fresh_agent()
r = agent.decide(Q, CANDS, CLEAR)
key = r["decision_key"]

try:
    agent.note_decision_outcome(key, True)
    check("rc-source-required", False, "no TypeError raised")
except TypeError:
    check("rc-source-required", True)

check("rc-acceptance-refused",
      agent.note_decision_outcome(key, True,
                                  resolution_source="acceptance")
      is False
      and len(agent.pending_decisions()) == 1
      and agent.calibration.pairs == [],
      f"pending={agent.pending_decisions()} pairs={agent.calibration.pairs}")
check("rc-self-and-none-refused",
      agent.note_decision_outcome(key, True,
                                  resolution_source="self-assessment")
      is False
      and agent.note_decision_outcome(key, True,
                                      resolution_source=None) is False
      and agent.calibration.pairs == [])

ok = agent.note_decision_outcome(
    key, True, resolution_source="observed-outcome",
    resolved_by="test-suite")
rp = agent.resolved_pairs()
check("rc-resolved-with-provenance", ok is True
      and agent.calibration.pairs == [(r["confidence"], True)]
      and len(rp) == 1 and rp[0]["outcome"] is True
      and rp[0]["corrected"] is False
      and rp[0]["resolution_source"] == "observed-outcome"
      and rp[0]["resolved_by"] == "test-suite"
      and agent.pair_provenance(key)["kind"] == "outcome",
      f"{rp}")

# corrections: appended events; the log itself is never rewritten.
pairs_before = list(agent.calibration.pairs)
ok = agent.note_decision_correction(
    key, False, resolution_source="verified-record",
    resolved_by="test-suite", note="first reading was wrong")
rp = agent.resolved_pairs()
corr = agent.decision_corrections()
check("rc-correction-recorded", ok is True
      and agent.calibration.pairs == pairs_before
      and rp[0]["outcome"] is False
      and rp[0]["original_outcome"] is True
      and rp[0]["corrected"] is True
      and len(corr) == 1 and corr[0]["kind"] == "correction"
      and corr[0]["original_outcome"] is True
      and corr[0]["previous_outcome"] is True
      and corr[0]["corrected_outcome"] is False, f"{corr}")
check("rc-correction-latest-wins",
      agent.note_decision_correction(
          key, True, resolution_source="verified-record") is True
      and agent.resolved_pairs()[0]["outcome"] is True
      and len(agent.decision_corrections()) == 2
      and agent.calibration.pairs == pairs_before)

r3 = agent.decide("hold the v2 build until 2026-10-30 per plan P-9?",
                  CANDS, CLEAR)
check("rc-correction-refusals",
      agent.note_decision_correction(
          r3["decision_key"], True,
          resolution_source="verified-record") is False
      and agent.note_decision_correction(
          "decision-key-99999", True,
          resolution_source="verified-record") is False
      and agent.note_decision_correction(
          key, True, resolution_source="acceptance") is False)

# privacy: pair records are numbers + resolution metadata only.
# The RESOLVED decision's question text must be gone from both
# files (it is dropped at resolution); the still-pending r3 entry
# legitimately holds its own, different question in the registry.
with open(cal_path, encoding="utf-8") as f:
    cal_text = f.read()
with open(cal_path + ".pending.json", encoding="utf-8") as f:
    sidecar_text = f.read()
check("rc-privacy-no-question-text", Q not in cal_text
      and Q not in sidecar_text, "question text leaked into pair data")

# consent control: off blocks accumulation, decisions stay pending.
agent2, _c2, _t2 = fresh_agent()
rr = agent2.decide(Q, CANDS, CLEAR)
check("rc-recording-off-blocks",
      agent2.set_pair_recording(False) is False
      and agent2.note_decision_outcome(
          rr["decision_key"], True,
          resolution_source="observed-outcome") is False
      and agent2.calibration.pairs == []
      and len(agent2.pending_decisions()) == 1
      and agent2.calibration_status()["pair_recording_enabled"] is False)
check("rc-recording-reenable",
      agent2.set_pair_recording(True) is True
      and agent2.note_decision_outcome(
          rr["decision_key"], True,
          resolution_source="observed-outcome") is True
      and len(agent2.calibration.pairs) == 1)
agent3, _c3, _t3 = fresh_agent(pair_recording=False)
rr3 = agent3.decide(Q, CANDS, CLEAR)
check("rc-constructor-off", agent3.note_decision_outcome(
    rr3["decision_key"], True,
    resolution_source="observed-outcome") is False
    and agent3.calibration.pairs == [])

# status: legacy unkeyed pairs count in the log total only.
agent.log_decision_pair(0.8, True)
st = agent.calibration_status()
check("rc-status-counts", st["log_pairs_total"] == 2
      and st["pairs_with_provenance"] == 1
      and st["corrections"] == 2
      and st["evaluation_unlocked"] is False
      and "evaluation only" in st["fitting"], f"{st}")
check("rc-legacy-pair-no-provenance", len(agent.resolved_pairs()) == 1)

# persistence: provenance + corrections survive a restart, and a
# persisted recording-off state wins over the constructor default.
agent4 = MemoryAgent(SQLiteStore(os.path.join(tdir, "memory.db")),
                     calibration_path=cal_path)
rp4 = agent4.resolved_pairs()
check("rc-persistence", len(rp4) == 1 and rp4[0]["outcome"] is True
      and rp4[0]["corrected"] is True
      and rp4[0]["resolution_source"] == "observed-outcome"
      and len(agent4.decision_corrections()) == 2, f"{rp4}")
agent4.set_pair_recording(False)
agent5 = MemoryAgent(SQLiteStore(os.path.join(tdir, "memory.db")),
                     calibration_path=cal_path)
check("rc-off-persists", agent5.pair_recording_enabled is False)

# the unlock is evaluation-only: 30 real pairs land, the status
# flips, and NOTHING is fitted - no model artifact appears.
agent6, _c6, td6 = fresh_agent()
for i in range(30):
    ri = agent6.decide(f"decision {i} on plan P-7?", CANDS, CLEAR)
    agent6.note_decision_outcome(
        ri["decision_key"], i % 3 != 0,
        resolution_source="observed-outcome", resolved_by="test-suite")
st6 = agent6.calibration_status()
files6 = sorted(os.listdir(td6))
check("rc-unlock-evaluation-only", st6["pairs_with_provenance"] == 30
      and st6["evaluation_unlocked"] is True
      and all(fn.startswith("memory.db")
              or fn in ("calibration.json",
                        "calibration.json.pending.json")
              for fn in files6),
      f"status={st6} files={files6}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
