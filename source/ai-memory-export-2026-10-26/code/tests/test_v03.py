"""v0.3 smoke test: the full memory → DECISION cycle on a toy scenario.

Scenario: an agent must pick a launch action for a kids' colouring book.
Three candidates, three evidence items, one negative constraint, one
rejected-choice record. Asserts the cycle behaves as the spec says:

  propose → inject_rejections → valuate → DDM accumulate → confidence →
  metacognition → preference votes → select (Soar) — with impasse on a tie.

Run:  python3 tests/test_v03.py   (from the repo root)
"""

import sys
from datetime import datetime

sys.path.insert(0, ".")

from mm.confidence import (
    CandidateOption, score_options, CalibrationLog, bound_for_stakes,
)
from mm.decision import (
    Candidate, Preference, RejectedChoiceRecord, Decision,
    inject_rejections, select,
)
from mm.temporal import RankedEvidence
from mm.reflect import MemoryRecord
from mm.constraints import NegativeConstraint


def ev(eid: str, score: float, valence: float = 1.0, salience: float = 0.5) -> RankedEvidence:
    return RankedEvidence(
        record=MemoryRecord(id=eid, text=f"evidence {eid}",
                            timestamp=datetime.utcnow(), salience=salience),
        score=score,
        signals={"valence": valence},
    )


