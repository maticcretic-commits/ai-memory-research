"""calibration_fit — Phase-3 calibration harness (per-M-band temperature re-fit).

Frozen v0.5 scheme (Head decision 2026-10-19):
  Bands: M=0 | (0,0.50] | (0.50,0.70] | (0.70,1], with MIN_SAMPLES=30.
  A band below the floor does NOT get its own temperature — it falls back
  to the M>0 pooled curve (the data is bimodal: M=0 vs M>0.70; the middle
  bands are nearly empty on synthetic tasks). Every band's report states
  its count and whether its temperature was fitted or borrowed.
  The Phase-2 decision logic (kappa=0.25, lambda_=2.5) is NOT touched;
  only the post-hoc temperature changes.

Fit slice:  seed-7 decision bench (300 tasks, non-gate).  NEVER gate data.
Eval slice: conflict-heldout-120 (independent, measured ONCE here).
Do not re-fit or re-threshold on the eval slice.

Metrics: ECE overall + on conflict (M>0), top-choice Brier, FULL-VECTOR
Brier (multiclass, normalized over options — fixes the gate-(b)
methodology caveat), per-band Brier with counts, reliability data.
Targets (W2, unchanged): ECE <= 0.05 overall, <= 0.10 on conflict.
Rollback: one fix per identified cause, rerun once, then escalate.

Run:  python3 -m evals.calibration_fit  (from ~/workspace/ai-memory-milestone)
"""

from __future__ import annotations

import json
import math
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals import decision_bench as db
from evals import conflict_heldout as ch
from mm import confidence as C

MIN_SAMPLES = 30
BANDS = [("M=0", 0.0, 0.0), ("(0,0.50]", 0.0, 0.50),
         ("(0.50,0.70]", 0.50, 0.70), ("(0.70,1]", 0.70, 1.0)]

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")


def band_of(m: float) -> str:
    if m == 0.0:
        return "M=0"
    if m <= 0.50:
        return "(0,0.50]"
    if m <= 0.70:
        return "(0.50,0.70]"
    return "(0.70,1]"


def collect_pairs(tasks: list[dict],
                  cal_log: C.CalibrationLog | None = None) -> list[dict]:
    """Run the Phase-2 pipeline with temp=1 (no scaling), capture raw pairs."""
    rows = []
    for task in tasks:
        options, ranked, link = db.task_to_inputs(task)

        def link_fn(ev, opt, link=link):
            return link.get(ev.record.id, {}).get(opt.id, 0.0)

        # Monitor M (same call the pipeline makes internally).
        m = C._conflict_monitor([e.record for e in ranked],
                                stakes="medium").score
        scored = C.score_options(
            options, ranked, stakes="medium", link_fn=link_fn,
            calibration=cal_log,          # None = no-history operating point
            kappa=C.KAPPA, lambda_=C.LAMBDA, temp=1.0)
        # top-choice pair
        top = scored[0]
        # full-vector: normalize non-pruned confidences into a distribution
        vec = {s.option.id: s.confidence
               for s in scored if not s.pruned_by_constraint}
        tot = sum(vec.values()) or 1.0
        full = {k: v / tot for k, v in vec.items()}
        gold = task["gold_best"]
        rows.append({
            "task_id": task["task_id"],
            "M": round(m, 4),
            "band": band_of(m),
            "p_raw": top.confidence,          # temp=1 => adjusted pre-scaling
            "correct": top.option.id == gold,
            "gold_best": gold,
            "full_vec": full,
        })
    return rows


def apply_temp(p: float, t: float) -> float:
    return C.recalibrate(p, t)


def brier_top(pairs, tmap: dict) -> float:
    s = 0.0
    for r in pairs:
        p = apply_temp(r["p_raw"], tmap.get(r["band"], 1.0))
        s += (p - (1.0 if r["correct"] else 0.0)) ** 2
    return s / len(pairs) if pairs else 0.0


