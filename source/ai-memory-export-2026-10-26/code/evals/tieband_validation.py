"""Asymmetric tie band (TB-Q) accuracy evaluation.
PREREGISTERED: hidden_files/implementation/
asymmetric-tieband-preregistration.md. Two stages, fresh seed pairs;
stage 2 runs ONLY if stage 1 passes the primary endpoint and
every harm bound (see the preregistration).

Construction identical to evals/density_noisegate_validation.py
(same generator, score_options shared per task per cell,
per-record preferences, paired lognormal jitter), with the TB
arms replacing the gated arms: TB passes tie_band_quality=True
with the frozen thresholds (lo 0.6, hi 0.9, widen 1.25, shrink
0.8) into MemoryAgent.decide. Arms: PROD (adopted stack, band
off; R0 comparator), TB0 (band on, R0), REL1 (R1 comparator),
TB1 (band on, R1). Density stays off throughout (the ruling's
guard: the band is tested alone).

Primary contrast: mean over regimes of the conflict-slice
accuracy-interaction contrast (TB minus comparator), paired
bootstrap over tasks, 1000 resamples, seed 4242. Harm bounds:
(H1) |TB-minus-comparator control-slice accuracy-interaction
contrast| <= 0.01 in EACH regime and pooled (the corrected
paired form); (H2) high-stakes check: PROD vs TB0 outcomes
identical on every conflict task at the primary cell, stakes
high; (H3) tie-variant harm bound: the UPPER 95% confidence
bound on the PAIRED per-task change in tie-variant resolution
rate (TB minus comparator, primary cell) must be <= 0, pooled
and per regime.

Run:  python3 -m evals.tieband_validation [stage]
      stage = 1 (seeds 13000-13001) or 2 (seeds 14000-14001)
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
STAGE_SEEDS = {1: (13000, 13001), 2: (14000, 14001)}
N_PER_SEED = dav.N_PER_SEED
CELLS = dav.CELLS
PRIMARY_CELL = dav.PRIMARY_CELL
BOOTSTRAP_SEED = dav.BOOTSTRAP_SEED
N_BOOT = dav.N_BOOT
NET_TOL = dav.NET_TOL
TB_LO, TB_HI, TB_WIDEN, TB_SHRINK = 0.6, 0.9, 1.25, 0.8

REGIMES = {"R0": ("prod", "tb0"), "R1": ("rel1", "tb1")}
ARMS = ("prod", "tb0", "rel1", "tb1")
cell_key = dav.cell_key
interaction = dav.interaction
mean_at = dav.mean_at


def q_of(candidates, prefs):
    """The TB-Q balance statistic for these preferences, computed
    exactly as mm.decision.select computes it (frozen thresholds).
    Returns (q, m); q is None when the band is degenerate (inert).
    Descriptive only."""
    ranking, _, _ = attach_preferences(candidates, prefs)
    if len(ranking) < 2:
        return None, 1.0
    w = [sum(v.weight for v in prefs
             if v.kind in ("better", "worse")
             and v.candidate_id == cid and v.weight > 0)
         for cid, _ in ranking[:2]]
    if (w[0] + w[1]) <= 0:
        return None, 1.0
    q = w[0] / (w[0] + w[1])
    if q <= TB_LO:
        m = TB_WIDEN
    elif q >= TB_HI:
        m = TB_SHRINK
    else:
        m = TB_WIDEN + (TB_SHRINK - TB_WIDEN) * (
            (q - TB_LO) / (TB_HI - TB_LO))
    return q, m


def run(seeds):
    print(f"TB-Q accuracy: seeds {seeds} ...", flush=True)
    tasks_by_seed = {seed: db.gen_suite(N_PER_SEED, seed)
                     for seed in seeds}
    n = N_PER_SEED * len(seeds)
    rows = {arm: {cell_key(*c): {"correct": [], "conf": [],
                                 "impasse": []}
                  for c in CELLS} for arm in ARMS}
    variants: list[str] = []
    m_all: list[float] = []
    q_primary: list[float | None] = []
    m_primary = {"R0": [], "R1": []}
    net_violations = 0
    tie_positions: list[int] = []
    tie_res = {arm: [] for arm in ARMS}

    for kappa, lambda_ in CELLS:
        ck = cell_key(kappa, lambda_)
        for seed in seeds:
            agents = {arm: dav.fresh_agent("tieband-") for arm in ARMS}
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
                plan = [("prod", base, False),
                        ("tb0", per, True),
                        ("rel1", jit, False),
                        ("tb1", jit, True)]
                for arm, prefs, band in plan:
                    res = agents[arm].decide(
                        f"bench task {task['task_id']}", candidates,
                        prefs, evidence, tie_band_quality=band)
                    rows[arm][ck]["correct"].append(
                        1.0 if res["selected_id"] == task["gold_best"]
                        else 0.0)
                    rows[arm][ck]["conf"].append(res["confidence"])
                    rows[arm][ck]["impasse"].append(
                        1.0 if res["impasse"] else 0.0)
                    if (kappa, lambda_) == PRIMARY_CELL:
                        if task["variant"] == "tie":
                            if arm == "prod":
                                tie_positions.append(
                                    len(tie_res["prod"]))
                            tie_res[arm].append(
                                1.0 if res["selected_id"] is not None
                                else 0.0)
                    if arm == "prod" and ck == cell_key(0.0, 0.0):
                        m_all.append(res["conflict_score"])
                        variants.append(task["variant"])
                if (kappa, lambda_) == PRIMARY_CELL:
                    q, _m = q_of(candidates, per)
                    q_primary.append(q)
                    m_primary["R0"].append(_m)
                    _, _m_j = q_of(candidates, jit)
                    m_primary["R1"].append(_m_j)
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
        comp, tb = REGIMES[regime]
        fn = acc_interaction if stat == "accuracy" else brier_interaction
        return fn(tb, samp) - fn(comp, samp)

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
        for regime, (comp, tb) in REGIMES.items():
            block[regime] = {
                "comparator": comp, "tieband": tb,
                "accuracy_interaction": {
                    comp: acc_interaction(comp, idx),
                    tb: acc_interaction(tb, idx)},
                "impasse_rate": {
                    arm: {ck: mean_at(rows[arm][ck]["impasse"], idx)
                          for ck in rows[arm]}
                    for arm in (comp, tb)}}
        return block

    ece_block = {}
    for regime, (comp, tb) in REGIMES.items():
        ece_block[regime] = {}
        for arm in (comp, tb):
            pairs = [(rows[arm][pc]["conf"][i],
                      bool(rows[arm][pc]["correct"][i]))
                     for i in conflict_idx]
            ece_block[regime][arm] = db.ece(pairs)["ece"]

    imp_vals = {}
    for regime, (comp, tb) in REGIMES.items():
        imp_vals[regime] = (mean_at(rows[tb][pc]["impasse"], conflict_idx)
                            - mean_at(rows[comp][pc]["impasse"],
                                      conflict_idx))

    # control-slice contrasts (the corrected paired form)
    ctrl = {}
    for regime, (comp, tb) in REGIMES.items():
        ctrl[regime] = (acc_interaction(tb, control_idx)
                        - acc_interaction(comp, control_idx))
    ctrl["pooled"] = sum(ctrl[r] for r in REGIMES) / len(REGIMES)

    # H3: paired change in tie-variant resolution rate (TB - comparator)
    def h3_bootstrap():
        rng = __import__("random").Random(BOOTSTRAP_SEED)
        out = {}
        diffs = {}
        for regime, (comp, tb) in REGIMES.items():
            diffs[regime] = [tie_res[tb][j] - tie_res[comp][j]
                             for j in range(len(tie_positions))]
        diffs["pooled"] = diffs["R0"] + diffs["R1"]
        for key, ds in diffs.items():
            boots = []
            for _ in range(N_BOOT):
                samp = [rng.choice(ds) for _ in range(len(ds))]
                boots.append(sum(samp) / len(samp) if samp else 0.0)
            v = sorted(boots)
            point = (sum(ds) / len(ds)) if ds else 0.0
            out[key] = {"point": point,
                        "ci95": [v[int(0.025 * N_BOOT)],
                                 v[int(0.975 * N_BOOT)]],
                        "n_tie_tasks": len(ds)}
        return out

    h3 = h3_bootstrap()

    def pct(vals, q):
        return vals[min(len(vals) - 1, int(q * len(vals)))] if vals else None

    q_vals = sorted(q for q in q_primary if q is not None)
    terciles = []
    if q_vals:
        lo = q_vals[len(q_vals) // 3]
        hi = q_vals[2 * len(q_vals) // 3]
        for name, pred in (("low", lambda q: q <= lo),
                           ("mid", lambda q: lo < q <= hi),
                           ("high", lambda q: q > hi)):
            idx = [i for i in conflict_idx
                   if q_primary[i] is not None and pred(q_primary[i])]
            if idx:
                terciles.append({
                    "band": name, "n_conflict": len(idx),
                    "prod_acc_primary_cell": mean_at(
                        rows["prod"][pc]["correct"], idx),
                    "tb0_acc_primary_cell": mean_at(
                        rows["tb0"][pc]["correct"], idx),
                    "prod_impasse_primary_cell": mean_at(
                        rows["prod"][pc]["impasse"], idx),
                    "tb0_impasse_primary_cell": mean_at(
                        rows["tb0"][pc]["impasse"], idx)})

    def band_block(idxs):
        out = {}
        for regime in REGIMES:
            ms = [m_primary[regime][i] for i in idxs]
            if ms:
                out[regime] = {
                    "mean_m": sum(ms) / len(ms),
                    "frac_widened": sum(1 for m in ms if m > 1.0)
                    / len(ms),
                    "frac_shrunk": sum(1 for m in ms if m < 1.0)
                    / len(ms)}
        return out

    report = {
        "validation": "tieband-tb-q",
        "preregistration": "asymmetric-tieband-preregistration.md",
        "seeds": list(seeds), "n_tasks": n,
        "band_thresholds": {"lo": TB_LO, "hi": TB_HI,
                            "widen": TB_WIDEN, "shrink": TB_SHRINK},
        "jitter_sigma_log": dav.JITTER_SIGMA,
        "net_equality_violations": net_violations,
        "q_distribution_primary_cell": {
            "min": q_vals[0] if q_vals else None,
            "p25": pct(q_vals, 0.25), "median": pct(q_vals, 0.5),
            "p75": pct(q_vals, 0.75),
            "max": q_vals[-1] if q_vals else None,
            "mean": (sum(q_vals) / len(q_vals)) if q_vals else None,
            "n_none": sum(1 for q in q_primary if q is None)},
        "band_firing_primary_cell": {
            "all_tasks": band_block(list(range(n))),
            "conflict_slice": band_block(conflict_idx)},
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
            "tb_by_q_tercile_descriptive": terciles},
        "control_slice": {
            "n": len(control_idx),
            "accuracy_interaction": {
                arm: acc_interaction(arm, control_idx) for arm in ARMS},
            "tb_minus_comparator_contrast": ctrl,
            "harm_bound_abs": 0.01,
            "harm_bound_pass": {
                r: abs(ctrl[r]) <= 0.01 for r in ("R0", "R1", "pooled")}},
        "tie_variant_resolution_primary_cell": {
            arm: {"selected": sum(tie_res[arm]),
                  "n": len(tie_res[arm]),
                  "rate": (sum(tie_res[arm]) / len(tie_res[arm])
                           if tie_res[arm] else None)}
            for arm in ARMS},
        "tie_variant_harm_bound_H3": {
            "paired_change_ci95": h3,
            "bound": "upper ci95 <= 0, pooled and per regime",
            "harm_bound_pass": {
                k: h3[k]["ci95"][1] <= 0 for k in h3}},
    }
    return report, tasks_by_seed, m_all


def high_stakes_check(tasks_by_seed, m_all, seeds):
    """Frozen harm check: primary cell, stakes 'high', conflict
    tasks only - PROD vs TB0 outcomes must be identical."""
    kappa, lambda_ = PRIMARY_CELL
    conflict = set(i for i, m in enumerate(m_all) if m > 0)
    divergences = []
    checked = 0
    offset = 0
    for seed in seeds:
        agents = {arm: dav.fresh_agent("tieband-hs-")
                  for arm in ("prod", "tb0")}
        for j, task in enumerate(tasks_by_seed[seed]):
            if offset + j not in conflict:
                continue
            _o, candidates, evidence, scored = dav.score_task(
                task, kappa, lambda_)
            base, per = dav.build_prefs(task, task["options"], scored)
            outs = {}
            for arm, prefs, band in (
                    ("prod", base, False),
                    ("tb0", per, True)):
                res = agents[arm].decide(
                    f"bench task {task['task_id']}", candidates,
                    prefs, evidence, stakes="high",
                    tie_band_quality=band)
                outs[arm] = (res["selected_id"], res["impasse"])
            checked += 1
            if outs["prod"] != outs["tb0"]:
                divergences.append({"seed": seed,
                                    "task_id": task["task_id"],
                                    "prod": outs["prod"],
                                    "tb0": outs["tb0"]})
        offset += len(tasks_by_seed[seed])
    return {"checked": checked, "divergences": divergences,
            "identical": not divergences}


def main() -> None:
    stage = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    seeds = STAGE_SEEDS[stage]
    t0 = time.time()
    report, tasks_by_seed, m_all = run(seeds)
    print("TB-Q accuracy: high-stakes harm check ...", flush=True)
    report["high_stakes_check"] = high_stakes_check(
        tasks_by_seed, m_all, seeds)
    report["stage"] = stage
    report["elapsed_s"] = round(time.time() - t0, 1)
    path = OUT + f"tieband-run{stage}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    slim = {k: report[k] for k in (
        "seeds", "net_equality_violations", "band_firing_primary_cell",
        "high_stakes_check")}
    slim["primary"] = report["conflict_slice"][
        "primary_accuracy_interaction_contrast"]
    slim["control_contrasts"] = report["control_slice"][
        "tb_minus_comparator_contrast"]
    slim["control_pass"] = report["control_slice"]["harm_bound_pass"]
    slim["H3"] = report["tie_variant_harm_bound_H3"]
    print(json.dumps(slim, indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
