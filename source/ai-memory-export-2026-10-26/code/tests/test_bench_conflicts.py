"""W3-prep test: the decision bench's "conflicting" tasks declare provenance
contradictions, so the Phase-1 conflict monitor reads M>0 on them — and
M=0 on every other variant.

Covers the v0.4 W3-prep bench extension (evals/decision_bench.py):
  - conflicting tasks carry >= 1 declared contradiction pair, referencing
    real, distinct evidence ids;
  - bidirectional wiring dedupes to unique pairs in the monitor;
  - monitor reads M>0 (count>0) on conflicting tasks, M=0 elsewhere;
  - contradiction sets are deterministic across runs (same seed);
  - the extension consumes no rng: non-conflicting variants' evidence and
    gold are byte-identical to the pre-extension generator (verified
    separately against a snapshot; see IMPLEMENTATION-NOTES.md W3-prep).

Run:  python3 tests/test_bench_conflicts.py   (from the repo root)
"""

import sys

sys.path.insert(0, ".")

from evals import decision_bench as db
from mm.confidence import score_options
from mm.resolver import monitor


def records_of(task):
    _, ranked, _ = db.task_to_inputs(task)
    return [re.record for re in ranked]


def main() -> None:
    suite = db.gen_suite(120, seed=7)
    by_variant: dict[str, list] = {}
    for t in suite:
        by_variant.setdefault(t["variant"], []).append(t)
    assert set(by_variant) >= {"standard", "conflicting", "tie", "sparse"}, \
        set(by_variant)
    assert len(by_variant["conflicting"]) >= 5, "need a real conflict slice"

    # 1. Every conflicting task declares >= 1 contradiction over real,
    #    distinct evidence ids; the monitor reads M>0.
    total_pairs = 0
    for t in by_variant["conflicting"]:
        assert len(t["contradictions"]) >= 1, t["task_id"]
        ev_ids = {e[0] for e in t["evidence"]}
        for a, b in t["contradictions"]:
            assert a != b, (t["task_id"], a, b)
            assert a in ev_ids and b in ev_ids, (t["task_id"], a, b)
        r = monitor(records_of(t), stakes="medium")
        assert r.contradiction_count >= 1, (t["task_id"], r)
        assert r.score > 0.0, (t["task_id"], r)
        total_pairs += r.contradiction_count
    print(f"conflicting OK: {len(by_variant['conflicting'])} tasks, "
          f"{total_pairs} counted pairs, all M>0")

    # 2. All other variants: no declarations, monitor reads M=0.
    for variant in ("standard", "tie", "sparse"):
        for t in by_variant[variant]:
            assert t["contradictions"] == [], (variant, t["task_id"])
            r = monitor(records_of(t), stakes="medium")
            assert r.contradiction_count == 0 and r.score == 0.0, \
                (variant, t["task_id"], r)
    n_other = sum(len(by_variant[v]) for v in ("standard", "tie", "sparse"))
    print(f"non-conflicting OK: {n_other} tasks, no declarations, all M=0")

    # 3. Determinism: same seed -> identical contradiction sets.
    s1 = db.gen_suite(120, seed=7)
    s2 = db.gen_suite(120, seed=7)
    assert [t["contradictions"] for t in s1] == \
           [t["contradictions"] for t in s2]
    print("determinism OK: contradiction sets identical across runs")

    # 4. Bidirectional wiring is dedupe-safe: declared unique pairs ==
    #    monitor-counted pairs (both-directions declarations count once).
    t = by_variant["conflicting"][0]
    uniq = {frozenset(p) for p in t["contradictions"]}
    assert len(uniq) == len(t["contradictions"]), "duplicate pairs emitted"
    r = monitor(records_of(t), stakes="medium")
    assert r.contradiction_count == len(uniq), (r, uniq)
    print(f"dedupe OK: {len(uniq)} declared pairs -> "
          f"{r.contradiction_count} counted")

    # 5. End-to-end through the real pipeline: score_options logs the
    #    monitor in every option trace, and scores are UNCHANGED by the
    #    declarations (Phase-1 measurement-only wiring invariant).
    options, ranked, link = db.task_to_inputs(t)

    def link_fn(ev, opt):
        return link.get(ev.record.id, {}).get(opt.id, 0.0)

    scored = score_options(options, ranked, stakes="medium", link_fn=link_fn)
    for s in scored:
        cm = s.ddm_trace["conflict_monitor"]
        assert cm["contradiction_count"] >= 1, cm
        assert cm["score"] > 0.0, cm
    # v0.4 Phase 2: with the controller on, declared conflict moves
    # confidences (that's the feature). The stability invariant is now:
    # controller OFF (kappa=0, lambda_=0) with declarations present ==
    # controller OFF with declarations stripped (measurement-only behavior).
    on_with_decl = score_options(options, ranked, stakes="medium",
                                 link_fn=link_fn)
    off_with_decl = score_options(options, ranked, stakes="medium",
                                  link_fn=link_fn, kappa=0.0, lambda_=0.0)
    for re in ranked:
        re.record.provenance.contradicts.clear()
    off_stripped = score_options(options, ranked, stakes="medium",
                                 link_fn=link_fn, kappa=0.0, lambda_=0.0)
    for a, b in zip(off_with_decl, off_stripped):
        assert a.confidence == b.confidence, (a.confidence, b.confidence)
        assert a.crossed == b.crossed
    # And the controller-on path must actually respond to conflict.
    assert any(a.confidence != b.confidence
               for a, b in zip(on_with_decl, off_with_decl)), \
        "controller had no effect"
    print("pipeline OK: monitor logged (M>0); controller-off stable; "
          "controller-on responds")

    print("\nALL BENCH-CONFLICT TESTS PASSED")


if __name__ == "__main__":
    main()
