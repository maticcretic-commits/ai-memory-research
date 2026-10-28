"""conflict-heldout-120 — independently sampled held-out conflict slice.

ChatGPT flag #1 (W2 gate criteria): the decision bench's 63-task conflict
slice is too small for narrow calibration/safety claims. This module
generates 120 NEW conflicting tasks under a different seed (99), saved as
a standalone dataset so Phase-2 gate measurements can supplement the main
bench.

Generation uses the same conflicting-variant generator (with the W3a
declared-contradiction extension) as the main bench — only the seed and the
task-id namespace differ. Independently sampled: seed 99, ids hc0000+,
never overlapping the seed-7 main bench.

Run:  python3 -m evals.conflict_heldout --out evals/data/conflict-heldout-120.json
      (from the repo root)
"""

from __future__ import annotations

import argparse
import json
import sys

import random

from evals import decision_bench as db
from mm.confidence import CandidateOption

HELDOUT_SEED = 99
HELDOUT_N = 120
HELDOUT_ID_PREFIX = "hc"


def generate(n: int = HELDOUT_N, seed: int = HELDOUT_SEED) -> list[dict]:
    """Generate n conflicting tasks under an independent seed."""
    rng = random.Random(seed)
    return [db.gen_task(rng, f"{HELDOUT_ID_PREFIX}{i:04d}", "conflicting")
            for i in range(n)]


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


def save(path: str, n: int = HELDOUT_N, seed: int = HELDOUT_SEED) -> dict:
    """Generate and write the held-out dataset file. Returns the doc."""
    tasks = generate(n, seed)
    doc = {
        "protocol": "decision-bench-v1",
        "dataset": "conflict-heldout-120",
        "variant": "conflicting",
        "n": n,
        "seed": seed,
        "generator": ("evals.decision_bench.gen_task, conflicting variant "
                      "with W3a declared-contradiction extension"),
        "tasks": [task_to_json(t) for t in tasks],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    return doc


def load(path: str) -> list[dict]:
    """Load the held-out dataset; returns task dicts ready for task_to_inputs."""
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    assert doc.get("dataset") == "conflict-heldout-120", doc.get("dataset")
    assert doc.get("variant") == "conflicting", doc.get("variant")
    return [task_from_json(t) for t in doc["tasks"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="generate conflict held-out set")
    ap.add_argument("--n", type=int, default=HELDOUT_N)
    ap.add_argument("--seed", type=int, default=HELDOUT_SEED)
    ap.add_argument("--out", default="evals/data/conflict-heldout-120.json")
    args = ap.parse_args(argv)
    doc = save(args.out, n=args.n, seed=args.seed)
    print(f"wrote {args.out}: {doc['n']} tasks, seed {doc['seed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
