"""decision_bench — the memory→decision benchmark (the milestone's own
contribution).

No public benchmark scores memory → ranked-option recommendation with
calibrated confidence, so v0.3 designs one. Construction:

  Task: an agent must pick among K options. Each task ships M evidence
  items; each item links to one option with a signed drift (strength ×
  valence). The GROUND-TRUTH ranking is by total signed drift per option —
  known by construction, never shown to the modules.

  The harness runs the REAL v0.3 pipeline on each task:
    MemoryRecords → RankedEvidence → mm.confidence.score_options (DDM +
    metacognition) → mm.decision.select (Soar preferences from scores)

  Metrics:
    - NDCG@K of the scored ranking vs ground truth
    - selection accuracy (top-1 == gold-best)
    - ECE of top-option confidence vs correctness (10 bins)
    - Brier score of top-option confidence
    - impasse rate on seeded near-tie tasks (a tie impasse is CORRECT there)

Task variants: standard (clear winner), conflicting (strong evidence both
ways), tie (two options within epsilon — gold answer is impasse), sparse
(too little evidence to cross — expects no-crossing / low confidence).

v0.4 W3-prep: the "conflicting" variant additionally declares explicit
provenance contradictions (`task["contradictions"]`, wired into
MemoryRecord.provenance.contradicts by task_to_inputs) so the Phase-1
conflict monitor reads M>0 on conflicting tasks. All other variants are
untouched — same seed still yields byte-identical evidence and gold.

v0.3 real. Run: python3 -m evals.decision_bench [--n 200] [--seed 7]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime

from mm.reflect import MemoryRecord
from mm.temporal import RankedEvidence
from mm.confidence import CandidateOption, score_options, CalibrationLog
from mm.decision import Candidate, Preference, select


# ---------------------------------------------------------------------------
# Task generation (seeded, ground truth by construction)
# ---------------------------------------------------------------------------

# |drift| below this is noise, not a declared contradiction. The generator
# forces conflicting-variant opposition at strength 0.7-1.0 × relevance
# 0.5-1.0, so genuine opposition clears this easily; near-zero drifts from
# the N(0, 0.15) jitter do not get declared as contradictions.
CONTRADICTION_DRIFT_MIN = 0.25


def _declared_contradictions(task_id: str,
                             evidence: list[tuple[str, int, float, float]]
                             ) -> list[tuple[str, str]]:
    """Declared provenance contradictions for a "conflicting" task.

    Pairs same-option evidence items with clearly opposing drift signs —
    the generator's own knowledge of which claims oppose each other, made
    explicit in provenance (the W1 monitor counts ONLY declared relations;
    valence opposition alone reads M=0).

    Deterministic WITHOUT consuming the shared rng: pairing is by sorted
    evidence id, so the main rng stream — and every other variant/task —
    is bit-identical to the pre-extension generator. Returns sorted
    (id_a, id_b) pairs with id_a < id_b, deduplicated. Declares the FULL
    bipartite product per option (W9): every positive-drift item paired
    with every negative-drift item, since each such pair is a genuine
    contradiction the monitor should count.

    Fallback: if no same-option opposing pair clears the drift threshold
    (possible in principle, vanishingly rare in practice), pair the
    strongest-positive-drift item with the strongest-negative-drift item
    overall, so every conflicting task declares >= 1 contradiction.
    """
    by_opt: dict[int, dict[str, list[str]]] = {}
    drift_of: dict[str, float] = {}
    for ev_id, opt_idx, _relevance, drift in evidence:
        drift_of[ev_id] = drift
        slot = by_opt.setdefault(opt_idx, {"pos": [], "neg": []})
        if drift > CONTRADICTION_DRIFT_MIN:
            slot["pos"].append(ev_id)
        elif drift < -CONTRADICTION_DRIFT_MIN:
            slot["neg"].append(ev_id)

    pairs: set[tuple[str, str]] = set()
    for opt_idx in sorted(by_opt):
        pos = sorted(by_opt[opt_idx]["pos"])
        neg = sorted(by_opt[opt_idx]["neg"])
        # Full bipartite product: every (positive, negative) pair with
        # clearly opposing drifts is a genuine contradiction. Zip-pairing
        # (W3a) declared only min(k, m) of the k*m pairs, systematically
        # understating M (W8 referee: recall 0.141). Precision is unaffected:
        # every bipartite pair clears the drift threshold by construction.
        for a in pos:
            for b in neg:
                pairs.add((a, b) if a < b else (b, a))

    if not pairs:
        # Fallback: strongest opposing claims in the whole task.
        pos_ids = sorted(e for e, d in drift_of.items() if d > 0)
        neg_ids = sorted(e for e, d in drift_of.items() if d < 0)
        if pos_ids and neg_ids:
            top_pos = max(pos_ids, key=lambda e: (drift_of[e], e))
            top_neg = min(neg_ids, key=lambda e: (drift_of[e], e))
            a, b = (top_pos, top_neg) if top_pos < top_neg else (top_neg, top_pos)
            pairs.add((a, b))

    return sorted(pairs)


def gen_task(rng: random.Random, task_id: str, variant: str = "standard") -> dict:
    """Build one decision task. Returns dict with options, evidence, gold."""
    k = rng.choice([3, 4, 5])
    options = [CandidateOption(id=f"opt{i}", description=f"option {i} of {task_id}",
                               action=f"do option {i}")
               for i in range(k)]
    m = k * rng.randint(4, 7)   # enough evidence per option to cross a bound
    evidence: list[tuple[str, int, float, float]] = []  # (ev_id, opt_idx, relevance, drift)
    for j in range(m):
        i = rng.randrange(k)
        relevance = rng.uniform(0.5, 1.0)
        strength = rng.uniform(0.5, 1.2)
        if variant == "sparse":
            strength *= 0.2    # weak signals: the bound should NOT cross
        valence = 1.0 if rng.random() < 0.72 else -1.0
        if variant == "conflicting" and j % 3 == 2:
            valence = -1.0     # heavy opposition mixed in
            strength = rng.uniform(0.7, 1.0)
        drift = relevance * strength * valence + rng.gauss(0, 0.15)
        evidence.append((f"{task_id}-e{j}", i, relevance, drift))

    def drift_sums(ev):
        sums = [0.0] * k
        for _, i, _, d in ev:
            sums[i] += d
        return sums

    if variant == "tie":
        # Force a genuine near-tie in the evidence itself: nudge the
        # runner-up's evidence until the top-two drift sums are within 0.05.
        for _ in range(20):
            sums = drift_sums(evidence)
            order = sorted(range(k), key=lambda i: sums[i], reverse=True)
            a, b = order[0], order[1]
            gap = sums[a] - sums[b]
            if gap <= 0.05:
                break
            nudge = gap * rng.uniform(0.85, 0.98)
            evidence.append((f"{task_id}-tie-nudge", b, 1.0, nudge))

    gold_drift = drift_sums(evidence)
    gold_rank = sorted(range(k), key=lambda i: gold_drift[i], reverse=True)
    gold_best = gold_rank[0]
    # Declared provenance contradictions — conflicting variant ONLY. Empty
    # for every other variant (their evidence/gold are byte-identical to
    # the pre-extension generator; no rng is consumed here).
    contradictions = (_declared_contradictions(task_id, evidence)
                      if variant == "conflicting" else [])
    return {"task_id": task_id, "variant": variant, "options": options,
            "evidence": evidence, "gold_rank": gold_rank,
            "gold_best": options[gold_best].id, "gold_drift": gold_drift,
            "contradictions": contradictions}


def gen_suite(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    variants = (["standard"] * 6 + ["conflicting"] * 2 + ["tie", "sparse"])
    return [gen_task(rng, f"t{i:04d}", rng.choice(variants)) for i in range(n)]


# ---------------------------------------------------------------------------
# Harness execution
# ---------------------------------------------------------------------------

def task_to_inputs(task: dict) -> tuple[list[CandidateOption], list[RankedEvidence], dict]:
    options = task["options"]
    ranked: list[RankedEvidence] = []
    link: dict[str, dict[str, float]] = {}  # ev_id -> {opt_id: relevance}
    by_id: dict[str, MemoryRecord] = {}
    for ev_id, opt_idx, relevance, drift in task["evidence"]:
        opt_id = options[opt_idx].id
        valence = 1.0 if drift >= 0 else -1.0
        score = min(1.0, abs(drift))
        record = MemoryRecord(id=ev_id, text=f"evidence {ev_id}",
                              timestamp=datetime.utcnow(), salience=0.5)
        by_id[ev_id] = record
        ranked.append(RankedEvidence(
            record=record, score=score, signals={"valence": valence},
        ))
        link.setdefault(ev_id, {})[opt_id] = relevance
    # Wire declared contradictions into provenance, bidirectionally. The
    # monitor dedupes unordered pairs, so both-directions declarations
    # count once; self-references cannot occur (pairs hold distinct ids)
    # and dangling refs are skipped defensively.
    for a_id, b_id in task.get("contradictions", []):
        ra, rb = by_id.get(a_id), by_id.get(b_id)
        if ra is None or rb is None or ra is rb:
            continue
        if b_id not in ra.provenance.contradicts:
            ra.provenance.contradicts.append(b_id)
        if a_id not in rb.provenance.contradicts:
            rb.provenance.contradicts.append(a_id)
    return options, ranked, link


def run_task(task: dict, calibration: CalibrationLog | None = None,
             stakes: str = "medium", kappa: float | None = None,
             lambda_: float | None = None, temp: float | None = None) -> dict:
    options, ranked, link = task_to_inputs(task)
    opt_ids = [o.id for o in options]

    def link_fn(ev, opt):
        return link.get(ev.record.id, {}).get(opt.id, 0.0)

    kw = dict(stakes=stakes, link_fn=link_fn, calibration=calibration)
    if kappa is not None:
        kw["kappa"] = kappa
    if lambda_ is not None:
        kw["lambda_"] = lambda_
    if temp is not None:
        kw["temp"] = temp
    scored = score_options(options, ranked, **kw)
    ranking = [s.option.id for s in scored if not s.pruned_by_constraint]
    top = scored[0]

    # Soar layer: preferences from the confidence ranking
    cands = [Candidate(id=o.id, description=o.description, action=o.action)
             for o in options]
    votes = []
    conf_by = {s.option.id: s.confidence for s in scored}
    for a, b in zip(ranking, ranking[1:]):
        votes.append(Preference(candidate_id=a, kind="better",
                                weight=round(conf_by[a], 3),
                                source_module="confidence",
                                reason=f"DDM confidence {conf_by[a]:.2f}"))
    decision = select(cands, votes)

    gold_rank_ids = [options[i].id for i in task["gold_rank"]]
    correct = top.option.id == task["gold_best"]
    if calibration is not None:
        calibration.record(top.confidence, correct)

    return {
        "task_id": task["task_id"], "variant": task["variant"],
        "ranking": ranking, "gold_rank": gold_rank_ids,
        "top_confidence": top.confidence, "correct": correct,
        "top_crossed": top.crossed,
        "impasse": decision.impasse.kind if decision.impasse else None,
        "selected": decision.selected_id,
        "tie_correct": (decision.impasse is not None and
                        decision.impasse.kind == "tie") if task["variant"] == "tie"
        else None,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def ndcg(ranked_ids: list[str], gold_ids: list[str], k: int | None = None) -> float:
    """NDCG with exponential gains — wrong top-1 is punished hard.

    Graded relevance rel = (len - position); gain = 2^rel - 1. A random
    ranking scores ~0.3-0.4 here (vs ~0.8 with linear gains), so the number
    carries real signal about top-of-list quality.
    """
    k = k or len(gold_ids)
    gold_pos = {oid: len(gold_ids) - i for i, oid in enumerate(gold_ids)}
    gain = {oid: 2 ** rel - 1 for oid, rel in gold_pos.items()}
    dcg = sum(gain.get(oid, 0) / math.log2(i + 2)
              for i, oid in enumerate(ranked_ids[:k]))
    ideal = sorted(gain.values(), reverse=True)
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal[:k]))
    return dcg / idcg if idcg else 0.0


def ece(pairs: list[tuple[float, bool]], n_bins: int = 10) -> dict:
    bins: list[list[bool]] = [[] for _ in range(n_bins)]
    confs: list[list[float]] = [[] for _ in range(n_bins)]
    for c, o in pairs:
        b = max(0, min(n_bins - 1, int(c * n_bins)))
        bins[b].append(o)
        confs[b].append(c)
    total = len(pairs) or 1
    err, detail = 0.0, []
    for b in range(n_bins):
        if not bins[b]:
            continue
        acc = sum(bins[b]) / len(bins[b])
        mc = sum(confs[b]) / len(confs[b])
        w = len(bins[b]) / total
        err += w * abs(acc - mc)
        detail.append({"bin": b, "n": len(bins[b]),
                       "mean_conf": round(mc, 3), "accuracy": round(acc, 3)})
    return {"ece": round(err, 4), "bins": detail}


def run(n: int = 200, seed: int = 7, stakes: str = "medium") -> dict:
    t0 = time.time()
    suite = gen_suite(n, seed)
    cal = CalibrationLog(min_samples=1)
    rows, pairs = [], []
    ndcgs, correct, crossed, tie_ok, tie_n = [], 0, 0, 0, 0
    by_variant: dict[str, dict] = {}
    for task in suite:
        r = run_task(task, calibration=cal, stakes=stakes)
        rows.append(r)
        pairs.append((r["top_confidence"], r["correct"]))
        ndcgs.append(ndcg(r["ranking"], r["gold_rank"]))
        correct += r["correct"]
        crossed += r["top_crossed"]
        v = by_variant.setdefault(task["variant"], {"n": 0, "ndcg": 0.0,
                                                    "acc": 0, "cross": 0,
                                                    "ece_pairs": []})
        v["n"] += 1
        v["ndcg"] += ndcgs[-1]
        v["acc"] += r["correct"]
        v["cross"] += r["top_crossed"]
        v["ece_pairs"].append((r["top_confidence"], r["correct"]))
        if task["variant"] == "tie":
            tie_n += 1
            tie_ok += bool(r["tie_correct"])
    brier = sum((c - o) ** 2 for c, o in pairs) / len(pairs)
    report = {
        "protocol": "decision-bench-v1",
        "n_tasks": n, "seed": seed, "stakes": stakes,
        "elapsed_s": round(time.time() - t0, 1),
        "ndcg_mean": round(sum(ndcgs) / len(ndcgs), 4),
        "selection_accuracy": round(correct / n, 4),
        "cross_rate": round(crossed / n, 4),
        "brier": round(brier, 4),
        "ece_overall": ece(pairs),
        "tie_impasse_rate": round(tie_ok / tie_n, 4) if tie_n else None,
        "by_variant": {
            v: {"n": d["n"], "ndcg": round(d["ndcg"] / d["n"], 4),
                "accuracy": round(d["acc"] / d["n"], 4),
                "cross_rate": round(d["cross"] / d["n"], 4),
                "ece": ece(d["ece_pairs"])["ece"]}
            for v, d in sorted(by_variant.items())
        },
        "tasks": rows,
        "note": ("Synthetic benchmark with ground truth by construction: the "
                 "gold ranking is the evidence-drift order, which the modules "
                 "never see. NDCG (exponential gains)/accuracy measure ranking "
                 "quality; ECE/Brier measure confidence calibration. "
                 "cross_rate: fraction of tasks where the top option's "
                 "evidence crossed the DDM bound — low cross_rate means the "
                 "bound is miscalibrated for the evidence scale, and "
                 "everything degrades to the 0.35 undecided prior. "
                 "tie_impasse_rate: seeded near-ties SHOULD end in a tie "
                 "impasse — that is the correct behavior there, not a miss."),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="memory→decision benchmark")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--stakes", default="medium",
                    choices=["low", "medium", "high"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    report = run(n=args.n, seed=args.seed, stakes=args.stakes)
    text = json.dumps(report, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.out}")
    slim = {k: v for k, v in report.items() if k != "tasks"}
    print(json.dumps(slim, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
