"""recall — LongMemEval-S recall-half runner.

Protocol: for each item, haystack sessions become MemoryRecords (id =
session id, timestamp = haystack date, salience 0.5 default), the question
is the query, and the retriever ranks them. Metrics are retrieval metrics
— recall@k and MRR against gold_session_ids — NOT answer correctness.
That is deliberate: the recall half measures whether memory retrieves
the right sessions; answer extraction (QA mode with an LLM judge) plugs
in when the answer model is wired (OmniRoute keys pending).

v0.3 real. Run: python3 -m evals.recall [--limit N] [--k 1,5,10]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime

from mm.reflect import MemoryRecord

from evals.datasets import load_longmemeval_s
from evals.retrieval import (Retriever, BaselineRetriever,
                             ChunkedRetriever, DayWindowRetriever,
                             ValidWindowRetriever,
                             parse_lmeval_date)


def item_to_records(item) -> list[MemoryRecord]:
    records = []
    for sid, text, date in zip(item.session_ids, item.session_texts,
                               item.session_dates):
        records.append(MemoryRecord(
            id=sid, text=text, timestamp=parse_lmeval_date(date),
            source="episodic/longmemeval-s", salience=0.5,
        ))
    return records


def recall_at_k(ranked_ids: list[str], gold: list[str], k: int) -> float:
    return 1.0 if any(g in ranked_ids[:k] for g in gold) else 0.0


def reciprocal_rank(ranked_ids: list[str], gold: list[str]) -> float:
    for i, sid in enumerate(ranked_ids, start=1):
        if sid in set(gold):
            return 1.0 / i
    return 0.0


def run(retriever: Retriever, limit: int | None = None,
        ks: tuple[int, ...] = (1, 5, 10),
        per_type: bool = True) -> dict:
    """Run the recall protocol. Returns a report dict."""
    items = load_longmemeval_s(limit=limit)
    t0 = time.time()
    agg = {k: 0.0 for k in ks}
    mrr = 0.0
    by_type: dict[str, dict] = defaultdict(lambda: {"n": 0, "mrr": 0.0,
                                                   **{f"r{k}": 0.0 for k in ks}})
    n = 0
    per_item = []
    for item in items:
        records = item_to_records(item)
        now = parse_lmeval_date(item.question_date)
        ranked = retriever.rank(records, item.question, now=now)
        ranked_ids = [e.record.id for e in ranked]
        rr = reciprocal_rank(ranked_ids, item.gold_session_ids)
        mrr += rr
        row = {"question_id": item.question_id, "question_type": item.question_type,
               "rr": round(rr, 4),
               "gold_rank": next((i + 1 for i, sid in enumerate(ranked_ids)
                                  if sid in set(item.gold_session_ids)), None)}
        for k in ks:
            r = recall_at_k(ranked_ids, item.gold_session_ids, k)
            agg[k] += r
            row[f"recall@{k}"] = r
            by_type[item.question_type][f"r{k}"] += r
        by_type[item.question_type]["n"] += 1
        by_type[item.question_type]["mrr"] += rr
        per_item.append(row)
        n += 1
    report = {
        "protocol": "longmemeval-s-recall",
        "retriever": retriever.name,
        "n_items": n,
        "elapsed_s": round(time.time() - t0, 1),
        "recall@k": {str(k): round(agg[k] / n, 4) for k in ks},
        "mrr": round(mrr / n, 4),
        "by_question_type": {
            qt: {"n": v["n"], "mrr": round(v["mrr"] / v["n"], 4),
                 **{f"recall@{k}": round(v[f"r{k}"] / v["n"], 4) for k in ks}}
            for qt, v in sorted(by_type.items())
        } if per_type else {},
        "items": per_item,
        "note": ("Retrieval metrics only (did the gold session rank?). "
                 "The baseline-tfidf retriever is the harness's own "
                 "reference — its numbers are the floor mm.temporal must "
                 "beat once implemented. QA-mode answer correctness with "
                 "an LLM judge plugs in when the answer model is wired."),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LongMemEval-S recall runner")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--k", default="1,5,10")
    ap.add_argument("--retriever", default="baseline",
                    choices=["baseline", "chunked", "windowed",
                             "instantwindow", "daywindow"],
                    help="harness retriever to measure (B1, 2026-10-20; "
                         "instantwindow = B2 valid-window chunked at "
                         "instant precision, Wave 2 - 'windowed' is its "
                         "deprecated alias, kept so Wave 2 commands "
                         "still run; daywindow = the same window at "
                         "day precision, granularity follow-up. Per "
                         "the incharge's ruling both precisions stay "
                         "explicitly named arms - neither is a default)")
    ap.add_argument("--out", default=None, help="write JSON report here")
    args = ap.parse_args(argv)
    ks = tuple(int(x) for x in args.k.split(","))
    retriever = {"baseline": BaselineRetriever,
                 "chunked": ChunkedRetriever,
                 "windowed": ValidWindowRetriever,
                 "instantwindow": ValidWindowRetriever,
                 "daywindow": DayWindowRetriever}[args.retriever]()
    report = run(retriever, limit=args.limit, ks=ks)
    if isinstance(retriever, (ValidWindowRetriever, DayWindowRetriever)):
        report["records_filtered_by_window"] = retriever.n_filtered
    text = json.dumps(report, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.out}")
    else:
        # print summary; full per-item detail goes to --out
        slim = {k: v for k, v in report.items() if k != "items"}
        print(json.dumps(slim, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
