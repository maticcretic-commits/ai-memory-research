"""Density scaling (DS-A) + provenance tie-break (PT-A) tests
(2026-10-21; ChatGPT rulings DS-A/PT-A + supplementary PG-D;
preregistration: implementation/density-tiebreak-preregistration.md;
record: implementation/density-tiebreak-record.md).

DS-A: select() with density_scale=True divides the RELATIVE tie
epsilon by sqrt(d), d = mean scoring-vote count over the top two.
PT-A: a tie in select() may be resolved by caller-supplied
per-candidate provenance scores when the caller armed it
(tie_break_allowed) and |P_first - P_second| >= 0.15; decide()
arms it only in the Policy C contested zone (TB-1) and only when
the caller attributed support evidence per candidate.

PG-D (supplementary ruling): PT is verified here at unit /
integration level ONLY - no bench accuracy claim is made for it.
DS is verified as a formula (the bench-level split characterization
lives in evals/density_tiebreak_validation.py), not as accuracy.

Run:  python3 tests/test_density_tiebreak.py   (from the repo root)
"""

import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, ".")

from mm.agent import MemoryAgent
from mm.decision import Candidate, Preference, select
from mm.reflect import MemoryRecord, Provenance
from mm.storage import SQLiteStore

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


C1 = Candidate(id="c1", description="keep building")
C2 = Candidate(id="c2", description="stop and report")
CANDS = [C1, C2]


def split_votes(pairs, k):
    """pairs: [(candidate_id, weight)] single better-votes; returns
    the deterministic k-split: each vote becomes k votes of w/k."""
    out = []
    for cid, w in pairs:
        out += [Preference(candidate_id=cid, kind="better",
                           weight=w / k, source_module="bench-split")
                for _ in range(k)]
    return out


def rec(rid, tier="unknown", conf=1.0, salience=0.5, contradicts=None):
    return MemoryRecord(
        id=rid, text=f"record {rid} with concrete detail for gates",
        timestamp=datetime.utcnow(), salience=salience,
        epistemic_tier=tier,
        provenance=Provenance(confidence=conf,
                               contradicts=contradicts or []))


def conflict_evidence(n_pairs, salience=0.9, conf=0.6):
    """Declared-contradiction pairs driving monitor M into a band
    (same construction as tests/test_research_program.py):
    raw = n_pairs * salience; M = 1 - exp(-raw / 4)."""
    ev = []
    for i in range(n_pairs):
        ev.append(rec(f"ca-{i}", conf=conf, salience=salience,
                      contradicts=[f"cb-{i}"]))
        ev.append(rec(f"cb-{i}", conf=conf, salience=salience))
    return ev


def fresh_agent():
    tdir = tempfile.mkdtemp()
    store = SQLiteStore(os.path.join(tdir, "memory.db"))
    cal = os.path.join(tdir, "calibration.json")
    return MemoryAgent(store, calibration_path=cal), store


# ---------------------------------------------------------------------------
# DS-A at select() level: the formula
# ---------------------------------------------------------------------------

# nets 0.30 vs 0.29: relative eps = 0.05 * 0.30 = 0.015; margin 0.01.
P_K1 = split_votes([("c1", 0.30), ("c2", 0.29)], 1)
P_K4 = split_votes([("c1", 0.30), ("c2", 0.29)], 4)

d = select(CANDS, P_K1, tie_epsilon_mode="relative")
check("ds-d1-tie-without-density", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie",
      f"got {d.selected_id}/{d.impasse}")
d = select(CANDS, P_K1, tie_epsilon_mode="relative", density_scale=True)
check("ds-d1-inert", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie",
      "density at d=1 must exactly preserve the relative epsilon")

d = select(CANDS, P_K4, tie_epsilon_mode="relative")
check("ds-k4-tie-without-density", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie",
      "split alone must not change nets or the relative outcome")
d = select(CANDS, P_K4, tie_epsilon_mode="relative", density_scale=True)
check("ds-k4-shrink-decides", d.selected_id == "c1"
      and d.tie_broken is None,
      "eps 0.015/sqrt(4)=0.0075 < margin 0.01 must decide the leader")

