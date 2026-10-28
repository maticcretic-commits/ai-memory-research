"""trace_refit - re-fit confidence_from_trace coefficients (chunk 3).

The z-formula in mm.confidence.confidence_from_trace
(4.0*speed + 2.0*decisiveness + 0.3*log1p(mass) - 0.08*steps - 1.4)
carries v0.3 PRIORS, never tuned on data (calibration-rescope-phase3.md
section 2). This harness fits logistic regression (IRLS, pure Python)
on the trace features of the TOP option's DDM trace -> P(top correct),
using the same harness-generated pair batch conventions as
isotonic_run.py (fit: gen_suite(1200, seed=21); validation:
conflict-heldout-120 seed 99 + gen_suite(600, seed=23)). PLAINLY:
harness-generated data, not real decisions - same provenance caveat
as the isotonic fit, stated in the output JSON.

Features (exactly the formula's inputs, from ScoredOption.ddm_trace):
  speed        = margin / (bound * (1 + steps))
  decisiveness = |drift at crossing| / total evidence mass
  log1p(mass), steps, intercept.
Non-crossed traces are excluded (their confidence is the fixed 0.35
undecided prior, not the formula).

ADOPTION RULE (declared before the run): the re-fit coefficients are
written into mm/confidence.py ONLY IF they beat the v0.3 priors on
Brier on BOTH validation slices AND do not worsen ECE on either. Any
other outcome: coefficients reported here, priors kept, item logged
as still-open in the chunk record.

AMENDMENT (2026-10-20, after run 1, BEFORE any adoption was applied):
run 1 fired "adopted" with the heldout validation slice at n=1 crossed
trace - a void validation (the Phase-2 bound raise means conflict
tasks almost never cross, so the trace formula almost never governs
their stated confidence). A slice with n < MIN_VAL_N=30 crossed traces
(the codebase's standing MIN_SAMPLES floor) cannot validate anything;
the rule now requires n >= 30 on BOTH slices. Disclosed in the chunk-3
record; no coefficient was ever written to mm/confidence.py under the
void firing.

Run:  python3 -m evals.trace_refit
"""

from __future__ import annotations

import json
import math
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import conflict_heldout as ch
from evals import decision_bench as db
from mm import confidence as C

OLD_COEFS = [4.0, 2.0, 0.3, -0.08, -1.4]  # speed, dec, log1p(mass), steps, 1
OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")


def collect_traces(tasks: list[dict]) -> list[dict]:
    rows = []
    for task in tasks:
        options, ranked, link = db.task_to_inputs(task)

        def link_fn(ev, opt, link=link):
            return link.get(ev.record.id, {}).get(opt.id, 0.0)

        scored = C.score_options(
            options, ranked, stakes="medium", link_fn=link_fn,
            calibration=None, kappa=C.KAPPA, lambda_=C.LAMBDA, temp=1.0)
        top = scored[0]
        tr = top.ddm_trace
        if not top.crossed:
            continue  # fixed 0.35 prior - not the formula's output
        mass = tr["total_evidence"]
        net = abs(tr["path"][-1]) if tr["path"] else 0.0
        feats = [
            tr["margin"] / (tr["bound"] * (1 + tr["cross_step"])),
            (net / mass) if mass > 0 else 0.0,
            math.log1p(mass),
            float(tr["cross_step"]),
            1.0,
        ]
        rows.append({"feats": feats,
                     "correct": top.option.id == task["gold_best"]})
    return rows


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination for small dense systems."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        for r in range(n):
            if r != col and m[r][col] != 0.0:
                f = m[r][col] / pv
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def fit_logistic(rows: list[dict], iters: int = 50) -> list[float]:
    """IRLS logistic regression with a whisper of ridge (1e-6)."""
    k = len(OLD_COEFS)
    beta = [0.0] * k
    x = [r["feats"] for r in rows]
    y = [1.0 if r["correct"] else 0.0 for r in rows]
    for _ in range(iters):
        grad = [0.0] * k
        hess = [[0.0] * k for _ in range(k)]
        for xi, yi in zip(x, y):
            z = sum(b * v for b, v in zip(beta, xi))
            p = 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, z))))
            w = max(p * (1.0 - p), 1e-9)
            for a in range(k):
                grad[a] += xi[a] * (yi - p)
                for b_ in range(k):
                    hess[a][b_] += w * xi[a] * xi[b_]
        for a in range(k):
            hess[a][a] += 1e-6
            grad[a] -= 1e-6 * beta[a]
        step = _solve(hess, grad)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-8:
            break
    return beta


