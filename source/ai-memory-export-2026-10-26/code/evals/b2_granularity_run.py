"""b2_granularity_run - B2 window granularity follow-up driver.

Runs the preregistered three-arm measurement (chunked /
instant window / day window) over the full LongMemEval-S
recall protocol in ONE session on ONE code state, plus a
predicate pass that counts filtered records and filtered
GOLD sessions per window precision and audits every gold
record the day window filters (its start day must be after
its question day - anything else trips the preregistration's
STOP condition).

Preregistration: hidden_files/implementation/
b2-granularity-preregistration.md (goal workspace).

Run: python3 -m evals.b2_granularity_run
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.episodic import valid_at_day, valid_at_instant

from evals.datasets import load_longmemeval_s
from evals.recall import item_to_records, run
from evals.retrieval import (ChunkedRetriever, DayWindowRetriever,
                             ValidWindowRetriever, parse_lmeval_date)

OUT_DIR = os.path.join(os.path.dirname(__file__), "reports")


def predicate_pass() -> dict:
    """Count filtered records / gold per window precision and
    audit the day window's filtered gold."""
    items = load_longmemeval_s()
    tot_rec = tot_gold = 0
    arms = {"instant": {"rec": 0, "gold": 0, "gold_by_type": {}},
            "day": {"rec": 0, "gold": 0, "gold_by_type": {}}}
    day_gold_audit = []
    for item in items:
        records = item_to_records(item)
        now = parse_lmeval_date(item.question_date)
        gold = set(item.gold_session_ids)
        tot_rec += len(records)
        tot_gold += len(gold)
        for name, pred in (("instant", valid_at_instant),
                           ("day", valid_at_day)):
            kept_out = [r for r in records if not pred(r, now)]
            arms[name]["rec"] += len(kept_out)
            g = [r for r in kept_out if r.id in gold]
            arms[name]["gold"] += len(g)
            if g:
                bt = arms[name]["gold_by_type"]
                bt[item.question_type] = bt.get(item.question_type, 0) + len(g)
            if name == "day":
                for r in g:
                    start = r.valid_at or r.timestamp
                    day_gold_audit.append({
                        "question_id": item.question_id,
                        "type": item.question_type,
                        "gold_id": r.id,
                        "start_day": start.date().isoformat(),
                        "question_day": now.date().isoformat(),
                        "genuinely_future": start.date() > now.date(),
                    })
    return {"total_records": tot_rec, "total_gold": tot_gold,
            "arms": arms, "day_gold_audit": day_gold_audit}


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    print("predicate pass ...", flush=True)
    pp = predicate_pass()
    print(json.dumps(pp, indent=1), flush=True)
    with open(os.path.join(OUT_DIR, "b2-granularity-filtered.json"),
              "w", encoding="utf-8") as f:
        json.dump(pp, f, indent=1)

    for label, retriever in (
            ("chunked", ChunkedRetriever()),
            ("instant", ValidWindowRetriever()),
            ("day", DayWindowRetriever())):
        print(f"arm {label} ...", flush=True)
        report = run(retriever)
        if hasattr(retriever, "n_filtered"):
            report["records_filtered_by_window"] = retriever.n_filtered
        path = os.path.join(OUT_DIR, f"b2-granularity-{label}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        slim = {k: v for k, v in report.items() if k != "items"}
        print(json.dumps(slim, indent=1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