# sqrt ratio pinned at two densities: nets 1.00 vs 0.98, margin 0.02,
# relative eps 0.05. k=4 -> eps 0.025 (tie); k=16 -> eps 0.0125 (decide).
d = select(CANDS, split_votes([("c1", 1.00), ("c2", 0.98)], 4),
           tie_epsilon_mode="relative", density_scale=True)
check("ds-ratio-k4-tie", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie",
      f"eps(k=4)=0.025 >= margin 0.02 must tie, got {d.selected_id}")
d = select(CANDS, split_votes([("c1", 1.00), ("c2", 0.98)], 16),
           tie_epsilon_mode="relative", density_scale=True)
check("ds-ratio-k16-decides", d.selected_id == "c1",
      f"eps(k=16)=0.0125 < margin 0.02 must decide, got {d.selected_id}")

# worse votes are scoring votes and count toward density; nets use
# zero-weight worse votes so only the count moves: c1 count 4, c2
# count 1, d = 2.5; nets 0.40 vs 0.385, margin 0.015 < relative
# eps 0.02 (a tie at d = 1), but eps/sqrt(2.5) = 0.0126 < 0.015.
P_WORSE = [Preference(candidate_id="c1", kind="better", weight=0.40),
           Preference(candidate_id="c2", kind="better", weight=0.385)]
P_WORSE += [Preference(candidate_id="c1", kind="worse", weight=0.0)
            for _ in range(3)]
d = select(CANDS, P_WORSE, tie_epsilon_mode="relative",
           density_scale=True)
check("ds-worse-votes-count", d.selected_id == "c1",
      "eps 0.02/sqrt(2.5)=0.0126 < margin 0.015 must decide when "
      "worse votes count toward density")

# indifferent votes are NOT scoring votes: 15 of them on c1 must not
# move d off 1, so the margin-0.015 < eps-0.02 tie stands.
P_IND = [Preference(candidate_id="c1", kind="better", weight=0.40),
         Preference(candidate_id="c2", kind="better", weight=0.385)]
P_IND += [Preference(candidate_id="c1", kind="indifferent", weight=1.0)
          for _ in range(15)]
d = select(CANDS, P_IND, tie_epsilon_mode="relative", density_scale=True)
check("ds-indifferent-not-counted", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie",
      "indifferent votes must not shrink the epsilon")

try:
    select(CANDS, P_K1, tie_epsilon_mode="absolute", density_scale=True)
    check("ds-absolute-raises", False, "no ValueError raised")
except ValueError:
    check("ds-absolute-raises", True)

# ---------------------------------------------------------------------------
# PT-A at select() level: firing conditions (PG-D mechanism matrix)
# ---------------------------------------------------------------------------

TIED = split_votes([("c1", 0.30), ("c2", 0.30)], 1)   # exact tie
NEAR = split_votes([("c1", 0.30), ("c2", 0.295)], 1)  # margin < eps

d = select(CANDS, TIED, tie_epsilon_mode="relative",
           tie_break_provenance={"c1": 0.90, "c2": 0.60},
           tie_break_allowed=True)
check("pt-fires-leader", d.selected_id == "c1"
      and d.tie_broken == "provenance", f"got {d.selected_id}")

d = select(CANDS, NEAR, tie_epsilon_mode="relative",
           tie_break_provenance={"c1": 0.55, "c2": 0.85},
           tie_break_allowed=True)
check("pt-fires-runnerup", d.selected_id == "c2"
      and d.tie_broken == "provenance",
      "the provenance winner may be the net runner-up")

d = select(CANDS, TIED, tie_epsilon_mode="relative",
           tie_break_provenance={"c1": 0.80, "c2": 0.70},
           tie_break_allowed=True)
check("pt-margin-short-stands", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie"
      and d.tie_broken is None, "|dP| = 0.10 < 0.15 must not fire")

