#!/usr/bin/env python3
"""B2 remainders validation driver (2026-10-21).

M1 of b2-remainders-preregistration.md: stock-bench inertness of
the monitor's window-overlap signal (ruling W-A). Runs
mm.resolver.monitor over every task of the W3b decision bench
(evals/decision_bench gen_suite, n=300, seed=7 - the set the
monitor's saturation scale was tuned on) and verifies the
preregistered STOP conditions: no task resolves a pair, and the
windowed values equal the unwindowed values everywhere (bench
records carry no validity windows, so every window is open-ended
and any resolution would indict the fallback semantics).

The signal was ADOPTED on this measurement (ChatGPT ruling,
b2-remainders-adoption-ruling.txt): score/raw_score are now the
windowed values and the pre-signal values ride as *_unwindowed,
so inertness reads adopted == unwindowed on every task. The JSON
artifact is regenerated in the adopted code state; the
measurement itself is unchanged (same bench, same predicate).

Also reports the non-vacuity counters (tasks that actually carry
declared contradiction pairs, total pairs) so the zero is read
against a measured denominator - the corpus-3512 discipline: a
verified zero closes a cost question only when the denominator
is printed next to it.

Writes evals/reports/b2-remainders-m1.json. No LLM. Run from the
repo root: python3 evals/b2_remainders_validation.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evals.decision_bench import gen_suite, task_to_inputs
from mm.resolver import monitor


def main() -> int:
    tasks = gen_suite(300, 7)
    rows = []
    violations = []
    tasks_with_pairs = 0
    total_pairs = 0
    max_delta = 0.0
    for t in tasks:
        _, ranked, _ = task_to_inputs(t)
        rep = monitor([e.record for e in ranked], stakes="medium")
        total_pairs += rep.contradiction_count
        if rep.contradiction_count:
            tasks_with_pairs += 1
        delta = abs(rep.score - rep.score_unwindowed)
        max_delta = max(max_delta, delta)
        bad = (rep.window_resolved_count != 0
               or rep.score_unwindowed != rep.score
               or rep.raw_score_unwindowed != rep.raw_score)
        if bad:
            violations.append(t["task_id"])
        rows.append({
            "task_id": t["task_id"], "variant": t["variant"],
            "pairs": rep.contradiction_count,
            "window_resolved": rep.window_resolved_count,
            "M": rep.score, "M_unwindowed": rep.score_unwindowed,
            "M_raw": rep.raw_score,
            "M_raw_unwindowed": rep.raw_score_unwindowed,
        })
    report = {
        "measurement": "M1 stock-bench inertness (B2 remainders)",
        "bench": "evals/decision_bench gen_suite(n=300, seed=7)",
        "n_tasks": len(tasks),
        "tasks_with_pairs": tasks_with_pairs,
        "total_pairs": total_pairs,
        "violations": violations,
        "max_abs_M_delta": max_delta,
        "verdict": "PASS" if not violations else "STOP",
        "rows": rows,
    }
    out = os.path.join(os.path.dirname(__file__), "reports",
                       "b2-remainders-m1.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=1)
    print(f"n={len(tasks)} tasks_with_pairs={tasks_with_pairs} "
          f"total_pairs={total_pairs} violations={len(violations)} "
          f"max|dM|={max_delta} verdict={report['verdict']}")
    print(f"wrote {out}")
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
