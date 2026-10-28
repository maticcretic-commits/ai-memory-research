"""Asymmetric evidence-quality-conditioned tie band (TB-Q) tests
(2026-10-21; ChatGPT ruling in
implementation/asymmetric-tieband-chatgpt-ruling.txt; preregistration:
implementation/asymmetric-tieband-preregistration.md;
record: implementation/asymmetric-tieband-record.md).

TB-Q: select() with tie_band_quality=True multiplies the FINAL eps_eff
(after any density multiplier) by m(q), where q is the leader's share of
top-two scoring-vote weight (kinds better/worse, weight > 0, no centring)
- a balance signal, not total evidence. m(q) = tie_band_widen (1.25) at
q <= tie_band_lo (0.6), m(q) = tie_band_shrink (0.8) at q >= tie_band_hi
(0.9), linear between. Degenerate inputs (fewer than two ranked
candidates, or zero total top-two scoring weight) leave the band inert
(m = 1.0), the fail-safe toward the adopted stack.
Verified here as a FORMULA at unit level, not as accuracy (the bench
evaluation lives in evals/tieband_validation.py).

Run:  python3 tests/test_tieband.py  (from repo root)
"""

import os
import sys
import tempfile

sys.path.insert(0, ".")

from mm.agent import MemoryAgent
from mm.decision import Candidate, Preference, select
from mm.storage import SQLiteStore

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else FAIL) + name
          + (f" - {detail}" if detail and not cond else ""))


C1 = Candidate(id="c1", description="keep building")
C2 = Candidate(id="c2", description="stop and report")
CANDS = [C1, C2]
BAND = dict(tie_band_quality=True)


def better(cid, weights):
    return [Preference(candidate_id=cid, kind="better", weight=w,
                       source_module="bench-tb") for w in weights]


def worse(cid, weights):
    return [Preference(candidate_id=cid, kind="worse", weight=w,
                       source_module="bench-tb") for w in weights]


def is_tie(d):
    return (d.selected_id is None and d.impasse is not None
            and d.impasse.kind == "tie")


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


# ---------------------------------------------------------------------------
# Misconfiguration: no silent fallback, ever
# ---------------------------------------------------------------------------

check("tb-lo-gte-hi-raises",
      raises(lambda: select(CANDS, better("c1", [0.3]),
                            tie_epsilon_mode="relative", **BAND,
                            tie_band_lo=0.9, tie_band_hi=0.6)),
      "lo >= hi must raise")
check("tb-lo-below-half-raises",
      raises(lambda: select(CANDS, better("c1", [0.3]),
                            tie_epsilon_mode="relative", **BAND,
                            tie_band_lo=0.4)),
      "lo < 0.5 must raise")
check("tb-hi-above-one-raises",
      raises(lambda: select(CANDS, better("c1", [0.3]),
                            tie_epsilon_mode="relative", **BAND,
                            tie_band_hi=1.1)),
      "hi > 1.0 must raise")
check("tb-widen-below-one-raises",
      raises(lambda: select(CANDS, better("c1", [0.3]),
                            tie_epsilon_mode="relative", **BAND,
                            tie_band_widen=0.9)),
      "widen < 1.0 must raise")
check("tb-shrink-zero-raises",
      raises(lambda: select(CANDS, better("c1", [0.3]),
                            tie_epsilon_mode="relative", **BAND,
                            tie_band_shrink=0.0)),
      "shrink <= 0 must raise")
check("tb-shrink-above-one-raises",
      raises(lambda: select(CANDS, better("c1", [0.3]),
                            tie_epsilon_mode="relative", **BAND,
                            tie_band_shrink=1.5)),
      "shrink > 1.0 must raise")

# ---------------------------------------------------------------------------
# Shrink zone: q >= 0.9 -> m = 0.8 resolves a tie the base band keeps
# ---------------------------------------------------------------------------

# c1: net 0.30, weight 3.00; c2: net 0.287, weight 0.30.
# q = 3.00/3.30 = 0.909 >= 0.9 -> m = 0.8.
# Relative eps = 0.05 * 0.30 = 0.015 >= margin 0.013: tie without band.
# Banded eps = 0.012 < 0.013: decides c1.
P_SHRINK = (better("c1", [1.65]) + worse("c1", [1.35])
            + better("c2", [0.2935]) + worse("c2", [0.0065]))
d_rel = select(CANDS, P_SHRINK, tie_epsilon_mode="relative")
d_tb = select(CANDS, P_SHRINK, tie_epsilon_mode="relative", **BAND)
check("tb-shrink-resolves", is_tie(d_rel)
      and d_tb.selected_id == "c1",
      "q=0.909 -> m=0.8: banded eps 0.012 < margin 0.013 decides, "
      "where the relative band ties")

# ---------------------------------------------------------------------------
# Widen zone: q <= 0.6 -> m = 1.25 protects a tie the base band resolves
# ---------------------------------------------------------------------------