d = select(CANDS, TIED, tie_epsilon_mode="relative",
           tie_break_provenance={"c1": 0.95, "c2": 0.55},
           tie_break_allowed=False)
check("pt-not-allowed-stands", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie",
      "unarmed tie-break must never fire")

d = select(CANDS, TIED, tie_epsilon_mode="relative",
           tie_break_provenance={"c1": 0.95}, tie_break_allowed=True)
check("pt-missing-score-stands", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie",
      "both tied candidates need a provenance score")

d = select(CANDS, TIED, tie_epsilon_mode="relative",
           tie_break_provenance=None, tie_break_allowed=True)
check("pt-no-scores-stands", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "tie",
      "no provenance dict = no tie-break")

d = select(CANDS, split_votes([("c1", 0.30), ("c2", 0.10)], 1),
           tie_epsilon_mode="relative",
           tie_break_provenance={"c1": 0.40, "c2": 0.95},
           tie_break_allowed=True)
check("pt-nontie-untouched", d.selected_id == "c1"
      and d.tie_broken is None,
      "a clear margin decides on the margin; provenance never "
      "overrides a non-tie")

d = select(CANDS, TIED, tie_epsilon_mode="relative", conflict_score=0.9,
           conflict_threshold=0.75,
           tie_break_provenance={"c1": 0.95, "c2": 0.55},
           tie_break_allowed=True)
check("pt-conflict-precedence", d.selected_id is None
      and d.impasse is not None and d.impasse.kind == "conflict"
      and d.tie_broken is None,
      "the conflict impasse precedes and precludes the tie-break")

# Composition order (Q3): density first - a tie the density shrink
# resolves is a plain selection, never a tie-break...
d = select(CANDS, P_K4, tie_epsilon_mode="relative", density_scale=True,
           tie_break_provenance={"c1": 0.95, "c2": 0.55},
           tie_break_allowed=True)
check("pt-composition-density-first", d.selected_id == "c1"
      and d.tie_broken is None,
      "density-resolved selections carry no tie_broken stamp")
# ...and with density off, the same fixture's tie reaches the break.
d = select(CANDS, P_K4, tie_epsilon_mode="relative",
           tie_break_provenance={"c1": 0.95, "c2": 0.55},
           tie_break_allowed=True)
check("pt-composition-break-after", d.selected_id == "c1"
      and d.tie_broken == "provenance",
      "a tie surviving the epsilon stage reaches the provenance break")

# ---------------------------------------------------------------------------
# decide() level: TB-1 scope, P_c formula, stamping, pass-throughs
# ---------------------------------------------------------------------------

EV_CONTESTED = conflict_evidence(8, salience=0.9)    # M ~ 0.835
EV_EXTREME = conflict_evidence(14, salience=0.95)     # M ~ 0.964
EV_LOW = conflict_evidence(2, salience=0.9)          # M ~ 0.362
TIED_PREFS = [Preference(candidate_id="c1", kind="better", weight=1.0),
              Preference(candidate_id="c2", kind="better", weight=1.0)]
SUP_C1 = [rec("sup-a1", tier="observed", conf=0.95)]   # P_c1 = 0.95
SUP_C2 = [rec("sup-b1", tier="inferred", conf=0.60)]   # P_c2 = 0.60

agent, store = fresh_agent()
r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support={"c1": SUP_C1, "c2": SUP_C2})
check("dt-fires", r["selected_id"] == "c1"
      and r["tie_broken"] == "provenance"
      and r["conflict_conditioned"] is True
      and r["impasse"] is None, f"result={r}")
stamp = store.get(r["record_id"]) if r.get("record_id") else None
check("dt-stamp-persisted", stamp is not None
      and "tie broken by provenance" in stamp.text
      and json.loads(stamp.content).get("tie_broken") == "provenance",
      "the persisted decision record must carry the stamp")

r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS,
                 [Preference(candidate_id="c1", kind="better",
                             weight=1.0),
                  Preference(candidate_id="c2", kind="better",
                             weight=0.99)],
                 EV_CONTESTED, stakes="medium",
                 evidence_support={"c1": SUP_C2, "c2": SUP_C1})
