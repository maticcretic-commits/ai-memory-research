"""Janitor resurrection measurement M0 (2026-10-21).

Preregistration: janitor-resurrection-preregistration.md
(implementation records). Measures CURRENT behaviour - no code
change - for the question flagged in b2-remainders-record.md
sec. 4: can a no-longer-in-force (past invalid_at) cooled record
resurrect via Janitor step 3, and what does resurrection restore?

Battery F1-F7 as preregistered. Deterministic fixtures; NOW
fixed at 2026-02-01T12:00:00Z. Prints a summary and writes
evals/reports/janitor-resurrection-m0.json.

Run: python3 evals/janitor_resurrection_measurement.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.janitor import Janitor
from mm.reflect import MemoryRecord

D = 86400.0
NOW = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()


def naive_days_before(days: float) -> datetime:
    return datetime.fromtimestamp(NOW - days * D,
                                  tz=timezone.utc).replace(tzinfo=None)


def naive_days_after(days: float) -> datetime:
    return datetime.fromtimestamp(NOW + days * D,
                                  tz=timezone.utc).replace(tzinfo=None)


def jrec(rid, tier="active", last_accessed=None, invalid_at=None,
         decay_exempt=False, owner=""):
    return MemoryRecord(
        id=rid, text=f"record {rid}",
        timestamp=datetime(2026, 1, 1), tier=tier,
        created_at=NOW - 40 * D,
        last_accessed=(NOW - D if last_accessed is None
                       else last_accessed),
        invalid_at=invalid_at, decay_exempt=decay_exempt,
        owner=owner)


def ops_of(report, kind=None):
    out = [o for o in report.ops]
    if kind is not None:
        out = [o for o in out if o.op == kind]
    return [{"op": o.op, "from": o.from_tier, "to": o.to_tier,
             "reason": o.reason} for o in out]


def log3(jan, rid, now, actor=""):
    """Retrieval accesses on 3 distinct days inside the window."""
    for at in (now - 2 * D, now - 1 * D, now - 0.5 * D):
        jan.log_access(rid, at, actor=actor)


results = {}

# --- F1: out-of-force, J-A path -------------------------------------------
jan = Janitor()
rec = jrec("f1", tier="active", invalid_at=naive_days_before(20),
           last_accessed=NOW - D)
records = {"f1": rec}
rep1 = jan.run(records, NOW)
f1 = {"pass1_ops": ops_of(rep1), "tier_after_pass1": rec.tier}
log3(jan, "f1", NOW)
rep2 = jan.run(records, NOW)
f1["pass2_ops"] = ops_of(rep2)
f1["tier_after_pass2"] = rec.tier
f1["last_accessed_after"] = rec.last_accessed
results["F1_out_of_force_ja_path"] = f1

# --- F2: oscillation over 5 further passes --------------------------------
seq = []
for k in range(1, 6):
    now_k = NOW + k * D
    log3(jan, "f1", now_k)
    rep = jan.run(records, now_k)
    seq.append({"pass": k, "ops": [o["op"] for o in ops_of(rep)],
                "tier_after": rec.tier})
results["F2_oscillation"] = {
    "passes": seq,
    "resurrect_ops": sum(s["ops"].count("resurrect") for s in seq),
    "migrate_ops": sum(s["ops"].count("migrate") for s in seq),
}

# --- F3: in-force control (no window) --------------------------------------
jan = Janitor()
rec = jrec("f3", tier="cooled", invalid_at=None,
           last_accessed=NOW - 2 * D)
log3(jan, "f3", NOW)
rep = jan.run({"f3": rec}, NOW)
results["F3_in_force_control"] = {
    "ops": ops_of(rep), "tier_after": rec.tier}

# --- F4: future window ------------------------------------------------------
jan = Janitor()
rec = jrec("f4", tier="cooled", invalid_at=naive_days_after(10),
           last_accessed=NOW - 2 * D)
log3(jan, "f4", NOW)
rep = jan.run({"f4": rec}, NOW)
results["F4_future_window"] = {
    "ops": ops_of(rep), "tier_after": rec.tier}

# --- F5: inside J-A grace (invalid 5d ago) ----------------------------------
jan = Janitor()
rec = jrec("f5", tier="cooled", invalid_at=naive_days_before(5),
           last_accessed=NOW - 2 * D)
log3(jan, "f5", NOW)
rep = jan.run({"f5": rec}, NOW)
results["F5_inside_ja_grace"] = {
    "ops": ops_of(rep), "tier_after": rec.tier}

# --- F6: decay_exempt cooled, long out of force -----------------------------
jan = Janitor()
rec = jrec("f6", tier="cooled", invalid_at=naive_days_before(100),
           decay_exempt=True, last_accessed=NOW - 2 * D)
log3(jan, "f6", NOW)
rep = jan.run({"f6": rec}, NOW)
results["F6_decay_exempt"] = {
    "ops": ops_of(rep), "tier_after": rec.tier,
    "resurrect_ops": len(ops_of(rep, "resurrect"))}

# --- F7: attributed wiring ---------------------------------------------------
jan = Janitor(attributed_resurrection=True)
rec = jrec("f7", tier="cooled", invalid_at=naive_days_before(20),
           last_accessed=NOW - 2 * D, owner="alice")
log3(jan, "f7", NOW, actor="alice")
rep = jan.run({"f7": rec}, NOW)
f7 = {"owner_only_resurrect_ops": len(ops_of(rep, "resurrect")),
      "tier_after_owner_only": rec.tier}
jan = Janitor(attributed_resurrection=True)
rec = jrec("f7b", tier="cooled", invalid_at=naive_days_before(20),
           last_accessed=NOW - 2 * D, owner="alice")
log3(jan, "f7b", NOW, actor="bob")
rep = jan.run({"f7b": rec}, NOW)
f7["non_owner_resurrect_ops"] = len(ops_of(rep, "resurrect"))
f7["tier_after_non_owner"] = rec.tier
results["F7_attributed_wiring"] = f7

out_path = os.path.join(os.path.dirname(__file__), "reports",
                        "janitor-resurrection-m0.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as fh:
    json.dump(results, fh, indent=2, sort_keys=True)

for case, data in results.items():
    print(f"== {case}: {json.dumps(data)}")
print(f"\nartifact: {out_path}")
