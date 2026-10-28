"""Density-scaling (DS-A) accuracy evaluation. PREREGISTERED:
hidden_files/implementation/density-accuracy-preregistration.md.
One run, this analysis, reported as measured.

Design (frozen in the preregistration): gen_suite seeds
8000-8001, 500/seed; the four Arm-A (kappa, lambda) cells;
score_options computed ONCE per task per cell and shared by all
arms/regimes. Preferences are rebuilt at evidence granularity:
one "better" vote per evidence record linked to an option,
weight = confidence * (|drift| * relevance) share within the
option, so nets are EXACTLY the production (single-vote) nets
and d - the mean top-two scoring-vote count select() uses - is
the endogenous evidence count of the top-two candidates.

Regimes: R0 = per-record weights as constructed (generator-
intrinsic noise); R1 = the same weights with per-vote lognormal
jitter exp(N(0, 0.25)) from a per-(seed, task, cell) seeded rng,
identical for both R1 arms (paired). Arms: PROD (single-vote,
density off; R0 comparator = current production), DS-R0,
REL-R1 (R1 comparator), DS-R1 - all through MemoryAgent.decide,
stakes "medium", tie_epsilon_mode "relative" (adopted default).

Primary contrast: mean over regimes of the conflict-slice
accuracy-interaction contrast (DS minus comparator), paired
bootstrap over tasks, 1000 resamples, seed 4242.

Run:  python3 -m evals.density_accuracy_validation
"""

from __future__ import annotations

import json
import math
import random
import sys
import tempfile
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import decision_bench as db
from mm import confidence as C
from mm.agent import MemoryAgent
from mm.decision import Candidate, Preference, attach_preferences
from mm.storage import SQLiteStore

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")
SEEDS = (8000, 8001)
N_PER_SEED = 500
CELLS = [(0.0, 0.0), (0.25, 0.0), (0.0, 2.5), (0.25, 2.5)]
PRIMARY_CELL = (0.25, 2.5)
BOOTSTRAP_SEED = 4242
N_BOOT = 1000
JITTER_SIGMA = 0.25
NET_TOL = 1e-12

# regime -> (comparator arm, density arm)
REGIMES = {"R0": ("prod", "ds0"), "R1": ("rel1", "ds1")}
ARMS = ("prod", "ds0", "rel1", "ds1")


def cell_key(kappa: float, lambda_: float) -> str:
    return f"k{kappa}_l{lambda_}"


def interaction(means: dict[str, float]) -> float:
    return (means[cell_key(0.25, 2.5)] - means[cell_key(0.25, 0.0)]
            - means[cell_key(0.0, 2.5)] + means[cell_key(0.0, 0.0)])


def mean_at(vals: list[float], samp: list[int]) -> float:
    return sum(vals[i] for i in samp) / len(samp)


def fresh_agent(prefix: str) -> MemoryAgent:
    tdir = tempfile.mkdtemp(prefix=prefix)
    return MemoryAgent(SQLiteStore(f"{tdir}/memory.db"),
                       calibration_path=f"{tdir}/calibration.json")


def score_task(task, kappa, lambda_):
    """score_options ONCE per task per cell (Arm-A sharing)."""
    options, ranked, link = db.task_to_inputs(task)

    def link_fn(ev, opt, link=link):
        return link.get(ev.record.id, {}).get(opt.id, 0.0)

    scored = C.score_options(options, ranked, stakes="medium",
                             link_fn=link_fn, calibration=None,
                             kappa=kappa, lambda_=lambda_, temp=1.0)
    candidates = [Candidate(id=o.id, description=o.id,
                            source="bench") for o in options]
    evidence = [e.record for e in ranked]
    return options, candidates, evidence, scored