check("dt-fires-runnerup", r["selected_id"] == "c2"
      and r["tie_broken"] == "provenance",
      "support favouring the net runner-up must select it")

# Tier cap binds inside P_c: c1 declares confidence 1.0 but tier
# "unknown" caps it at 0.50; c2 observed at 0.66 -> P 0.66 wins.
r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support={
                     "c1": [rec("sup-c1", tier="unknown", conf=1.0)],
                     "c2": [rec("sup-c2", tier="observed", conf=0.66)]})
check("dt-tier-cap-binds", r["selected_id"] == "c2"
      and r["tie_broken"] == "provenance",
      "P_c must use min(declared confidence, tier cap), not the "
      "declared value")

r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support={
                     "c1": SUP_C1,
                     "c2": [rec("sup-d1", tier="derived", conf=0.85)]})
check("dt-margin-short-stands", r["selected_id"] is None
      and r["impasse"] == "tie" and r["tie_broken"] is None,
      "|dP| = 0.95 - 0.85 = 0.10 < 0.15 must impasse")

r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, TIED_PREFS, EV_CONTESTED, stakes="high",
                 evidence_support={"c1": SUP_C1, "c2": SUP_C2})
check("dt-high-stakes-closed", r["selected_id"] is None
      and r["impasse"] == "conflict" and r["tie_broken"] is None,
      "high stakes stays fail-closed regardless of support")

r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, TIED_PREFS, EV_EXTREME, stakes="low",
                 evidence_support={"c1": SUP_C1, "c2": SUP_C2})
check("dt-extreme-closed", r["selected_id"] is None
      and r["impasse"] == "conflict" and r["tie_broken"] is None,
      "policy_score >= 0.95 stays fail-closed regardless of support")

r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, TIED_PREFS, EV_LOW, stakes="medium",
                 evidence_support={"c1": SUP_C1, "c2": SUP_C2})
check("dt-below-floor-stands", r["selected_id"] is None
      and r["impasse"] == "tie" and r["tie_broken"] is None,
      "TB-1: below the contested floor a tie impasses even with "
      "support")

r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium")
check("dt-no-support-stands", r["selected_id"] is None
      and r["impasse"] == "tie" and r["tie_broken"] is None
      and r["density_scale"] is False,
      "no support argument = today's behaviour exactly")

r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support={"c1": SUP_C1})
check("dt-missing-candidate-support", r["selected_id"] is None
      and r["impasse"] == "tie" and r["tie_broken"] is None,
      "a candidate without support has no P_c; the break cannot "
      "fire")

# Density pass-through at decide() level: nets 0.50 vs 0.48 from
# 4 votes each (d = 4); margin 0.02 < relative eps 0.025 but
# > eps/sqrt(4) = 0.0125.
DENSE_PREFS = split_votes([("c1", 0.50), ("c2", 0.48)], 4)
r_off = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                     CANDS, DENSE_PREFS, EV_CONTESTED, stakes="medium")
r_on = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                    CANDS, DENSE_PREFS, EV_CONTESTED, stakes="medium",
                    density_scale=True)
check("dt-density-passthrough", r_off["selected_id"] is None
      and r_off["impasse"] == "tie"
      and r_on["selected_id"] == "c1" and r_on["impasse"] is None
      and r_on["tie_broken"] is None and r_on["density_scale"] is True,
      f"off={r_off['selected_id']}/{r_off['impasse']} "
      f"on={r_on['selected_id']}/{r_on['impasse']}")

# Defaults regression: the pre-build contested-zone behaviour,
# including the two new result keys sitting at their defaults.
r = agent.decide("ship the v2 build on 2026-10-23 per plan P-7?",
                 CANDS,
                 [Preference(candidate_id="c1", kind="better",
                             weight=1.0)],
                 EV_CONTESTED, stakes="medium")
check("dt-defaults-unchanged", r["selected_id"] == "c1"
      and r["tie_broken"] is None and r["density_scale"] is False
      and r["conflict_conditioned"] is True, f"result={r}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
