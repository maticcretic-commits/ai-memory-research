"""Benchmark-wave tests (2026-10-20): qa_client prompt budget +
robustness, agent_qa stratified sampling + summarize math.

All tests are LLM-free: they exercise the deterministic harness code
whose defects invalidated QA v1 (question deleted by budget trim;
int gold answers crashing the deterministic judge).

Run: python3 tests/test_benchmark_wave.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import qa_client as qc
from evals.agent_qa import stratified_items, summarize

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


# --- t1: question survives an over-cap haystack -------------------
big = ["filler text " * 1500 for _ in range(40)]  # ~720k chars total
p = qc.build_answer_prompt("What degree did I graduate with?", big,
                           dates=["2023/01/01"] * 40)
check("t1-question-kept-over-cap",
      "What degree did I graduate with?" in p)
check("t1-prompt-within-budget", len(p) <= qc._MAX_PROMPT_CHARS + 200,
      f"len={len(p)}")

# --- t2: newest survives, oldest dropped --------------------------
sessions = [f"OLDMARKER session {i} " + "x " * 2000 for i in range(30)]
sessions[-1] = "NEWMARKER final session " + "y " * 2000
p2 = qc.build_answer_prompt("Q?", sessions)
check("t2-newest-kept", "NEWMARKER" in p2)
check("t2-oldest-dropped", "OLDMARKER session 0 " not in p2)

# --- t3: small haystack passes through whole ----------------------
p3 = qc.build_answer_prompt("Q?", ["alpha", "beta", "gamma"])
check("t3-all-sessions-kept",
      all(s in p3 for s in ("alpha", "beta", "gamma")))

# --- t4: non-string gold answers do not crash the judges -----------
check("t4-int-gold-exact", qc.judge_exact(3, "3")["exact"] is True)
check("t4-int-gold-contains",
      qc.judge_exact(45, "about 45 minutes")["contains"] is True)
check("t4-norm-coerces", qc._norm(120) == "120")

# --- t5: stratified sampling is balanced ---------------------------
items = stratified_items(2)
from collections import Counter
counts = Counter(it.question_type for it in items)
check("t5-stratified-count", len(items) == 12, f"n={len(items)}")
check("t5-stratified-balanced",
      len(counts) == 6 and all(v == 2 for v in counts.values()),
      str(dict(counts)))

# --- t6: summarize math --------------------------------------------
rows = [
    {"question_id": "a", "type": "t1", "gold": "x", "pred": "x",
     "exact": True, "contains": True, "llm_judge": True,
     "gold_in_topk": True},
    {"question_id": "b", "type": "t1", "gold": "y", "pred": "z",
     "exact": False, "contains": False, "llm_judge": False,
     "gold_in_topk": False},
    {"question_id": "c", "type": "t2", "gold": "w", "pred": "w",
     "exact": True, "contains": True, "llm_judge": None,
     "gold_in_topk": True},
]
s = summarize(rows, failed=1)
check("t6-n", s["n_answered"] == 3 and s["n_answer_failed"] == 1)
check("t6-exact", abs(s["exact_acc"] - 2 / 3) < 1e-3)  # summarize rounds 4dp
check("t6-llm-over-judged", abs(s["llm_judge_acc"] - 0.5) < 1e-3)
check("t6-judge-failed-counted", s["llm_judge_failed"] == 1)
check("t6-per-type", s["per_type_llm_judge"]["t2"]["acc"] is None)

# --- t7: chunked retriever (B1) ------------------------------------
from datetime import datetime, timedelta

from evals.retrieval import ChunkedRetriever, _turn_chunks
from mm.reflect import MemoryRecord

turns = "\n".join(f"[user] turn {i} about topic{i}" for i in range(7))
ch = _turn_chunks(turns, window=3)
check("t7-chunk-count", len(ch) == 3, f"chunks={len(ch)}")
check("t7-chunk-fallback", _turn_chunks("no markers here") ==
      ["no markers here"])

now = datetime(2023, 6, 1)
filler = "\n".join(
    f"[user] garden note {i}: watering the tomato plants and roses"
    for i in range(11))
gold = MemoryRecord(
    id="gold", timestamp=now - timedelta(days=1), salience=0.5,
    text=(filler + "\n[user] I graduated with a degree in Business "
          "Administration"))
noise = MemoryRecord(
    id="noise", timestamp=now - timedelta(days=1), salience=0.5,
    text="[user] How do I sear a steak properly?\n"
         "[assistant] Heat the pan until it smokes, then add oil.")
q = "What degree did I graduate with?"
ranked = ChunkedRetriever().rank([noise, gold], q, now=now)
check("t7-chunked-ranks-gold-first", ranked[0].record.id == "gold",
      f"top={ranked[0].record.id}")
check("t7-contract", ranked[0].signals["lexical"] > 0)
# The mechanism claim: one relevant turn buried in a long session is
# diluted by whole-session TF-IDF and concentrated by chunking.
from evals.retrieval import BaselineRetriever
base = BaselineRetriever().rank([noise, gold], q, now=now)
base_gold = next(e for e in base if e.record.id == "gold")
chk_gold = next(e for e in ranked if e.record.id == "gold")
check("t7-chunk-beats-dilution",
      chk_gold.signals["lexical"] > base_gold.signals["lexical"],
      f"chunk={chk_gold.signals['lexical']:.3f} "
      f"base={base_gold.signals['lexical']:.3f}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
