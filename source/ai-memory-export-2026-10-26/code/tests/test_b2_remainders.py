"""B2 remainders tests (2026-10-21): Janitor cooled-eligibility
past invalid_at + ttl, and the decision monitor's window-overlap
M signal.

Contracts (Benchmark Wave 1 record sec. 6 spec; ChatGPT rulings
2026-10-21, b2-remainders-chatgpt-ruling.txt):
- J-A: cooling eligibility begins at invalid_at + 14d (the
  existing schedule's first period), regardless of later access;
  subsequent lifecycle steps unchanged. decay_exempt records
  never migrate, B2 included.
- W-A: a declared contradiction pair whose validity windows are
  disjoint contributes zero to M; overlapping pairs retain full
  severity. Built measurement-only per ruling Q3, measured
  (M1/M2), then ADOPTED by ChatGPT's separate ruling on the
  measured numbers (b2-remainders-adoption-ruling.txt): score /
  raw_score ARE the windowed values; the pre-signal values are
  retained as score_unwindowed / raw_score_unwindowed for audit.
  Stock-bench inertness (M1) is pinned here over the full W3b
  set (n=300, seed 7): adopted == unwindowed on every task.

Preregistration: b2-remainders-preregistration.md.

Run: python3 tests/test_b2_remainders.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.janitor import Janitor
from mm.reflect import MemoryRecord, Provenance
from mm.resolver import monitor, normalize_m

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


D = 86400.0
NOW = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()


def naive_days_before(days: float) -> datetime:
    """Naive-UTC datetime `days` before NOW (record convention)."""
    return datetime.fromtimestamp(NOW - days * D,
                                  tz=timezone.utc).replace(tzinfo=None)


def jrec(rid="j1", tier="active", last_accessed=None, invalid_at=None,
         decay_exempt=False, **kw):
    base = dict(id=rid, text=f"record {rid}",
                timestamp=datetime(2026, 1, 1), tier=tier,
                created_at=NOW - 40 * D,
                last_accessed=(NOW - D if last_accessed is None
                               else last_accessed),
                invalid_at=invalid_at, decay_exempt=decay_exempt)
    base.update(kw)
    return MemoryRecord(**base)


def migrate_ops(rec, now=NOW):
    ops = Janitor()._lifecycle_for(rec, now, {rec.id: rec})
    return [o for o in ops if o.op == "migrate"]


# ---------------------------------------------------------------------------
# Janitor - J-A window-close cooling
# ---------------------------------------------------------------------------

# Accessed yesterday, window closed 15d ago: legacy idle rule is
# silent (1d < 14d); B2 must fire, and name itself in the reason.
r = jrec(invalid_at=naive_days_before(15))
ops = migrate_ops(r)
check("b2j-cools-despite-recent-access",
      len(ops) == 1 and ops[0].to_tier == "cooled"
      and "B2 window-close cooling" in ops[0].reason,
      str([o.reason for o in ops]))

# Window closed 13d ago: not yet eligible on either rule.
r = jrec(invalid_at=naive_days_before(13))
check("b2j-window-closed-13d-not-yet", migrate_ops(r) == [])

# Exact boundary: now == invalid_at + 14d fires (>=).
r = jrec(invalid_at=naive_days_before(14))
check("b2j-exact-boundary-fires", len(migrate_ops(r)) == 1)

# No window, recent access: fully inert.
r = jrec(invalid_at=None)
check("b2j-no-window-recent-access-inert", migrate_ops(r) == [])

# No window, idle 15d: legacy rule, legacy reason byte-preserved.
r = jrec(invalid_at=None, last_accessed=NOW - 15 * D)
ops = migrate_ops(r)
check("b2j-no-window-legacy-reason-preserved",
      len(ops) == 1 and ops[0].reason == "idle 15.0d >= 14d",
      str([o.reason for o in ops]))

# Future invalid_at (scheduled invalidation): inert.
r = jrec(invalid_at=naive_days_before(-10))
check("b2j-future-invalid-inert", migrate_ops(r) == [])

# decay_exempt: never migrates, however old the closed window.
r = jrec(invalid_at=naive_days_before(100), decay_exempt=True)
check("b2j-decay-exempt-never-cools", migrate_ops(r) == [])

# Cooled tier: B2 grants cooled-eligibility only - a cooled record
# with an old closed window and 10d idle must NOT archive early.
r = jrec(tier="cooled", invalid_at=naive_days_before(100),
         last_accessed=NOW - 10 * D)
check("b2j-cooled-no-archive-acceleration", migrate_ops(r) == [])

# Archive tier: no prune acceleration either (idle 10d < 90d).
r = jrec(tier="archive", invalid_at=naive_days_before(100),
         last_accessed=NOW - 10 * D)
ops = Janitor()._lifecycle_for(r, NOW, {r.id: r})
check("b2j-archive-no-prune-acceleration",
      all(o.op != "prune_eligible" for o in ops))

# Both rules fire (idle 20d AND window closed 20d ago): exactly
# one migrate op, reason names both facts.
r = jrec(invalid_at=naive_days_before(20), last_accessed=NOW - 20 * D)
ops = migrate_ops(r)
check("b2j-both-fire-single-op",
      len(ops) == 1 and "B2 window-close cooling" in ops[0].reason
      and "also idle" in ops[0].reason,
      str([o.reason for o in ops]))

# Dry-run changes nothing; a real run applies the cooling.
r = jrec(invalid_at=naive_days_before(15))
j = Janitor()
j.run({r.id: r}, NOW, dry_run=True)
dry_ok = r.tier == "active"
j.run({r.id: r}, NOW)
check("b2j-dry-run-then-apply", dry_ok and r.tier == "cooled",
      f"tier={r.tier}")

# verdict_preview surfaces the B2 op as an update (P-G2 path).
r = jrec(invalid_at=naive_days_before(15))
prev = Janitor().verdict_preview({r.id: r}, NOW)
check("b2j-verdict-preview-lists-op",
      prev[0]["verdict"] == "update" and "migrate" in prev[0]["ops"]
      and any("B2 window-close" in x for x in prev[0]["reasons"]),
      str(prev[0]))

# ---------------------------------------------------------------------------
# Monitor - W-A window-overlap signal (measurement-only)
# ---------------------------------------------------------------------------

D1 = datetime(2026, 1, 1)
D5 = datetime(2026, 1, 5)
D10 = datetime(2026, 1, 10)
D15 = datetime(2026, 1, 15)
D20 = datetime(2026, 1, 20)


def mrec(rid, salience=0.5, contradicts=(), valid_at=None,
         invalid_at=None, ts=None):
    return MemoryRecord(
        id=rid, text=f"record {rid}", timestamp=ts or D1,
        salience=salience,
        provenance=Provenance(contradicts=list(contradicts)),
        valid_at=valid_at, invalid_at=invalid_at)


# Succession: loser's window closes exactly when winner's opens
# (end-exclusive => disjoint => resolved). Adopted: M itself is
# the windowed value (0 here); the pre-signal M survives as the
# unwindowed audit pair.
a = mrec("a", contradicts=["b"], valid_at=D1, invalid_at=D10, ts=D1)
b = mrec("b", valid_at=D10, ts=D10)
rep = monitor([a, b])
check("b2m-succession-touching-resolved",
      rep.contradiction_count == 1 and rep.window_resolved_count == 1
      and rep.window_resolved_pairs == [("a", "b")]
      and rep.raw_score == 0.0 and rep.score == 0.0
      and rep.raw_score_unwindowed > 0 and rep.score_unwindowed > 0,
      f"raw={rep.raw_score} raw_unw={rep.raw_score_unwindowed}")

# Gap disjointness resolves too.
a = mrec("a", contradicts=["b"], valid_at=D1, invalid_at=D5, ts=D1)
b = mrec("b", valid_at=D20, ts=D20)
rep = monitor([a, b])
check("b2m-gap-disjoint-resolved", rep.window_resolved_count == 1)

# Reverse order + one-direction declaration: still one pair,
# still resolved.
a = mrec("a", valid_at=D20, ts=D20)
b = mrec("b", contradicts=["a"], valid_at=D1, invalid_at=D5, ts=D1)
rep = monitor([a, b])
check("b2m-reverse-order-resolved",
      rep.contradiction_count == 1 and rep.window_resolved_count == 1)

# Partial overlap: live contradiction, adopted == unwindowed.
a = mrec("a", contradicts=["b"], valid_at=D1, invalid_at=D15, ts=D1)
b = mrec("b", valid_at=D10, ts=D10)
rep = monitor([a, b])
check("b2m-partial-overlap-live",
      rep.window_resolved_count == 0
      and rep.raw_score_unwindowed == rep.raw_score
      and rep.score_unwindowed == rep.score)

# Containment: live.
a = mrec("a", contradicts=["b"], valid_at=D1, invalid_at=D20, ts=D1)
b = mrec("b", valid_at=D5, invalid_at=D10, ts=D5)
rep = monitor([a, b])
check("b2m-containment-live", rep.window_resolved_count == 0)

# Both open-ended (the stock-bench shape): live, always.
a = mrec("a", contradicts=["b"], ts=D1)
b = mrec("b", ts=D5)
rep = monitor([a, b])
check("b2m-both-open-live",
      rep.window_resolved_count == 0
      and rep.score_unwindowed == rep.score)

# One open-ended, overlapping the other's window: live.
a = mrec("a", contradicts=["b"], valid_at=D1, invalid_at=D10, ts=D1)
b = mrec("b", ts=D5)
rep = monitor([a, b])
check("b2m-one-open-overlap-live", rep.window_resolved_count == 0)

# Timestamp fallback: valid_at unset -> start is the timestamp.
a = mrec("a", contradicts=["b"], invalid_at=D5, ts=D1)
b = mrec("b", ts=D10)
rep = monitor([a, b])
check("b2m-timestamp-fallback-disjoint",
      rep.window_resolved_count == 1)

# valid_at governs over the timestamp when both exist: a's raw
# timestamp (D1) would overlap b's window; its valid_at (D20)
# does not.
a = mrec("a", contradicts=["b"], valid_at=D20, ts=D1)
b = mrec("b", valid_at=D1, invalid_at=D10, ts=D1)
rep = monitor([a, b])
check("b2m-valid-at-overrides-timestamp",
      rep.window_resolved_count == 1)

# Mixed set, exact arithmetic: 3 pairs (sev 0.5 disjoint; 0.7 and
# 0.9 live). Declared basis: count 3, mean 0.7, unwindowed raw 2.1.
# Adopted (windowed): live count 2, mean 0.8, raw 1.6.
a1 = mrec("a1", salience=0.6, contradicts=["b1"], valid_at=D1,
          invalid_at=D5, ts=D1)
b1 = mrec("b1", salience=0.4, valid_at=D10, ts=D10)
a2 = mrec("a2", salience=0.8, contradicts=["b2"], valid_at=D1, ts=D1)
b2 = mrec("b2", salience=0.6, valid_at=D5, ts=D5)
a3 = mrec("a3", salience=1.0, contradicts=["b3"], ts=D1)
b3 = mrec("b3", salience=0.8, ts=datetime(2026, 1, 2))
rep = monitor([a1, b1, a2, b2, a3, b3])
check("b2m-mixed-arithmetic",
      rep.contradiction_count == 3
      and abs(rep.severity - 0.7) < 1e-9
      and abs(rep.raw_score_unwindowed - 2.1) < 1e-9
      and rep.window_resolved_count == 1
      and rep.window_resolved_pairs == [("a1", "b1")]
      and abs(rep.raw_score - 1.6) < 1e-9
      and abs(rep.score - round(normalize_m(1.6, stakes="medium"), 4)) < 1e-9
      and abs(rep.score_unwindowed - round(normalize_m(2.1, stakes="medium"), 4)) < 1e-9,
      f"raw={rep.raw_score} raw_unw={rep.raw_score_unwindowed} "
      f"M={rep.score} M_unw={rep.score_unwindowed}")

# Audit continuity: the windowed pair's UNwindowed values equal
# its windowless twin's M exactly - adoption moved only what the
# windows license.
a = mrec("a", salience=0.6, contradicts=["b"], valid_at=D1,
         invalid_at=D10, ts=D1)
b = mrec("b", salience=0.4, valid_at=D10, ts=D10)
a2 = mrec("a", salience=0.6, contradicts=["b"], ts=D1)
b2 = mrec("b", salience=0.4, ts=D10)
rw, rn = monitor([a, b]), monitor([a2, b2])
check("b2m-unwindowed-matches-legacy",
      rw.score_unwindowed == rn.score
      and rw.raw_score_unwindowed == rn.raw_score
      and rw.severity == rn.severity
      and rw.score == 0.0 and rn.score > 0)

# Stakes invariance holds for adopted and unwindowed alike (W11).
lo = monitor([a1, b1, a2, b2, a3, b3], stakes="low")
hi = monitor([a1, b1, a2, b2, a3, b3], stakes="high")
check("b2m-stakes-invariant-windowed",
      lo.score == hi.score and lo.raw_score == hi.raw_score
      and lo.score_unwindowed == hi.score_unwindowed
      and lo.raw_score_unwindowed == hi.raw_score_unwindowed)

# Dangling refs unaffected: counted nowhere, windowed or not.
a = mrec("a", contradicts=["ghost", "b"], valid_at=D1,
         invalid_at=D10, ts=D1)
b = mrec("b", valid_at=D10, ts=D10)
rep = monitor([a, b])
check("b2m-dangling-unaffected",
      rep.dangling_refs == ["ghost"] and rep.contradiction_count == 1
      and rep.window_resolved_count == 1)

# No pairs: every window field is zero/empty.
rep = monitor([mrec("a"), mrec("b")])
check("b2m-no-pairs-windowed-zero",
      rep.window_resolved_count == 0 and rep.window_resolved_pairs == []
      and rep.raw_score_unwindowed == 0.0 and rep.score_unwindowed == 0.0
      and rep.raw_score == 0.0 and rep.score == 0.0)

# The notes line names the signal when it fires.
a = mrec("a", contradicts=["b"], valid_at=D1, invalid_at=D10, ts=D1)
b = mrec("b", valid_at=D10, ts=D10)
rep = monitor([a, b])
check("b2m-notes-name-signal",
      any("window-resolved" in n for n in rep.notes))

# ---------------------------------------------------------------------------
# M1 - stock-bench inertness (preregistered STOP condition)
# ---------------------------------------------------------------------------

from evals.decision_bench import gen_suite, task_to_inputs

tasks = gen_suite(300, 7)
violations = []
tasks_with_pairs = 0
for t in tasks:
    _, ranked, _ = task_to_inputs(t)
    rep = monitor([e.record for e in ranked])
    if rep.contradiction_count:
        tasks_with_pairs += 1
    if (rep.window_resolved_count != 0
            or rep.score_unwindowed != rep.score
            or rep.raw_score_unwindowed != rep.raw_score):
        violations.append(t["task_id"])
check("b2m-stock-bench-inert-n300",
      not violations and tasks_with_pairs > 0,
      f"tasks_with_pairs={tasks_with_pairs} violations={violations[:5]}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
