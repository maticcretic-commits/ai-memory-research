#!/usr/bin/env python3
"""run_evals.py — the memory-milestone eval harness runner.

v0.3 REAL (2026-10-14). Subcommands:

  list        dataset registry: pinned sets, licenses, cache state
  recall      LongMemEval-S recall half (retrieval metrics; no LLM needed)
  decision    the memory→decision benchmark (NDCG + calibration; no LLM needed)
  qa          full QA protocol (answer extraction + judge) — client
              implemented 2026-10-15 against OmniRoute (evals/qa_client.py);
              runs the day the free-provider keys land. Until then it prints
              the wiring contract and exits.

Run from the repo root:  python3 evals/run_evals.py <subcommand> [flags]
"""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, ".")


def cmd_list(_args) -> int:
    from evals.datasets import list_datasets
    for d in list_datasets():
        cached = "cached" if d["cached"] else "not cached"
        print(f"- {d['key']:14s} {d['repo']}")
        print(f"    license: {d['license']}" +
              (f"  *** {d['license_note']}" if d["license_note"] else ""))
        print(f"    role: {d['role']}")
        print(f"    state: {cached}" + (f" ({d['path']})" if d["cached"] else ""))
    return 0


def cmd_recall(args) -> int:
    from evals import recall as r
    from evals.retrieval import BaselineRetriever
    ks = tuple(int(x) for x in args.k.split(","))
    report = r.run(BaselineRetriever(), limit=args.limit, ks=ks)
    text = json.dumps(report, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.out}")
    slim = {k: v for k, v in report.items() if k != "items"}
    print(json.dumps(slim, indent=1))
    return 0


def cmd_decision(args) -> int:
    from evals import decision_bench as db
    report = db.run(n=args.n, seed=args.seed, stakes=args.stakes)
    text = json.dumps(report, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.out}")
    slim = {k: v for k, v in report.items() if k != "tasks"}
    print(json.dumps(slim, indent=1))
    return 0


_QA_CONTRACT = """\
qa mode: full LongMemEval-S QA protocol (answer extraction + judge).

Wiring status (2026-10-15): the answer/judge CLIENT is implemented
(evals/qa_client.py) against OmniRoute's local router. It needs:
  1. --model <id>      an answer model wired in OmniRoute (the five free
                       provider keys land -> wire-free-providers.sh)
  2. --llm            optional LLM judge; pass --judge-model <id> on the
                       first wired run, then PIN it in qa_client.py
                       (JUDGE_MODEL_PIN) — one judge per comparison series.
  3. Deterministic fallback judge (exact + contains) always runs and is
     always reported alongside any LLM-judge score — never instead of it.

Protocol: the answer model sees the FULL haystack (all sessions), not the
retrieved subset — this measures memory→answer, the sibling of the recall
half. A failed LLM call is reported as failed, never as a silent zero.
"""


def cmd_qa(args) -> int:
    from evals import qa_client as qc
    from evals.datasets import load_longmemeval_s

    if not args.model:
        print(_QA_CONTRACT)
        return 2

    items = load_longmemeval_s(limit=args.limit)
    judge_model = args.judge_model or qc.JUDGE_MODEL_PIN
    if args.llm and not judge_model:
        print("ERROR: --llm needs a judge model: pass --judge-model <id>.\n"
              "Then pin it: JUDGE_MODEL_PIN in evals/qa_client.py — "
              "one judge per comparison series, no mixing.")
        return 2

    results = []
    skipped = 0
    for it in items:
        try:
            pred = qc.answer(it.question, it.session_texts, args.model,
                             dates=it.session_dates)
        except RuntimeError as e:
            print(f"SKIP {it.question_id}: answer model failed: {e}")
            skipped += 1
            continue
        fb = qc.judge_exact(it.answer, pred)
        row = {"question_id": it.question_id, "type": it.question_type,
               "gold": it.answer, "pred": pred,
               "exact": fb["exact"], "contains": fb["contains"],
               "llm_judge": None}
        if args.llm:
            v = qc.judge_llm(it.question, it.answer, pred, judge_model)
            row["llm_judge"] = v  # None = judge call failed, not "wrong"
        results.append(row)

    n = len(results)
    report = {
        "n": n, "skipped": skipped, "answer_model": args.model,
        "judge_model": judge_model,
        "exact_acc": sum(r["exact"] for r in results) / n if n else None,
        "contains_acc": sum(r["contains"] for r in results) / n if n else None,
    }
    judged = [r for r in results if r["llm_judge"] is not None]
    if args.llm:
        report["llm_judge_acc"] = (
            sum(r["llm_judge"] for r in judged) / len(judged)
            if judged else None)
        report["llm_judge_failed"] = n - len(judged)
    text = json.dumps(report, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"report": report, "results": results}, f, indent=1)
        print(f"wrote {args.out}")
    print(text)
    if args.llm and qc.JUDGE_MODEL_PIN is None:
        print(f"\nPIN THIS JUDGE before comparing runs: "
              f"JUDGE_MODEL_PIN = {judge_model!r}  (evals/qa_client.py)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="memory-milestone eval harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="dataset registry")

    p = sub.add_parser("recall", help="LongMemEval-S recall half")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--k", default="1,5,10")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_recall)

    p = sub.add_parser("decision", help="memory→decision benchmark")
    p.add_argument("--n", type=int, default=200)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--stakes", default="medium",
                   choices=["low", "medium", "high"])
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_decision)

    p = sub.add_parser("qa", help="full QA protocol (wired via OmniRoute)")
    p.add_argument("--model", default=None,
                   help="answer model id in OmniRoute (required)")
    p.add_argument("--judge-model", default=None,
                   help="LLM judge model id (required with --llm)")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--llm", action="store_true",
                   help="also run the LLM judge (pin it after first run)")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_qa)

    args = ap.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(args)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
