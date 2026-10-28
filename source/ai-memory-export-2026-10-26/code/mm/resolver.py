"""resolver — deterministic conflict resolver + ACC-style conflict monitor.

v0.4 Phase 1 (SEQUENCED build, 2026-10-15): the cheap MONITOR is now
implemented. The CONTROLLER (tiered strategies low/medium/high) stays
stubbed — `resolve` still raises NotImplementedError.

Contradictory memories must never reach scoring unresolved. Per the v0.2
policy (ACC-style split): a cheap monitor always runs and emits a graded
conflict score (contradiction count × severity — stakes-invariant since
W11, 2026-10-15: stakes scales the response, never the measurement); a
controller picks strategy by score — low → recency supersession, medium →
provenance-weighted adjudication (mnemonic-style bi-temporal
provenance.confidence + supersedes), high → escalate/refuse.
Lazy-vs-eager: ANSWERED — monitor always runs, control invoked by score.

Phase-1 scope (council decision, unanimous sequenced B): the monitor is a
PURE MEASURING INSTRUMENT. It is computed and logged per decision
(mm.confidence attaches its report to every option's ddm_trace) but is
NOT used to adjust confidence — the flat 0.3 × conflict_score penalty in
mm.confidence.metacognitive_review is untouched, and mm.decision.select
is untouched. The graded score exists so Phase 2 can price the penalty
(κ × M × (1−P)) and the bound raise (λ × M) against measured M.

Pattern inspiration: Memori deterministic supersession; hindsight
background reconciliation; LongMemory (W2) conflict-gating; mnemonic
(W4) bi-temporal primitives; honcho dialectic reconciliation (AGPL-3.0 —
reimplement, never copy); neuro track §8 (ACC monitor≠resolver). License:
Soar NOASSERTION vs BSD claim — verify LICENSE.md before any reuse.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from mm.reflect import MemoryRecord


@dataclass
class Supersession:
    """One deterministic resolution event, for the audit trail."""

    winner_id: str
    loser_id: str
    rule: str                        # e.g. "recency-supersession"
    resolved_at: datetime = field(default_factory=datetime.utcnow)
    note: str = ""


def resolve(
    records: list[MemoryRecord],
) -> tuple[list[MemoryRecord], list[Supersession]]:
    """Resolve contradictions deterministically.

    Returns (surviving records, supersession log). Contradicted losers are
    excluded from the surviving set — they never reach the confidence
    scorer. Near-duplicates are merged, not treated as contradictions
    (see TODO).

    TODO (research): precedence-rule details — exact weighting of
    provenance.confidence × recency for old-vs-new claims; conflict-score
    thresholds for the low/medium/high strategy tiers; near-duplicate merge
    vs contradiction-resolve semantics. See ARCHITECTURE.md §4.
    """
    raise NotImplementedError(
        "v0.2 stub — monitor→controller policy defined; implement once "
        "precedence weights and score thresholds are set "
        "(ARCHITECTURE.md §4)."
    )


# ---------------------------------------------------------------------------
# v0.4 Phase 1: the cheap monitor (IMPLEMENTED)
# ---------------------------------------------------------------------------
# Graded conflict score M = contradiction_count × severity — STAKES-INVARIANT
# (W11, 2026-10-15, founder decision): M measures conflict in the evidence
# only. Pure counting over MemoryRecord.provenance fields — deterministic,
# no LLM, no content analysis. A contradiction exists ONLY when a record's
# provenance explicitly declares it (provenance.contradicts lists the other
# record's id). Supersession (provenance.supersedes) is NOT counted: a
# superseded claim is resolved-by-design, not an open contradiction.
#
# Stakes now scales the RESPONSE, not the measurement: STAKES_WEIGHTS /
# stakes_weight_for are retained as the response-stage weight (reported on
# every ConflictReport for Phase-2's κ × M and λ × M pricing), but they no
# longer enter raw M. Rationale (W10 finding): at stakes="high" the 4×
# weight saturated 69.8% of tasks at M=1.0, emptying the lower preregistered
# bands — the bands could not transfer across stakes. Conflict is a
# property of the evidence; stakes is a property of the decision context.

STAKES_WEIGHTS = {
    "low": 0.5,      # everyday tool-choice: conflict response scaled down
    "medium": 1.0,   # default: conflict priced at face value
    "high": 4.0,     # irreversible / high-cost: conflict response amplified
}
# First-cut priors (same convention as STAKES_BOUNDS in mm.confidence):
# inspectable arguments for the eval harness to refine, not final constants.
# W11: these now scale what we DO about M (response stage), never M itself.


def stakes_weight_for(stakes: str) -> float:
    """Map a task-stakes label to the monitor's stakes weight."""
    try:
        return STAKES_WEIGHTS[stakes]
    except KeyError:
        raise ValueError(
            f"unknown stakes {stakes!r}; expected one of {sorted(STAKES_WEIGHTS)}"
        ) from None


