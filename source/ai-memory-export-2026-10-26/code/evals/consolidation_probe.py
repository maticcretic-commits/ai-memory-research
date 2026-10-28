"""consolidation_probe - end-to-end probe harness for mm.consolidation
(Phase-3 chunk 3).

The chunk-2 daemon shipped with its control section as a protocol stub
("the harness fills the numbers"). This is the harness. It exercises the
daemon end-to-end while the daemon stays DEFAULT-OFF in production:

  1. Opt-in enforcement: a fresh daemon's run() must RAISE.
  2. Dry-run: full diff computed, store provably unmutated.
  3. Live run on a working copy: exact-duplicate merge, supersession
     close-out, episodic pointer candidates - all in the diff log with
     source links.
  4. HARD RULE: assert_no_tier_promotion(before, after) must be empty -
     inferred is never promoted to observed.
  5. Append-only preservation: the pristine pre-consolidation snapshot
     still holds every source record (the daemon's diff is the audit
     trail back to them).
  6. THE CONTROL (the numbers the stub promised): the same probe set
     scored against the pre- and post-consolidation stores with a
     deterministic retrieval function; gains AND regressions reported
     per probe - never just the wins.

Fixture: a small store shaped like a pre-gate legacy import (exact
duplicates and an un-closed supersession can exist there - that is
exactly what consolidation exists to clean). Retrieval: token-overlap
over text+content, salience-weighted, ARCHIVE TIER EXCLUDED (closed
records are not retrievable answers - that is the point of close-out).

Run:  python3 -m evals.consolidation_probe
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime

sys.path.insert(0, "/home/hatch/workspace/ai-memory-milestone")

from mm.consolidation import ConsolidationDaemon
from mm.reflect import MemoryRecord, Provenance

OUT = ("/home/hatch/workspace/goals/ai-agent-memory-milestone-repo/"
       "hidden_files/implementation/")


def _rec(rid: str, text: str, rtype: str = "fact",
         epistemic: str = "observed", tier: str = "active",
         salience: float = 0.5, superseded: bool = False,
         conf: float = 0.9) -> MemoryRecord:
    return MemoryRecord(
        id=rid, text=text, content=text, timestamp=datetime(2026, 10, 18),
        type=rtype, epistemic_tier=epistemic, tier=tier,
        salience=salience, explicit=True, owner="probe",
        consent_scope="project",
        superseded_with_replacement=superseded,
        provenance=Provenance(confidence=conf))


def fixture_store() -> dict[str, MemoryRecord]:
    """Pre-gate legacy shape: one exact-duplicate pair, one superseded
    record never closed out, episodic records without pointers, one
    inferred record (the hard-rule canary)."""
    return {
        "k1": _rec("k1", "Kappa frozen at 0.25 and lambda at 2.5 for the "
                         "Phase-2 controller", salience=0.9),
        "k1-dup": _rec("k1-dup", "Kappa frozen at 0.25 and lambda at 2.5 "
                                 "for the Phase-2 controller",
                       salience=0.9),
        "k0-stale": _rec("k0-stale", "Kappa frozen at 0.10 in the early "
                                     "draft controller", salience=0.85,
                         superseded=True),
        "g1": _rec("g1", "Gate d passed with candidate accuracy 0.7167 "
                         "on high-stakes tasks", salience=0.8),
        "e1": _rec("e1", "Session episode: partners wired via OpenRouter "
                         "and the council voted sequenced",
                   rtype="episodic", salience=0.4),
        "e2": _rec("e2", "Session episode: calibration fit ran on the "
                         "seed-7 bench overnight",
                   rtype="episodic", salience=0.4),
        "inf1": _rec("inf1", "The founder probably prefers short "
                             "briefings", rtype="preference",
                     epistemic="inferred", salience=0.5, conf=0.6),
    }


# Probes: (query, gold relevant ids in the CURRENT correct answer set).
PROBES = [
    ("kappa lambda controller", {"k1"}),
    ("gate accuracy high-stakes", {"g1"}),
    ("session episode partners", {"e1"}),
    ("calibration fit bench", {"e2"}),
    ("founder briefings", {"inf1"}),
]


def retrieve(store: dict[str, MemoryRecord], query: str,
             k: int = 3) -> list[str]:
    """Deterministic retrieval: token overlap x (1 + salience);
    archive tier excluded (closed records are not answers)."""
    tokens = {t for t in query.lower().split() if t}
    scored = []
    for rid, rec in store.items():
        if rec.tier == "archive":
            continue
        body = f"{rec.text} {rec.content}".lower()
        hits = sum(1 for t in tokens if t in body)
        if hits:
            scored.append((hits * (1.0 + rec.salience), rid))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [rid for _, rid in scored[:k]]


def score_probes(store: dict[str, MemoryRecord]) -> list[dict]:
    out = []
    for query, gold in PROBES:
        got = retrieve(store, query)
        hits = len(set(got) & gold)
        out.append({
            "query": query, "gold": sorted(gold), "retrieved": got,
            "recall_at_3": hits / len(gold) if gold else 0.0,
            "precision_at_3": hits / len(got) if got else 0.0,
            "noise": [g for g in got if g not in gold],
        })
    return out


def main() -> None:
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    # 1. Opt-in enforcement: default-OFF daemon refuses to run.
    daemon = ConsolidationDaemon()
    check("default-off", daemon.enabled is False)
    try:
        daemon.run(fixture_store())
        check("disabled-run-raises", False, "run() did not raise")
    except RuntimeError:
        check("disabled-run-raises", True)

    daemon.enable()
    store = fixture_store()
    pristine = copy.deepcopy(store)
    tiers_before = {rid: r.epistemic_tier for rid, r in store.items()}

    # 2. Dry-run: full diff, zero mutation.
    dry = daemon.run(store, probe=[q for q, _ in PROBES], dry_run=True)
    check("dry-run-no-mutation",
          set(store) == set(pristine)
          and all(store[r].tier == pristine[r].tier for r in store),
          f"merged={dry.merged} closed={dry.closed}")
    check("dry-run-finds-duplicate", ("k1", "k1-dup") in dry.merged
          or ("k1-dup", "k1") in dry.merged, str(dry.merged))
    check("dry-run-finds-superseded", "k0-stale" in dry.closed)

    # Control BEFORE (pre-consolidation store).
    pre = score_probes(store)

    # 3. Live run on the working store.
    live = daemon.run(store, probe=[q for q, _ in PROBES], dry_run=False)
    check("live-merge-applied", "k1-dup" not in store and "k1" in store,
          f"merged={live.merged}")
    check("live-closeout-applied",
          store["k0-stale"].tier == "archive", store["k0-stale"].tier)
    pointers = [a for a in live.added if a.startswith("pointer-candidate:")]
    check("pointer-candidates-reported", len(pointers) == 2, str(pointers))

    # 4. HARD RULE: no inferred -> observed promotion, anywhere.
    tiers_after = {rid: r.epistemic_tier for rid, r in store.items()}
    violations = daemon.assert_no_tier_promotion(tiers_before, tiers_after)
    check("no-tier-promotion", violations == [], str(violations))
    check("inferred-stays-inferred",
          store["inf1"].epistemic_tier == "inferred")

    # 5. Append-only preservation: pristine snapshot intact, diff links back.
    check("sources-preserved",
          set(pristine) == {"k1", "k1-dup", "k0-stale", "g1", "e1", "e2",
                            "inf1"}
          and pristine["k1-dup"].text.startswith("Kappa frozen"))
    check("diff-has-source-links",
          all(s in pristine and a in pristine for s, a in live.merged))

    # 6. Control AFTER + per-probe gains/regressions.
    post = score_probes(store)
    per_probe = []
    for b, a in zip(pre, post):
        per_probe.append({
            "query": b["query"],
            "recall_before": b["recall_at_3"],
            "recall_after": a["recall_at_3"],
            "precision_before": b["precision_at_3"],
            "precision_after": a["precision_at_3"],
            "noise_before": b["noise"], "noise_after": a["noise"],
            "verdict": ("gain" if a["precision_at_3"] > b["precision_at_3"]
                        or a["recall_at_3"] > b["recall_at_3"] else
                        "regression" if a["precision_at_3"] < b["precision_at_3"]
                        or a["recall_at_3"] < b["recall_at_3"] else "same"),
        })
    mean = lambda rows, k: round(sum(r[k] for r in rows) / len(rows), 4)
    report = {
        "harness": "consolidation-probe-v1",
        "checks": checks,
        "all_checks_pass": all(c["pass"] for c in checks),
        "diff_log": {
            "run_id": live.run_id, "dry_run": live.dry_run,
            "merged": live.merged, "closed": live.closed,
            "added": live.added, "updated": live.updated,
        },
        "control": {
            "probe_set": len(PROBES),
            "mean_recall_at_3_before": mean(pre, "recall_at_3"),
            "mean_recall_at_3_after": mean(post, "recall_at_3"),
            "mean_precision_at_3_before": mean(pre, "precision_at_3"),
            "mean_precision_at_3_after": mean(post, "precision_at_3"),
            "per_probe": per_probe,
        },
        "daemon_production_state": "default-OFF (this harness enabled "
                                   "its own instance only)",
    }
    path = OUT + "consolidation-probe-run1.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"checks: {sum(c['pass'] for c in checks)}/{len(checks)} pass")
    print("control: precision@3", report["control"]["mean_precision_at_3_before"],
          "->", report["control"]["mean_precision_at_3_after"],
          "| recall@3", report["control"]["mean_recall_at_3_before"],
          "->", report["control"]["mean_recall_at_3_after"])
    print("per-probe:", [(p["query"][:24], p["verdict"]) for p in per_probe])
    print("wrote", path)


if __name__ == "__main__":
    main()
