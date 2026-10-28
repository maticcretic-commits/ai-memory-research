"""W10 test: the 10,000-task high-stakes conflict slice for gate (d).

Covers the gate-(d) sizing gap (W6/W7 follow-up): ~6.6k-13k high-stakes
tasks are needed for 80% power on the one-sided 95% upper CB < +2pp
excess-error margin. The 63-task bench slice and the 120-task held-out
set are orders of magnitude too small, so Phase-2 gate (d) gets 10,000
independently sampled conflicting tasks (seeds 1000-1009, ids hs00000+).

  - the dataset file holds exactly 10,000 tasks, all variant="conflicting";
  - every task declares >= 1 contradiction (full-bipartite, W9);
  - regenerating seeds 1000/1005/1009 reproduces the file's tasks exactly
    (determinism + independence from the main bench and the held-out set);
  - task ids do not collide with the t* or hc* namespaces;
  - monitor sanity spot-check: 200 sampled tasks all read M>0 at
    stakes="high".

Run:  python3 tests/test_highstakes_slice.py   (from the repo root)
"""

import json
import sys

sys.path.insert(0, ".")

from evals import highstakes_slice as hs
from evals import decision_bench as db
from mm.resolver import monitor

DATA = "evals/data/conflict-highstakes-10k.json"
SPOT_SEEDS = (1000, 1005, 1009)


def main() -> None:
    # 1. File: exactly 10,000 tasks, all conflicting; header sane.
    with open(DATA, encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["dataset"] == "conflict-highstakes-10k", doc.get("dataset")
    assert doc["n"] == 10000 and len(doc["tasks"]) == 10000, doc.get("n")
    assert doc["seeds"] == list(range(1000, 1010)), doc.get("seeds")
    assert doc["variant"] == "conflicting"
    tasks = [hs.task_from_json(t) for t in doc["tasks"]]
    assert all(t["variant"] == "conflicting" for t in tasks)
    print("file OK: 10,000 tasks, all variant=conflicting")

    # 2. Every task declares >= 1 contradiction (W9 full-bipartite).
    for t in tasks:
        assert len(t["contradictions"]) >= 1, t["task_id"]
    n_pairs = sum(len(t["contradictions"]) for t in tasks)
    print(f"declarations OK: all tasks declare >= 1 pair "
          f"({n_pairs} total, mean {n_pairs / len(tasks):.1f}/task)")

    # 3. Determinism: regenerating 3 seeds reproduces the file exactly.
    for seed in SPOT_SEEDS:
        s_idx = seed - 1000
        block = slice(s_idx * 1000, (s_idx + 1) * 1000)
        regen = [hs.task_to_json(t) for t in hs.generate(1000, [seed])]
        assert regen == doc["tasks"][block], f"seed {seed} diverged"
    print(f"determinism OK: seeds {SPOT_SEEDS} regenerate file tasks exactly")

    # 4. Independence: hs* ids disjoint from the t* and hc* namespaces.
    hs_ids = {t["task_id"] for t in tasks}
    assert all(i.startswith("hs") for i in hs_ids)
    assert len(hs_ids) == 10000, "duplicate hs ids"
    main_ids = {f"t{i:04d}" for i in range(300)}
    hc_ids = {f"hc{i:04d}" for i in range(120)}
    assert not (hs_ids & main_ids), hs_ids & main_ids
    assert not (hs_ids & hc_ids), hs_ids & hc_ids
    print("independence OK: hs* namespace disjoint from t*/hc*")

    # 5. Monitor sanity: 200-task spot-check, all M>0 at stakes="high".
    for t in tasks[::50]:  # 200 evenly spread tasks
        _, ranked, _ = db.task_to_inputs(t)
        r = monitor([re.record for re in ranked], stakes="high")
        assert r.contradiction_count >= 1 and r.score > 0.0, (t["task_id"], r)
    print("monitor OK: 200-task spot-check, all M>0 at stakes=high")

    print("\nALL HIGH-STAKES SLICE TESTS PASSED")


if __name__ == "__main__":
    main()
