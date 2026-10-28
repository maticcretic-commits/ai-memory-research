"""Calibration-shaped interaction measurement.
PREREGISTERED: hidden_files/implementation/
calibration-shaped-interaction-preregistration.md.
MEASUREMENT ONLY - no implementation, no fitting, nothing
shipped. HD-2 holds: all statistics are descriptive (group
accuracy, within-group bootstrap CIs, Mann-Whitney AUC). No
model is fitted on synthetic pairs.

Arm: A0 = MemoryAgent.decide() as shipped (agent default).
Fresh seeds 12000-12001, never used by any prior lane.

Run:  python3 -m evals.calibration_shaped_interaction
(from the repo root)
"""

from __future__ import annotations

import json
import random
import sys
import tempfile
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import decision_bench as db
from mm import confidence as C
from mm.agent import MemoryAgent
from mm.decision import Candidate, Preference
from mm.storage import SQLiteStore

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/"
       "calibration-shaped-interaction-run1.json")
SEEDS = (12000, 12001)
N_PER_SEED = 1000
KAPPA, LAMBDA, TEMP = 0.25, 2.5, 1.0
BOOT_REPS = 1000


# ---------------------------------------------------------------------------
# Descriptive statistics (no fitting)
# ---------------------------------------------------------------------------

def _group_accuracy(labels: list[float]) -> float:
    return sum(labels) / len(labels) if labels else 0.0


def delta_acc_ci(labels_a: list[float], labels_b: list[float],
                 reps: int = BOOT_REPS, seed: int = 42) -> dict:
    """acc(B) - acc(A) with 95% within-group bootstrap CI."""
    rng = random.Random(seed)
    if not labels_a or not labels_b:
        return {"delta": 0.0, "ci_lo": 0.0, "ci_hi": 0.0,
                "n_a": len(labels_a), "n_b": len(labels_b),
                "insufficient": True}
    obs = _group_accuracy(labels_b) - _group_accuracy(labels_a)
    deltas = []
    for _ in range(reps):
        sa = [labels_a[rng.randrange(len(labels_a))]
              for _ in range(len(labels_a))]
        sb = [labels_b[rng.randrange(len(labels_b))]
              for _ in range(len(labels_b))]
        deltas.append(_group_accuracy(sb) - _group_accuracy(sa))
    deltas.sort()
    return {
        "delta": round(obs, 4),
        "ci_lo": round(deltas[int(0.025 * (reps - 1))], 4),
        "ci_hi": round(deltas[int(0.975 * (reps - 1))], 4),
        "acc_a": round(_group_accuracy(labels_a), 4),
        "acc_b": round(_group_accuracy(labels_b), 4),
        "n_a": len(labels_a), "n_b": len(labels_b),
        "insufficient": len(labels_a) < 30 or len(labels_b) < 30,
    }


