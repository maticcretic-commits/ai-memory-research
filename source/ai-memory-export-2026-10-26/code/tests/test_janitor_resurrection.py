"""Janitor resurrection gate tests (2026-10-21): should a
no-longer-in-force record be resurrectable?

Contract (ChatGPT ruling 2026-10-21, janitor-resurrection-
chatgpt-ruling.txt; measured first per janitor-resurrection-
preregistration.md, battery F1-F7 in evals/janitor_resurrection_
measurement.py, artifact evals/reports/janitor-resurrection-
m0.json):
- NEVER resurrect an out-of-force record: Janitor step 3 skips
  promotion whenever invalid_at is set and invalid_at <= now.
  The gate key is invalid_at itself, NOT invalid_at + 14d - the
  J-A grace (which governs migration timing only) opens no
  resurrection window: out of force 5d blocks exactly like out
  of force 100d.
- In-force and future-window records remain eligible under the
  existing rules (reason string byte-preserved).
- Accesses to a blocked record still log and count toward
  half-life estimation; they cannot promote.
- decay_exempt unchanged: pinned by the step-1b early return,
  never reaches step 3.

Pre-ruling behaviour (M0, for contrast): step 3 was window-
blind - F1 resurrected a record 20d out of force, and F2
oscillated migrate/resurrect indefinitely under J-A.

Run: python3 tests/test_janitor_resurrection.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.janitor import Janitor
from mm.reflect import MemoryRecord

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


D = 86400.0
NOW = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()


def naive_days_before(days: float) -> datetime:
    return datetime.fromtimestamp(NOW - days * D,
                                  tz=timezone.utc).replace(tzinfo=None)


def naive_at(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch,
                                  tz=timezone.utc).replace(tzinfo=None)


def jrec(rid="r1", tier="cooled", last_accessed=None, invalid_at=None,
         decay_exempt=False, owner=""):
    return MemoryRecord(
        id=rid, text=f"record {rid}",
        timestamp=datetime(2026, 1, 1), tier=tier,
        created_at=NOW - 40 * D,
        last_accessed=(NOW - 2 * D if last_accessed is None
                       else last_accessed),
        invalid_at=invalid_at, decay_exempt=decay_exempt,
        owner=owner)


def log3(jan, rid, now=NOW, actor=""):
    for at in (now - 2 * D, now - 1 * D, now - 0.5 * D):
        jan.log_access(rid, at, actor=actor)


def resurrect_ops(jan, rec, now=NOW):
    ops = jan._lifecycle_for(rec, now, {rec.id: rec})
    return [o for o in ops if o.op == "resurrect"]


# --- The gate ---------------------------------------------------------------

# F1 under the ruling: cooled, window closed 20d ago, 3 distinct-
# day accesses -> NO resurrect op; a full run leaves it cooled.
jan = Janitor()
r = jrec(invalid_at=naive_days_before(20))
log3(jan, r.id)
check("jr-out-of-force-blocked", resurrect_ops(jan, r) == [])
rep = jan.run({r.id: r}, NOW)
check("jr-out-of-force-stays-cooled",
      r.tier == "cooled"
      and not any(o.op == "resurrect" for o in rep.ops))

# Gate key is invalid_at itself: invalid_at exactly == now is
# already out of force ([start, end) semantics) -> blocked.
jan = Janitor()
r = jrec(invalid_at=naive_at(NOW))
log3(jan, r.id)
check("jr-gate-key-exact-boundary", resurrect_ops(jan, r) == [])

# F5 under the ruling: out of force only 5d (inside the J-A
# grace) blocks exactly like long-out-of-force - the grace is
# migration timing, not resurrection eligibility.
jan = Janitor()
r = jrec(invalid_at=naive_days_before(5))
log3(jan, r.id)
check("jr-grace-still-blocked", resurrect_ops(jan, r) == [])

# One second of force left: invalid_at 1s in the future ->
# still in force at promotion time -> resurrects.
jan = Janitor()
r = jrec(invalid_at=naive_at(NOW) + timedelta(seconds=1))
log3(jan, r.id)
ops = resurrect_ops(jan, r)
check("jr-one-second-in-force-resurrects", len(ops) == 1)

# F3 control: no window at all -> resurrects, reason preserved.
jan = Janitor()
r = jrec(invalid_at=None)
log3(jan, r.id)
ops = resurrect_ops(jan, r)
check("jr-in-force-control-resurrects",
      len(ops) == 1 and ops[0].to_tier == "active"
      and ops[0].reason == "3 distinct-day accesses in 30d",
      str([o.reason for o in ops]))

# --- The oscillation is dead (F2 pattern) -----------------------------------

jan = Janitor()
r = jrec(tier="active", invalid_at=naive_days_before(20),
         last_accessed=NOW - D)
records = {r.id: r}
rep = jan.run(records, NOW)
check("jr-oscillation-pass1-ja-cools",
      r.tier == "cooled"
      and any(o.op == "migrate" for o in rep.ops))
total_resurrects = 0
for k in range(1, 6):
    now_k = NOW + k * D
    log3(jan, r.id, now=now_k)
    rep = jan.run(records, now_k)
    total_resurrects += sum(1 for o in rep.ops if o.op == "resurrect")
check("jr-oscillation-dead",
      total_resurrects == 0 and r.tier == "cooled",
      f"resurrects={total_resurrects} tier={r.tier}")

# --- Unchanged semantics ------------------------------------------------------

# F6: decay_exempt cooled record, long out of force -> no
# resurrect (step-1b early return precedes the gate entirely).
jan = Janitor()
r = jrec(invalid_at=naive_days_before(100), decay_exempt=True)
log3(jan, r.id)
check("jr-decay-exempt-unchanged", resurrect_ops(jan, r) == [])

# F7a: attributed wiring intact on an IN-FORCE record: owner-only
# accesses do not count; non-owner accesses resurrect.
jan = Janitor(attributed_resurrection=True)
r = jrec(invalid_at=None, owner="alice")
log3(jan, r.id, actor="alice")
check("jr-attributed-owner-only-no-count",
      resurrect_ops(jan, r) == [])
jan = Janitor(attributed_resurrection=True)
r = jrec(invalid_at=None, owner="alice")
log3(jan, r.id, actor="bob")
check("jr-attributed-nonowner-resurrects",
      len(resurrect_ops(jan, r)) == 1)

# F7b: the gate precedes the wiring - non-owner accesses cannot
# resurrect an out-of-force record either.
jan = Janitor(attributed_resurrection=True)
r = jrec(invalid_at=naive_days_before(20), owner="alice")
log3(jan, r.id, actor="bob")
check("jr-attributed-nonowner-blocked-out-of-force",
      resurrect_ops(jan, r) == [])

# Blocked accesses still log and count toward half-life
# estimation (not frozen): 3 logged retrievals on the blocked
# record -> 2 intervals counted, record not in the censored
# cohort of its class.
jan = Janitor()
r = jrec(invalid_at=naive_days_before(20))
log3(jan, r.id)
est = jan.estimate_half_life_for({r.id: r})
entry = est[r.ttl_class]
check("jr-accesses-still-count-for-halflife",
      entry["n"] == 2 and entry["censored"] == 0,
      str(entry))

# Dry-run changes nothing on either side of the gate.
jan = Janitor()
r_out = jrec(rid="d1", invalid_at=naive_days_before(20))
r_in = jrec(rid="d2", invalid_at=None)
log3(jan, "d1")
log3(jan, "d2")
jan.run({"d1": r_out, "d2": r_in}, NOW, dry_run=True)
check("jr-dry-run-changes-nothing",
      r_out.tier == "cooled" and r_in.tier == "cooled")

# verdict_preview inherits the gate via _lifecycle_for: the
# blocked record's preview lists no resurrect op; the in-force
# control's preview does.
jan = Janitor()
r_out = jrec(rid="p1", invalid_at=naive_days_before(20))
r_in = jrec(rid="p2", invalid_at=None)
log3(jan, "p1")
log3(jan, "p2")
prev = {p["record_id"]: p for p in
        jan.verdict_preview({"p1": r_out, "p2": r_in}, NOW)}
check("jr-verdict-preview-reflects-gate",
      "resurrect" not in prev["p1"]["ops"]
      and "resurrect" in prev["p2"]["ops"],
      str({k: v["ops"] for k, v in prev.items()}))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
