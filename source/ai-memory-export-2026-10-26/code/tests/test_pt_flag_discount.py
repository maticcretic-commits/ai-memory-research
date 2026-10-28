"""PT flag-discount (FD-3) tests (2026-10-21; design consult,
ChatGPT ruling D1-D5; preregistration:
implementation/design-consults-preregistration.md; design:
implementation/pt-flag-discount-design.md).

FD-3: when decide() is given a source-trust registry, each
support record's P_c contribution is adjusted by its own
origin's flag state - permanent origins EXCLUDED from P_c,
active flags HALVED (factor 0.50, the ruling's policy price),
rehabilitated / never-flagged / proven / unproven origins at
full value (no cold-start tax). Scope is P_c only: the
precision P is untouched. Stamps tie_break_discounted in the
result and the persisted decision record when any support
record was halved or excluded. No registry = pre-build
behaviour. PT remains mechanism-verified only (PG-D) - no
accuracy claim is made or tested here.

Run:  python3 tests/test_pt_flag_discount.py   (from repo root)
"""

import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, ".")

from mm.agent import MemoryAgent
from mm.decision import Candidate, Preference
from mm.reflect import MemoryRecord, Provenance
from mm.source_trust import SourceTrustRegistry
from mm.storage import SQLiteStore

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


CANDS = [Candidate(id="c1", description="keep building"),
         Candidate(id="c2", description="stop and report")]
TIED_PREFS = [Preference(candidate_id="c1", kind="better", weight=1.0),
              Preference(candidate_id="c2", kind="better", weight=1.0)]
Q = "ship the v2 build on 2026-10-23 per plan P-7?"


def rec(rid, tier="unknown", conf=1.0, salience=0.5, contradicts=None,
        owner="", source=""):
    return MemoryRecord(
        id=rid, text=f"record {rid} with concrete detail for gates",
        timestamp=datetime.utcnow(), salience=salience,
        epistemic_tier=tier, owner=owner, source=source,
        provenance=Provenance(confidence=conf,
                               contradicts=contradicts or []))


def conflict_evidence(n_pairs, salience=0.9, conf=0.6):
    ev = []
    for i in range(n_pairs):
        ev.append(rec(f"ca-{i}", conf=conf, salience=salience,
                      contradicts=[f"cb-{i}"]))
        ev.append(rec(f"cb-{i}", conf=conf, salience=salience))
    return ev


EV_CONTESTED = conflict_evidence(8, salience=0.9)    # M ~ 0.835


def fresh_agent():
    tdir = tempfile.mkdtemp()
    store = SQLiteStore(os.path.join(tdir, "memory.db"))
    cal = os.path.join(tdir, "calibration.json")
    return MemoryAgent(store, calibration_path=cal), store


def sup(rid, owner, source, conf, tier="observed"):
    return rec(rid, tier=tier, conf=conf, owner=owner, source=source)


def probe(owner, source):
    return rec("probe", owner=owner, source=source)


def flagged_reg(owner, source):
    reg = SourceTrustRegistry()
    reg.note_poison(probe(owner, source))
    return reg


def rehabilitated_reg(owner, source):
    reg = flagged_reg(owner, source)
    p = probe(owner, source)
    for _ in range(5):
        reg.note_admitted(p)
    return reg


def permanent_reg(owner, source):
    reg = rehabilitated_reg(owner, source)
    reg.note_poison(probe(owner, source))
    return reg


BAD = ("badlane", "ops/feed")
CLEAN = ("cleanlane", "lab/notes")
agent, store = fresh_agent()

# Registry state sanity (the fixtures the decide() checks rely on).
st = flagged_reg(*BAD).stats_for(*BAD)
check("fx-flagged-state", st.poison == 1 and st.permanent is False)
st = rehabilitated_reg(*BAD).stats_for(*BAD)
check("fx-rehabilitated-state", st.rehabilitations == 1
      and st.poison == st.poison_covered and st.permanent is False)
st = permanent_reg(*BAD).stats_for(*BAD)
check("fx-permanent-state", st.permanent is True)

# FD3-1: the 0.50 factor, exactly. Flagged support q=0.80 -> 0.40;
# clean support 0.55. |dP| = 0.15 fires for the CLEAN candidate
# only if the discounted value is exactly 0.40. Control (no
# registry): |0.80 - 0.55| = 0.25 fires for c1.
SUP1 = {"c1": [sup("s-bad", *BAD, 0.80)], "c2": [sup("s-cln", *CLEAN, 0.55)]}
r = agent.decide(Q, CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support=SUP1, trust_registry=flagged_reg(*BAD))
check("fd1-discount-flips-to-clean", r["selected_id"] == "c2"
      and r["tie_broken"] == "provenance", f"result={r}")
check("fd1-stamp-in-result", r["tie_break_discounted"] is True)
stamp = store.get(r["record_id"]) if r.get("record_id") else None
check("fd1-stamp-persisted", stamp is not None
      and json.loads(stamp.content).get("tie_break_discounted") is True,
      "the persisted decision record JSON must carry the stamp")

