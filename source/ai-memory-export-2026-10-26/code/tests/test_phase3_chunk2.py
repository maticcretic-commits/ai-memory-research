"""Phase-3 chunk-2 tests: write gate (fail-closed), M-bands, Janitor,
consolidation (opt-in), isotonic calibration.

Run:  python3 tests/test_phase3_chunk2.py   (from the repo root)
"""

import math
import sys
from datetime import datetime

sys.path.insert(0, ".")

from mm.reflect import MemoryRecord, Provenance
from mm.mbands import band_for, fit_band_stats, band_normalize, band_curve_source
from mm.write_gate import WriteGate
from mm.janitor import Janitor, ACTIVE_TO_COOLED_S
from mm.consolidation import ConsolidationDaemon
from evals.isotonic_fit import (
    IsotonicCalibrator, brier_full_vector, decompose_brier, _pava,
)

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" - {detail}" if detail and not cond else ""))


def rec(**kw):
    # HD-1: default fixture carries concrete detail (P-gate-passing) so
    # tests exercise their intended gate, not the 2.1 pre-gates.
    base = dict(id="r1", text="The deploy failed at 14:02 because of a bad "
                "config in deploy.yaml v2.3; roll back to v2.2 and re-run "
                "the smoke test.",
                timestamp=datetime(2026, 10, 20), type="error_fix",
                epistemic_tier="observed", explicit=True, owner="nitesh")
    base.update(kw)
    r = MemoryRecord(**base)
    if not r.created_at:
        r.created_at = 1790000000.0
    return r


# --- M-bands ---------------------------------------------------------------
check("band m=0 -> none", band_for(0.0) == "none")
check("band 0.25 -> low", band_for(0.25) == "low")
check("band 0.50 -> low (upper-inclusive)", band_for(0.50) == "low")
check("band 0.70 -> medium (upper-inclusive)", band_for(0.70) == "medium")
check("band 0.85 -> high", band_for(0.85) == "high")
check("band 1.5 clamped -> high", band_for(1.5) == "high")

stats = fit_band_stats({"none": [0.5] * 40, "low": [0.6, 0.7],
                        "medium": [0.8] * 40, "high": [0.9] * 5})
check("thin low band borrows pooled", stats["low"].borrowed is True)
check("thin low band declares source", stats["low"].borrowed_from == "pooled-m>0")
check("fitted medium band not borrowed", stats["medium"].borrowed is False)
check("band_normalize z-scores", abs(band_normalize(0.8, 0.6, stats) - 0.0) < 1e-9)
src = band_curve_source("low", stats)
check("curve source declares BORROWED", "BORROWED" in src, src)

# --- write gate -------------------------------------------------------------
g = WriteGate()
# G5b (Red-Team Round 2): a lone claim at confidence >= 0.80 now queues
# without a disjoint-origin corroborator. The clean record's claim is
# corroborated by the wiki mirror (different owner AND source root) so
# this section exercises the pipeline's admit path, as before.
store = {"wiki1": rec(id="wiki1", owner="wiki-mirror", source="wiki/run")}
out = g.admit(rec(), store)
check("clean record admitted", out.admitted, str(out.reasons))
check("write_audit populated", bool(out.record.write_audit.get("gates")))

# fail-closed: inferred without corroboration -> queued, not admitted
g2 = WriteGate()
q = g2.admit(rec(id="r2", epistemic_tier="inferred", explicit=False,
                 provenance=Provenance(confidence=0.6)), {})
check("inferred w/o corroboration queued", q.queued, str(q.reasons))
check("queued item in review queue", len(g2.review_queue.pending()) == 1)
check("nothing silently landed", q.record.id not in {})

# overconfident claim for tier -> queued
g3 = WriteGate()
q3 = g3.admit(rec(id="r3", epistemic_tier="unknown",
                  provenance=Provenance(confidence=0.9)), {})
check("unknown-tier 0.9 confidence queued", q3.queued, str(q3.reasons))

# exact dedup before contradiction
g4 = WriteGate()
store4 = {"a1": rec(id="a1")}
d = g4.admit(rec(id="a2"), store4)  # identical -> duplicate
check("exact duplicate rejected", d.verdict == "rejected", str(d.reasons))
check("duplicate refreshed original", store4["a1"].access_count == 1)

# secrets never stored, never queued
g5 = WriteGate()
s = g5.admit(rec(id="s1", text="Rotate the api_key: sk-abcdefghijklmnop123 "
                   "in vault.yaml v3; deploy the replacement at 14:00."), {})
check("secret rejected", s.verdict == "rejected", str(s.reasons))
check("secret not queued", len(g5.review_queue.pending()) == 0)

# contradiction without supersession -> review; with supersedes -> close-on-replacement
g6 = WriteGate()
old = rec(id="old1", text="Config X is correct.")
store6 = {"old1": old}
c = g6.admit(rec(id="new1", text="Config X is wrong: timeouts fire at 30s "
                   "instead of the documented 60s; fix retry_count in "
                   "config.yaml v3.",
                 provenance=Provenance(confidence=0.8, contradicts=["old1"])), store6)
check("open contradiction queued", c.queued, str(c.reasons))
g7 = WriteGate()
# G5b: the correction at confidence 0.80 carries a disjoint-origin
# corroborator (same claim, wiki mirror) so the supersession flow -
# this section's subject - is what decides the verdict.
store7 = {"old1": rec(id="old1", text="Config X is correct."),
          "corr1": rec(id="corr1", owner="wiki-mirror", source="wiki/run",
                       text="Config X is wrong, fixed in v2.3 at "
                            "14:02; verify the rollout before closing.",
                       provenance=Provenance(confidence=0.6))}
