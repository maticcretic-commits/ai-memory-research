"""gate_b_rerun - Phase-3 chunk 3 execution of the gate-(b) protocol.

PREREGISTERED: hidden_files/implementation/gate-b-rerun-preregistration.md
(written before this run). Read it first. Summary of the frozen design:

- Fresh seeds 4000-4003, n=2000/seed (Phase-2 gate seeds never reused).
- Cells (kappa, lambda): (0,0), (0.25,0), (0,2.5), (0.25,2.5).
- Temperature post-hoc per cell as Phase-2's rerun: T=2.0 if the cell's
  controller is active, else T=1.0.
- Matched controls: conflict slice (measured M>0) vs control slice
  (M==0) from the SAME suites/seeds.
- Metrics: accuracy, top-choice Brier (Phase-2 continuity), full-vector
  Brier (isotonic_fit.brier_full_vector - the proper scoring rule).
- Interactions with paired bootstrap CIs (1000 resamples, rng seed 4242).
- Murphy decomposition per cell on the conflict slice.
- VERDICT (frozen): PASS iff full-vector Brier interaction on the
  conflict slice is within +/-0.02.

Run:  python3 -m evals.gate_b_rerun
"""

from __future__ import annotations

import json
import math
import random
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import decision_bench as db
from evals.isotonic_fit import brier_full_vector
from mm import confidence as C

SEEDS = [4000, 4001, 4002, 4003]
N_PER_SEED = 2000
CELLS = [(0.0, 0.0), (0.25, 0.0), (0.0, 2.5), (0.25, 2.5)]
BOOTSTRAP_REPS = 1000
BOOTSTRAP_SEED = 4242
MARGIN = 0.02
OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")


def cell_key(kappa: float, lambda_: float) -> str:
    return f"k{int(kappa > 0)}l{int(lambda_ > 0)}"


def cell_temp(kappa: float, lambda_: float) -> float:
    return 1.0 if (kappa == 0 and lambda_ == 0) else C.TEMP


def collect_cell(tasks: list[dict], kappa: float, lambda_: float) -> list[dict]:
    """Run one factorial cell over the shared task stream (temp=1 raw)."""
    rows = []
    for task in tasks:
        options, ranked, link = db.task_to_inputs(task)

        def link_fn(ev, opt, link=link):
            return link.get(ev.record.id, {}).get(opt.id, 0.0)

        scored = C.score_options(
            options, ranked, stakes="medium", link_fn=link_fn,
            calibration=None, kappa=kappa, lambda_=lambda_, temp=1.0)
        top = scored[0]
        vec = {s.option.id: s.confidence
               for s in scored if not s.pruned_by_constraint}
        rows.append({
            "correct": top.option.id == task["gold_best"],
            "p_top_raw": top.confidence,
            "vec_raw": vec,
            "opt_order": [o.id for o in options],
            "gold": task["gold_best"],
        })
    return rows


def task_metrics(row: dict, temp: float) -> tuple[float, float]:
    """(brier_top, brier_full) for one task under one cell's temperature."""
    p_top = C.recalibrate(row["p_top_raw"], temp)
    brier_top = (p_top - (1.0 if row["correct"] else 0.0)) ** 2
    adj = {k: C.recalibrate(v, temp) for k, v in row["vec_raw"].items()}
    tot = sum(adj.values()) or 1.0
    probs = [adj.get(oid, 0.0) / tot for oid in row["opt_order"]]
    brier_full = brier_full_vector(probs, row["opt_order"].index(row["gold"]))
    return brier_top, brier_full


def interaction(means: dict[str, float]) -> float:
    return means["k1l1"] - means["k1l0"] - means["k0l1"] + means["k0l0"]


def bootstrap_ci(per_cell: dict[str, list[float]], idx: list[int],
                 reps: int = BOOTSTRAP_REPS) -> tuple[float, float]:
    """Paired bootstrap CI for the interaction over the given task idx."""
    rng = random.Random(BOOTSTRAP_SEED)
    n = len(idx)
    stats = []
    for _ in range(reps):
        sample = [idx[rng.randrange(n)] for _ in range(n)]
        means = {ck: sum(per_cell[ck][i] for i in sample) / n
                 for ck in per_cell}
        stats.append(interaction(means))
    stats.sort()
    return stats[int(0.025 * reps)], stats[int(0.975 * reps)]


def murphy(forecasts: list[float], outcomes: list[bool],
           bins: int = 10) -> dict:
    """Murphy decomposition of binary Brier: rel - res + unc."""
    n = len(forecasts)
    base = sum(outcomes) / n if n else 0.0
    unc = base * (1.0 - base)
    buckets: dict[int, list[tuple[float, bool]]] = {}
    for f, o in zip(forecasts, outcomes):
        b = max(0, min(bins - 1, int(f * bins)))
        buckets.setdefault(b, []).append((f, o))
    rel = res = 0.0
    for items in buckets.values():
        nk = len(items)
        fk = sum(f for f, _ in items) / nk
        ok = sum(o for _, o in items) / nk
        rel += (nk / n) * (fk - ok) ** 2
        res += (nk / n) * (ok - base) ** 2
    brier = sum((f - (1.0 if o else 0.0)) ** 2
                for f, o in zip(forecasts, outcomes)) / n if n else 0.0
    return {"reliability": round(rel, 5), "resolution": round(res, 5),
            "uncertainty": round(unc, 5), "brier": round(brier, 5),
            "identity_check": round(rel - res + unc, 5)}


