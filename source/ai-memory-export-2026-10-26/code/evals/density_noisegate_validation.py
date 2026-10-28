"""Noise-gated density (DS-NG) accuracy evaluation.
PREREGISTERED: hidden_files/implementation/
next-lever-preregistration.md. Two stages, fresh seed pairs;
stage 2 runs ONLY if stage 1 passes the primary endpoint and
every harm bound (see the preregistration).

Construction identical to evals/density_accuracy_validation.py
(same generator, score_options shared per task per cell,
per-record preferences, paired lognormal jitter), with the DS
arms replaced by gated arms: NG passes density_scale=True +
density_noise_gate=True with the frozen thresholds
(lo 0.51, hi 0.80) into MemoryAgent.decide. Arms: PROD
(single-vote, density off; R0 comparator = the adopted stack),
NG-R0, REL-R1 (R1 comparator), NG-R1.

Primary contrast: mean over regimes of the conflict-slice
accuracy-interaction contrast (NG minus comparator), paired
bootstrap over tasks, 1000 resamples, seed 4242. Harm bound
(the corrected paired form licensed in DS-A run 2): |NG-minus-
comparator control-slice accuracy-interaction contrast| <=
0.01 in EACH regime and pooled. High-stakes check: PROD vs
NG-R0 outcomes identical on every conflict task at the
primary cell, stakes high.

Run:  python3 -m evals.density_noisegate_validation [stage]
      stage = 1 (seeds 11000-11001) or 2 (seeds 12000-12001)
"""

from __future__ import annotations

import json
import math
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import decision_bench as db
from evals import density_accuracy_validation as dav
from mm.decision import attach_preferences

OUT = dav.OUT
STAGE_SEEDS = {1: (11000, 11001), 2: (12000, 12001)}
N_PER_SEED = dav.N_PER_SEED
CELLS = dav.CELLS
PRIMARY_CELL = dav.PRIMARY_CELL
BOOTSTRAP_SEED = dav.BOOTSTRAP_SEED
N_BOOT = dav.N_BOOT
NET_TOL = dav.NET_TOL
LO, HI = 0.51, 0.80

REGIMES = {"R0": ("prod", "ng0"), "R1": ("rel1", "ng1")}
ARMS = ("prod", "ng0", "rel1", "ng1")
cell_key = dav.cell_key
interaction = dav.interaction
mean_at = dav.mean_at


def gate_of(candidates, prefs):
    """The DS-NG gate value for these preferences, computed
    exactly as mm.decision.select computes it (frozen
    thresholds). Descriptive only."""
    ranking, _, _ = attach_preferences(candidates, prefs)
    if len(ranking) < 2:
        return 0.0
    pooled: list[float] = []
    for cid, _ in ranking[:2]:
        logs = [math.log(v.weight) for v in prefs
                if v.kind in ("better", "worse")
                and v.candidate_id == cid and v.weight > 0]
        if logs:
            m = sum(logs) / len(logs)
            pooled.extend(x - m for x in logs)
    if len(pooled) < 4:
        return 0.0
    mu = sum(pooled) / len(pooled)
    nu = math.sqrt(sum((x - mu) ** 2 for x in pooled) / len(pooled))
    if nu <= LO:
        return 1.0
    if nu >= HI:
        return 0.0
    return (HI - nu) / (HI - LO)


