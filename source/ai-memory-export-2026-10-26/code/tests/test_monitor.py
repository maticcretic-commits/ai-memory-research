"""v0.4 Phase 1 test: the cheap conflict monitor (measurement-only).

Asserts the monitor contract from V04-CONFLICT-DESIGN.md §3a, as amended
by the W11 founder decision (2026-10-15, stakes-invariant M):
  raw M = contradiction_count × severity (NO stakes multiplier),
  pure counting over MemoryRecord.provenance fields — deterministic,
  no LLM; reported score = normalize_m(raw) (W4 saturating, tau=4.0).
Stakes scales the RESPONSE (DDM bound, penalty pricing), never M:
stakes_weight_for is retained as the response-stage weight.
Also asserts the Phase-1 wiring invariant: the monitor is
computed and logged per decision but changes NOTHING about scores
(the flat 0.3 × conflict_score penalty and select() are untouched).

Run:  python3 tests/test_monitor.py   (from the repo root)
"""

import math
import sys
from datetime import datetime

sys.path.insert(0, ".")

from mm.reflect import MemoryRecord, Provenance
from mm.resolver import (
    monitor, normalize_m, stakes_weight_for, ConflictReport, resolve,
    M_SATURATION_TAU,
)
from mm.confidence import CandidateOption, score_options
from mm.temporal import RankedEvidence


def rec(rid: str, salience: float = 0.5, contradicts: list | None = None,
        supersedes: list | None = None) -> MemoryRecord:
    return MemoryRecord(
        id=rid, text=f"record {rid}", timestamp=datetime.utcnow(),
        salience=salience,
        provenance=Provenance(contradicts=list(contradicts or []),
                              supersedes=list(supersedes or [])),
    )


