"""conflict-highstakes-10k — high-stakes conflict slice for gate (d).

Gate-(d) sizing (W6/W7 follow-up): ~6.6k-13k high-stakes tasks are needed
for 80% power on the one-sided 95% upper CB < +2pp excess-error margin.
The 63-task bench slice and the 120-task held-out set are orders of
magnitude too small, so this module generates 10,000 NEW conflicting
tasks under fresh seeds (1000-1009), ids hs00000-hs09999, as a standalone
dataset for Phase-2 gate-(d) measurement.

Generation uses the same conflicting-variant generator as the main bench,
including the W9 full-bipartite declared-contradiction extension — only
the seeds and the task-id namespace differ. Deterministic: each seed owns
an independent rng and a fixed 1000-task id block, so regenerating any
seed reproduces its tasks byte-identically.

Run:  python3 -m evals.highstakes_slice --out evals/data/conflict-highstakes-10k.json
      (from the repo root)
"""

from __future__ import annotations

import argparse
import json
import sys

import random

from evals import decision_bench as db
from mm.confidence import CandidateOption

HS_SEEDS = list(range(1000, 1010))   # 10 seeds
HS_PER_SEED = 1000                   # 1000 tasks each -> 10,000 total
HS_N = len(HS_SEEDS) * HS_PER_SEED
HS_ID_PREFIX = "hs"


def _seed_offset(seed: int, seeds: list[int], n_per_seed: int) -> int:
    """Id-block offset for one seed.

    Canonical seeds always use their HS_SEEDS position, so regenerating
    any subset (e.g. [1005]) reproduces the file's ids byte-identically.
    Non-canonical seeds fall back to their position in the given list.
    """
    if seed in HS_SEEDS:
        return HS_SEEDS.index(seed) * n_per_seed
    return seeds.index(seed) * n_per_seed


def generate(n_per_seed: int = HS_PER_SEED,
             seeds: list[int] = HS_SEEDS) -> list[dict]:
    """Generate n_per_seed conflicting tasks per seed (fresh rng each)."""
    tasks: list[dict] = []
    for seed in seeds:
        rng = random.Random(seed)
        base = _seed_offset(seed, seeds, n_per_seed)
        for i in range(n_per_seed):
            tasks.append(db.gen_task(rng, f"{HS_ID_PREFIX}{base + i:05d}",
                                     "conflicting"))
    return tasks


def task_to_json(task: dict) -> dict:
    """Serialize a generated task to JSON-safe dicts."""
    return {
        "task_id": task["task_id"],
        "variant": task["variant"],
        "options": [{"id": o.id, "description": o.description,
                     "action": o.action} for o in task["options"]],
        "evidence": [list(e) for e in task["evidence"]],
        "gold_rank": list(task["gold_rank"]),
        "gold_best": task["gold_best"],
        "gold_drift": list(task["gold_drift"]),
        "contradictions": [list(p) for p in task["contradictions"]],
    }


def task_from_json(d: dict) -> dict:
    """Rebuild a task dict (same shape as gen_task output) from JSON."""
    return {
        "task_id": d["task_id"],
        "variant": d["variant"],
        "options": [CandidateOption(id=o["id"], description=o["description"],
                                    action=o["action"]) for o in d["options"]],
        "evidence": [tuple(e) for e in d["evidence"]],
        "gold_rank": list(d["gold_rank"]),
        "gold_best": d["gold_best"],
        "gold_drift": list(d["gold_drift"]),
        "contradictions": [tuple(p) for p in d["contradictions"]],
    }


def save(path: str, n_per_seed: int = HS_PER_SEED,
         seeds: list[int] = HS_SEEDS) -> dict:
    """Generate and write the high-stakes dataset file. Returns the doc."""
    tasks = generate(n_per_seed, seeds)
    doc = {
        "protocol": "decision-bench-v1",
        "dataset": "conflict-highstakes-10k",
        "variant": "conflicting",
        "n": len(tasks),
        "seeds": list(seeds),
        "n_per_seed": n_per_seed,
        "generator": ("evals.decision_bench.gen_task, conflicting variant "
                      "with W3a declared-contradiction extension and W9 "
                      "full-bipartite declaration"),
        "tasks": [task_to_json(t) for t in tasks],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    return doc


def load(path: str) -> list[dict]:
    """Load the high-stakes dataset; returns task dicts ready for task_to_inputs."""
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    assert doc.get("dataset") == "conflict-highstakes-10k", doc.get("dataset")
    assert doc.get("variant") == "conflicting", doc.get("variant")
    return [task_from_json(t) for t in doc["tasks"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="generate high-stakes conflict slice")
    ap.add_argument("--per-seed", type=int, default=HS_PER_SEED)
    ap.add_argument("--seeds", type=int, nargs="*", default=HS_SEEDS)
    ap.add_argument("--out", default="evals/data/conflict-highstakes-10k.json")
    args = ap.parse_args(argv)
    doc = save(args.out, n_per_seed=args.per_seed, seeds=args.seeds)
    print(f"wrote {args.out}: {doc['n']} tasks, seeds {doc['seeds']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
