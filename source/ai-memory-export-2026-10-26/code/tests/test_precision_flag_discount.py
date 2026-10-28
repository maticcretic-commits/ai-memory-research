"""Precision-P flag-discount (PF-1) tests (2026-10-21;
follow-up D4 of the PT flag-discount ruling; design:
implementation/precision-flag-discount-design.md; ruling:
implementation/precision-flag-discount-chatgpt-ruling.txt;
preregistration: implementation/
precision-flag-discount-preregistration.md).

PF-1: when decide() is given a source-trust registry, the
precision P (mean over ALL evidence of min(provenance.
confidence, tier cap)) is adjusted per evidence record by
its own origin's flag state, on the FD-3 ladder - PERMANENT
origins EXCLUDED from numerator and denominator, ACTIVE
flags HALVED (0.50, the ruling's policy price),
rehabilitated / never-flagged / proven / unproven at full
value. All-permanent evidence falls back to 0.5 (ruling
E3, the no-evidence default). P feeds ONLY the
kappa*M*(1-P) confidence penalty, so selection, Policy C
zone classification and the fail-closed impasse are
invariant; only stated confidence moves, only downward.
Result (and persisted record) carry precision (raw),
precision_effective, precision_discounted (ruling E5).
No registry = pre-build behaviour. Mechanism-verified
only - production decision pairs = 0, no accuracy claim.

Run:  python3 tests/test_precision_flag_discount.py
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
CLEAR_PREFS = [Preference(candidate_id="c1", kind="better",
                          weight=1.0),
               Preference(candidate_id="c2", kind="better",
                          weight=0.2)]
TIED_PREFS = [Preference(candidate_id="c1", kind="better",
                         weight=1.0),
              Preference(candidate_id="c2", kind="better",
                         weight=1.0)]
Q = "ship the v2 build on 2026-10-23 per plan P-7?"


def rec(rid, tier="unknown", conf=1.0, salience=0.5,
        contradicts=None, owner="", source=""):
    return MemoryRecord(
        id=rid, text=f"record {rid} with concrete detail for gates",
        timestamp=datetime.utcnow(), salience=salience,
        epistemic_tier=tier, owner=owner, source=source,
        provenance=Provenance(confidence=conf,
                              contradicts=contradicts or []))


def ev(rid, owner, source, conf, contradicts=None):
    # tier "observed" (cap 1.00) so the per-record quantity
    # q == conf exactly; salience 0.9 for a live conflict.
    return rec(rid, tier="observed", conf=conf, salience=0.9,
               contradicts=contradicts, owner=owner, source=source)


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
PERM = ("permlane", "ops/feed")


def fresh_agent():
    tdir = tempfile.mkdtemp()
    store = SQLiteStore(os.path.join(tdir, "memory.db"))
    cal = os.path.join(tdir, "calibration.json")
    return MemoryAgent(store, calibration_path=cal), store


agent, store = fresh_agent()

# Fixture sanity: the registry states the checks rely on.
st = flagged_reg(*BAD).stats_for(*BAD)
ok1 = st.poison == 1 and st.permanent is False
st = rehabilitated_reg(*BAD).stats_for(*BAD)
ok2 = st.rehabilitations == 1 and st.permanent is False
st = permanent_reg(*PERM).stats_for(*PERM)
ok3 = st.permanent is True
check("fx-registry-states", ok1 and ok2 and ok3)

# PF-1: exact halving over the evidence list. Flagged q=0.80
# x2 + clean q=0.60 x2: raw = 0.70, effective = (0.40+0.40+
# 0.60+0.60)/4 = 0.50.
EV_PF1 = [ev("a1", *BAD, 0.80, contradicts=["a2"]),
          ev("a2", *BAD, 0.80),
          ev("b1", *CLEAN, 0.60, contradicts=["b2"]),
          ev("b2", *CLEAN, 0.60)]
r = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF1, stakes="medium",
                 trust_registry=flagged_reg(*BAD))
check("pf1-exact-halving",
      abs(r["precision"] - 0.70) < 1e-9
      and abs(r["precision_effective"] - 0.50) < 1e-9
      and r["precision_discounted"] is True, f"result={r}")

# PF-2: the confidence delta is EXACTLY kappa * policy_score
# * (raw - effective); selection and policy score unchanged.
r_off = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF1,
                     stakes="medium")
r_on = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF1,
                    stakes="medium",
                    trust_registry=flagged_reg(*BAD))
delta = r_off["confidence"] - r_on["confidence"]
expect = 0.25 * r_on["policy_score"] * (
    r_on["precision"] - r_on["precision_effective"])
check("pf2-confidence-delta-exact",
      r_off["selected_id"] == r_on["selected_id"] == "c1"
      and r_off["policy_score"] == r_on["policy_score"]
      and abs(delta - expect) < 1e-9 and delta > 0,
      f"off={r_off['confidence']} on={r_on['confidence']}")

# PF-3: permanent origins EXCLUDED - denominator shrinks.
# Perm q=0.95 x2 + clean q=0.60 x2: raw = 0.775, effective
# = 0.60 exactly.
EV_PF3 = [ev("p1", *PERM, 0.95, contradicts=["p2"]),
          ev("p2", *PERM, 0.95),
          ev("c1", *CLEAN, 0.60, contradicts=["c2"]),
          ev("c2", *CLEAN, 0.60)]
r = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF3, stakes="medium",
                 trust_registry=permanent_reg(*PERM))
check("pf3-permanent-excluded",
      abs(r["precision"] - 0.775) < 1e-9
      and abs(r["precision_effective"] - 0.60) < 1e-9
      and r["precision_discounted"] is True, f"result={r}")

# PF-4: ALL evidence permanent -> effective falls back to
# 0.5 (ruling E3), raw stays the records' own mean.
EV_PF4 = [ev("p1", *PERM, 0.95, contradicts=["p2"]),
          ev("p2", *PERM, 0.95)]
r = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF4, stakes="medium",
                 trust_registry=permanent_reg(*PERM))
check("pf4-all-permanent-fallback",
      abs(r["precision"] - 0.95) < 1e-9
      and r["precision_effective"] == 0.5
      and r["precision_discounted"] is True, f"result={r}")

# PF-5: rehabilitated origin at FULL value in P.
EV_PF5 = [ev("a1", *BAD, 0.80, contradicts=["a2"]),
          ev("a2", *BAD, 0.80)]
r = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF5, stakes="medium",
                 trust_registry=rehabilitated_reg(*BAD))
check("pf5-rehabilitated-full-value",
      abs(r["precision_effective"] - r["precision"]) < 1e-9
      and abs(r["precision"] - 0.80) < 1e-9
      and r["precision_discounted"] is False, f"result={r}")

# PF-6: proven origin at full value (no track-record tax).
reg6 = SourceTrustRegistry()
p6 = probe("prolane", "ops/feed")
for _ in range(5):
    reg6.note_admitted(p6)
EV_PF6 = [ev("g1", "prolane", "ops/feed", 0.80,
             contradicts=["g2"]),
          ev("g2", "prolane", "ops/feed", 0.80)]
r = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF6, stakes="medium",
                 trust_registry=reg6)
check("pf6-proven-full-value",
      abs(r["precision_effective"] - r["precision"]) < 1e-9
      and r["precision_discounted"] is False
      and reg6.tier_for("prolane", "ops/feed") == "proven",
      f"result={r}")

# PF-7: empty evidence - the pre-existing 0.5 default, no
# stamp, registry or not.
r = agent.decide(Q, CANDS, CLEAR_PREFS, [], stakes="medium",
                 trust_registry=flagged_reg(*BAD))
check("pf7-empty-evidence-default",
      r["precision"] == 0.5 and r["precision_effective"] == 0.5
      and r["precision_discounted"] is False, f"result={r}")

# Contested fixture with flagged evidence: 8 contradiction
# pairs (M ~ 0.835, contested zone), pairs 0-3 from BAD,
# pairs 4-7 from CLEAN; every record tier-unknown conf 0.6
# -> q = 0.50, flagged halves to 0.25. raw = 0.50,
# effective = (8*0.25 + 8*0.50)/16 = 0.375.
def contested_flagged():
    out = []
    for i in range(8):
        o, s = BAD if i < 4 else CLEAN
        out.append(rec(f"ca-{i}", conf=0.6, salience=0.9,
                       contradicts=[f"cb-{i}"], owner=o, source=s))
        out.append(rec(f"cb-{i}", conf=0.6, salience=0.9,
                       owner=o, source=s))
    return out


EV_CONT = contested_flagged()

# PF-8: INVARIANCE on a contested decision - selection,
# impasse, scores identical; confidence strictly lower;
# exact discounted mean.
r_off = agent.decide(Q, CANDS, CLEAR_PREFS, EV_CONT,
                     stakes="medium")
r_on = agent.decide(Q, CANDS, CLEAR_PREFS, EV_CONT,
                    stakes="medium",
                    trust_registry=flagged_reg(*BAD))
check("pf8-invariance-contested",
      r_off["selected_id"] == r_on["selected_id"]
      and r_off["impasse"] == r_on["impasse"]
      and r_off["conflict_score"] == r_on["conflict_score"]
      and r_off["policy_score"] == r_on["policy_score"]
      and r_off["tie_broken"] == r_on["tie_broken"]
      and abs(r_on["precision"] - 0.50) < 1e-9
      and abs(r_on["precision_effective"] - 0.375) < 1e-9
      and r_on["confidence"] < r_off["confidence"]
      and r_on["precision_discounted"] is True
      and r_off["precision_discounted"] is False,
      f"off={r_off} on={r_on}")

# PF-9: INVARIANCE through a provenance tie-break - clean
# support (P_c undiscounted both ways), flagged evidence:
# the break fires identically, confidence alone moves.
SUP9 = {"c1": [rec("s-c1", tier="observed", conf=0.80,
                   owner=CLEAN[0], source=CLEAN[1])],
        "c2": [rec("s-c2", tier="observed", conf=0.55,
                   owner=CLEAN[0], source=CLEAN[1])]}
r_off = agent.decide(Q, CANDS, TIED_PREFS, EV_CONT,
                     stakes="medium", evidence_support=SUP9)
r_on = agent.decide(Q, CANDS, TIED_PREFS, EV_CONT,
                    stakes="medium", evidence_support=SUP9,
                    trust_registry=flagged_reg(*BAD))
check("pf9-invariance-tie-break",
      r_off["selected_id"] == r_on["selected_id"] == "c1"
      and r_off["tie_broken"] == r_on["tie_broken"]
      == "provenance"
      and r_on["tie_break_discounted"] is False
      and r_on["precision_discounted"] is True
      and r_on["confidence"] < r_off["confidence"],
      f"off={r_off} on={r_on}")

# PF-10: INVARIANCE at high stakes - the fail-closed
# impasse is identical; only its stated confidence drops.
r_off = agent.decide(Q, CANDS, CLEAR_PREFS, EV_CONT,
                     stakes="high")
r_on = agent.decide(Q, CANDS, CLEAR_PREFS, EV_CONT,
                    stakes="high",
                    trust_registry=flagged_reg(*BAD))
check("pf10-invariance-high-stakes",
      r_off["selected_id"] is None and r_on["selected_id"]
      is None
      and r_off["impasse"] == r_on["impasse"] is not None
      and r_off["policy_score"] == r_on["policy_score"]
      and r_on["confidence"] < r_off["confidence"],
      f"off={r_off} on={r_on}")

# PF-11: registry supplied, evidence origins UNKNOWN to it
# -> full value, no stamp (a flag exists only where poison
# was recorded).
EV_PF11 = [ev("u1", "otherlane", "misc/feed", 0.80,
              contradicts=["u2"]),
           ev("u2", "otherlane", "misc/feed", 0.80)]
r = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF11,
                 stakes="medium",
                 trust_registry=flagged_reg(*BAD))
check("pf11-unknown-identity-full-value",
      abs(r["precision_effective"] - r["precision"]) < 1e-9
      and r["precision_discounted"] is False, f"result={r}")

# PF-12: registry WITHOUT evidence_support - P is priced,
# the tie-break machinery stays unarmed and unstamped.
r = agent.decide(Q, CANDS, TIED_PREFS, EV_PF1, stakes="medium",
                 trust_registry=flagged_reg(*BAD))
check("pf12-registry-without-support",
      r["precision_discounted"] is True
      and r["tie_break_discounted"] is False
      and r["tie_broken"] is None, f"result={r}")

# PF-13: scope boundary the other way - flagged SUPPORT
# with CLEAN evidence discounts P_c only; P is untouched.
EV_PF13 = [ev("k1", *CLEAN, 0.80, contradicts=["k2"]),
           ev("k2", *CLEAN, 0.80),
           ev("k3", *CLEAN, 0.80, contradicts=["k4"]),
           ev("k4", *CLEAN, 0.80),
           ev("k5", *CLEAN, 0.80, contradicts=["k6"]),
           ev("k6", *CLEAN, 0.80),
           ev("k7", *CLEAN, 0.80, contradicts=["k8"]),
           ev("k8", *CLEAN, 0.80),
           ev("k9", *CLEAN, 0.80, contradicts=["k10"]),
           ev("k10", *CLEAN, 0.80),
           ev("k11", *CLEAN, 0.80, contradicts=["k12"]),
           ev("k12", *CLEAN, 0.80),
           ev("k13", *CLEAN, 0.80, contradicts=["k14"]),
           ev("k14", *CLEAN, 0.80),
           ev("k15", *CLEAN, 0.80, contradicts=["k16"]),
           ev("k16", *CLEAN, 0.80)]
SUP13 = {"c1": [rec("s-bad", tier="observed", conf=0.80,
                    owner=BAD[0], source=BAD[1])],
         "c2": [rec("s-cln", tier="observed", conf=0.55,
                    owner=CLEAN[0], source=CLEAN[1])]}
r = agent.decide(Q, CANDS, TIED_PREFS, EV_PF13,
                 stakes="medium", evidence_support=SUP13,
                 trust_registry=flagged_reg(*BAD))
check("pf13-support-flagged-evidence-clean",
      r["precision_discounted"] is False
      and abs(r["precision_effective"] - r["precision"]) < 1e-9
      and r["tie_break_discounted"] is True,
      f"result={r}")

# PF-14: the three fields are PERSISTED in the decision
# record JSON (ruling E5 auditability). A distinct question
# keeps this decision's record id separate from PF-1/PF-2's.
Q14 = "hold the v2 build on 2026-10-24 per plan P-9?"
r = agent.decide(Q14, CANDS, CLEAR_PREFS, EV_PF1,
                 stakes="medium",
                 trust_registry=flagged_reg(*BAD))
saved = store.get(r["record_id"]) if r.get("record_id") else None
body = json.loads(saved.content) if saved else {}
check("pf14-fields-persisted",
      body.get("precision") == r["precision"]
      and body.get("precision_effective")
      == r["precision_effective"]
      and body.get("precision_discounted") is True,
      f"persisted={body}")

# PF-15: mixed three-origin mean - flagged-active 0.80,
# permanent 0.95, clean 0.60: raw = 2.35/3, effective =
# (0.40 + 0.60)/2 = 0.50 (permanent out of BOTH numerator
# and denominator). One registry holding both states, built
# through the public note_* path (poison -> K=5 clean
# admissions -> poison again = permanent).
reg15 = SourceTrustRegistry()
reg15.note_poison(probe(*BAD))
p15 = probe(*PERM)
reg15.note_poison(p15)
for _ in range(5):
    reg15.note_admitted(p15)
reg15.note_poison(p15)
EV_PF15 = [ev("m1", *BAD, 0.80), ev("m2", *PERM, 0.95),
           ev("m3", *CLEAN, 0.60)]
r = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF15,
                 stakes="medium", trust_registry=reg15)
check("pf15-mixed-three-origins",
      abs(r["precision"] - (2.35 / 3)) < 1e-9
      and abs(r["precision_effective"] - 0.50) < 1e-9
      and r["precision_discounted"] is True
      and reg15.stats_for(*PERM).permanent is True,
      f"result={r}")

# PF-16: no registry - the E5 fields exist, effective ==
# raw, no stamp (the default path is auditable too).
r = agent.decide(Q, CANDS, CLEAR_PREFS, EV_PF1, stakes="medium")
check("pf16-no-registry-fields",
      abs(r["precision"] - 0.70) < 1e-9
      and r["precision_effective"] == r["precision"]
      and r["precision_discounted"] is False, f"result={r}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
