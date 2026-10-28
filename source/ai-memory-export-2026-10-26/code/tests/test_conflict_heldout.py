"""W5 test: the 120-task held-out conflict dataset.

Covers ChatGPT flag #1 (W2 gate criteria): the main bench's 63-task
conflict slice is too small for narrow calibration/safety claims, so
Phase-2 gates get 120 independently sampled conflicting tasks
(seed 99, ids hc0000+, never overlapping the seed-7 main bench).

  - the dataset file holds exactly 120 tasks, all variant="conflicting";
  - every task declares >= 1 contradiction and the monitor reads M>0;
  - regenerating from seed 99 reproduces the file's tasks exactly
    (determinism + independence from the main bench);
  - task ids do not collide with the main bench's namespace.

Run:  python3 tests/test_conflict_heldout.py   (from the repo root)
"""

import json
import sys

sys.path.insert(0, ".")

from evals import conflict_heldout as ch
from evals import decision_bench as db
from mm.resolver import monitor

DATA = "evals/data/conflict-heldout-120.json"


def main() -> None:
    # 1. File: exactly 120 tasks, all conflicting.
    tasks = ch.load(DATA)
    assert len(tasks) == 120, len(tasks)
    assert all(t["variant"] == "conflicting" for t in tasks)
    print("file OK: 120 tasks, all variant=conflicting")

    # 2. Every task declares >= 1 contradiction; the monitor reads M>0.
    for t in tasks:
        assert len(t["contradictions"]) >= 1, t["task_id"]
        _, ranked, _ = db.task_to_inputs(t)
        r = monitor([re.record for re in ranked], stakes="medium")
        assert r.contradiction_count >= 1 and r.score > 0.0, (t["task_id"], r)
    print("monitor OK: all 120 tasks declare contradictions, all M>0")

    # 3. Determinism + file fidelity: seed 99 regenerates the file's tasks.
    with open(DATA, encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["n"] == 120 and doc["seed"] == 99, (doc.get("n"), doc.get("seed"))
    regen = [ch.task_to_json(t) for t in ch.generate(120, 99)]
    assert regen == doc["tasks"], "regeneration diverged from saved file"
    again = [ch.task_to_json(t) for t in ch.generate(120, 99)]
    assert again == regen, "seed 99 not deterministic across runs"
    print("determinism OK: seed 99 regenerates the file's tasks exactly")

    # 4. Independence: no task-id overlap with the main bench namespace.
    main_ids = {t["task_id"] for t in db.gen_suite(300, seed=7)}
    held_ids = {t["task_id"] for t in tasks}
    assert not (main_ids & held_ids), main_ids & held_ids
    assert all(i.startswith("hc") for i in held_ids)
    print("independence OK: no id overlap with the seed-7 main bench")

    print("\nALL CONFLICT-HELDOUT TESTS PASSED")


if __name__ == "__main__":
    main()
