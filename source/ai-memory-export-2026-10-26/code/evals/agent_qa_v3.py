"""agent_qa_v3 - end-to-end QA on LongMemEval-S, Wave 2 protocol.

Why v3 exists (Wave 1 record, benchmark-wave-record.md sec. 2):
v2's gated arm was INVALID as a comparison - with the gate in
its post-Round-2/3 state and no declared source path, every
session queued as an uncorroborated lone-source claim
(reproduced: admitted 0/53, store empty, answers all "not
specified"). v2's full arm stands as a budget-window
long-context reference (LLM-judge 0.179, n=58); it is NOT the
ungated arm of this protocol.

v3 protocol (same items, same pins, different reader + B5):
  - Sampling: stratified, first 10 items per question type
    (n=60) - identical to v2 (dataset is type-grouped).
  - Reader: ChunkedRetriever (B1) top-k for BOTH arms - the
    delta between arms isolates the write gate in QA exactly
    as the recall protocol isolates it in retrieval.
  - gated arm: sessions ingested through MemoryAgent.ingest
    with the B5 benchmark registration wired in (Benchmark
    Wave 2): corroboration satisfied by registration, every
    quality gate (P1-P3, G0-G7) still applies.
  - ungated arm: the same sessions, ungated, same retriever.
  - Answer + judge models: qa_client pins (gpt-6-luna both),
    unchanged from v2. Deterministic exact + contains always
    reported alongside the LLM judge; failures counted, never
    silent zeros.
  - Tripwire: before any LLM call, the first item is ingested
    alone; if the gated arm admits 0 records the run ABORTS
    and writes a blocked report instead of burning the sample
    on a starved arm (the v2 failure mode, made structural).

Checkpoint/resume per item (VM replacements kill long runs),
same discipline as v2.

Run:  python3 -m evals.agent_qa_v3 [--per-type 10] [--k 10]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import qa_client as qc
from evals.agent_qa import judge_row, stratified_items, summarize
from evals.agent_recall_pilot import run_arm_b
from evals.recall import item_to_records
from evals.retrieval import ChunkedRetriever, parse_lmeval_date

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")


def _texts_dates_chronological(item, top_ids):
    text_by_id = dict(zip(item.session_ids, item.session_texts))
    date_by_id = dict(zip(item.session_ids, item.session_dates))
    picked = [(date_by_id[i], text_by_id[i]) for i in top_ids
              if i in text_by_id]
    picked.sort(key=lambda p: parse_lmeval_date(p[0]))
    return [t for _, t in picked], [d for d, _ in picked]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=10)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    model = args.model or qc.DEFAULT_ANSWER_MODEL
    if not model or not qc.JUDGE_MODEL_PIN:
        print("ERROR: answer/judge model pins missing in qa_client.py")
        return 2

    items = stratified_items(args.per_type)
    retriever = ChunkedRetriever()
    ks = (1, 5, 10)
    out_path = args.out or (OUT + "agent-qa-v3-n60.json")
    t0 = time.time()

    # --- tripwire: the gated arm must be alive before we spend --
    probe = run_arm_b(items[0], retriever, ks,
                      benchmark_registered=True)
    if probe["n_admitted"] == 0:
        blocked = {
            "protocol": "longmemeval-s-qa-v3-stratified-chunked-b5",
            "status": "BLOCKED",
            "reason": ("tripwire: gated arm admitted 0 records on "
                       "the probe item with B5 registration on - "
                       "the v2 starvation failure mode; no LLM "
                       "calls were made"),
            "probe_verdicts": probe["verdicts"],
            "probe_reject_reasons": probe["reject_reasons"],
        }
        with open(out_path, "w") as f:
            json.dump(blocked, f, indent=2)
        print(json.dumps(blocked, indent=1))
        print("wrote", out_path)
        return 3
    print(f"tripwire ok: probe item admitted "
          f"{probe['n_admitted']}/{probe['n_total']}", flush=True)

    arms_rows: dict[str, list] = {"gated": [], "ungated": []}
    arms_failed: dict[str, int] = {"gated": 0, "ungated": 0}
    gated_stats: dict[str, dict] = {}
    resumed = False
    done_ids: set[str] = set()
    try:
        with open(out_path + ".partial.json") as f:
            prev = json.load(f)
        arms_rows = prev["rows"]
        arms_failed = {k: int(v) for k, v in
                       prev["arms_failed"].items()}
        gated_stats = prev.get("gated_stats", {})
        done_ids = {r["question_id"] for rows in arms_rows.values()
                    for r in rows}
        resumed = bool(done_ids)
        if resumed:
            print(f"resuming: {len(done_ids)} items already done",
                  flush=True)
    except (OSError, ValueError, KeyError):
        pass

    def checkpoint(done: int) -> None:
        partial = {"protocol": "longmemeval-s-qa-v3-stratified-chunked-b5",
                   "partial": True, "items_done": done,
                   "n_items": len(items),
                   "resumed_from_checkpoint": resumed,
                   "arms_failed": dict(arms_failed),
                   "gated_stats": gated_stats,
                   "rows": arms_rows}
        with open(out_path + ".partial.json", "w") as f:
            json.dump(partial, f, indent=2)

    new_done = 0
    for idx, item in enumerate(items, 1):
        if item.question_id in done_ids:
            continue
        now = parse_lmeval_date(item.question_date)
        # ungated arm: all sessions through the same reader
        records = item_to_records(item)
        ranked_u = retriever.rank(records, item.question, now=now)
        top_u = [e.record.id for e in ranked_u[:args.k]]
        # gated arm: B5-registered ingest, admitted records only
        b = run_arm_b(item, retriever, ks, benchmark_registered=True)
        top_g = b["ranked_ids"][:args.k]
        gated_stats[item.question_id] = {
            "n_admitted": b["n_admitted"], "n_total": b["n_total"],
            "verdicts": b["verdicts"]}
        for arm, top_ids in (("gated", top_g), ("ungated", top_u)):
            texts, dates = _texts_dates_chronological(item, top_ids)
            gold_in = any(g in top_ids
                          for g in item.gold_session_ids)
            try:
                pred = qc.answer(item.question, texts, model,
                                 dates=dates)
            except RuntimeError as e:
                print(f"FAIL {arm} {item.question_id}: {e}",
                      flush=True)
                arms_failed[arm] += 1
                continue
            arms_rows[arm].append(judge_row(item, pred, gold_in))
        new_done += 1
        checkpoint(len(done_ids) + new_done)
        if idx % 10 == 0:
            print(f"  {idx}/{len(items)} items ...", flush=True)

    adm = [s["n_admitted"] / max(1, s["n_total"])
           for s in gated_stats.values()]
    report = {
        "protocol": "longmemeval-s-qa-v3-stratified-chunked-b5",
        "dataset": "xiaowu0162/longmemeval-cleaned (pinned), S split",
        "sampling": f"stratified: first {args.per_type} items per "
                    "question type (dataset is type-grouped)",
        "n_items": len(items),
        "resumed_from_checkpoint": resumed,
        "answer_model": model,
        "judge_model": qc.JUDGE_MODEL_PIN,
        "reader": retriever.name,
        "topk": args.k,
        "arms": {arm: summarize(arms_rows[arm], arms_failed[arm])
                 for arm in arms_rows},
        "gold_in_topk_rate": {
            arm: (round(sum(r["gold_in_topk"] for r in rows)
                        / len(rows), 4) if rows else None)
            for arm, rows in arms_rows.items()},
        "gated_admission_rate_mean": round(sum(adm) / len(adm), 4)
            if adm else None,
        "elapsed_s": round(time.time() - t0, 1),
        "note": ("End-to-end QA subset. NOT the official "
                 "LongMemEval harness; judge+answer are the "
                 "pinned local model (gpt-6-luna) - compare with "
                 "published system numbers only with those "
                 "caveats. Both arms read via chunked retrieval "
                 "top-k; the delta isolates the write gate. The "
                 "gated arm ingests with the B5 benchmark "
                 "registration (corroboration by registration; "
                 "quality gates unchanged). v2's full arm "
                 "(budget-window reader, 0.179) is a different "
                 "reader and not this protocol's ungated arm."),
    }
    with open(out_path, "w") as f:
        json.dump({"report": report, "rows": arms_rows,
                   "gated_stats": gated_stats}, f, indent=2)
    try:
        import os
        os.remove(out_path + ".partial.json")
    except OSError:
        pass
    print(json.dumps(report, indent=1))
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
