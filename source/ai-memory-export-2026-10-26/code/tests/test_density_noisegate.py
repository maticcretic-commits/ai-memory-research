"""Noise-gated density (DS-NG) tests (2026-10-21; ChatGPT
ruling in implementation/next-lever-chatgpt-ruling.txt;
preregistration: implementation/next-lever-preregistration.md;
record: implementation/next-lever-record.md).

DS-NG: select() with density_scale=True + density_noise_gate=
True scales the DS-A sqrt(d) shrinkage by a per-task gate
g in [0, 1] driven by nu, the pooled dispersion of the top-two
candidates' centred scoring-vote log-weights. g = 1 at
nu <= density_noise_lo (full DS-A), g = 0 at
nu >= density_noise_hi (plain relative epsilon), linear
between; fewer than 4 pooled positive weights -> g = 0.
Verified here as a FORMULA at unit level, not as accuracy
(the bench evaluation lives in
evals/density_noisegate_validation.py).

Run:  python3 tests/test_density_noisegate.py  (from repo root)
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
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


C1 = Candidate(id="c1", description="keep building")
C2 = Candidate(id="c2", description="stop and report")
CANDS = [C1, C2]


def votes(cid, weights):
    return [Preference(candidate_id=cid, kind="better", weight=w,
                       source_module="bench-ng") for w in weights]


def is_tie(d):
    return (d.selected_id is None and d.impasse is not None
            and d.impasse.kind == "tie")


def raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


# nets 0.30 vs 0.29 (margin 0.01); relative eps = 0.015 (tie);
# DS-A at d = 4: eps 0.0075 (decides c1).
P_EQ4 = votes("c1", [0.075] * 4) + votes("c2", [0.0725] * 4)

# ---------------------------------------------------------------------------
# Misconfiguration: no silent fallback, ever
# ---------------------------------------------------------------------------

check("ng-gate-without-density-raises",
      raises(lambda: select(CANDS, P_EQ4, tie_epsilon_mode="relative",
                            density_noise_gate=True)),
      "gate without density_scale must raise")
check("ng-gate-absolute-raises",
      raises(lambda: select(CANDS, P_EQ4, tie_epsilon_mode="absolute",
                            density_scale=True,
                            density_noise_gate=True)),
      "gate under absolute mode must raise (via DS-A's rule)")
check("ng-bad-thresholds-raise",
      raises(lambda: select(CANDS, P_EQ4, tie_epsilon_mode="relative",
                            density_scale=True, density_noise_gate=True,
                            density_noise_lo=0.80, density_noise_hi=0.51)),
      "lo >= hi must raise")

# ---------------------------------------------------------------------------
# g = 1: zero dispersion reproduces DS-A exactly
# ---------------------------------------------------------------------------

d_ds = select(CANDS, P_EQ4, tie_epsilon_mode="relative",
              density_scale=True)
d_ng = select(CANDS, P_EQ4, tie_epsilon_mode="relative",
              density_scale=True, density_noise_gate=True)
check("ng-clean-votes-equal-dsa", d_ng.selected_id == "c1"
      and d_ds.selected_id == "c1",
      "equal-split votes have nu = 0, so the gate is fully open "
      "and eps 0.0075 < margin 0.01 decides, exactly as DS-A")

# ---------------------------------------------------------------------------
# g = 0: extreme dispersion reproduces the relative stack
# ---------------------------------------------------------------------------

# Same nets (0.30 / 0.29), pooled centred log-weight std ~1.42.
P_WILD = votes("c1", [0.27, 0.01, 0.01, 0.01]) \
    + votes("c2", [0.26, 0.01, 0.01, 0.01])
d_ds = select(CANDS, P_WILD, tie_epsilon_mode="relative",
              density_scale=True)
d_ng = select(CANDS, P_WILD, tie_epsilon_mode="relative",
              density_scale=True, density_noise_gate=True)
d_rel = select(CANDS, P_WILD, tie_epsilon_mode="relative")
check("ng-wild-votes-close-gate", d_ds.selected_id == "c1"
      and is_tie(d_ng) and is_tie(d_rel),
      "nu ~1.42 >= hi 0.80: the gate closes, the gated outcome "
      "is the relative tie, while DS-A on the same votes decides")

# ---------------------------------------------------------------------------
# Partial gate: nu between the thresholds interpolates the eps
# ---------------------------------------------------------------------------

# Centred log-weight std 0.2027 for both candidates (two-high /
# two-low splits at a fixed ratio). With lo = 0.10, hi = 0.30:
# g = (0.30 - 0.2027) / 0.20 ~ 0.486; at d = 4 the shrink is
# 1 - 0.486 * (1 - 1/2) ~ 0.757, eps ~ 0.0114 on a 0.30 leader.
P_MID = votes("c1", [0.09, 0.09, 0.06, 0.06]) \
    + votes("c2", [0.087, 0.087, 0.058, 0.058])  # margin 0.01
P_MID2 = votes("c1", [0.09, 0.09, 0.06, 0.06]) \
    + votes("c2", [0.0864, 0.0864, 0.0576, 0.0576])  # margin 0.012
KW = dict(tie_epsilon_mode="relative", density_scale=True,
          density_noise_gate=True,
          density_noise_lo=0.10, density_noise_hi=0.30)
check("ng-partial-blocks-dsa-decision",
      is_tie(select(CANDS, P_MID, **KW))
      and select(CANDS, P_MID, tie_epsilon_mode="relative",
                 density_scale=True).selected_id == "c1",
      "gated eps ~0.0114 >= margin 0.01 ties, where full DS-A "
      "(eps 0.0075) decides")
check("ng-partial-beats-relative",
      select(CANDS, P_MID2, **KW).selected_id == "c1"
      and is_tie(select(CANDS, P_MID2, tie_epsilon_mode="relative")),
      "gated eps ~0.0114 < margin 0.012 decides, where the "
      "plain relative eps 0.015 ties: the gate is strictly "
      "between the two arms, not a disguised copy of either")

# ---------------------------------------------------------------------------
# Undefined statistic: fewer than 4 pooled votes -> g = 0
# ---------------------------------------------------------------------------

# c1 two votes, c2 one vote (pooled 3 < 4); d = 1.5; margin 0.013:
# relative eps 0.015 ties, DS-A eps 0.015/sqrt(1.5) = 0.01225
# decides, gated must tie because nu is undefined.
P_THIN = votes("c1", [0.15, 0.15]) + votes("c2", [0.287])
check("ng-thin-votes-close-gate",
      is_tie(select(CANDS, P_THIN, tie_epsilon_mode="relative",
                    density_scale=True, density_noise_gate=True))
      and select(CANDS, P_THIN, tie_epsilon_mode="relative",
                 density_scale=True).selected_id == "c1",
      "pooled votes < 4: statistic undefined, gate closed")

# ---------------------------------------------------------------------------
# decide() passthrough and defaults
# ---------------------------------------------------------------------------

tdir = tempfile.mkdtemp()
agent = MemoryAgent(SQLiteStore(os.path.join(tdir, "memory.db")),
                    calibration_path=os.path.join(tdir, "cal.json"))
r = agent.decide("ng passthrough?", CANDS,
                 votes("c1", [0.6]) + votes("c2", [0.2]), [],
                 density_scale=True, density_noise_gate=True)
check("ng-decide-passthrough", r["density_noise_gate"] is True
      and r["density_scale"] is True, f"result keys: "
      f"gate={r.get('density_noise_gate')}")
r = agent.decide("ng default?", CANDS,
                 votes("c1", [0.6]) + votes("c2", [0.2]), [])
check("ng-decide-default-off", r["density_noise_gate"] is False
      and r["density_scale"] is False,
      "defaults unchanged: no gate, no density")
check("ng-decide-gate-without-density-raises",
      raises(lambda: agent.decide("ng bad?", CANDS,
                                  votes("c1", [0.6]), [],
                                  density_noise_gate=True)),
      "decide() must surface select()'s refusal, not swallow it")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
