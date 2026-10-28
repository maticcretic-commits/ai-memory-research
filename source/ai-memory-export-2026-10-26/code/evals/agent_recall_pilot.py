"""agent_recall_pilot - first benchmark of the AGENT (not just the
retriever) against LongMemEval-S (thin pilot, n=50 of 500 items).

Two arms, same ranker (evals.retrieval.Retriever), different record
sets - the delta ISOLATES the write gate's effect on recall:

  Arm A (baseline): session records straight into the ranker.
  Arm B (agent-gated): sessions ingested through MemoryAgent.ingest()
      (P1-P3 + G0-G7 active); only admitted records reach the ranker.

Metrics are retrieval metrics (recall@k, MRR vs gold_session_ids),
NOT answer correctness - same protocol as evals/recall.py. Reported
as measured with sample sizes; the admission rate is part of the
result, not a footnote.

Run:  python3 -m evals.agent_recall_pilot [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals.datasets import load_longmemeval_s
from evals.recall import item_to_records, recall_at_k, reciprocal_rank
from evals.retrieval import (BaselineRetriever, ChunkedRetriever,
                             parse_lmeval_date)
from mm.agent import MemoryAgent
from mm.source_trust import SourceTrustRegistry
from mm.storage import SQLiteStore
from mm.write_gate import WriteGate

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")

# B5 (Benchmark Wave 2): the harness files every session under
# owner "" / source "episodic/longmemeval-s" (see
# evals.recall.item_to_records). Registration declares exactly
# that identity as the benchmark corpus ingest path.
BENCHMARK_DATASET = "xiaowu0162/longmemeval-cleaned (pinned), S split"
BENCHMARK_HARNESS = "evals benchmark harness (B5 registration)"


def benchmark_registry() -> SourceTrustRegistry:
    """A fresh in-memory registry carrying the B5 benchmark
    registration for the harness's filing identity. Per-run and
    in-memory only: nothing is registered in any production
    store, and SQLiteStore's default gate (no registry wired)
    is untouched - this replaces the gate only on the harness's
    own throwaway store."""
    reg = SourceTrustRegistry()
    reg.register_benchmark_source(
        "", "episodic/longmemeval-s",
        dataset=BENCHMARK_DATASET, harness=BENCHMARK_HARNESS)
    return reg


def run_arm_b(item, retriever, ks,
              benchmark_registered: bool = False) -> dict:
    """Ingest the item's sessions through the agent's write gate; rank
    only what the gate admitted.

    benchmark_registered=True wires a B5-registered source-trust
    registry into the gate (Benchmark Wave 2): the corpus is a
    declared ingest path, so G5b/G5c corroboration is satisfied
    by registration while every quality gate (P1-P3, G0-G7)
    applies unchanged. Without it, today's gate queues every
    lone-source session (Wave 1's invalidated QA arm)."""
    tdir = tempfile.mkdtemp(prefix="recall-pilot-")
    store = SQLiteStore(f"{tdir}/memory.db")
    if benchmark_registered:
        store.gate = WriteGate(trust_registry=benchmark_registry())
    agent = MemoryAgent(store, calibration_path=f"{tdir}/calibration.json")
    records = item_to_records(item)
    admitted = []
    verdicts: dict[str, int] = {}
    reject_reasons: dict[str, int] = {}
    seen_ids: set[str] = set()
    for rec in records:
        # Honest production typing: a chat session IS an episodic
        # record of directly observed conversation history. Without
        # this the retention/epistemic gates (not the P-gates under
        # test) queue everything and the pilot measures nothing.
        rec.type = "episodic"
        rec.epistemic_tier = "observed"
        if rec.id in seen_ids:
            # Dataset quirk: the same session id twice in one item.
            # The seal refuses re-insertion (correct); a production
            # ingest loop skips, counts, and continues.
            verdicts["sealed-duplicate-skip"] = verdicts.get(
                "sealed-duplicate-skip", 0) + 1
            continue
        seen_ids.add(rec.id)
        try:
            out = agent.ingest(rec)
        except Exception as e:
            verdicts[f"ingest-error:{type(e).__name__}"] = verdicts.get(
                f"ingest-error:{type(e).__name__}", 0) + 1
            continue
        verdicts[out["verdict"]] = verdicts.get(out["verdict"], 0) + 1
        if out["verdict"] == "rejected":
            for reason in out.get("reasons", [])[:1]:
                key = reason[:60]
                reject_reasons[key] = reject_reasons.get(key, 0) + 1
        if out["verdict"] == "admitted":
            admitted.append(rec)
    now = parse_lmeval_date(item.question_date)
    ranked = retriever.rank(admitted, item.question, now=now)
    ranked_ids = [e.record.id for e in ranked]
    return {"ranked_ids": ranked_ids, "verdicts": verdicts,
            "reject_reasons": reject_reasons,
            "benchmark_registered": benchmark_registered,
            "n_admitted": len(admitted), "n_total": len(records)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--retriever", default="baseline",
                    choices=["baseline", "chunked"],
                    help="ranker for both arms (B1 chunked, Wave 1)")
    ap.add_argument("--registered", action="store_true",
                    help="B5: wire the benchmark registration into "
                         "the gated arm's gate (Benchmark Wave 2)")
    ap.add_argument("--out", default=None,
                    help="output JSON path (default: OUT/agent-recall-pilot1.json)")
    args = ap.parse_args(argv)
    ks = (1, 5, 10)
    items = load_longmemeval_s(limit=args.limit)
    retriever = (ChunkedRetriever() if args.retriever == "chunked"
                 else BaselineRetriever())
    t0 = time.time()

    arms = {"baseline": {"r": {k: 0.0 for k in ks}, "mrr": 0.0},
            "agent_gated": {"r": {k: 0.0 for k in ks}, "mrr": 0.0}}
    admission_rates = []
    all_reject_reasons: dict[str, int] = {}
    per_type: dict[str, dict] = {}
    n = 0
    for item in items:
        records = item_to_records(item)
        now = parse_lmeval_date(item.question_date)
        # Arm A
        ranked_a = [e.record.id for e in
                    retriever.rank(records, item.question, now=now)]
        arms["baseline"]["mrr"] += reciprocal_rank(
            ranked_a, item.gold_session_ids)
        for k in ks:
            arms["baseline"]["r"][k] += recall_at_k(
                ranked_a, item.gold_session_ids, k)
        # Arm B
        b = run_arm_b(item, retriever, ks,
                      benchmark_registered=args.registered)
        arms["agent_gated"]["mrr"] += reciprocal_rank(
            b["ranked_ids"], item.gold_session_ids)
        for k in ks:
            arms["agent_gated"]["r"][k] += recall_at_k(
                b["ranked_ids"], item.gold_session_ids, k)
        # Per-type accumulation (both arms)
        t = per_type.setdefault(item.question_type, {
            "n": 0,
            "baseline": {"r": {k: 0.0 for k in ks}, "mrr": 0.0},
            "agent_gated": {"r": {k: 0.0 for k in ks}, "mrr": 0.0}})
        t["n"] += 1
        t["baseline"]["mrr"] += reciprocal_rank(
            ranked_a, item.gold_session_ids)
        t["agent_gated"]["mrr"] += reciprocal_rank(
            b["ranked_ids"], item.gold_session_ids)
        for k in ks:
            t["baseline"]["r"][k] += recall_at_k(
                ranked_a, item.gold_session_ids, k)
            t["agent_gated"]["r"][k] += recall_at_k(
                b["ranked_ids"], item.gold_session_ids, k)
        admission_rates.append(b["n_admitted"] / max(1, b["n_total"]))
        for k, v in b["reject_reasons"].items():
            all_reject_reasons[k] = all_reject_reasons.get(k, 0) + v
        n += 1
        if n % 10 == 0:
            print(f"  {n}/{len(items)} items ...", flush=True)

    report = {
        "protocol": "longmemeval-s-recall-agent-pilot",
        "dataset": "xiaowu0162/longmemeval-cleaned (pinned), S split",
        "retriever": retriever.name,
        "benchmark_registered": bool(args.registered),
        "n_items": n,
        "arms": {
            name: {
                f"recall@{k}": round(v["r"][k] / n, 4) for k in ks
            } | {"mrr": round(v["mrr"] / n, 4)}
            for name, v in arms.items()
        },
        "per_type": {
            tname: {
                "n": tv["n"],
                "baseline": {
                    f"recall@{k}": round(tv["baseline"]["r"][k] / tv["n"], 4)
                    for k in ks
                } | {"mrr": round(tv["baseline"]["mrr"] / tv["n"], 4)},
                "agent_gated": {
                    f"recall@{k}": round(tv["agent_gated"]["r"][k] / tv["n"], 4)
                    for k in ks
                } | {"mrr": round(tv["agent_gated"]["mrr"] / tv["n"], 4)},
            }
            for tname, tv in sorted(per_type.items())
        },
        "agent_gated_admission_rate_mean": round(
            sum(admission_rates) / n, 4),
        "agent_gated_reject_reasons": dict(sorted(
            all_reject_reasons.items(), key=lambda kv: -kv[1])[:8]),
        "elapsed_s": round(time.time() - t0, 1),
        "note": (f"n={n} of 500 LongMemEval-S items. Same ranker both "
                 "arms; the delta isolates the write gate (P1-P3 + "
                 "G0-G7). Retrieval metrics only. Sessions typed "
                 "episodic/observed (honest production typing); "
                 "rejections are the quality gates under test."),
    }
    path = args.out or (OUT + "agent-recall-pilot1.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=1))
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