def brier_full(pairs, tmap: dict) -> float:
    """Multiclass Brier on the normalized option-confidence vector."""
    s, n = 0.0, 0
    for r in pairs:
        t = tmap.get(r["band"], 1.0)
        vec = {k: apply_temp(v, t) for k, v in r["full_vec"].items()}
        tot = sum(vec.values()) or 1.0
        vec = {k: v / tot for k, v in vec.items()}
        gold = r["gold_best"]
        s += sum(((vec.get(oid, 0.0) - (1.0 if oid == gold else 0.0)) ** 2)
                 for oid in set(vec) | {gold})
        n += 1
    return s / n if n else 0.0


def ece(pairs, tmap: dict, n_bins: int = 10) -> dict:
    bins: list[list[bool]] = [[] for _ in range(n_bins)]
    confs: list[list[float]] = [[] for _ in range(n_bins)]
    for r in pairs:
        c = apply_temp(r["p_raw"], tmap.get(r["band"], 1.0))
        b = max(0, min(n_bins - 1, int(c * n_bins)))
        bins[b].append(r["correct"])
        confs[b].append(c)
    total = len(pairs) or 1
    err, detail = 0.0, []
    for b in range(n_bins):
        if not bins[b]:
            continue
        acc = sum(bins[b]) / len(bins[b])
        mc = sum(confs[b]) / len(confs[b])
        err += (len(bins[b]) / total) * abs(acc - mc)
        detail.append({"bin": b, "n": len(bins[b]),
                       "mean_conf": round(mc, 3),
                       "accuracy": round(acc, 3)})
    return {"ece": round(err, 4), "n": len(pairs), "bins": detail}


def fit_temperatures(fit_rows: list[dict]) -> dict:
    """Grid-search T in [0.25, 6.0] per band minimizing top-choice Brier."""
    temps = [round(0.25 + 0.05 * i, 2) for i in range(116)]  # to 6.0
    by_band: dict[str, list[dict]] = {b[0]: [] for b in BANDS}
    for r in fit_rows:
        by_band[r["band"]].append(r)
    pooled_conflict = [r for r in fit_rows if r["M"] > 0]
    # Fit the pooled M>0 curve once (fallback for thin bands).
    pooled_t = min(temps, key=lambda t: sum(
        (apply_temp(r["p_raw"], t) - (1.0 if r["correct"] else 0.0)) ** 2
        for r in pooled_conflict) / max(1, len(pooled_conflict)))
    out: dict[str, dict] = {}
    for name, rows in by_band.items():
        if name == "M=0" and len(rows) >= MIN_SAMPLES:
            t = min(temps, key=lambda t: sum(
                (apply_temp(r["p_raw"], t) - (1.0 if r["correct"] else 0.0)) ** 2
                for r in rows) / len(rows))
            out[name] = {"T": t, "fitted": True, "n": len(rows)}
        elif name != "M=0" and len(rows) >= MIN_SAMPLES:
            t = min(temps, key=lambda t: sum(
                (apply_temp(r["p_raw"], t) - (1.0 if r["correct"] else 0.0)) ** 2
                for r in rows) / len(rows))
            out[name] = {"T": t, "fitted": True, "n": len(rows)}
        else:
            # Thin band -> borrow the M>0 pooled curve (declared fallback).
            out[name] = {"T": pooled_t, "fitted": False, "n": len(rows),
                         "borrowed_from": "M>0 pooled"}
    return out