c7 = g7.admit(rec(id="new1", text="Config X is wrong, fixed in v2.3 at "
                    "14:02; verify the rollout before closing.",
                  provenance=Provenance(confidence=0.8, contradicts=["old1"],
                                        supersedes=["old1"])), store7)
check("supersedes closes on replacement", c7.admitted, str(c7.reasons))
check("loser archived + flagged",
      store7["old1"].tier == "archive" and store7["old1"].superseded_with_replacement)

# salience scored with components
check("salience components stored",
      "type_weight" in out.record.write_audit.get("salience_components", {}))

# founder bar: admitted records are sealed (immutable, verbatim recall)
check("admitted record sealed",
      out.record.write_audit.get("immutable") is True
      and "sealed_at" in out.record.write_audit)

# --- janitor -----------------------------------------------------------------
j = Janitor()
now = 1790000000.0
old_rec = rec(id="j1", tier="active", created_at=now - 20 * 86400,
              last_accessed=now - 20 * 86400)
new_rec = rec(id="j2", tier="active", created_at=now - 3600,
              last_accessed=now - 3600)
records = {"j1": old_rec, "j2": new_rec}
rep = j.run(records, now, dry_run=True)
check("dry-run changes nothing", old_rec.tier == "active")
ops = [o.op for o in rep.ops]
check("20d-idle active -> migrate op proposed", "migrate" in ops, str(ops))
rep2 = j.run(records, now, dry_run=False)
check("applied migrate", old_rec.tier == "cooled")

# resurrection needs distinct-day accesses
j3 = Janitor()
cool = rec(id="c1", tier="cooled", created_at=now - 20 * 86400,
           last_accessed=now - 20 * 86400)
for d in (1, 2, 3):
    j3.log_access("c1", now - d * 86400)  # 3 distinct days
r3 = j3.run({"c1": cool}, now, dry_run=False)
check("3 distinct-day accesses resurrect", cool.tier == "active",
      str([o.op for o in r3.ops]))
j4 = Janitor()
cool2 = rec(id="c2", tier="cooled", created_at=now - 20 * 86400,
            last_accessed=now - 20 * 86400)
for _ in range(5):
    j4.log_access("c2", now - 3600)  # 5 same-day: clustered, not meaningful
r4 = j4.run({"c2": cool2}, now, dry_run=False)
check("clustered same-day accesses do NOT resurrect", cool2.tier == "cooled")

# half-life: insufficient data, not invented
j5 = Janitor()
hl = j5.estimate_half_life_for({"x": rec(id="x", ttl_class="session")})
check("half-life insufficient-data reported",
      hl["session"]["status"] == "insufficient-data"
      and hl["session"]["half_life_days"] is None)

# --- consolidation ------------------------------------------------------------
d_off = ConsolidationDaemon()  # default off
try:
    d_off.run({}, dry_run=True)
    check("disabled daemon refuses", False)
except RuntimeError:
    check("disabled daemon refuses", True)
d_on = ConsolidationDaemon(enabled=True)
crecs = {"m1": rec(id="m1", text="Same fact."), "m2": rec(id="m2", text="Same fact.")}
diff = d_on.run(crecs, dry_run=True)
check("dry-run merges exact dup in diff", diff.merged == [("m1", "m2")],
      str(diff.merged))
check("dry-run mutates nothing", len(crecs) == 2)
diff2 = d_on.run(crecs, dry_run=False)
check("real run dedups working set", len(crecs) == 1)
viol = d_on.assert_no_tier_promotion({"m1": "inferred"}, {"m1": "observed"})
check("inferred->observed promotion detected", viol == ["m1"])

# --- isotonic ------------------------------------------------------------------
xs, ys = _pava([0.9, 0.1, 0.5, 0.3], [1.0, 0.0, 1.0, 0.0])
check("pava monotone non-decreasing",
      all(ys[i] <= ys[i + 1] for i in range(len(ys) - 1)), str(ys))
cal = IsotonicCalibrator()
check("no data -> identity", cal.calibrate(0.8, 0.5) == 0.8)
check("no data status", cal.status == "no-data")
pairs = [(0.9, True, 0.0)] * 40 + [(0.9, False, 0.8)] * 40
cal.fit(pairs, source="real-decisions")
check("fitted status", cal.status == "fitted")
check("conflict band calibrates down", cal.calibrate(0.9, 0.8) < 0.9)
check("no-conflict band keeps high", cal.calibrate(0.9, 0.0) > 0.8)
# HD-2: source parameter enforced - anything but 'real-decisions' raises
for bad in ("synthetic", "bench", "harness", "", None):
    try:
        IsotonicCalibrator().fit(pairs, source=bad)
        check(f"fit refuses source={bad!r}", False, "no raise")
    except (ValueError, TypeError):
        check(f"fit refuses source={bad!r}", True)
try:
    IsotonicCalibrator().fit(pairs)
    check("fit requires source", False, "no raise without source")
except TypeError:
    check("fit requires source", True)
rep = cal.report()
check("report declares bands", set(rep) == {"none", "low", "medium", "high"})

b = brier_full_vector([0.7, 0.2, 0.1], 0)
check("full-vector brier correct", abs(b - (0.09 + 0.04 + 0.01) / 3) < 1e-9, str(b))
dec = decompose_brier([0.9, 0.1], 1)
check("decompose finds overconfidence", dec["overconfidence_gap"] == 0.9 - 0.0,
      str(dec))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
