"""Referee-40 recompute test (W8).

Loads evals/data/referee-40.json — the independent check set for the v0.4
Phase-1 conflict monitor — and recomputes precision/recall/false-negative
rate from the stored blind labels, declared pairs, and per-pair
adjudication. Asserts the recomputed values match the recorded metrics.

The labels were applied BLIND (evidence id/opt_idx/drift only, contradicts
fields unseen) under the criterion documented in the JSON; unblinding
happened only for comparison. See hidden_files/implementation/W8 notes.
"""

import json
import os

DATA = os.path.join(os.path.dirname(__file__), "..", "evals", "data",
                    "referee-40.json")


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def recompute(doc):
    tp_strict = tp_lenient = n_declared = 0
    n_genuine = n_recalled = 0
    m0_tasks = m0_with_genuine = m0_pairs = 0
    for t in doc["tasks"]:
        declared = set(tuple(p) for p in t["declared_pairs"])
        n_declared += len(declared)
        for a in t["adjudication"]:
            assert tuple(a["pair"]) in declared, "adjudication outside declared"
            if a["verdict"] == "genuine":
                tp_strict += 1
                tp_lenient += 1
            elif a["verdict"] == "ambiguous":
                tp_lenient += 1
            else:
                assert a["verdict"] == "not-genuine", a["verdict"]
        for g in t["blind_genuine_pairs"]:
            n_genuine += 1
            if tuple(sorted(g["pair"])) in declared:
                n_recalled += 1
        if t["variant"] in ("standard", "sparse", "tie"):
            m0_tasks += 1
            if t["blind_genuine_pairs"]:
                m0_with_genuine += 1
            m0_pairs += len(t["blind_genuine_pairs"])
    return {
        "precision_strict": round(tp_strict / n_declared, 4),
        "precision_lenient": round(tp_lenient / n_declared, 4),
        "recall": round(n_recalled / n_genuine, 4),
        "n_declared": n_declared,
        "n_genuine": n_genuine,
        "n_recalled": n_recalled,
        "m0_tasks": m0_tasks,
        "m0_tasks_with_genuine": m0_with_genuine,
        "m0_task_fnr": round(m0_with_genuine / m0_tasks, 4),
        "m0_genuine_pairs_uncounted": m0_pairs,
    }


def test_referee_metrics_recompute():
    doc = load()
    assert len(doc["tasks"]) == 40, "referee set must hold 40 tasks"
    got = recompute(doc)
    for k, v in doc["metrics"].items():
        assert got[k] == v, f"metric {k}: recomputed {got[k]} != recorded {v}"


def test_referee_monitor_m_consistent():
    # Every task whose monitor read M>0 must have >=1 declared pair, and
    # every M=0 task must have zero declared pairs (monitor counts
    # declarations only).
    doc = load()
    for t in doc["tasks"]:
        m = t["monitor"]["M"] or 0
        n_decl = len(t["declared_pairs"])
        if m > 0:
            assert n_decl > 0, t["task_id"]
        else:
            assert n_decl == 0, t["task_id"]


if __name__ == "__main__":
    test_referee_metrics_recompute()
    print("metrics recompute OK: precision/recall match recorded values")
    test_referee_monitor_m_consistent()
    print("monitor-M consistency OK")
    print("\nALL REFEREE TESTS PASSED")