def build_prefs(task, options, scored):
    """Return (base, per_record) preference lists.

    base: one "better" vote per non-pruned option, weight =
    confidence (Arm-A routing, current production). per_record:
    the same support split over the option's linked evidence
    records by (|drift| * relevance) share; nets identical.
    Options with no linked records (or zero total mass) keep a
    single vote of the full confidence (net-preserving fallback).
    """
    mass: dict[str, float] = {}
    shares: dict[str, list[float]] = {}
    for _ev_id, opt_idx, relevance, drift in task["evidence"]:
        oid = options[opt_idx].id
        m = abs(drift) * relevance
        mass[oid] = mass.get(oid, 0.0) + m
        shares.setdefault(oid, []).append(m)
    base, per = [], []
    for s in scored:
        if s.pruned_by_constraint:
            continue
        oid = s.option.id
        base.append(Preference(candidate_id=oid, kind="better",
                               weight=s.confidence,
                               source_module="bench"))
        opt_shares = shares.get(oid, [])
        total = mass.get(oid, 0.0)
        if not opt_shares or total <= 0.0:
            per.append(Preference(candidate_id=oid, kind="better",
                                  weight=s.confidence,
                                  source_module="bench-fallback"))
        else:
            for m in opt_shares:
                per.append(Preference(
                    candidate_id=oid, kind="better",
                    weight=s.confidence * m / total,
                    source_module="bench-record"))
    return base, per


def jitter(prefs, seed, task_id, ck):
    """R1: per-vote lognormal jitter, deterministic per
    (seed, task, cell); the returned list is shared verbatim by
    both R1 arms (paired)."""
    rng = random.Random(f"{seed}|{task_id}|{ck}|R1")
    return [Preference(candidate_id=p.candidate_id, kind=p.kind,
                       weight=p.weight * math.exp(
                           rng.gauss(0.0, JITTER_SIGMA)),
                       source_module=p.source_module)
            for p in prefs]


def density_of(candidates, prefs):
    """d as select() computes it: mean scoring-vote count over
    the top-two ranked candidates."""
    ranking, _, _ = attach_preferences(candidates, prefs)
    if not ranking:
        return 0.0
    counts = {cid: 0 for cid, _ in ranking}
    for v in prefs:
        if v.kind in ("better", "worse") and v.candidate_id in counts:
            counts[v.candidate_id] += 1
    top = [counts[cid] for cid, _ in ranking[:2]]
    return sum(top) / len(top) if top else 0.0