def auc_mann_whitney(scores: list[float],
                     labels: list[float]) -> float:
    """P(score(correct) > score(incorrect)) + 0.5 * ties."""
    pos = [s for s, y in zip(scores, labels) if y == 1.0]
    neg = [s for s, y in zip(scores, labels) if y == 0.0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def auc_ci(scores: list[float], labels: list[float],
           reps: int = BOOT_REPS, seed: int = 43) -> dict:
    rng = random.Random(seed)
    n = len(scores)
    if n == 0:
        return {"auc": 0.5, "ci_lo": 0.5, "ci_hi": 0.5, "n": 0,
                "insufficient": True}
    obs = auc_mann_whitney(scores, labels)
    vals = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(auc_mann_whitney(
            [scores[i] for i in idx], [labels[i] for i in idx]))
    vals.sort()
    return {
        "auc": round(obs, 4),
        "ci_lo": round(vals[int(0.025 * (reps - 1))], 4),
        "ci_hi": round(vals[int(0.975 * (reps - 1))], 4),
        "n": n, "insufficient": n < 30,
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run() -> dict:
    t0 = time.time()
    rows: list[dict] = []
    agent = None
    for seed in SEEDS:
        tdir = tempfile.mkdtemp(prefix="csi-")
        agent = MemoryAgent(
            SQLiteStore(f"{tdir}/memory.db"),
            calibration_path=f"{tdir}/calibration.json")
        for task in db.gen_suite(N_PER_SEED, seed):
            options, ranked, link = db.task_to_inputs(task)
            evidence = [e.record for e in ranked]

            def link_fn(ev, opt, link=link):
                return link.get(ev.record.id, {}).get(opt.id, 0.0)

            scored = C.score_options(
                options, ranked, stakes="medium", link_fn=link_fn,
                calibration=None, kappa=KAPPA, lambda_=LAMBDA,
                temp=TEMP)
            candidates = [Candidate(id=o.id, description=o.id,
                                    source="bench") for o in options]
            prefs = [Preference(candidate_id=s.option.id,
                                kind="better", weight=s.confidence,
                                reason="csi-bench",
                                source_module="bench")
                     for s in scored if not s.pruned_by_constraint]
            question = f"csi task {seed}-{task['task_id']}"
            res = agent.decide(question, candidates, prefs, evidence)
            sel = res["selected_id"]
            rows.append({
                "seed": seed, "task_id": task["task_id"],
                "variant": task["variant"],
                "gold_best": task["gold_best"],
                "selected_id": sel,
                "impasse": res["impasse"],
                "confidence": res["confidence"],
                "conflict_score": res["conflict_score"],
                "correct": (1.0 if sel == task["gold_best"] else 0.0)
                if sel is not None else None,
            })
        print(f"  seed {seed} done ({time.time() - t0:.0f}s)",
              flush=True)

    sel = [r for r in rows if r["selected_id"] is not None]
    correct = [r["correct"] for r in sel]

    # T1: tie-variant membership among selections
    tie_lab = [r["correct"] for r in sel if r["variant"] == "tie"]
    rest_lab = [r["correct"] for r in sel
                if r["variant"] != "tie"]
    t1 = delta_acc_ci(tie_lab, rest_lab)

    # T2: anchor membership - conf == 0.70 vs conf < 0.70
    anchor_lab = [r["correct"] for r in sel
                  if abs(r["confidence"] - 0.70) < 1e-9]
    penal_lab = [r["correct"] for r in sel
                 if r["confidence"] < 0.70 - 1e-9]
    t2 = delta_acc_ci(penal_lab, anchor_lab)

    # T3: conflict_score as a correctness classifier (selections)
    scores = [r["conflict_score"] for r in sel]
    t3 = auc_ci(scores, correct)

    # T4: within the M>0-penalized selections, split at the
    # median conflict_score - below vs at/above
    pen = [r for r in sel if r["conflict_score"] > 0]
    t4 = {"n_penalized": len(pen)}
    if pen:
        med = sorted(r["conflict_score"]
                     for r in pen)[len(pen) // 2]
        lo_lab = [r["correct"] for r in pen
                  if r["conflict_score"] < med]
        hi_lab = [r["correct"] for r in pen
                  if r["conflict_score"] >= med]
        t4 = delta_acc_ci(lo_lab, hi_lab)
        t4["median_conflict_score"] = round(med, 4)
        t4["n_penalized"] = len(pen)

    # T5: all-tasks selection-state separator (context only)
    sel_all_lab = [r["correct"] for r in sel]
    imp_all_lab = [0.0 for r in rows
                   if r["selected_id"] is None]
    t5 = delta_acc_ci(imp_all_lab, sel_all_lab)

    # two-way cell table (variant x anchor), descriptive
    cells = {}
    for v in ("standard", "conflicting", "tie"):
        for anchor in ("anchor070", "penalized"):
            cr = [r["correct"] for r in sel if r["variant"] == v
                  and ((abs(r["confidence"] - 0.70) < 1e-9)
                       == (anchor == "anchor070"))]
            cells[f"{v}/{anchor}"] = {
                "n": len(cr),
                "accuracy": round(_group_accuracy(cr), 4) if cr
                else None,
            }

    summary = {
        "n_tasks": len(rows),
        "n_selected": len(sel),
        "impasse_rate": round(1 - len(sel) / len(rows), 4),
        "selection_accuracy": round(_group_accuracy(correct), 4),
        "anchor070_n": len(anchor_lab),
        "penalized_n": len(penal_lab),
        "T1_tie_vs_rest_delta_acc": t1,
        "T2_anchor_vs_penalized_delta_acc": t2,
        "T3_conflict_score_auc": t3,
        "T4_median_split_within_penalized": t4,
        "T5_alltasks_select_vs_impasse_delta_acc": t5,
        "variant_x_anchor_cells": cells,
    }
    out = {
        "protocol": "calibration-shaped-interaction-v1",
        "preregistration": ("hidden_files/implementation/"
                            "calibration-shaped-interaction-"
                            "preregistration.md"),
        "seeds": list(SEEDS), "n_per_seed": N_PER_SEED,
        "cell": {"kappa": KAPPA, "lambda": LAMBDA, "temp": TEMP},
        "arm": "A0-agent-default",
        "elapsed_s": round(time.time() - t0, 1),
        "summary": summary,
        "rows": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {OUT}", flush=True)
    print(json.dumps(summary, indent=1), flush=True)
    return out


if __name__ == "__main__":
    run()
