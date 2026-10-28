"""Tie-regime lever validation (next-steps item 1). PREREGISTERED:
hidden_files/implementation/tie-lever-prereg.md. One run, this
analysis, reported as measured.

Arm A conventions (evals/agent_validation.py) with fresh seeds
6000-6001: per task per (kappa, lambda) cell, score_options is
computed ONCE and shared by the two arms; the arms differ only in
agent.decide(tie_epsilon_mode=...) - "absolute" (current production)
vs "relative" (eps_eff = tie_epsilon * |top net score|).

Primary contrast: accuracy interaction (conflict slice), relative
minus absolute, paired bootstrap 95% CI (1000 resamples, seed 4242).

Run:  python3 -m evals.tie_lever_validation   (from the repo root)
"""

from __future__ import annotations

import json
import os
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
       "hidden_files/implementation/")
SEEDS = (6000, 6001)
N_PER_SEED = 500
CELLS = [(0.0, 0.0), (0.25, 0.0), (0.0, 2.5), (0.25, 2.5)]
ARMS = ("absolute", "relative")
BOOTSTRAP_SEED = 4242
N_BOOT = 1000


def cell_key(kappa: float, lambda_: float) -> str:
    return f"k{kappa}_l{lambda_}"


def interaction(means: dict[str, float]) -> float:
    return (means[cell_key(0.25, 2.5)] - means[cell_key(0.25, 0.0)]
            - means[cell_key(0.0, 2.5)] + means[cell_key(0.0, 0.0)])


def mean_at(vals: list[float], samp: list[int]) -> float:
    return sum(vals[i] for i in samp) / len(samp)


def run() -> dict:
    print("Tie lever: generating tasks ...", flush=True)
    n = N_PER_SEED * len(SEEDS)
    # per[arm][cell] -> rows over the shared task list (seed order)
    per: dict[str, dict[str, dict[str, list]]] = {
        arm: {} for arm in ARMS}
    m_all: list[float] = []
    for kappa, lambda_ in CELLS:
        ck = cell_key(kappa, lambda_)
        rows = {arm: {"correct": [], "conf": [], "impasse": []}
                for arm in ARMS}
        for seed in SEEDS:
            agents = {}
            for arm in ARMS:
                tdir = tempfile.mkdtemp(prefix="tie-")
                agents[arm] = MemoryAgent(
                    SQLiteStore(f"{tdir}/memory.db"),
                    calibration_path=f"{tdir}/calibration.json")
            for task in db.gen_suite(N_PER_SEED, seed):
                options, ranked, link = db.task_to_inputs(task)

                def link_fn(ev, opt, link=link):
                    return link.get(ev.record.id, {}).get(opt.id, 0.0)

                scored = C.score_options(
                    options, ranked, stakes="medium", link_fn=link_fn,
                    calibration=None, kappa=kappa, lambda_=lambda_,
                    temp=1.0)
                candidates = [Candidate(id=o.id, description=o.id,
                                        source="bench") for o in options]
                prefs = [Preference(candidate_id=s.option.id,
                                    kind="better", weight=s.confidence,
                                    reason=f"tie-cell-{ck}",
                                    source_module="bench")
                         for s in scored if not s.pruned_by_constraint]
                evidence = [e.record for e in ranked]
                for arm in ARMS:
                    res = agents[arm].decide(
                        f"bench task {task['task_id']}", candidates,
                        prefs, evidence, tie_epsilon_mode=arm)
                    rows[arm]["correct"].append(
                        1.0 if res["selected_id"] == task["gold_best"]
                        else 0.0)
                    rows[arm]["conf"].append(res["confidence"])
                    rows[arm]["impasse"].append(
                        1.0 if res["impasse"] else 0.0)
                    if arm == "absolute" and ck == cell_key(0.0, 0.0):
                        m_all.append(res["conflict_score"])
        for arm in ARMS:
            per[arm][ck] = rows[arm]
        print(f"  cell {ck} done", flush=True)

    conflict_idx = [i for i in range(n) if m_all[i] > 0]
    control_idx = [i for i in range(n) if m_all[i] == 0]

    def slice_stats(arm: str, idx: list[int]) -> dict:
        acc = {ck: mean_at(per[arm][ck]["correct"], idx) for ck in per[arm]}
        brier = {ck: mean_at(
            [(per[arm][ck]["conf"][i] - per[arm][ck]["correct"][i]) ** 2
             for i in range(n)], idx) for ck in per[arm]}
        imp = {ck: mean_at(per[arm][ck]["impasse"], idx) for ck in per[arm]}
        return {"accuracy_per_cell": acc,
                "accuracy_interaction": interaction(acc),
                "brier_interaction": interaction(brier),
                "impasse_rate_per_cell": imp}

    def paired_contrast(idx: list[int], stat: str) -> dict:
        # stat: "accuracy" or "brier"; interaction per arm per resample
        rng = random.Random(BOOTSTRAP_SEED)
        diffs = []
        for _ in range(N_BOOT):
            samp = [rng.choice(idx) for _ in range(len(idx))]
            vals = {}
            for arm in ARMS:
                if stat == "accuracy":
                    means = {ck: mean_at(per[arm][ck]["correct"], samp)
                             for ck in per[arm]}
                else:
                    means = {ck: mean_at(
                        [(per[arm][ck]["conf"][i]
                          - per[arm][ck]["correct"][i]) ** 2
                         for i in range(n)], samp) for ck in per[arm]}
                vals[arm] = interaction(means)
            diffs.append(vals["relative"] - vals["absolute"])
        diffs.sort()
        point = (slice_stats("relative", idx)[
                     "accuracy_interaction" if stat == "accuracy"
                     else "brier_interaction"]
                 - slice_stats("absolute", idx)[
                     "accuracy_interaction" if stat == "accuracy"
                     else "brier_interaction"])
        return {"point": point,
                "ci95": [diffs[int(0.025 * N_BOOT)],
                         diffs[int(0.975 * N_BOOT)]]}

    report = {
        "validation": "tie-lever-item1",
        "preregistration": "tie-lever-prereg.md",
        "seeds": list(SEEDS), "n_tasks": n,
        "conflict_slice": {
            "n": len(conflict_idx),
            "absolute": slice_stats("absolute", conflict_idx),
            "relative": slice_stats("relative", conflict_idx),
            "accuracy_interaction_contrast":
                paired_contrast(conflict_idx, "accuracy"),
            "brier_interaction_contrast":
                paired_contrast(conflict_idx, "brier"),
        },
        "control_slice": {
            "n": len(control_idx),
            "absolute": slice_stats("absolute", control_idx),
            "relative": slice_stats("relative", control_idx),
        },
    }
    return report


def main() -> None:
    t0 = time.time()
    report = run()
    report["elapsed_s"] = round(time.time() - t0, 1)
    path = OUT + "tie-lever-run1.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