def main() -> None:
    t0 = time.time()
    print("fit slice: seed-7 bench (300, non-gate) ...", flush=True)
    fit_tasks = db.gen_suite(300, 7)
    fit_rows = collect_pairs(fit_tasks)
    print("eval slice: conflict-heldout-120 (measured once) ...", flush=True)
    eval_rows = collect_pairs(ch.generate(120, 99))

    # --- Mode B: seeded metacognitive history (second identified cause) ---
    # The Phase-2 pipeline's metacognitive pass shrinks toward calibration
    # history ONLY when a CalibrationLog exists. Production ships with a
    # live log; eval with cal_log=None never engages shrinkage. Mode B
    # seeds the log from the FIT slice only (never eval) and re-fits.
    cal_log = C.CalibrationLog(min_samples=1)
    for r in fit_rows:
        cal_log.record(r["p_raw"], r["correct"])
    fit_rows_h = collect_pairs(fit_tasks, cal_log=cal_log)
    eval_rows_h = collect_pairs(ch.generate(120, 99), cal_log=cal_log)

    fit = fit_temperatures(fit_rows)
    tmap_fit = {b: v["T"] for b, v in fit.items()}
    base = {b: C.TEMP for b in tmap_fit}   # Phase-2 global T=2.0

    conflict_eval = [r for r in eval_rows if r["M"] > 0]

    # Mode B fit + eval.
    fit_h = fit_temperatures(fit_rows_h)
    tmap_h = {b: v["T"] for b, v in fit_h.items()}
    conflict_eval_h = [r for r in eval_rows_h if r["M"] > 0]

    report = {
        "protocol": "calibration-fit-v0.5",
        "frozen_schema": "v0.5",
        "min_samples": MIN_SAMPLES,
        "fit_slice": "seed-7 decision bench, n=300 (non-gate)",
        "eval_slice": "conflict-heldout-120, n=120 (independent, measured once)",
        "operating_point": "kappa=0.25, lambda_=2.5, calibration=None (no-history)",
        "band_temperatures": fit,
        "baseline_global_T": C.TEMP,
        "eval": {
            "baseline_T2.0": {
                "ece_overall": ece(eval_rows, base),
                "ece_conflict": ece(conflict_eval, base),
                "brier_top": round(brier_top(eval_rows, base), 4),
                "brier_full": round(brier_full(eval_rows, base), 4),
            },
            "fitted_per_band": {
                "ece_overall": ece(eval_rows, tmap_fit),
                "ece_conflict": ece(conflict_eval, tmap_fit),
                "brier_top": round(brier_top(eval_rows, tmap_fit), 4),
                "brier_full": round(brier_full(eval_rows, tmap_fit), 4),
            },
            "seeded_history": {
                "note": ("metacognitive CalibrationLog seeded from FIT slice "
                         "only; per-band T re-fit on history-adjusted pairs"),
                "band_temperatures": fit_h,
                "ece_overall": ece(eval_rows_h, tmap_h),
                "ece_conflict": ece(conflict_eval_h, tmap_h),
                "brier_top": round(brier_top(eval_rows_h, tmap_h), 4),
                "brier_full": round(brier_full(eval_rows_h, tmap_h), 4),
            },
        },
        "targets": {"ece_overall_le": 0.05, "ece_conflict_le": 0.10},
        "elapsed_s": round(time.time() - t0, 1),
    }
    # Per-band detail on eval slice (counts + which T applied).
    for split, rows in (("baseline", eval_rows), ("fitted", eval_rows)):
        tmap = base if split == "baseline" else tmap_fit
        per_band = {}
        for name in [b[0] for b in BANDS]:
            br = [r for r in rows if r["band"] == name]
            per_band[name] = {
                "n": len(br),
                "ece": ece(br, tmap)["ece"] if br else None,
                "brier_top": round(brier_top(br, tmap), 4) if br else None,
                "brier_full": round(brier_full(br, tmap), 4) if br else None,
                "T": tmap[name],
            }
        report["eval"]["fitted_per_band" if split == "fitted"
                       else "baseline_T2.0"][f"per_band_{split}"] = per_band

    path = OUT + "calibration-fit-run1.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: report[k] for k in ("band_temperatures", "targets")},
                     indent=2))
    ev = report["eval"]
    for label in ("baseline_T2.0", "fitted_per_band", "seeded_history"):
        if label == "seeded_history":
            e = ev[label]
            print(f"{label}: ECE_all={e['ece_overall']['ece']} "
                  f"ECE_conf={e['ece_conflict']['ece']} "
                  f"Brier_top={e['brier_top']} Brier_full={e['brier_full']}")
            continue
        e = ev[label]
        print(f"{label}: ECE_all={e['ece_overall']['ece']} "
              f"ECE_conf={e['ece_conflict']['ece']} "
              f"Brier_top={e['brier_top']} Brier_full={e['brier_full']}")
    print("wrote", path)


if __name__ == "__main__":
    main()
