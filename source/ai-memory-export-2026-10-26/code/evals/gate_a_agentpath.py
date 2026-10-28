"""Gate-(a) agent-path calibration characterization.
PREREGISTERED: hidden_files/implementation/
gate-a-agentpath-preregistration.md. One run, this analysis,
reported as measured. MEASUREMENT ONLY - no recalibration is
fitted or shipped; the isotonic harness is never invoked.

Arms (same 1000 tasks, paired): L = library bridge
(db.run_task defaults, the Phase-2 gate-(a) construction);
A0 = agent default; A1 = A0 + PT-A evidence_support;
A2 = A0 + trust_registry (PF-1 only); A3 = A1 + registry
(FD-3 + PF-1). Origin fixture: record j -> owner lane-{j%4},
source origin{j%4}/feed; origin1 ACTIVE flag, origin2
PERMANENT, origins 0/3 never flagged.

Run:  python3 -m evals.gate_a_agentpath   (from the repo root)
"""

from __future__ import annotations

import json
import sys
import tempfile
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import decision_bench as db
from mm import confidence as C
from mm.agent import MemoryAgent
from mm.decision import Candidate, Preference
from mm.reflect import MemoryRecord
from mm.source_trust import SourceTrustRegistry
from datetime import datetime
from mm.storage import SQLiteStore

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/gate-a-agentpath-run1.json")
SEEDS = (11000, 11001)
N_PER_SEED = 500
KAPPA, LAMBDA, TEMP = 0.25, 2.5, 1.0
ARMS = ("A0", "A1", "A2", "A3")


# ---------------------------------------------------------------------------
# Registry fixture (mirrors tests/test_precision_flag_discount.py)
# ---------------------------------------------------------------------------

def _probe(owner: str, source: str) -> MemoryRecord:
    return MemoryRecord(
        id=f"probe-{owner}-{source}",
        text=f"probe record for {owner} with concrete detail",
        timestamp=datetime.utcnow(), salience=0.5,
        owner=owner, source=source)


def build_registry() -> SourceTrustRegistry:
    reg = SourceTrustRegistry()
    # origin1: ACTIVE flag (a single poison event)
    reg.note_poison(_probe("lane-1", "origin1/feed"))
    # origin2: PERMANENT (poison, K=5 clean streak completes the
    # rehabilitation, poison again - journey cannot be reused)
    p2 = _probe("lane-2", "origin2/feed")
    reg.note_poison(p2)
    for _ in range(5):
        reg.note_admitted(p2)
    reg.note_poison(p2)
    return reg


def check_registry(reg: SourceTrustRegistry) -> dict:
    state = {}
    for j in range(4):
        st = reg.stats_for(f"lane-{j}", f"origin{j}/feed")
        state[f"origin{j}"] = {
            "permanent": bool(st.permanent),
            "flag_active": bool(SourceTrustRegistry.flag_active(st)),
            "poison": st.poison, "rehabilitations": st.rehabilitations,
        }
    assert state["origin1"]["flag_active"] \
        and not state["origin1"]["permanent"], state
    assert state["origin2"]["permanent"], state
    assert not state["origin0"]["flag_active"], state
    assert not state["origin3"]["flag_active"], state
    return state


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def ece_equal_mass(pairs: list[tuple[float, float]], n_bins: int = 10) -> float:
    if not pairs:
        return 0.0
    srt = sorted(pairs)
    n = len(srt)
    err = 0.0
    for b in range(n_bins):
        lo = (b * n) // n_bins
        hi = ((b + 1) * n) // n_bins
        if hi <= lo:
            continue
        chunk = srt[lo:hi]
        acc = sum(y for _, y in chunk) / len(chunk)
        mc = sum(c for c, _ in chunk) / len(chunk)
        err += (len(chunk) / n) * abs(acc - mc)
    return round(err, 4)


def slice_report(pairs: list[tuple[float, float]]) -> dict:
    """pairs = (confidence, correct 0/1)."""
    if not pairs:
        return {"n": 0}
    n = len(pairs)
    acc = sum(y for _, y in pairs) / n
    mc = sum(c for c, _ in pairs) / n
    brier = sum((c - y) ** 2 for c, y in pairs) / n
    prev_brier = sum((acc - y) ** 2 for _, y in pairs) / n
    return {
        "n": n,
        "accuracy": round(acc, 4),
        "mean_confidence": round(mc, 4),
        "signed_error": round(mc - acc, 4),
        "ece_equal_width": db.ece(pairs)["ece"],
        "ece_equal_mass": ece_equal_mass(pairs),
        "brier": round(brier, 4),
        "brier_prevalence_only": round(prev_brier, 4),
    }


