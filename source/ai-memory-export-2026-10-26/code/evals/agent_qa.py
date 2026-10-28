"""agent_qa - end-to-end QA on LongMemEval-S, two arms, same items.

v2 (2026-10-20, benchmark wave). v1 findings that forced the rewrite:
  - The dataset file is TYPE-GROUPED: the first 50 items are all
    single-session-user, so any "first N" subset measures one type.
    v2 defaults to a stratified sample: first 10 items of each of
    the 6 question types (n=60) from the full 500.
  - qa_client.build_answer_prompt deleted the question itself on
    over-cap haystacks (fixed in qa_client, 2026-10-20) and its
    900-char session cap truncated answer-bearing turns (raised to
    3000). v1 QA numbers are invalid artifacts; v2 supersedes them.

Arms (same items, same answer model, same pinned judge):
  - gated: sessions ingested through the agent's write gate
    (MemoryAgent.ingest, P1-P3 + G0-G7); the pilot's TF-IDF ranker
    ranks admitted records; the answer model sees only the top-k.
    This is our system end-to-end: gate -> store -> retrieve -> answer.
  - full: the answer model sees the item's sessions directly,
    subject to qa_client's prompt budget (header + question always
    kept; oldest sessions dropped first). A long-context reader
    reference point, NOT an official-harness number.

Judging follows EVAL_PLAN rules: deterministic exact + contains are
ALWAYS reported alongside the LLM judge (pinned in qa_client.py,
JUDGE_MODEL_PIN, 2026-10-20). A failed LLM call is counted as failed,
never as a silent zero; accuracies are over answered items, with the
failed count stated.

Run:  python3 -m evals.agent_qa [--per-type 10] [--k 10] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import qa_client as qc
from evals.agent_recall_pilot import run_arm_b
from evals.datasets import load_longmemeval_s
from evals.retrieval import BaselineRetriever

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")


def stratified_items(per_type: int):
    """First `per_type` items of each question type, dataset order."""
    items = load_longmemeval_s(limit=None)
    seen: dict[str, int] = {}
    picked = []
    for it in items:
        if seen.get(it.question_type, 0) < per_type:
            picked.append(it)
            seen[it.question_type] = seen.get(it.question_type, 0) + 1
    return picked


def judge_row(item, pred, gold_in_topk):
    fb = qc.judge_exact(item.answer, pred)
    verdict = qc.judge_llm(item.question, item.answer, pred,
                           qc.JUDGE_MODEL_PIN)
    return {"question_id": item.question_id, "type": item.question_type,
            "gold": item.answer, "pred": pred,
            "exact": fb["exact"], "contains": fb["contains"],
            "llm_judge": verdict, "gold_in_topk": gold_in_topk}


def summarize(rows, failed):
    n = len(rows)
    judged = [r for r in rows if r["llm_judge"] is not None]
    per_type: dict[str, dict] = {}
    for r in rows:
        t = per_type.setdefault(r["type"], {"n": 0, "judged": 0,
                                            "llm_correct": 0})
        t["n"] += 1
        if r["llm_judge"] is not None:
            t["judged"] += 1
            t["llm_correct"] += 1 if r["llm_judge"] else 0
    return {
        "n_answered": n, "n_answer_failed": failed,
        "exact_acc": round(sum(r["exact"] for r in rows) / n, 4)
            if n else None,
        "contains_acc": round(sum(r["contains"] for r in rows) / n, 4)
            if n else None,
        "llm_judge_acc": round(
            sum(r["llm_judge"] for r in judged) / len(judged), 4)
            if judged else None,
        "llm_judge_failed": n - len(judged),
        "per_type_llm_judge": {
            t: {"n": v["n"], "judged": v["judged"],
                "acc": round(v["llm_correct"] / v["judged"], 4)
                if v["judged"] else None}
            for t, v in sorted(per_type.items())
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-type", type=int, default=10,
                    help="stratified items per question type")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--model", default=None,
                    help="answer model (default: qa_client pin)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    model = args.model or qc.DEFAULT_ANSWER_MODEL
    if not model or not qc.JUDGE_MODEL_PIN:
        print("ERROR: answer/judge model pins missing in qa_client.py")
        return 2

    items = stratified_items(args.per_type)
    retriever = BaselineRetriever()
    ks = (1, 5, 10)
    arms_rows: dict[str, list] = {"gated": [], "full": []}
    arms_failed: dict[str, int] = {"gated": 0, "full": 0}
    t0 = time.time()
    out_path = args.out or (OUT + "agent-qa-v2-n60.json")

    # Resume: VM replacements kill long runs. If a checkpoint partial
    # exists, seed rows/failures from it and skip finished items.
    resumed = False
    done_ids: set[str] = set()
    try:
        with open(out_path + ".partial.json") as f:
            prev = json.load(f)
        arms_rows = prev["rows"]
        arms_failed = {k: int(v) for k, v in
                       prev["arms_failed"].items()}
        done_ids = {r["question_id"] for rows in arms_rows.values()
                    for r in rows}
        resumed = bool(done_ids)
        if resumed:
            print(f"resuming: {len(done_ids)} items already done",
                  flush=True)
    except (OSError, ValueError, KeyError):
        pass

    def checkpoint(done: int) -> None:
        # VM replacements kill long runs and /tmp logs; write rows-so-far
        # after every item so a killed run still leaves evidence.
        partial = {"protocol": "longmemeval-s-qa-v2-stratified-two-arm",
                   "partial": True, "items_done": done,
                   "n_items": len(items),
        "resumed_from_checkpoint": resumed,
                   "arms_failed": dict(arms_failed),
                   "rows": arms_rows}
        with open(out_path + ".partial.json", "w") as f:
            json.dump(partial, f, indent=2)
    new_done = 0
    for idx, item in enumerate(items, 1):
        if item.question_id in done_ids:
            continue
        text_by_id = dict(zip(item.session_ids, item.session_texts))
        date_by_id = dict(zip(item.session_ids, item.session_dates))
        # gated arm: one ingest per item, reused for the answer
        b = run_arm_b(item, retriever, ks)
        top_ids = b["ranked_ids"][:args.k]
        g_texts = [text_by_id[i] for i in top_ids if i in text_by_id]
        g_dates = [date_by_id[i] for i in top_ids if i in date_by_id]
        gold_in = any(g in top_ids for g in item.gold_session_ids)
        for arm, texts, dates, gin in (
                ("gated", g_texts, g_dates, gold_in),
                ("full", item.session_texts, item.session_dates, True)):
            try:
                pred = qc.answer(item.question, texts, model, dates=dates)
            except RuntimeError as e:
                print(f"FAIL {arm} {item.question_id}: {e}", flush=True)
                arms_failed[arm] += 1
                continue
            arms_rows[arm].append(judge_row(item, pred, gin))
        new_done += 1
        checkpoint(len(done_ids) + new_done)
        if idx % 10 == 0:
            print(f"  {idx}/{len(items)} items ...", flush=True)

    report = {
        "protocol": "longmemeval-s-qa-v2-stratified-two-arm",
        "dataset": "xiaowu0162/longmemeval-cleaned (pinned), S split",
        "sampling": f"stratified: first {args.per_type} items per "
                    "question type (dataset is type-grouped; first-N "
                    "would be single-type)",
        "n_items": len(items),
        "resumed_from_checkpoint": resumed,
        "answer_model": model,
        "judge_model": qc.JUDGE_MODEL_PIN,
        "topk_gated": args.k,
        "arms": {arm: summarize(arms_rows[arm], arms_failed[arm])
                 for arm in arms_rows},
        "gated_gold_in_topk_rate": round(
            sum(r["gold_in_topk"] for r in arms_rows["gated"])
            / len(arms_rows["gated"]), 4) if arms_rows["gated"] else None,
        "elapsed_s": round(time.time() - t0, 1),
        "note": ("End-to-end QA subset. NOT the official LongMemEval "
                 "harness; judge+answer are the pinned local model "
                 "(gpt-6-luna), not GPT-4o/GPT-4o-mini - compare with "
                 "published system numbers only with those caveats. "
                 "Full arm is budget-limited by qa_client (question "
                 "always kept, oldest sessions dropped first)."),
    }
    path = out_path
    with open(path, "w") as f:
        json.dump({"report": report, "rows": arms_rows}, f, indent=2)
    try:
        import os
        os.remove(out_path + ".partial.json")
    except OSError:
        pass
    print(json.dumps(report, indent=1))
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