# c1: net 0.30, weight 0.30; c2: net 0.283, weight 0.283.
# q = 0.30/0.583 = 0.5146 <= 0.6 -> m = 1.25.
# Relative eps 0.015 < margin 0.017: decides without band.
# Banded eps = 0.01875 >= 0.017: tie.
P_WIDEN = better("c1", [0.20, 0.10]) + better("c2", [0.283])
d_rel = select(CANDS, P_WIDEN, tie_epsilon_mode="relative")
d_tb = select(CANDS, P_WIDEN, tie_epsilon_mode="relative", **BAND)
check("tb-widen-protects", d_rel.selected_id == "c1"
      and is_tie(d_tb),
      "q=0.5146 -> m=1.25: banded eps 0.01875 >= margin 0.017 ties, "
      "where the relative band decides")

# ---------------------------------------------------------------------------
# Interpolation: q = 0.75 -> m = 1.025, audited in the tie detail
# ---------------------------------------------------------------------------

# c1: net 0.30, weight 0.90; c2: net 0.285, weight 0.30.
# q = 0.90/1.20 = 0.75 -> m = 1.025. Banded eps = 0.015375.
# Margin 0.015 <= 0.015375: tie, and the detail stamps q and m.
P_MID = (better("c1", [0.60]) + worse("c1", [0.30])
         + better("c2", [0.2925]) + worse("c2", [0.0075]))
d_tb = select(CANDS, P_MID, tie_epsilon_mode="relative", **BAND)
detail = d_tb.impasse.detail if d_tb.impasse else ""
check("tb-interpolates", is_tie(d_tb)
      and "q=0.750" in detail and "m=1.025" in detail,
      f"q=0.75 interpolates to m=1.025; detail={detail!r}")

# ---------------------------------------------------------------------------
# Degenerate inputs: the band stays inert (m = 1.0)
# ---------------------------------------------------------------------------

# No scoring votes at all: ranking [(c1, 0.0), (c2, 0.0)] ties at
# margin 0; the band must not crash and must not change the tie.
d_rel = select(CANDS, [], tie_epsilon_mode="relative")
d_tb = select(CANDS, [], tie_epsilon_mode="relative", **BAND)
check("tb-no-votes-inert", is_tie(d_rel) and is_tie(d_tb),
      "zero top-two scoring weight: band inert, tie stands")

# Single candidate: no tie check at all; the band must not crash.
d_tb = select([C1], better("c1", [0.5]), tie_epsilon_mode="relative",
              **BAND)
check("tb-single-candidate-inert", d_tb.selected_id == "c1",
      "one ranked candidate: band inert, selection stands")

# ---------------------------------------------------------------------------
# Band off (default): byte-identical behaviour to relative mode
# ---------------------------------------------------------------------------

d_rel = select(CANDS, P_SHRINK, tie_epsilon_mode="relative")
d_off = select(CANDS, P_SHRINK, tie_epsilon_mode="relative",
               tie_band_quality=False)
check("tb-default-off", (d_rel.selected_id, d_rel.impasse)
      == (d_off.selected_id, d_off.impasse),
      "default off: identical outcome to plain relative mode")

# ---------------------------------------------------------------------------
# Composition with density: the band multiplies the FINAL eps_eff
# ---------------------------------------------------------------------------

# d = 4 (four scoring votes each); q = 0.5072 <= 0.6 -> m = 1.25.
# Relative eps 0.015; density eps 0.0075; density+band eps 0.009375.
# Margin 0.0085: density alone decides, density+band ties.
P_COMP = better("c1", [0.075] * 4) + better("c2", [0.072875] * 4)
d_ds = select(CANDS, P_COMP, tie_epsilon_mode="relative",
              density_scale=True)
d_both = select(CANDS, P_COMP, tie_epsilon_mode="relative",
                density_scale=True, **BAND)
check("tb-composes-after-density", d_ds.selected_id == "c1"
      and is_tie(d_both),
      "band multiplies the density-shrunk eps: 0.009375 >= margin "
      "0.0085 ties where density alone (0.0075) decides")

# ---------------------------------------------------------------------------
# Non-ties are untouched by the band
# ---------------------------------------------------------------------------

P_CLEAR = better("c1", [0.50]) + better("c2", [0.10])
d_tb = select(CANDS, P_CLEAR, tie_epsilon_mode="relative", **BAND)
check("tb-clear-nontie-untouched", d_tb.selected_id == "c1",
      "margin far above even the widened band: selection stands")

# ---------------------------------------------------------------------------
# decide() passthrough and defaults
# ---------------------------------------------------------------------------

tdir = tempfile.mkdtemp()
agent = MemoryAgent(SQLiteStore(os.path.join(tdir, "memory.db")),
                    calibration_path=os.path.join(tdir, "cal.json"))
r = agent.decide("tb passthrough?", CANDS,
                 better("c1", [0.6]) + better("c2", [0.2]), [],
                 tie_band_quality=True)
check("tb-decide-passthrough", r["tie_band_quality"] is True,
      "result carries the band flag")
r = agent.decide("tb default?", CANDS,
                 better("c1", [0.6]) + better("c2", [0.2]), [])
check("tb-decide-default-off", r["tie_band_quality"] is False,
      "defaults unchanged: no band")
check("tb-decide-bad-thresholds-raise",
      raises(lambda: agent.decide("tb bad?", CANDS,
                                  better("c1", [0.6]), [],
                                  tie_band_quality=True,
                                  tie_band_lo=0.9, tie_band_hi=0.6)),
      "decide() must surface select()'s refusal, not swallow it")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