@dataclass
class ConflictReport:
    """The monitor's measurement for one decision's record set."""

    score: float                      # normalized M — the graded conflict score
                                      # (B2/W-A adopted: windowed, see below)
    raw_score: float                  # pre-normalization M (see normalize_m)
    contradiction_count: int          # unique declared contradicting pairs
    severity: float                   # mean per-pair severity (0..1),
                                      # over ALL declared pairs (audit basis)
    stakes: str                       # stakes label of the decision context
    stakes_weight: float              # response-stage weight (W11: scales what
                                      # we DO about M, never M itself)
    pairs: list[tuple[str, str, float]] = field(default_factory=list)
    # (record_id_a, record_id_b, pair_severity), sorted for determinism
    # B2 remainder (Benchmark Wave 1 sec. 6 spec; ChatGPT ruling W-A,
    # 2026-10-21): the window-overlap signal, ADOPTED the same day
    # on the preregistered M1/M2 measurements (adoption ruling:
    # b2-remainders-adoption-ruling.txt). A declared pair whose
    # validity windows are DISJOINT was never simultaneously in
    # force - a succession, not a live conflict - and contributes
    # zero to M: score / raw_score above ARE the windowed values
    # (same formula over the overlapping subset). The pre-signal
    # values are retained below for audit. contradiction_count and
    # severity still describe ALL declared pairs.
    window_resolved_pairs: list[tuple[str, str]] = field(default_factory=list)
    # (record_id_a, record_id_b) pairs resolved by window disjointness
    window_resolved_count: int = 0
    raw_score_unwindowed: float = 0.0  # pre-signal raw M (all pairs)
    score_unwindowed: float = 0.0      # normalize_m(raw_score_unwindowed)
    dangling_refs: list[str] = field(default_factory=list)
    # contradicts-ids naming records absent from the input (counted nowhere)
    notes: list[str] = field(default_factory=list)


# Saturation scale for the graded conflict magnitude M (W4, Phase 1).
# Tuned against W3b bench measurements (n=300, seed 7): conflicting tasks
# (n=63) had mean raw M = 3.595 and max = 7.5, all other variants M = 0.
# tau = 4.0 maps the measured mean to ~0.59 and the max to ~0.85 —
# mid-scale with headroom before saturation, preserving discrimination.
# Phase-1 measurement default ONLY: gate (d) requires this scale/cap to be
# fixed and preregistered before Phase-2 measurement runs.
M_SATURATION_TAU = 4.0


def normalize_m(raw_m: float, *, stakes: str) -> float:
    """Saturating normalization for the graded conflict magnitude M.

    M_norm = 1 - exp(-raw / M_SATURATION_TAU).

    Bounds M to [0, 1) while preserving discrimination across the measured
    range: small conflicts stay distinguishable, extreme counts saturate
    instead of growing without bound. raw_m <= 0 maps to 0.0.

    Phase-1 measurement default (W4, 2026-10-15): tau = 4.0 was chosen
    against the W3b bench measurements (n=300, seed 7) — conflicting tasks
    (n=63) had mean raw M = 3.595, max = 7.5, and all other variants M = 0.
    With tau = 4.0 the measured mean maps to ~0.59 and the max to ~0.85:
    the operating range lands mid-scale with headroom before saturation.
    This scale/cap is NOT preregistered — ChatGPT's gate (d) requires the
    high-stakes margin AND M's cap/scale to be fixed and preregistered
    before Phase-2 measurement runs; revisit tau then. See
    V04-CONFLICT-DESIGN.md (the design's open tunable) and
    gate-criteria-chatgpt.md gate (d).

    The report carries BOTH raw and normalized values so Phase-2
    calibration can re-fit the scheme against the bench.

    W11 (2026-10-15, founder decision): M is stakes-invariant — the same
    record set yields the same raw and normalized M at any stakes label.
    Stakes now scales only the response (DDM bound, penalty pricing).
    """
    _ = stakes  # reserved: per-stakes schemes (z-scoring) will use this
    raw = max(0.0, raw_m)
    return 1.0 - math.exp(-raw / M_SATURATION_TAU)


def _window_of(rec: MemoryRecord) -> tuple[datetime, datetime | None]:
    """Effective validity window [start, end) of one record (B2):
    start = valid_at if set, else the record's own timestamp (the
    episodic fallback, mm.episodic.valid_at_instant); end =
    invalid_at, None = still in force (open-ended)."""
    return (rec.valid_at or rec.timestamp), rec.invalid_at


def _windows_overlap(a: MemoryRecord, b: MemoryRecord) -> bool:
    """True iff the two records were in force at some common
    instant. Half-open intervals, end-exclusive: end_a == start_b
    is DISJOINT (a supersession succession - the loser's window
    closes exactly when the winner's opens). A None end is
    open-ended and overlaps everything from its start on."""
    start_a, end_a = _window_of(a)
    start_b, end_b = _window_of(b)
    if end_a is not None and start_b >= end_a:
        return False
    if end_b is not None and start_a >= end_b:
        return False
    return True


def _pair_severity(a: MemoryRecord, b: MemoryRecord) -> float:
    """Severity of one contradiction pair: mean salience of the two records.

    Salience (0..1, "importance independent of recency") is the only
    importance signal on MemoryRecord today, so it prices severity with no
    invented mechanism: a contradiction between two high-salience records
    is more severe than one between trivia. Clamped to [0, 1].
    """
    return max(0.0, min(1.0, (a.salience + b.salience) / 2.0))


