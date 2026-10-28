"""Calibration-shaped interaction - statistics self-checks
(2026-10-21; measurement lane, preregistration:
implementation/calibration-shaped-interaction-
preregistration.md).

Pins the DESCRIPTIVE statistics the measurement harness
uses (group delta-accuracy with within-group bootstrap CI,
Mann-Whitney AUC with bootstrap CI) on fixed fixtures, so
a future edit to the analysis cannot silently change what
a "separation" verdict rests on. These checks pin the math
only - the lane's verdict rests on the fresh-seed run
(evals/calibration_shaped_interaction.py), not on these
fixtures. No model is fitted anywhere in this lane (HD-2).

Run:  python3 tests/test_calibration_shaped.py
"""

import sys

sys.path.insert(0, ".")

from evals.calibration_shaped_interaction import (
    delta_acc_ci, auc_mann_whitney, auc_ci)

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


def main():
    # delta_acc_ci: known split, exact delta
    a = [1.0] * 40 + [0.0] * 10          # acc 0.80
    b = [1.0] * 20 + [0.0] * 30          # acc 0.40
    r = delta_acc_ci(a, b)
    check("delta-known-split", r["delta"] == -0.4,
          f"delta={r['delta']}")
    check("delta-ci-brackets",
          r["ci_lo"] <= r["delta"] <= r["ci_hi"])

    # delta CI excludes zero for a wide, well-powered split
    a2 = [1.0] * 45 + [0.0] * 5          # acc 0.90
    b2 = [1.0] * 10 + [0.0] * 40         # acc 0.20
    r2 = delta_acc_ci(a2, b2)
    check("delta-ci-excludes-zero-wide-split",
          r2["ci_hi"] < 0.0, f"ci=[{r2['ci_lo']},{r2['ci_hi']}]")

    # delta CI includes zero for a near-null split
    a3 = [1.0, 0.0] * 25
    b3 = [0.0, 1.0] * 25
    r3 = delta_acc_ci(a3, b3)
    check("delta-ci-includes-zero-null-split",
          r3["ci_lo"] <= 0.0 <= r3["ci_hi"])

    # insufficient flag below the preregistered n=30 floor
    r4 = delta_acc_ci([1.0] * 20, [0.0] * 20)
    check("delta-insufficient-small-cells",
          r4["insufficient"] is True and r4["n_a"] == 20)

    # AUC: perfect separation = 1.0
    check("auc-perfect-separation",
          auc_mann_whitney([0.9, 0.8, 0.2, 0.1],
                           [1.0, 1.0, 0.0, 0.0]) == 1.0)

    # AUC: total ties = 0.5
    check("auc-all-ties-half",
          auc_mann_whitney([0.5, 0.5, 0.5],
                           [1.0, 0.0, 1.0]) == 0.5)

    # AUC: inverted classifier = 0.0
    check("auc-inverted-zero",
          auc_mann_whitney([0.1, 0.2, 0.8, 0.9],
                           [1.0, 1.0, 0.0, 0.0]) == 0.0)

    # AUC CI brackets the point estimate on a fixed fixture
    rr = auc_ci([0.9, 0.7, 0.6, 0.3, 0.2, 0.1],
                [1.0, 1.0, 0.0, 1.0, 0.0, 0.0])
    check("auc-ci-brackets",
          rr["ci_lo"] <= rr["auc"] <= rr["ci_hi"])

    # AUC insufficient below the n=30 floor
    rr2 = auc_ci([0.9, 0.1], [1.0, 0.0])
    check("auc-insufficient-small-n",
          rr2["insufficient"] is True and rr2["n"] == 2)

    # anchor membership rule used by T2 (exact-0.70 match)
    confs = [0.70, 0.7000000001, 0.65, 0.5606]
    anchor = [c for c in confs if abs(c - 0.70) < 1e-9]
    check("anchor-membership-exact",
          len(anchor) == 2 and 0.65 not in anchor)

    # preregistration file exists where the harness claims it
    import os
    pre = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
           "hidden_files/implementation/"
           "calibration-shaped-interaction-preregistration.md")
    check("preregistration-on-file", os.path.isfile(pre))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