def run():
    print("Density accuracy: generating tasks ...", flush=True)
    tasks_by_seed = {seed: db.gen_suite(N_PER_SEED, seed)
                     for seed in SEEDS}
    n = N_PER_SEED * len(SEEDS)
    rows = {arm: {cell_key(*c): {"correct": [], "conf": [],
                                 "impasse": []}
                  for c in CELLS} for arm in ARMS}
    variants: list[str] = []
    m_all: list[float] = []
    d_primary: list[float] = []
    net_violations = 0
    tie_sel = {arm: [0, 0] for arm in ARMS}

    for kappa, lambda_ in CELLS:
        ck = cell_key(kappa, lambda_)
        for seed in SEEDS:
            agents = {arm: fresh_agent("dens-") for arm in ARMS}
            for task in tasks_by_seed[seed]:
                _opts, candidates, evidence, scored = score_task(
                    task, kappa, lambda_)
                options = task["options"]
                base, per = build_prefs(task, options, scored)
                net_base = dict(attach_preferences(candidates, base)[0])
                net_per = dict(attach_preferences(candidates, per)[0])
                for cid in set(net_base) | set(net_per):
                    if abs(net_base.get(cid, 0.0)
                           - net_per.get(cid, 0.0)) > NET_TOL:
                        net_violations += 1
                jit = jitter(per, seed, task["task_id"], ck)
                plan = [("prod", base, False), ("ds0", per, True),
                        ("rel1", jit, False), ("ds1", jit, True)]
                for arm, prefs, ds in plan:
                    res = agents[arm].decide(
                        f"bench task {task['task_id']}", candidates,
                        prefs, evidence, density_scale=ds)
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
                    d_primary.append(density_of(candidates, per))
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
        comp, ds = REGIMES[regime]
        fn = acc_interaction if stat == "accuracy" else brier_interaction
        return fn(ds, samp) - fn(comp, samp)

    def pooled_contrast(samp, stat="accuracy"):
        return sum(regime_contrast(r, samp, stat)
                   for r in REGIMES) / len(REGIMES)

    def bootstrap(stat):
        rng = random.Random(BOOTSTRAP_SEED)
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
        for regime, (comp, ds) in REGIMES.items():
            block[regime] = {
                "comparator": comp, "density": ds,
                "accuracy_interaction": {
                    comp: acc_interaction(comp, idx),
                    ds: acc_interaction(ds, idx)},
                "impasse_rate": {
                    arm: {ck: mean_at(rows[arm][ck]["impasse"], idx)
                          for ck in rows[arm]}
                    for arm in (comp, ds)}}
        return block

    ece_block = {}
    for regime, (comp, ds) in REGIMES.items():
        ece_block[regime] = {}
        for arm in (comp, ds):
            pairs = [(rows[arm][pc]["conf"][i],
                      bool(rows[arm][pc]["correct"][i]))
                     for i in conflict_idx]
            ece_block[regime][arm] = db.ece(pairs)["ece"]

    imp_vals = {}
    for regime, (comp, ds) in REGIMES.items():
        imp_vals[regime] = (mean_at(rows[ds][pc]["impasse"], conflict_idx)
                            - mean_at(rows[comp][pc]["impasse"],
                                      conflict_idx))

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
                    "ds0_acc_primary_cell": mean_at(
                        rows["ds0"][pc]["correct"], idx),
                    "prod_impasse_primary_cell": mean_at(
                        rows["prod"][pc]["impasse"], idx),
                    "ds0_impasse_primary_cell": mean_at(
                        rows["ds0"][pc]["impasse"], idx)})

    report = {
        "validation": "density-accuracy-ds-a",
        "preregistration": "density-accuracy-preregistration.md",
        "seeds": list(SEEDS), "n_tasks": n,
        "jitter_sigma_log": JITTER_SIGMA,
        "net_equality_violations": net_violations,
        "d_distribution_primary_cell": {
            "min": d_sorted[0] if d_sorted else None,
            "p25": pct(d_sorted, 0.25), "median": pct(d_sorted, 0.5),
            "p75": pct(d_sorted, 0.75),
            "max": d_sorted[-1] if d_sorted else None,
            "mean": (sum(d_sorted) / len(d_sorted)) if d_sorted else None},
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
            "ds_by_d_tercile_descriptive": terciles},
        "control_slice": {
            "n": len(control_idx),
            "accuracy_interaction": {
                arm: acc_interaction(arm, control_idx) for arm in ARMS}},
        "tie_variant_resolution_primary_cell": {
            arm: {"selected": tie_sel[arm][0], "n": tie_sel[arm][1],
                  "rate": (tie_sel[arm][0] / tie_sel[arm][1]
                           if tie_sel[arm][1] else None)}
            for arm in ARMS},
    }
    return report, tasks_by_seed, m_all


def high_stakes_check(tasks_by_seed, m_all):
    """Frozen harm check: primary cell, stakes 'high', conflict
    tasks only - PROD vs DS-R0 outcomes must be identical."""
    kappa, lambda_ = PRIMARY_CELL
    conflict = set(i for i, m in enumerate(m_all) if m > 0)
    divergences = []
    checked = 0
    offset = 0
    for seed in SEEDS:
        agents = {arm: fresh_agent("dens-hs-") for arm in ("prod", "ds0")}
        for j, task in enumerate(tasks_by_seed[seed]):
            if offset + j not in conflict:
                continue
            _o, candidates, evidence, scored = score_task(
                task, kappa, lambda_)
            base, per = build_prefs(task, task["options"], scored)
            outs = {}
            for arm, prefs, ds in (("prod", base, False),
                                   ("ds0", per, True)):
                res = agents[arm].decide(
                    f"bench task {task['task_id']}", candidates,
                    prefs, evidence, stakes="high", density_scale=ds)
                outs[arm] = (res["selected_id"], res["impasse"])
            checked += 1
            if outs["prod"] != outs["ds0"]:
                divergences.append({"seed": seed,
                                    "task_id": task["task_id"],
                                    "prod": outs["prod"],
                                    "ds0": outs["ds0"]})
        offset += len(tasks_by_seed[seed])
    return {"checked": checked, "divergences": divergences,
            "identical": not divergences}


def main() -> None:
    t0 = time.time()
    report, tasks_by_seed, m_all = run()
    print("Density accuracy: high-stakes harm check ...", flush=True)
    report["high_stakes_check"] = high_stakes_check(tasks_by_seed,
                                                    m_all)
    report["elapsed_s"] = round(time.time() - t0, 1)
    path = OUT + "density-accuracy-run1.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