def main() -> None:
    # 1. Empty record set → zero everywhere.
    r = monitor([], stakes="medium")
    assert isinstance(r, ConflictReport)
    assert (r.score, r.raw_score, r.contradiction_count, r.severity) == (0.0, 0.0, 0, 0.0), r
    print("empty OK: M=0")

    # 2. One declared contradiction: count=1, severity=mean salience,
    #    M = 1 × severity (stakes-invariant W11 — no stakes multiplier).
    a, b = rec("a", salience=0.8, contradicts=["b"]), rec("b", salience=0.6)
    r = monitor([a, b], stakes="medium")
    assert r.contradiction_count == 1, r
    assert r.severity == 0.7, r.severity
    assert r.raw_score == 0.7, r.raw_score
    assert r.stakes_weight == 1.0, r.stakes_weight  # reported, not multiplied
    assert r.score == round(normalize_m(0.7, stakes="medium"), 4), r.score
    assert 0.0 < r.score < r.raw_score, r.score  # saturating, not identity
    assert r.pairs == [("a", "b", 0.7)], r.pairs
    print(f"single-pair OK: M_raw={r.raw_score}, M={r.score}")

    # 3. Bidirectional declaration counts once (dedupe).
    a2 = rec("a", salience=0.8, contradicts=["b"])
    b2 = rec("b", salience=0.6, contradicts=["a"])
    r = monitor([a2, b2])
    assert r.contradiction_count == 1, r
    print("dedupe OK")

    # 4. Self-reference ignored; dangling refs not counted, but reported.
    s = rec("s", contradicts=["s"])
    d = rec("d", contradicts=["ghost"])
    r = monitor([s, d, rec("e")])
    assert r.contradiction_count == 0, r
    assert r.dangling_refs == ["ghost"], r.dangling_refs
    assert any("self-contradiction" in n for n in r.notes), r.notes
    print("self/dangling OK")

    # 5. supersedes is NOT a contradiction (resolved-by-design).
    x = rec("x", supersedes=["y"])
    r = monitor([x, rec("y")])
    assert r.contradiction_count == 0, r
    print("supersedes-not-counted OK")

    # 6. Determinism: input order must not change the report.
    recs = [rec("m1", salience=0.9, contradicts=["m2"]),
            rec("m2", salience=0.3), rec("m3", salience=0.5, contradicts=["m1"])]
    r1 = monitor(recs, stakes="high")
    r2 = monitor(list(reversed(recs)), stakes="high")
    assert r1.score == r2.score and r1.pairs == r2.pairs, (r1, r2)
    # pairs: {m1,m2} sev 0.6, {m1,m3} sev 0.7 → mean 0.65; stakes-invariant
    # W11: NO high-stakes multiplier — raw = 2 × 0.65 regardless of stakes.
    assert r1.raw_score == 2 * 0.65, r1.raw_score
    assert r1.score == round(normalize_m(r1.raw_score, stakes="high"), 4), r1.score
    assert r1.score < r1.raw_score, r1.score
    assert r1.stakes_weight == 4.0, r1.stakes_weight  # reported only
    print(f"determinism OK: high-stakes M_raw={r1.raw_score}, M={r1.score}")

    # 6b. W11 core invariant: same records → same M at EVERY stakes label.
    r_low = monitor(recs, stakes="low")
    r_med = monitor(recs, stakes="medium")
    assert (r_low.raw_score, r_low.score) == (r1.raw_score, r1.score), (r_low, r1)
    assert (r_med.raw_score, r_med.score) == (r1.raw_score, r1.score), (r_med, r1)
    # ...while the response-stage weight still differs (it scales what we
    # DO about M, never M itself).
    assert (r_low.stakes_weight, r_med.stakes_weight, r1.stakes_weight) == (0.5, 1.0, 4.0)
    print("stakes-invariance OK: M identical at low/medium/high")

    # 7. Stakes weight retained for the response stage + unknown stakes error.
    assert stakes_weight_for("low") == 0.5
    assert stakes_weight_for("high") == 4.0
    try:
        monitor([a, b], stakes="extreme")
        raise AssertionError("expected ValueError")
    except ValueError:
        print("stakes validation OK")

    # 8. Normalization (W4): saturating 1 - exp(-raw/tau), tau = 4.0.
    #    Bounds 0 <= M_norm < 1 and strict monotonicity; identity is gone.
    assert M_SATURATION_TAU == 4.0, M_SATURATION_TAU
    assert normalize_m(0.0, stakes="medium") == 0.0
    assert normalize_m(-3.0, stakes="medium") == 0.0  # defensive clamp
    prev = 0.0
    for raw in (0.1, 0.5, 0.7, 2.4, 3.595, 5.2, 7.5, 20.0, 100.0):
        m = normalize_m(raw, stakes="medium")
        assert 0.0 <= m < 1.0, (raw, m)
        assert m > prev, (raw, m, prev)  # strictly increasing
        prev = m
    # Measured W3b range lands mid-scale: mean 3.595 -> ~0.59, max 7.5 -> ~0.85.
    assert abs(normalize_m(3.595, stakes="medium")
               - (1.0 - math.exp(-3.595 / 4.0))) < 1e-9
    assert normalize_m(7.5, stakes="medium") < 0.9
    assert r1.raw_score != r1.score  # no longer identity
    print("normalization OK: saturating, bounded, monotonic")

    # 9. Wiring invariant: the monitor is logged but changes nothing.
    #    Same evidence with and without declared contradictions must score
    #    IDENTICALLY (measurement-only).
    def ev(eid, score, val=1.0):
        return RankedEvidence(record=rec(eid), score=score,
                              signals={"valence": val})

    evidence = [ev("e1", 0.9), ev("e2", 0.7), ev("e3", 0.8, val=-1.0)]
    opts = [CandidateOption(id="o1", description="opt 1", action="do 1"),
            CandidateOption(id="o2", description="opt 2", action="do 2")]
    base = score_options(opts, evidence, stakes="medium",
                       kappa=0.0, lambda_=0.0)  # controller off: v0.3 behavior
    # Now declare contradictions among the same evidence records.
    evidence[0].record.provenance.contradicts.append("e3")
    evidence[2].record.provenance.contradicts.append("e1")
    with_conflict = score_options(opts, evidence, stakes="medium")
    # v0.4 Phase 2: the controller now USES M — confidences change when
    # the monitor fires (that's the point). The wiring invariant is now:
    # with kappa=0 and lambda_=0 (controller disabled), scores are
    # byte-identical to the measurement-only behavior.
    disabled = score_options(opts, evidence, stakes="medium",
                             kappa=0.0, lambda_=0.0)
    for sb, sw in zip(base, disabled):
        assert sb.confidence == sw.confidence, (sb.confidence, sw.confidence)
        assert sb.crossed == sw.crossed
    # ...and with the controller on, the conflict actually bites.
    changed = any(sb.confidence != sw.confidence
                  for sb, sw in zip(with_conflict, disabled))
    assert changed, "Phase-2 controller had no effect on confidences"
    # ...but the monitor report IS logged in every trace.
    for s in with_conflict:
        cm = s.ddm_trace["conflict_monitor"]
        assert cm["contradiction_count"] == 1, cm
        assert cm["raw_score"] == 0.5, cm  # sev 0.5, stakes-invariant W11
        assert cm["score"] == round(normalize_m(0.5, stakes="medium"), 4), cm
        assert "Phase-2 controller" in s.rationale
    print("wiring invariant OK: controller-off = old behavior, "
          f"M={with_conflict[0].ddm_trace['conflict_monitor']['score']}")

    # 10. The controller stays stubbed in Phase 1.
    try:
        resolve([a, b])
        raise AssertionError("expected NotImplementedError")
    except NotImplementedError:
        print("resolve() still stubbed OK")

    print("\nALL MONITOR TESTS PASSED")


if __name__ == "__main__":
    main()