def main() -> None:
    # 1. Propose candidates.
    candidates = [
        Candidate(id="amazon-kdp", description="Launch on Amazon KDP print",
                  action="publish kdp paperback 8.5x11"),
        Candidate(id="etsy-digital", description="Sell digital PDFs on Etsy",
                  action="list etsy digital bundle"),
        Candidate(id="whatsapp-pdf", description="Sell via WhatsApp PDF",
                  action="sell whatsapp pdf direct"),
    ]

    # 2. selvedge injection: one prior rejection (whatsapp-pdf was tried and
    #    judged too manual) → pruned. A second record names a change
    #    condition → flagged, not pruned.
    records = [
        RejectedChoiceRecord(
            entity_key="whatsapp-pdf",
            rejected_approach="sell whatsapp pdf direct",
            rationale="manual fulfillment doesn't scale past 20 orders/day",
        ),
        RejectedChoiceRecord(
            entity_key="etsy-digital",
            rejected_approach="list etsy digital bundle",
            rationale="digital can't sell to Indian buyers on Etsy",
            what_would_change_your_mind="export-first catalog ready",
        ),
    ]
    survivors, inj_log = inject_rejections(candidates, records)
    assert [c.id for c in survivors] == ["amazon-kdp", "etsy-digital"], survivors
    assert any("PRUNED whatsapp-pdf" in l for l in inj_log), inj_log
    assert any("FLAGGED etsy-digital" in l for l in inj_log), inj_log
    print("inject_rejections OK:", *inj_log, sep="\n  ")

    # 3. Score the survivors: kdp has strong supporting evidence; etsy has
    #    weaker, mixed evidence. A negative constraint matches etsy's
    #    digital-to-India pattern → pruned with audit trail.
    evidence = [
        ev("e1", 0.9, valence=1.0, salience=0.9),   # strong support
        ev("e2", 0.7, valence=1.0, salience=0.6),
        ev("e3", 0.8, valence=-1.0, salience=0.7),  # strong opposition
        ev("e4", 0.9, valence=1.0, salience=0.8),   # strong support
    ]
    constraints = [
        NegativeConstraint(
            id="c-india-digital", description="Etsy digital can't sell to IN buyers",
            failed_pattern="etsy digital", severity=0.8),
    ]

    # Link function: e1/e2/e4 support amazon-kdp, e3 opposes etsy-digital.
    def link(e, o):
        if o.id == "amazon-kdp" and e.record.id in ("e1", "e2", "e4"):
            return 1.0
        if o.id == "etsy-digital" and e.record.id == "e3":
            return 1.0
        return 0.0

    options = [CandidateOption(id=c.id, description=c.description, action=c.action)
               for c in survivors]
    # Add a weak fourth candidate: not enough evidence to cross the bound.
    weak = CandidateOption(id="hold", description="Wait and do nothing",
                           action="defer launch")
    scored = score_options(options + [weak], evidence, constraints,
                           stakes="medium", link_fn=link,
                           kappa=0.0, lambda_=0.0)  # v0.3 mode
    by_id = {s.option.id: s for s in scored}
    assert by_id["etsy-digital"].pruned_by_constraint == "c-india-digital"
    assert by_id["etsy-digital"].confidence == 0.0
    kdp = by_id["amazon-kdp"]
    assert kdp.crossed, kdp.ddm_trace
    assert kdp.confidence > 0.7, kdp.confidence
    assert kdp.ddm_trace["bound"] == bound_for_stakes("medium") == 2.0
    assert len(kdp.ddm_trace["path"]) == kdp.ddm_trace["cross_step"] + 1
    print(f"DDM OK: kdp confidence={kdp.confidence}, "
          f"cross_step={kdp.ddm_trace['cross_step']}, "
          f"margin={kdp.ddm_trace['margin']:.2f}")
    print("rationale:", kdp.rationale)
    # No-cross path: weak evidence never reaches the bound → undecided 0.35.
    weak_scored = by_id["hold"]
    assert not weak_scored.crossed
    assert weak_scored.confidence == 0.35, weak_scored.confidence
    print("no-cross OK: hold -> confidence 0.35 (impasse material)")

    # 4. Calibration + metacognition: with history saying 0.9-stated is
    #    right 60% of the time, the adjusted score shrinks toward 0.6.
    cal = CalibrationLog(min_samples=2)
    for _ in range(3):
        cal.record(0.72, False)
    for _ in range(2):
        cal.record(0.72, True)
    rescored = score_options(options, evidence, constraints,
                             stakes="medium", link_fn=link, calibration=cal,
                             kappa=0.0, lambda_=0.0)  # v0.3 mode
    meta_kdp = [s for s in rescored if s.option.id == "amazon-kdp"][0]
    assert meta_kdp.confidence < kdp.confidence, \
        (meta_kdp.confidence, kdp.confidence)
    print(f"metacognition OK: {kdp.confidence} -> {meta_kdp.confidence} "
          f"(history 0.60)")

    # 5. Soar select: kdp gets better votes, etsy is prohibited → kdp wins.
    votes = [
        Preference(candidate_id="amazon-kdp", kind="better", weight=2.0,
                   source_module="temporal", reason="evidence fusion favors"),
        Preference(candidate_id="etsy-digital", kind="prohibit",
                   source_module="constraints", reason="India digital gate"),
    ]
    decision: Decision = select(survivors, votes)
    assert decision.selected_id == "amazon-kdp", decision
    assert decision.excluded_ids == ["etsy-digital"], decision
    assert decision.impasse is None
    print("select OK: selected", decision.selected_id)

    # 6. Tie impasse: two candidates with equal votes → tie, with a subgoal.
    tie_votes = [
        Preference(candidate_id="amazon-kdp", kind="better", weight=1.0),
        Preference(candidate_id="etsy-digital", kind="better", weight=1.0),
    ]
    d2 = select([Candidate(id="amazon-kdp", description=""),
                 Candidate(id="etsy-digital", description="")],
                [v for v in tie_votes])
    assert d2.impasse is not None and d2.impasse.kind == "tie", d2
    assert "gather more evidence" in d2.impasse.suggested_subgoal
    print("tie impasse OK:", d2.impasse.detail)

    # 7. Conflict impasse.
    d3 = select(survivors, votes, conflict_score=0.9)
    assert d3.impasse is not None and d3.impasse.kind == "conflict", d3
    print("conflict impasse OK:", d3.impasse.detail)

    # 8. Calibration log round-trips through JSON.
    cal2 = CalibrationLog.load_json(cal.to_json())
    assert cal2.reliability(0.9) == cal.reliability(0.9)
    print("calibration persistence OK")

    print("\nALL v0.3 TESTS PASSED")


if __name__ == "__main__":
    main()
