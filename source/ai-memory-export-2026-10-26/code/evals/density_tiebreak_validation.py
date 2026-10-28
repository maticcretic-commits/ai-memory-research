"""Density-scaling split characterization (density/provenance
build). PREREGISTERED: hidden_files/implementation/
density-tiebreak-preregistration.md.

FORMULA VERIFICATION ONLY - NOT ACCURACY EVIDENCE. ChatGPT ruling
Q1/Q4/Q5 (density-tiebreak-chatgpt-ruling.txt): the deterministic
split test "validates only density-metadata invariance"; DS-A's
accuracy benefit requires a separately preregistered
production-representative density/noise design, which is OWED and
not run here. Gold labels are read only to slice nothing - this
script never scores correctness; it checks the epsilon arithmetic
on real task shapes.

Design (frozen): seed 7000, cell (kappa, lambda) = (0.25, 2.5),
first 200 tasks of decision_bench.gen_suite(500, 7000).
score_options computed ONCE per task on stock records (Arm-A
sharing). Preference sets at k in {1, 4, 16}: each option's single
better-vote of weight w split deterministically into k votes of
w/k (nets identical by construction). Arms at each k:
select(relative) vs select(relative + density_scale), called
directly - the density lever lives in select(); decide()-level
pass-through is pinned by tests/test_density_tiebreak.py.

Frozen checks:
(a) net scores identical across k (tolerance 1e-9);
(b) at k = 1, density outcomes equal relative outcomes on every
    task (d = 1 must be exactly inert);
(c) tie counts under the density arm are monotone non-increasing
    in k;
(d) every outcome the density arm changes (vs relative at the
    same k) was a tie under relative and selects the net leader.

Run:  python3 -m evals.density_tiebreak_validation
"""

from __future__ import annotations

import json
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import decision_bench as db
from mm import confidence as C
from mm.decision import Candidate, Preference, attach_preferences, select

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")
SEED = 7000
N_SUITE = 500
N_TASKS = 200
KAPPA, LAMBDA = 0.25, 2.5
KS = (1, 4, 16)
TOL = 1e-9


def split(prefs, k):
    out = []
    for p in prefs:
        out += [Preference(candidate_id=p.candidate_id, kind="better",
                           weight=p.weight / k,
                           source_module="bench-split")
                for _ in range(k)]
    return out


def outcome(decision):
    if decision.selected_id is not None:
        return ("select", decision.selected_id)
    return ("impasse", decision.impasse.kind if decision.impasse else "?")


def run() -> dict:
    tasks = db.gen_suite(N_SUITE, SEED)[:N_TASKS]
    nets_bad = 0
    d1_mismatch = 0
    changed_bad = 0
    ties = {arm: {} for arm in ("relative", "density")}
    changed = {}
    for k in KS:
        ties["relative"][k] = 0
        ties["density"][k] = 0
        changed[k] = 0
    for task in tasks:
        options, ranked, link = db.task_to_inputs(task)

        def link_fn(ev, opt, link=link):
            return link.get(ev.record.id, {}).get(opt.id, 0.0)

        scored = C.score_options(
            options, ranked, stakes="medium", link_fn=link_fn,
            calibration=None, kappa=KAPPA, lambda_=LAMBDA, temp=1.0)
        candidates = [Candidate(id=o.id, description=o.id,
                                source="bench") for o in options]
        base = [Preference(candidate_id=s.option.id, kind="better",
                           weight=s.confidence, source_module="bench")
                for s in scored if not s.pruned_by_constraint]
        nets_by_k = {}
        for k in KS:
            prefs = split(base, k)
            ranking, _, _ = attach_preferences(candidates, prefs)
            nets_by_k[k] = dict(ranking)
            rel = select(candidates, prefs, tie_epsilon_mode="relative")
            den = select(candidates, prefs, tie_epsilon_mode="relative",
                         density_scale=True)
            if outcome(rel) == ("impasse", "tie"):
                ties["relative"][k] += 1
            if outcome(den) == ("impasse", "tie"):
                ties["density"][k] += 1
            if k == 1 and outcome(den) != outcome(rel):
                d1_mismatch += 1
            if outcome(den) != outcome(rel):
                changed[k] += 1
                leader = ranking[0][0] if ranking else None
                if not (outcome(rel) == ("impasse", "tie")
                        and outcome(den) == ("select", leader)):
                    changed_bad += 1
        ref = nets_by_k[KS[0]]
        for k in KS[1:]:
            for cid, net in nets_by_k[k].items():
                if abs(net - ref.get(cid, 0.0)) > TOL:
                    nets_bad += 1
    tie_seq = [ties["density"][k] for k in KS]
    checks = {
        "a_nets_identical_across_k": nets_bad == 0,
        "b_d1_density_inert": d1_mismatch == 0,
        "c_density_ties_monotone_nonincreasing":
            all(a >= b for a, b in zip(tie_seq, tie_seq[1:])),
        "d_changes_are_tie_to_leader": changed_bad == 0,
    }
    return {
        "validation": "density-split-characterization",
        "kind": "FORMULA VERIFICATION - NOT ACCURACY EVIDENCE",
        "preregistration": "density-tiebreak-preregistration.md",
        "seed": SEED, "n_tasks": len(tasks),
        "cell": {"kappa": KAPPA, "lambda": LAMBDA},
        "ks": list(KS),
        "ties_relative": {str(k): ties["relative"][k] for k in KS},
        "ties_density": {str(k): ties["density"][k] for k in KS},
        "outcomes_changed_by_density": {str(k): changed[k] for k in KS},
        "violations": {"nets": nets_bad, "d1_mismatch": d1_mismatch,
                       "changed_bad": changed_bad},
        "checks": checks,
        "all_checks_pass": all(checks.values()),
    }


def main() -> None:
    t0 = time.time()
    report = run()
    report["elapsed_s"] = round(time.time() - t0, 1)
    path = OUT + "density-tiebreak-run1.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