def monitor(
    records: list[MemoryRecord],
    stakes: str = "medium",
) -> ConflictReport:
    """Run the cheap ACC-style conflict monitor over a record set.

    Always runs; emits a graded conflict score. Pure counting over
    provenance fields — deterministic (no randomness, no LLM, no text
    analysis). Cost is O(n + d) in records + declared relations.

    Counting rule: a contradiction is one unique unordered pair {a, b},
    a ≠ b, both present in `records`, where a.provenance.contradicts
    names b.id or b.provenance.contradicts names a.id. Both-directions
    declarations count once. Self-references are ignored. References to
    ids absent from `records` are reported as dangling_refs, counted
    nowhere (a contradiction needs two measured sides for severity).

    B2 remainder (2026-10-21, ChatGPT ruling W-A, ADOPTED on the
    preregistered M1/M2 measurements): M is computed over only
    the pairs whose validity windows overlap (disjoint windows =
    never simultaneously in force = a succession, not a live
    conflict). The pre-signal M is retained on the report as
    score_unwindowed / raw_score_unwindowed for audit.

    Returns a ConflictReport with the graded score M (and the raw score
    pre-normalization, for Phase-2 calibration).
    """
    weight = stakes_weight_for(stakes)  # raises ValueError on unknown stakes
    by_id: dict[str, MemoryRecord] = {r.id: r for r in records}

    seen: set[frozenset[str]] = set()
    pairs: list[tuple[str, str, float]] = []
    dangling: set[str] = set()
    notes: list[str] = []

    for rec in records:
        for target_id in rec.provenance.contradicts:
            if target_id == rec.id:
                notes.append(f"ignored self-contradiction on {rec.id!r}")
                continue
            other = by_id.get(target_id)
            if other is None:
                dangling.add(target_id)
                continue
            key = frozenset((rec.id, target_id))
            if key in seen:
                continue
            seen.add(key)
            a_id, b_id = sorted((rec.id, target_id))
            sev = _pair_severity(by_id[a_id], by_id[b_id])
            pairs.append((a_id, b_id, round(sev, 4)))

    pairs.sort()  # deterministic order regardless of input order
    count = len(pairs)
    severity = round(sum(s for _, _, s in pairs) / count, 4) if count else 0.0
    # W11 (stakes-invariant M, founder decision 2026-10-15): raw M counts
    # conflict in the evidence ONLY — no stakes multiplier. `weight` is
    # validated above and reported on the report for the response stage
    # (Phase-2 prices the penalty/bound raise as κ × M × weight, etc.),
    # but it never enters M itself.
    raw_unwindowed = count * severity
    score_unwindowed = normalize_m(raw_unwindowed, stakes=stakes)

    # B2 window-overlap signal (ruling W-A; ADOPTED 2026-10-21 on
    # the preregistered M1/M2 measurements): M is the same formula
    # restricted to pairs whose validity windows overlap. Disjoint
    # pairs are successions, not live conflicts, and contribute
    # zero. On windowless record sets every window is open-ended,
    # nothing resolves, and M is identical to the pre-signal value
    # (M1: 1,957 bench pairs, max delta 0.0).
    resolved_pairs: list[tuple[str, str]] = []
    live_severities: list[float] = []
    for a_id, b_id, sev in pairs:
        if _windows_overlap(by_id[a_id], by_id[b_id]):
            live_severities.append(sev)
        else:
            resolved_pairs.append((a_id, b_id))
    live_count = len(live_severities)
    severity_windowed = (round(sum(live_severities) / live_count, 4)
                         if live_count else 0.0)
    raw = live_count * severity_windowed
    score = normalize_m(raw, stakes=stakes)

    if dangling:
        notes.append(
            f"{len(dangling)} dangling contradicts-ref(s) to records absent "
            f"from this set (not counted): {sorted(dangling)}"
        )
    notes.append(
        f"monitor v0.4-phase1: {count} contradiction(s), mean severity "
        f"{severity:.2f}, stakes {stakes!r} (response weight {weight}) → "
        f"M_raw={raw:.3f}, M={score:.3f} [stakes-invariant W11]"
    )
    if resolved_pairs:
        notes.append(
            f"window-overlap signal (B2/W-A, adopted): "
            f"{len(resolved_pairs)} pair(s) window-resolved (disjoint "
            f"validity windows - never simultaneously in force); "
            f"M_unwindowed={score_unwindowed:.3f} vs M={score:.3f} "
            f"[score IS the windowed value per adoption ruling]"
        )
    return ConflictReport(
        score=round(score, 4),
        raw_score=round(raw, 4),
        contradiction_count=count,
        severity=severity,
        stakes=stakes,
        stakes_weight=weight,
        pairs=pairs,
        window_resolved_pairs=resolved_pairs,
        window_resolved_count=len(resolved_pairs),
        raw_score_unwindowed=round(raw_unwindowed, 4),
        score_unwindowed=round(score_unwindowed, 4),
        dangling_refs=sorted(dangling),
        notes=notes,
    )
