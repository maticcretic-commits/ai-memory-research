"""Gate-(a) agent-path structural confidence bounds
(2026-10-21; characterization lane, preregistration:
implementation/gate-a-agentpath-preregistration.md).

The preregistered invariant check over the lane's 4000
harness decisions (fresh seeds 11000-11001, arms A0-A3)
found ZERO violations: absent calibration history,
decide()'s stated confidence is structurally bounded -
selected decisions in [0.05, 0.70] (base 0.70 minus the
kappa*M*(1-P) penalty, floored at 0.05), impasse decisions
in [0.05, 0.50] (base 0.50, penalty only lowers). This
suite pins that bound on fixtures so a future change to
the base constants or the review pass cannot silently
widen the user-facing confidence range. It pins a
STRUCTURAL bound only - the characterization record
(gate-a-agentpath-record.md) is explicit that the bounded
score is not thereby calibrated (gate (a) still fails).

Run:  python3 tests/test_gate_a_agentpath.py
"""

import sys
import tempfile
from datetime import datetime

sys.path.insert(0, ".")

from mm.agent import MemoryAgent
from mm.decision import Candidate, Preference
from mm.reflect import MemoryRecord, Provenance
from mm.storage import SQLiteStore

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


CANDS = [Candidate(id="c1", description="keep building"),
         Candidate(id="c2", description="stop and report")]
CLEAR_PREFS = [Preference(candidate_id="c1", kind="better",
                          weight=1.0),
               Preference(candidate_id="c2", kind="better",
                          weight=0.2)]
TIED_PREFS = [Preference(candidate_id="c1", kind="better",
                         weight=1.0),
              Preference(candidate_id="c2", kind="better",
                         weight=1.0)]
Q = "ship the v2 build on 2026-10-23 per plan P-7?"


def rec(rid, tier="observed", conf=1.0, salience=0.9,
        contradicts=None):
    return MemoryRecord(
        id=rid, text=f"record {rid} with concrete detail for gates",
        timestamp=datetime.utcnow(), salience=salience,
        epistemic_tier=tier,
        provenance=Provenance(confidence=conf,
                              contradicts=contradicts or []))


def agent():
    td = tempfile.mkdtemp(prefix="gatea-test-")
    return MemoryAgent(SQLiteStore(f"{td}/memory.db"),
                       calibration_path=f"{td}/calibration.json")


def main():
    # 1. Clear selection, no conflict: confidence is the
    #    0.70 base exactly, inside the selected bound.
    ag = agent()
    res = ag.decide(Q, CANDS, CLEAR_PREFS, [])
    check("clear selection made", res["selected_id"] == "c1")
    check("no-conflict confidence == 0.70 base",
          res["confidence"] == 0.70, f"got {res['confidence']}")
    check("selected confidence within [0.05, 0.70]",
          0.05 <= res["confidence"] <= 0.70)

    # 2. Conflicted selection: the penalty lowers confidence
    #    but the [0.05, 0.70] bound holds. Evidence is tier
    #    "unknown" (cap 0.5) so precision P < 1 and the
    #    kappa*M*(1-P) penalty actually bites - with
    #    full-precision evidence the penalty is 0 by design.
    ag = agent()
    ev = [rec("e1", tier="unknown", contradicts=["e2"]),
          rec("e2", tier="unknown", contradicts=["e1"]),
          rec("e3", tier="unknown", contradicts=["e4"]),
          rec("e4", tier="unknown", contradicts=["e3"])]
    res = ag.decide(Q, CANDS, CLEAR_PREFS, ev)
    check("conflict registered", res["conflict_score"] > 0,
          f"M={res['conflict_score']}")
    if res["selected_id"] is not None:
        check("conflicted selection penalized below base",
              res["confidence"] < 0.70, f"got {res['confidence']}")
        check("conflicted confidence within [0.05, 0.70]",
              0.05 <= res["confidence"] <= 0.70)
    else:
        check("conflicted impasse within [0.05, 0.50]",
              0.05 <= res["confidence"] <= 0.50)

    # 3. Tied preferences: impasse confidence within
    #    [0.05, 0.50] - never the selected base.
    ag = agent()
    res = ag.decide(Q, CANDS, TIED_PREFS, [])
    check("tie impasse", res["selected_id"] is None
          and res["impasse"] is not None)
    check("impasse confidence within [0.05, 0.50]",
          0.05 <= res["confidence"] <= 0.50,
          f"got {res['confidence']}")

    # 4. No preferences at all: impasse, same bound.
    ag = agent()
    res = ag.decide(Q, CANDS, [], [])
    check("empty impasse within [0.05, 0.50]",
          res["selected_id"] is None
          and 0.05 <= res["confidence"] <= 0.50)

    # 5. Every stated confidence is a probability-range
    #    value: [0, 1] on all fixtures above is implied by
    #    the tighter bounds; assert the floor never crosses
    #    zero even under maximal penalty (extreme conflict,
    #    zero-precision evidence).
    ag = agent()
    ev = [rec(f"x{i}", tier="unknown", conf=1.0, salience=1.0,
              contradicts=[f"x{i+1}"]) for i in range(0, 8, 2)]
    ev += [rec(f"x{i+1}", tier="unknown", conf=1.0, salience=1.0,
               contradicts=[f"x{i}"]) for i in range(0, 8, 2)]
    res = ag.decide(Q, CANDS, CLEAR_PREFS, ev)
    check("max-penalty confidence >= 0.05 floor",
          res["confidence"] >= 0.05, f"got {res['confidence']}")
    check("max-penalty confidence <= 0.70",
          res["confidence"] <= 0.70)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