r = agent.decide(Q, CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support=SUP1)
check("fd5-no-registry-prebuild", r["selected_id"] == "c1"
      and r["tie_broken"] == "provenance"
      and r["tie_break_discounted"] is False,
      "no registry = the pre-build outcome on the same fixture")

# FD3-2: discount stands a fire. Flagged 0.70 -> 0.35 vs clean
# 0.45: |dP| = 0.10 < 0.15 stands; undiscounted it would fire.
SUP2 = {"c1": [sup("s-bad", *BAD, 0.70)], "c2": [sup("s-cln", *CLEAN, 0.45)]}
r = agent.decide(Q, CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support=SUP2, trust_registry=flagged_reg(*BAD))
check("fd2-discount-stands", r["selected_id"] is None
      and r["impasse"] == "tie" and r["tie_broken"] is None
      and r["tie_break_discounted"] is True, f"result={r}")

# Halved but not excluded: flagged 0.90 -> 0.45 vs clean 0.29
# still fires for the flagged-backed candidate (|dP| = 0.16).
SUP2B = {"c1": [sup("s-bad", *BAD, 0.90)], "c2": [sup("s-cln", *CLEAN, 0.29)]}
r = agent.decide(Q, CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support=SUP2B, trust_registry=flagged_reg(*BAD))
check("fd2b-halved-still-counts", r["selected_id"] == "c1"
      and r["tie_broken"] == "provenance", f"result={r}")

# FD3-3: rehabilitated origin at FULL value - same outcome as
# the never-flagged control, and no stamp.
SUP3 = {"c1": [sup("s-reh", *BAD, 0.80)], "c2": [sup("s-cln", *CLEAN, 0.55)]}
r = agent.decide(Q, CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support=SUP3,
                 trust_registry=rehabilitated_reg(*BAD))
check("fd3-rehabilitated-full-value", r["selected_id"] == "c1"
      and r["tie_broken"] == "provenance"
      and r["tie_break_discounted"] is False, f"result={r}")

# FD3-4a: permanent origin EXCLUDED - a candidate backed only by
# it has NO score, so the break cannot fire at all.
SUP4 = {"c1": [sup("s-prm", *BAD, 0.95)], "c2": [sup("s-cln", *CLEAN, 0.60)]}
r = agent.decide(Q, CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support=SUP4, trust_registry=permanent_reg(*BAD))
check("fd4a-permanent-only-support-no-score",
      r["selected_id"] is None and r["impasse"] == "tie"
      and r["tie_broken"] is None
      and r["tie_break_discounted"] is True, f"result={r}")

# FD3-4b: mixed support - the mean recomputes over the rest.
# Excluded: P_c1 = 0.40, |dP| vs 0.60 = 0.20 fires for c2.
# (Included it would be 0.675 vs 0.60 - a stand.)
SUP5 = {"c1": [sup("s-prm", *BAD, 0.95), sup("s-mix", *CLEAN, 0.40)],
        "c2": [sup("s-cln", *CLEAN, 0.60)]}
r = agent.decide(Q, CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support=SUP5, trust_registry=permanent_reg(*BAD))
check("fd4b-mixed-support-recomputed", r["selected_id"] == "c2"
      and r["tie_broken"] == "provenance", f"result={r}")

# FD3-7: precision untouched. A clear-margin (non-tie) decision
# with flagged support in the room: registry or not, selection
# and reviewed confidence are identical.
CLEAR_PREFS = [Preference(candidate_id="c1", kind="better", weight=1.0),
               Preference(candidate_id="c2", kind="better", weight=0.2)]
r_off = agent.decide(Q, CANDS, CLEAR_PREFS, EV_CONTESTED,
                     stakes="medium", evidence_support=SUP1)
r_on = agent.decide(Q, CANDS, CLEAR_PREFS, EV_CONTESTED,
                    stakes="medium", evidence_support=SUP1,
                    trust_registry=flagged_reg(*BAD))
check("fd7-precision-untouched",
      r_off["selected_id"] == r_on["selected_id"] == "c1"
      and r_off["confidence"] == r_on["confidence"]
      and r_off["policy_score"] == r_on["policy_score"],
      f"off={r_off['confidence']} on={r_on['confidence']}")

# FD3-8: proven origin at full value (five clean admissions,
# no poison) - no cold-start / track-record tax in P_c.
reg = SourceTrustRegistry()
p = probe("prolane", "ops/feed")
for _ in range(5):
    reg.note_admitted(p)
SUP8 = {"c1": [sup("s-pro", "prolane", "ops/feed", 0.80)],
        "c2": [sup("s-cln", *CLEAN, 0.55)]}
r = agent.decide(Q, CANDS, TIED_PREFS, EV_CONTESTED, stakes="medium",
                 evidence_support=SUP8, trust_registry=reg)
check("fd8-proven-full-value", r["selected_id"] == "c1"
      and r["tie_break_discounted"] is False
      and reg.tier_for("prolane", "ops/feed") == "proven",
      f"result={r}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