def bin_table(pairs: list[tuple[float, float]]) -> list[dict]:
    out = []
    for b in range(10):
        lo, hi = b / 10, (b + 1) / 10
        chunk = [(c, y) for c, y in pairs
                 if (lo <= c < hi) or (b == 9 and c == 1.0)]
        if not chunk:
            continue
        out.append({
            "bin": b, "range": [lo, hi], "n": len(chunk),
            "mean_confidence": round(
                sum(c for c, _ in chunk) / len(chunk), 4),
            "accuracy": round(
                sum(y for _, y in chunk) / len(chunk), 4),
        })
    return out


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run() -> dict:
    t0 = time.time()
    reg = build_registry()
    reg_state = check_registry(reg)
    print(f"registry fixture verified: {reg_state}", flush=True)

    agents = {}
    for arm in ARMS:
        tdir = tempfile.mkdtemp(prefix=f"gatea-{arm}-")
        agents[arm] = MemoryAgent(
            SQLiteStore(f"{tdir}/memory.db"),
            calibration_path=f"{tdir}/calibration.json")

    rows: dict[str, list[dict]] = {arm: [] for arm in ARMS}
    bridge: list[dict] = []
    inv_violations: list[dict] = []

    for seed in SEEDS:
        for task in db.gen_suite(N_PER_SEED, seed):
            options, ranked, link = db.task_to_inputs(task)
            evidence = [e.record for e in ranked]
            # synthetic origin fixture, identical across arms
            for j, r in enumerate(evidence):
                r.owner = f"lane-{j % 4}"
                r.source = f"origin{j % 4}/feed"
            by_id = {r.id: r for r in evidence}
            support: dict[str, list] = {}
            for ev_id, opt_map in link.items():
                for opt_id in opt_map:
                    support.setdefault(opt_id, []).append(by_id[ev_id])

            def link_fn(ev, opt, link=link):
                return link.get(ev.record.id, {}).get(opt.id, 0.0)

            scored = C.score_options(
                options, ranked, stakes="medium", link_fn=link_fn,
                calibration=None, kappa=KAPPA, lambda_=LAMBDA,
                temp=TEMP)
            candidates = [Candidate(id=o.id, description=o.id,
                                    source="bench") for o in options]
            prefs = [Preference(candidate_id=s.option.id,
                                kind="better", weight=s.confidence,
                                reason="gate-a-cell",
                                source_module="bench")
                     for s in scored if not s.pruned_by_constraint]
            question = f"gate-a task {seed}-{task['task_id']}"

            # bridge arm L: library top-choice, Phase-2 construction
            lr = db.run_task(task)
            bridge.append({
                "seed": seed, "task_id": task["task_id"],
                "variant": task["variant"],
                "conf": lr["top_confidence"],
                "correct": 1.0 if lr["correct"] else 0.0,
            })

            for arm in ARMS:
                kw = {}
                if arm in ("A1", "A3"):
                    kw["evidence_support"] = support
                if arm in ("A2", "A3"):
                    kw["trust_registry"] = reg
                res = agents[arm].decide(
                    question, candidates, prefs, evidence, **kw)
                sel = res["selected_id"]
                correct = None
                if sel is not None:
                    correct = 1.0 if sel == task["gold_best"] else 0.0
                tie_correct = None
                if task["variant"] == "tie":
                    tie_correct = 1.0 if res["impasse"] == "tie" else 0.0
                rows[arm].append({
                    "seed": seed, "task_id": task["task_id"],
                    "variant": task["variant"],
                    "selected_id": sel, "impasse": res["impasse"],
                    "confidence": res["confidence"],
                    "conflict_score": res["conflict_score"],
                    "correct": correct, "tie_correct": tie_correct,
                    "tie_broken": res["tie_broken"],
                    "precision_discounted": res["precision_discounted"],
                    "precision": res["precision"],
                    "precision_effective": res["precision_effective"],
                })
                # structural invariant check (preregistered)
                conf = res["confidence"]
                if sel is not None and not (0.05 <= conf <= 0.70):
                    inv_violations.append(
                        {"arm": arm, "task": task["task_id"],
                         "kind": "selected-range", "conf": conf})
                if sel is None and not (0.05 <= conf <= 0.50):
                    inv_violations.append(
                        {"arm": arm, "task": task["task_id"],
                         "kind": "impasse-range", "conf": conf})
        print(f"  seed {seed} done ({time.time() - t0:.0f}s)",
              flush=True)

    # ---- aggregation -------------------------------------------------------
    def arm_report(arm: str) -> dict:
        rr = rows[arm]
        sel = [r for r in rr if r["selected_id"] is not None]
        pairs = [(r["confidence"], r["correct"]) for r in sel]
        all_pairs = [(r["confidence"],
                      r["correct"] if r["correct"] is not None else 0.0)
                     for r in rr]
        by_variant = {}
        for v in ("standard", "conflicting", "tie", "sparse"):
            vp = [(r["confidence"], r["correct"]) for r in sel
                  if r["variant"] == v]
            by_variant[v] = slice_report(vp)
        mon = [r for r in sel if r["conflict_score"] > 0]
        tie_rows = [r for r in rr if r["variant"] == "tie"]
        return {
            "n_tasks": len(rr),
            "n_selected": len(sel),
            "impasse_rate": round(1 - len(sel) / len(rr), 4),
            "impasse_rate_by_variant": {
                v: round(
                    1 - sum(1 for r in rr
                            if r["variant"] == v
                            and r["selected_id"] is not None)
                    / max(1, sum(1 for r in rr if r["variant"] == v)), 4)
                for v in ("standard", "conflicting", "tie", "sparse")},
            "tie_impasse_rate": round(
                sum(r["tie_correct"] for r in tie_rows) / len(tie_rows),
                4) if tie_rows else None,
            "primary_pairs": slice_report(pairs),
            "bin_table": bin_table(pairs),
            "conflict_variant_pairs": slice_report(
                [(r["confidence"], r["correct"]) for r in sel
                 if r["variant"] == "conflicting"]),
            "monitor_conflict_pairs": slice_report(
                [(r["confidence"], r["correct"]) for r in mon]),
            "by_variant_selected": by_variant,
            "all_tasks_pairs_secondary": slice_report(all_pairs),
            "impasse_confidence": {
                "n": len(rr) - len(sel),
                "mean": round(sum(r["confidence"] for r in rr
                                  if r["selected_id"] is None)
                              / max(1, len(rr) - len(sel)), 4),
                "min": min((r["confidence"] for r in rr
                            if r["selected_id"] is None), default=None),
                "max": max((r["confidence"] for r in rr
                            if r["selected_id"] is None), default=None),
            },
            "selected_confidence_range": [
                min((r["confidence"] for r in sel), default=None),
                max((r["confidence"] for r in sel), default=None)],
        }

    arms_out = {arm: arm_report(arm) for arm in ARMS}

    # bridge report (Phase-2 construction on the same tasks)
    bp = [(b["conf"], b["correct"]) for b in bridge]
    bridge_out = {
        "primary_pairs_all_tasks": slice_report(bp),
        "bin_table": bin_table(bp),
        "conflict_variant_pairs": slice_report(
            [(b["conf"], b["correct"]) for b in bridge
             if b["variant"] == "conflicting"]),
        "by_variant": {
            v: slice_report([(b["conf"], b["correct"]) for b in bridge
                             if b["variant"] == v])
            for v in ("standard", "conflicting", "tie", "sparse")},
    }

    # PF-1 shift audit: paired A0 vs A2
    a0 = {(r["seed"], r["task_id"]): r for r in rows["A0"]}
    a2 = {(r["seed"], r["task_id"]): r for r in rows["A2"]}
    deltas, deltas_disc, deltas_nodisc = [], [], []
    sel_changed = 0
    for key, r0 in a0.items():
        r2 = a2[key]
        d = r0["confidence"] - r2["confidence"]
        deltas.append(d)
        if r2["precision_discounted"]:
            deltas_disc.append(d)
        else:
            deltas_nodisc.append(d)
        if r0["selected_id"] != r2["selected_id"] \
                or r0["impasse"] != r2["impasse"]:
            sel_changed += 1
    deltas_sorted = sorted(deltas)

    def dstats(ds: list[float]) -> dict:
        if not ds:
            return {"n": 0}
        return {"n": len(ds), "mean": round(sum(ds) / len(ds), 4),
                "median": round(ds[len(ds) // 2], 4),
                "p90": round(ds[int(0.9 * (len(ds) - 1))], 4),
                "max": round(max(ds), 4),
                "share_moved": round(
                    sum(1 for d in ds if d > 1e-12) / len(ds), 4)}

    shift_out = {
        "all_tasks": dstats(deltas_sorted),
        "discounted_tasks": dstats(sorted(deltas_disc)),
        "nondiscounted_tasks": dstats(sorted(deltas_nodisc)),
        "selection_or_impasse_changed": sel_changed,
        "ece_A0_primary": arms_out["A0"]["primary_pairs"][
            "ece_equal_width"],
        "ece_A2_primary": arms_out["A2"]["primary_pairs"][
            "ece_equal_width"],
        "signed_error_A0": arms_out["A0"]["primary_pairs"][
            "signed_error"],
        "signed_error_A2": arms_out["A2"]["primary_pairs"][
            "signed_error"],
        "accuracy_A0": arms_out["A0"]["primary_pairs"]["accuracy"],
        "accuracy_A2": arms_out["A2"]["primary_pairs"]["accuracy"],
    }

    out = {
        "protocol": "gate-a-agentpath-v1",
        "seeds": list(SEEDS), "n_per_seed": N_PER_SEED,
        "cell": {"kappa": KAPPA, "lambda": LAMBDA, "temp": TEMP},
        "registry_fixture": reg_state,
        "elapsed_s": round(time.time() - t0, 1),
        "bridge_L": bridge_out,
        "arms": arms_out,
        "pf1_shift_audit": shift_out,
        "invariant_violations": inv_violations,
        "rows": rows, "bridge_rows": bridge,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {OUT}", flush=True)
    slim = {k: v for k, v in out.items()
            if k not in ("rows", "bridge_rows")}
    print(json.dumps(slim, indent=1), flush=True)
    return out


if __name__ == "__main__":
    run()