def run(seeds):
    print(f"DS-NG accuracy: seeds {seeds} ...", flush=True)
    tasks_by_seed = {seed: db.gen_suite(N_PER_SEED, seed)
                     for seed in seeds}
    n = N_PER_SEED * len(seeds)
    rows = {arm: {cell_key(*c): {"correct": [], "conf": [],
                                 "impasse": []}
                  for c in CELLS} for arm in ARMS}
    variants: list[str] = []
    m_all: list[float] = []
    d_primary: list[float] = []
    g_primary = {"R0": [], "R1": []}
    net_violations = 0
    tie_sel = {arm: [0, 0] for arm in ARMS}

    for kappa, lambda_ in CELLS:
        ck = cell_key(kappa, lambda_)
        for seed in seeds:
            agents = {arm: dav.fresh_agent("densng-") for arm in ARMS}
            for task in tasks_by_seed[seed]:
                _opts, candidates, evidence, scored = dav.score_task(
                    task, kappa, lambda_)
                options = task["options"]
                base, per = dav.build_prefs(task, options, scored)
                net_base = dict(attach_preferences(candidates, base)[0])
                net_per = dict(attach_preferences(candidates, per)[0])
                for cid in set(net_base) | set(net_per):
                    if abs(net_base.get(cid, 0.0)
                           - net_per.get(cid, 0.0)) > NET_TOL:
                        net_violations += 1
                jit = dav.jitter(per, seed, task["task_id"], ck)
                plan = [("prod", base, False, False),
                        ("ng0", per, True, True),
                        ("rel1", jit, False, False),
                        ("ng1", jit, True, True)]
                for arm, prefs, ds, gate in plan:
                    res = agents[arm].decide(
                        f"bench task {task['task_id']}", candidates,
                        prefs, evidence, density_scale=ds,
                        density_noise_gate=gate)
                    rows[arm][ck]["correct"].append(
                        1.0 if res["selected_id"] == task["gold_best"]
                        else 0.0)
                    rows[arm][ck]["conf"].append(res["confidence"])
                    rows[arm][ck]["impasse"].append(
                        1.0 if res["impasse"] else 0.0)
                    if (kappa, lambda_) == PRIMARY_CELL:
                        if task["variant"] == "tie":
                            tie_sel[arm][1] += 1
                            if res["selected_id"] is not None:
                                tie_sel[arm][0] += 1
                    if arm == "prod" and ck == cell_key(0.0, 0.0):
                        m_all.append(res["conflict_score"])
                        variants.append(task["variant"])
                if (kappa, lambda_) == PRIMARY_CELL:
                    d_primary.append(dav.density_of(candidates, per))
                    g_primary["R0"].append(gate_of(candidates, per))
                    g_primary["R1"].append(gate_of(candidates, jit))
        print(f"  cell {ck} done", flush=True)

    conflict_idx = [i for i in range(n) if m_all[i] > 0]
    control_idx = [i for i in range(n) if m_all[i] == 0]
    pc = cell_key(*PRIMARY_CELL)

    def acc_interaction(arm, samp):
        means = {ck: mean_at(rows[arm][ck]["correct"], samp)
                 for ck in rows[arm]}
        return interaction(means)

    def brier_interaction(arm, samp):
        means = {}
        for ck in rows[arm]:
            vals = [(rows[arm][ck]["conf"][i]
                     - rows[arm][ck]["correct"][i]) ** 2
                    for i in range(len(rows[arm][ck]["conf"]))]
            means[ck] = mean_at(vals, samp)
        return interaction(means)

    def regime_contrast(regime, samp, stat="accuracy"):
        comp, ng = REGIMES[regime]
        fn = acc_interaction if stat == "accuracy" else brier_interaction
        return fn(ng, samp) - fn(comp, samp)

    def pooled_contrast(samp, stat="accuracy"):
        return sum(regime_contrast(r, samp, stat)
                   for r in REGIMES) / len(REGIMES)

    def bootstrap(stat):
        rng = __import__("random").Random(BOOTSTRAP_SEED)
        pooled, per_regime = [], {r: [] for r in REGIMES}
        for _ in range(N_BOOT):
            samp = [rng.choice(conflict_idx)
                    for _ in range(len(conflict_idx))]
            pooled.append(pooled_contrast(samp, stat))
            for r in REGIMES:
                per_regime[r].append(regime_contrast(r, samp, stat))

        def ci(vals):
            v = sorted(vals)
            return [v[int(0.025 * N_BOOT)], v[int(0.975 * N_BOOT)]]

        return {"point": pooled_contrast(conflict_idx, stat),
                "ci95": ci(pooled),
                "per_regime": {
                    r: {"point": regime_contrast(r, conflict_idx, stat),
                        "ci95": ci(per_regime[r])} for r in REGIMES}}

    def slice_block(idx):
        block = {}
        for regime, (comp, ng) in REGIMES.items():
            block[regime] = {
                "comparator": comp, "noisegate": ng,
                "accuracy_interaction": {
                    comp: acc_interaction(comp, idx),
                    ng: acc_interaction(ng, idx)},
                "impasse_rate": {
                    arm: {ck: mean_at(rows[arm][ck]["impasse"], idx)
                          for ck in rows[arm]}
                    for arm in (comp, ng)}}
        return block

    ece_block = {}
    for regime, (comp, ng) in REGIMES.items():
        ece_block[regime] = {}
        for arm in (comp, ng):
            pairs = [(rows[arm][pc]["conf"][i],
                      bool(rows[arm][pc]["correct"][i]))
                     for i in conflict_idx]
            ece_block[regime][arm] = db.ece(pairs)["ece"]

    imp_vals = {}
    for regime, (comp, ng) in REGIMES.items():
        imp_vals[regime] = (mean_at(rows[ng][pc]["impasse"], conflict_idx)
                            - mean_at(rows[comp][pc]["impasse"],
                                      conflict_idx))

    # control-slice contrasts (the corrected paired form)
    ctrl = {}
    for regime, (comp, ng) in REGIMES.items():
        ctrl[regime] = (acc_interaction(ng, control_idx)
                        - acc_interaction(comp, control_idx))
    ctrl["pooled"] = sum(ctrl[r] for r in REGIMES) / len(REGIMES)

    d_sorted = sorted(d_primary)

    def pct(vals, q):
        return vals[min(len(vals) - 1, int(q * len(vals)))] if vals else None

    terciles = []
    if d_sorted:
        lo = d_sorted[len(d_sorted) // 3]
        hi = d_sorted[2 * len(d_sorted) // 3]
        for name, pred in (("low", lambda d: d <= lo),
                           ("mid", lambda d: lo < d <= hi),
                           ("high", lambda d: d > hi)):
            idx = [i for i in conflict_idx if pred(d_primary[i])]
            if idx:
                terciles.append({
                    "band": name, "n_conflict": len(idx),
                    "prod_acc_primary_cell": mean_at(
                        rows["prod"][pc]["correct"], idx),
                    "ng0_acc_primary_cell": mean_at(
                        rows["ng0"][pc]["correct"], idx),
                    "prod_impasse_primary_cell": mean_at(
                        rows["prod"][pc]["impasse"], idx),
                    "ng0_impasse_primary_cell": mean_at(
                        rows["ng0"][pc]["impasse"], idx)})

    def gate_block(idxs):
        out = {}
        for regime in REGIMES:
            gs = [g_primary[regime][i] for i in idxs]
            if gs:
                out[regime] = {
                    "mean_g": sum(gs) / len(gs),
                    "frac_g1": sum(1 for g in gs if g == 1.0) / len(gs),
                    "frac_g0": sum(1 for g in gs if g == 0.0) / len(gs)}
        return out

    report = {
        "validation": "density-noisegate-ds-ng",
        "preregistration": "next-lever-preregistration.md",
        "seeds": list(seeds), "n_tasks": n,
        "gate_thresholds": {"lo": LO, "hi": HI},
        "jitter_sigma_log": dav.JITTER_SIGMA,
        "net_equality_violations": net_violations,
        "d_distribution_primary_cell": {
            "min": d_sorted[0] if d_sorted else None,
            "p25": pct(d_sorted, 0.25), "median": pct(d_sorted, 0.5),
            "p75": pct(d_sorted, 0.75),
            "max": d_sorted[-1] if d_sorted else None,
            "mean": (sum(d_sorted) / len(d_sorted)) if d_sorted else None},
        "gate_firing_primary_cell": {
            "all_tasks": gate_block(list(range(n))),
            "conflict_slice": gate_block(conflict_idx)},
        "conflict_slice": {
            "n": len(conflict_idx),
            "by_regime": slice_block(conflict_idx),
            "primary_accuracy_interaction_contrast":
                bootstrap("accuracy"),
            "brier_interaction_contrast": bootstrap("brier"),
            "impasse_contrast_primary_cell": {
                "per_regime": imp_vals,
                "pooled": sum(imp_vals.values()) / len(imp_vals)},
            "ece_primary_cell": ece_block,
            "ng_by_d_tercile_descriptive": terciles},
        "control_slice": {
            "n": len(control_idx),
            "accuracy_interaction": {
                arm: acc_interaction(arm, control_idx) for arm in ARMS},
            "ng_minus_comparator_contrast": ctrl,
            "harm_bound_abs": 0.01,
            "harm_bound_pass": {
                r: abs(ctrl[r]) <= 0.01 for r in ("R0", "R1", "pooled")}},
        "tie_variant_resolution_primary_cell": {
            arm: {"selected": tie_sel[arm][0], "n": tie_sel[arm][1],
                  "rate": (tie_sel[arm][0] / tie_sel[arm][1]
                           if tie_sel[arm][1] else None)}
            for arm in ARMS},
    }
    return report, tasks_by_seed, m_all


def high_stakes_check(tasks_by_seed, m_all, seeds):
    """Frozen harm check: primary cell, stakes 'high', conflict
    tasks only - PROD vs NG-R0 outcomes must be identical."""
    kappa, lambda_ = PRIMARY_CELL
    conflict = set(i for i, m in enumerate(m_all) if m > 0)
    divergences = []
    checked = 0
    offset = 0
    for seed in seeds:
        agents = {arm: dav.fresh_agent("densng-hs-")
                  for arm in ("prod", "ng0")}
        for j, task in enumerate(tasks_by_seed[seed]):
            if offset + j not in conflict:
                continue
            _o, candidates, evidence, scored = dav.score_task(
                task, kappa, lambda_)
            base, per = dav.build_prefs(task, task["options"], scored)
            outs = {}
            for arm, prefs, ds, gate in (
                    ("prod", base, False, False),
                    ("ng0", per, True, True)):
                res = agents[arm].decide(
                    f"bench task {task['task_id']}", candidates,
                    prefs, evidence, stakes="high", density_scale=ds,
                    density_noise_gate=gate)
                outs[arm] = (res["selected_id"], res["impasse"])
            checked += 1
            if outs["prod"] != outs["ng0"]:
                divergences.append({"seed": seed,
                                    "task_id": task["task_id"],
                                    "prod": outs["prod"],
                                    "ng0": outs["ng0"]})
        offset += len(tasks_by_seed[seed])
    return {"checked": checked, "divergences": divergences,
            "identical": not divergences}


def main() -> None:
    stage = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    seeds = STAGE_SEEDS[stage]
    t0 = time.time()
    report, tasks_by_seed, m_all = run(seeds)
    print("DS-NG accuracy: high-stakes harm check ...", flush=True)
    report["high_stakes_check"] = high_stakes_check(
        tasks_by_seed, m_all, seeds)
    report["stage"] = stage
    report["elapsed_s"] = round(time.time() - t0, 1)
    path = OUT + f"next-lever-noisegate-run{stage}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    slim = {k: report[k] for k in (
        "seeds", "net_equality_violations", "gate_firing_primary_cell",
        "high_stakes_check")}
    slim["primary"] = report["conflict_slice"][
        "primary_accuracy_interaction_contrast"]
    slim["control_contrasts"] = report["control_slice"][
        "ng_minus_comparator_contrast"]
    slim["control_pass"] = report["control_slice"]["harm_bound_pass"]
    print(json.dumps(slim, indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