def main() -> None:
    t0 = time.time()
    print("generating suites (seeds 4000-4003, n=2000 each) ...", flush=True)
    tasks: list[dict] = []
    for seed in SEEDS:
        tasks.extend(db.gen_suite(N_PER_SEED, seed))

    # M measured once per task (property of the evidence, cell-invariant).
    print("measuring M per task ...", flush=True)
    ms = []
    for task in tasks:
        _, ranked, _ = db.task_to_inputs(task)
        ms.append(C._conflict_monitor([e.record for e in ranked],
                                      stakes="medium").score)
    conflict_idx = [i for i, m in enumerate(ms) if m > 0]
    control_idx = [i for i, m in enumerate(ms) if m == 0]
    print(f"tasks={len(tasks)} conflict={len(conflict_idx)} "
          f"control={len(control_idx)}", flush=True)

    per_cell_top: dict[str, list[float]] = {}
    per_cell_full: dict[str, list[float]] = {}
    per_cell_acc: dict[str, list[float]] = {}
    per_cell_forecast: dict[str, list[float]] = {}
    per_cell_outcome: dict[str, list[bool]] = {}
    for kappa, lambda_ in CELLS:
        ck = cell_key(kappa, lambda_)
        temp = cell_temp(kappa, lambda_)
        print(f"cell {ck} (kappa={kappa}, lambda={lambda_}, T={temp}) ...",
              flush=True)
        rows = collect_cell(tasks, kappa, lambda_)
        tops, fulls, accs, forecasts, outcomes = [], [], [], [], []
        for row in rows:
            bt, bf = task_metrics(row, temp)
            tops.append(bt)
            fulls.append(bf)
            accs.append(1.0 if row["correct"] else 0.0)
            forecasts.append(C.recalibrate(row["p_top_raw"], temp))
            outcomes.append(row["correct"])
        per_cell_top[ck] = tops
        per_cell_full[ck] = fulls
        per_cell_acc[ck] = accs
        per_cell_forecast[ck] = forecasts
        per_cell_outcome[ck] = outcomes

    def slice_report(idx: list[int]) -> dict:
        n = len(idx)
        out: dict = {"n": n}
        for name, per_cell in (("accuracy", per_cell_acc),
                               ("brier_top", per_cell_top),
                               ("brier_full", per_cell_full)):
            means = {ck: sum(per_cell[ck][i] for i in idx) / n
                     for ck in per_cell}
            lo, hi = bootstrap_ci(per_cell, idx)
            out[name] = {
                "cell_means": {k: round(v, 5) for k, v in means.items()},
                "interaction": round(interaction(means), 5),
                "interaction_ci95": [round(lo, 5), round(hi, 5)],
            }
        return out

    conflict = slice_report(conflict_idx)
    control = slice_report(control_idx)

    # Murphy decomposition per cell, conflict slice (top-choice Brier).
    murphy_cells = {}
    for ck in per_cell_forecast:
        murphy_cells[ck] = murphy(
            [per_cell_forecast[ck][i] for i in conflict_idx],
            [per_cell_outcome[ck][i] for i in conflict_idx])
    murphy_interactions = {
        comp: round(interaction({ck: murphy_cells[ck][comp]
                                 for ck in murphy_cells}), 5)
        for comp in ("reliability", "resolution", "uncertainty", "brier")
    }

    fv_interaction = conflict["brier_full"]["interaction"]
    verdict = ("PASS" if abs(fv_interaction) <= MARGIN else "FAIL")
    report = {
        "protocol": "gate-b-rerun-phase3-chunk3",
        "preregistration": "gate-b-rerun-preregistration.md",
        "seeds": SEEDS, "n_per_seed": N_PER_SEED,
        "phase2_reference": {
            "brier_top_interaction_after_temp_fix": 0.09195,
            "accuracy_interaction": 0.22092,
            "note": "different seeds by design (fresh, per preregistration)",
        },
        "conflict_slice": conflict,
        "control_slice_matched": control,
        "murphy_conflict_slice": {"cells": murphy_cells,
                                  "component_interactions":
                                  murphy_interactions},
        "verdict_rule": "PASS iff |full-vector Brier interaction| <= 0.02 "
                        "on the conflict slice",
        "verdict": verdict,
        "elapsed_s": round(time.time() - t0, 1),
    }
    path = OUT + "gate-b-rerun-run1.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({
        "conflict_brier_full": conflict["brier_full"],
        "conflict_brier_top": conflict["brier_top"],
        "control_brier_full": control["brier_full"],
        "murphy_interactions": murphy_interactions,
        "verdict": verdict}, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
