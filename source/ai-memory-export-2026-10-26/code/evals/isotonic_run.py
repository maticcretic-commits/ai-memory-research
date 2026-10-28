"""isotonic_run - per-M-band isotonic calibration, real-data fits (HD-2).

DATA PROVENANCE (HD-2, head decision 2026-10-20): this harness fits ONLY
on real decision pairs from mm.confidence.CalibrationLog
(data/calibration.json, written by MemoryAgent.log_decision_pair).
The source parameter is enforced: anything but source="real-decisions"
raises inside IsotonicCalibrator.fit(). No synthetic data in
calibration. When no real pairs exist yet, the run reports "no-data"
rather than fitting bench pairs and reporting a number.

History: isotonic-run-v1 (chunk 3) ran the declared synthetic regime
(decision_bench seed 21); its report is preserved as isotonic-run1.json
and is NOT a target measurement. v2 supersedes the harness, not the
record.

Run:  python3 -m evals.isotonic_run
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from evals.isotonic_fit import IsotonicCalibrator
from mm import confidence as C

REPO = "/home/hatch/workspace/ai-memory-milestone"
CALIBRATION_JSON = os.path.join(REPO, "data", "calibration.json")
OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")


def ece_with_fn(pairs: list[dict], fn, n_bins: int = 10) -> float:
    bins: list[list[bool]] = [[] for _ in range(n_bins)]
    confs: list[list[float]] = [[] for _ in range(n_bins)]
    for r in pairs:
        c = fn(r)
        b = max(0, min(n_bins - 1, int(c * n_bins)))
        bins[b].append(r["correct"])
        confs[b].append(c)
    total = len(pairs) or 1
    err = 0.0
    for b in range(n_bins):
        if bins[b]:
            acc = sum(bins[b]) / len(bins[b])
            mc = sum(confs[b]) / len(confs[b])
            err += (len(bins[b]) / total) * abs(acc - mc)
    return round(err, 4)


def brier_top_with_fn(pairs: list[dict], fn) -> float:
    return round(sum((fn(r) - (1.0 if r["correct"] else 0.0)) ** 2
                     for r in pairs) / len(pairs), 4) if pairs else 0.0


def brier_full_with_fn(pairs: list[dict], fn_vec) -> float:
    s = 0.0
    for r in pairs:
        vec = {k: fn_vec(v, r["M"]) for k, v in r["full_vec"].items()}
        tot = sum(vec.values()) or 1.0
        vec = {k: v / tot for k, v in vec.items()}
        gold = r["gold_best"]
        s += sum((vec.get(oid, 0.0) - (1.0 if oid == gold else 0.0)) ** 2
                 for oid in set(vec) | {gold})
    return round(s / len(pairs), 4) if pairs else 0.0

def main() -> None:
    t0 = time.time()
    triples: list[tuple[float, bool, float]] = []
    if os.path.exists(CALIBRATION_JSON):
        with open(CALIBRATION_JSON, encoding="utf-8") as f:
            log = C.CalibrationLog.load_json(f.read())
        triples = log.triples()

    report: dict = {
        "harness": "isotonic-run-v2",
        "data_provenance": ("real-decisions only (HD-2): "
                            "mm.confidence.CalibrationLog triples from "
                            "MemoryAgent.log_decision_pair; synthetic "
                            "bench pairs are refused by fit()"),
        "targets_W2": {"ece_overall_le": 0.05, "ece_conflict_le": 0.10},
        "elapsed_s": round(time.time() - t0, 1),
    }
    if not triples:
        # Fail-closed: no real pairs -> no fit, no number. The rescope
        # contract reserves target measurement for real data; a
        # synthetic fit here would launder bench numbers as calibration.
        report["status"] = "no-data"
        report["n_pairs"] = 0
        report["note"] = ("no real decision pairs in "
                          + CALIBRATION_JSON + " yet; fit refused "
                          "rather than fitting synthetic (HD-2)")
    else:
        calibrator = IsotonicCalibrator().fit(triples,
                                              source="real-decisions")
        report["status"] = calibrator.status
        report["n_pairs"] = len(triples)
        report["isotonic_report"] = calibrator.report()

    path = OUT + "isotonic-run2.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({k: v for k, v in report.items()
                      if k != "isotonic_report"}, indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