def predict(beta: list[float], feats: list[float]) -> float:
    z = sum(b * v for b, v in zip(beta, feats))
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, z))))


def evaluate(rows: list[dict], beta: list[float]) -> dict:
    pairs = [(predict(beta, r["feats"]), r["correct"]) for r in rows]
    brier = sum((p - (1.0 if o else 0.0)) ** 2 for p, o in pairs) / len(pairs)
    bins: list[list[bool]] = [[] for _ in range(10)]
    confs: list[list[float]] = [[] for _ in range(10)]
    for p, o in pairs:
        b = max(0, min(9, int(p * 10)))
        bins[b].append(o)
        confs[b].append(p)
    ece = 0.0
    for b in range(10):
        if bins[b]:
            ece += (len(bins[b]) / len(pairs)) * abs(
                sum(bins[b]) / len(bins[b]) - sum(confs[b]) / len(confs[b]))
    return {"n": len(pairs), "brier": round(brier, 4), "ece": round(ece, 4)}


def main() -> None:
    t0 = time.time()
    print("collecting traces (fit seed=21 n=1200; val: heldout-120 + "
          "seed=23 n=600) ...", flush=True)
    fit_rows = collect_traces(db.gen_suite(1200, 21))
    val_heldout = collect_traces(ch.generate(120, 99))
    val_bench = collect_traces(db.gen_suite(600, 23))

    new_coefs = fit_logistic(fit_rows)
    res = {
        "old": {"fit": evaluate(fit_rows, OLD_COEFS),
                "val_heldout120": evaluate(val_heldout, OLD_COEFS),
                "val_bench_seed23": evaluate(val_bench, OLD_COEFS)},
        "new": {"fit": evaluate(fit_rows, new_coefs),
                "val_heldout120": evaluate(val_heldout, new_coefs),
                "val_bench_seed23": evaluate(val_bench, new_coefs)},
    }
    MIN_VAL_N = 30  # standing MIN_SAMPLES floor: below this a slice is void
    enough = (res["new"]["val_heldout120"]["n"] >= MIN_VAL_N
              and res["new"]["val_bench_seed23"]["n"] >= MIN_VAL_N)
    adopt = enough and (
        res["new"]["val_heldout120"]["brier"] < res["old"]["val_heldout120"]["brier"]
        and res["new"]["val_bench_seed23"]["brier"] < res["old"]["val_bench_seed23"]["brier"]
        and res["new"]["val_heldout120"]["ece"] <= res["old"]["val_heldout120"]["ece"]
        and res["new"]["val_bench_seed23"]["ece"] <= res["old"]["val_bench_seed23"]["ece"])
    report = {
        "harness": "trace-refit-v1",
        "data_provenance": ("HARNESS-GENERATED traces (seeded bench) - "
                            "no real decision traces exist yet."),
        "features": ["speed", "decisiveness", "log1p(mass)", "steps",
                     "intercept"],
        "n_fit_crossed": len(fit_rows),
        "old_coefficients_v03_priors": OLD_COEFS,
        "new_coefficients": [round(c, 4) for c in new_coefs],
        "results": res,
        "adoption_rule": "adopt iff new Brier < old on BOTH validation "
                         "slices AND new ECE <= old on both AND both "
                         "slices have n >= 30 crossed traces (amended "
                         "after run 1's void n=1 heldout slice; see "
                         "module docstring)",
        "adopted": adopt,
        "adoption_blocker": (None if adopt else
                             "validation slice under-populated: heldout "
                             "conflict tasks almost never cross the "
                             "raised bound (n_crossed=1/120), so the "
                             "conflict regime cannot validate a trace "
                             "re-fit; priors kept, item still-open"),
        "elapsed_s": round(time.time() - t0, 1),
    }
    path = OUT + "trace-refit-run1.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print("old coefs:", OLD_COEFS)
    print("new coefs:", [round(c, 4) for c in new_coefs])
    print(json.dumps(res, indent=2))
    print("ADOPTED" if adopt else "NOT ADOPTED (priors kept)")
    print("wrote", path)


if __name__ == "__main__":
    main()
