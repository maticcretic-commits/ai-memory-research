"""test_harness.py — smoke tests for the v0.3 eval harness.

Covers: dataset registry, decision benchmark (small), recall runner
(small), NDCG/ECE metric sanity. The full 500-item recall and 300-task
decision runs live in evals/reports/, not in the test suite.

Run:  python3 tests/test_harness.py   (from the repo root)
"""

import json
import os
import sys

sys.path.insert(0, ".")

from evals import datasets, decision_bench as db
from evals import recall as rcl
from evals.retrieval import BaselineRetriever


def main() -> None:
    # 1. Registry: 5 datasets pinned, longmemeval-s cached on disk.
    reg = {d["key"]: d for d in datasets.list_datasets()}
    assert set(reg) == {"longmemeval-s", "locomo-mc10", "resilience",
                        "procedural", "privacy"}, set(reg)
    assert reg["longmemeval-s"]["license"] == "MIT"
    assert reg["longmemeval-s"]["cached"], "longmemeval-s not downloaded"
    assert "research only" in reg["locomo-mc10"]["license_note"].lower()
    print("registry OK: 5 datasets, longmemeval-s cached, locomo flagged research-only")

    # 2. Decision benchmark: small run, metrics in sane ranges.
    rep = db.run(n=30, seed=7)
    assert rep["protocol"] == "decision-bench-v1"
    assert 0.0 <= rep["ndcg_mean"] <= 1.0
    assert 0.0 <= rep["selection_accuracy"] <= 1.0
    assert 0.0 <= rep["cross_rate"] <= 1.0
    assert rep["ece_overall"]["ece"] >= 0.0
    # sparse variant must genuinely not cross (bound holds on weak evidence)
    sparse = rep["by_variant"].get("sparse", {})
    if sparse.get("n"):
        assert sparse["cross_rate"] == 0.0, sparse
    print(f"decision bench OK: n=30 ndcg={rep['ndcg_mean']} "
          f"acc={rep['selection_accuracy']} cross={rep['cross_rate']} "
          f"ece={rep['ece_overall']['ece']}")

    # 3. NDCG sanity: perfect ranking = 1.0, reversed is much lower.
    gold = ["a", "b", "c", "d"]
    assert db.ndcg(gold, gold) == 1.0
    rev = db.ndcg(list(reversed(gold)), gold)
    assert rev < 0.75, rev   # reversed must score clearly below perfect
    print(f"ndcg OK: perfect=1.0 reversed={rev:.3f}")

    # 4. Recall runner: 5 items, report shape + metric ranges.
    rrep = rcl.run(BaselineRetriever(), limit=5, ks=(1, 5))
    assert rrep["protocol"] == "longmemeval-s-recall"
    assert rrep["n_items"] == 5
    assert rrep["retriever"] == "baseline-tfidf"
    assert 0.0 <= rrep["mrr"] <= 1.0
    assert set(rrep["recall@k"]) == {"1", "5"}
    print(f"recall OK: n=5 mrr={rrep['mrr']} recall@1={rrep['recall@k']['1']}")

    # 5. The saved full-run reports exist and parse.
    for name in ("recall-baseline-2026-10-14.json",
                 "decision-bench-2026-10-14.json"):
        p = os.path.join("evals", "reports", name)
        assert os.path.exists(p), p
        json.load(open(p))
    print("reports OK: both full-run JSON reports present and valid")

    print("\nALL HARNESS TESTS PASSED")


if __name__ == "__main__":
    sys.exit(main())
