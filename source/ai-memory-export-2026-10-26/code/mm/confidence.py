"""confidence — confidence scorer: calibrated scores over ranked options.

v0.3 IMPLEMENTED (2026-10-14): the v0.2 algebra is now running code.
OFC-style valuation maps each candidate's heterogeneous evidence to a
common drift scale; drift-diffusion accumulation runs per candidate toward
a caution bound set by task stakes; confidence = f(crossing margin,
total evidence, accumulation time); a second-order metacognitive pass
adjusts the decider's score against historical accuracy; (stated
confidence, outcome) pairs feed a CalibrationLog.

First-cut parameter choices (bound heights, stake mapping, drift weights)
are documented below as tunable priors — the eval harness (evals/) is
expected to refine them against real decision data. Nothing here is a
final constant; every one is an inspectable argument.

Pattern inspiration: agentmemory / hippo-memory / memoripy confidence-scored
evidence (W1–W3); hindsight disposition traits as decision-posture knobs;
neuro track §§7, 9, 10 (Ratcliff; Padoa-Schioppa OFC; Fleming 2024).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from mm.temporal import RankedEvidence
from mm.constraints import NegativeConstraint
from mm.resolver import monitor as _conflict_monitor  # v0.4 Phase 1: measurement-only wiring


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class CandidateOption:
    """One option proposed by the agent planner, awaiting scoring."""

    id: str
    description: str
    action: str = ""                 # proposed action / tool call sketch


@dataclass
class ScoredOption:
    """A ranked, confidence-scored option with its audit trail."""

    option: CandidateOption
    confidence: float                # 0..1 — calibrated via DDM + metacognitive pass
    evidence_ids: list[str] = field(default_factory=list)
    rationale: str = ""
    pruned_by_constraint: str = ""   # constraint id if a negative constraint killed it
    audit_ref: str = ""
    ddm_trace: dict = field(default_factory=dict)  # evidence stream, bound, crossing margin
    crossed: bool = True             # False → no evidence crossed the bound (impasse-ish)


# ---------------------------------------------------------------------------
# Caution bound: stakes → bound height (tunable prior, v0.3)
# ---------------------------------------------------------------------------
# The bound is in drift units: the sum of |evidence drift| needed to force
# a decision. High-stakes decisions demand more evidence before they cross.
# These are first cuts; evals calibrate them.

STAKES_BOUNDS = {
    "low": 1.0,      # everyday tool-choice: a couple of weak signals decide
    "medium": 2.0,   # default: a few solid pieces of evidence required
    "high": 4.0,     # irreversible / high-cost: strong accumulation required
}


def bound_for_stakes(stakes: str) -> float:
    """Map a task-stakes label to a DDM caution bound height."""
    try:
        return STAKES_BOUNDS[stakes]
    except KeyError:
        raise ValueError(
            f"unknown stakes {stakes!r}; expected one of {sorted(STAKES_BOUNDS)}"
        ) from None


# ---------------------------------------------------------------------------
# OFC-style valuation: heterogeneous evidence → common drift scale
# ---------------------------------------------------------------------------
# Each evidence item becomes a signed drift contribution:
#   drift_i = weight * relevance * score * valence
# - score    : RankedEvidence.score (0..1, combined recency×salience×fusion)
# - valence  : +1 supporting, -1 opposing. Read from
#              evidence.signals.get("valence") when present; defaults +1.
#              (Constraint penalties arrive here as opposing drift too,
#              via the scorer — constraints.py's pruned items never do.)
# - relevance: how much this item bears on THIS option, from link_fn.
# - weight   : per-signal importance; default 1.0 (learn from calibration
#              data later — ARCHITECTURE.md §7 open question).

def valuate(evidence: RankedEvidence, relevance: float, weight: float = 1.0) -> float:
    """Map one heterogeneous evidence item to signed drift."""
    valence = float(evidence.signals.get("valence", 1.0))
    valence = max(-1.0, min(1.0, valence))
    return weight * max(0.0, relevance) * evidence.score * valence


def default_link(evidence: RankedEvidence, option: CandidateOption) -> float:
    """Default evidence→option relevance: full relevance.

    Deliberately naive. Callers that know their domain should pass a real
    link_fn (embedding similarity, entity overlap, explicit option tags).
    The naive default makes scores conservative: every candidate sees every
    evidence item, so only drift *direction* separates them.
    """
    return 1.0


# ---------------------------------------------------------------------------
# Drift-diffusion accumulation (per candidate)
# ---------------------------------------------------------------------------

def accumulate(drift_stream: list[tuple[str, float]], bound: float) -> dict:
    """Run DDM accumulation over an ordered drift stream.

    drift_stream: list of (evidence_id, drift). Ordered strongest-first by
    the caller — urgent evidence accumulates first (mirrors biological
    priority: salient signals drive the accumulator early).

    Returns a trace dict: the x(t) path, bound, crossing point, margin,
    steps taken, total evidence mass. First crossing of ±bound wins;
    reaching the end of the stream without crossing returns crossed=False
    (the decision module treats this as impasse material).
    """
    x = 0.0
    path = [x]
    steps = 0
    mass = 0.0
    for ev_id, drift in drift_stream:
        steps += 1
        x += drift
        mass += abs(drift)
        path.append(x)
        if abs(x) >= bound:
            margin = abs(x) - bound
            return {
                "bound": bound,
                "path": path,
                "evidence_order": [e for e, _ in drift_stream[:steps]],
                "crossed": True,
                "cross_step": steps,
                "margin": margin,
                "total_evidence": mass,
                "direction": 1 if x > 0 else -1,
            }
    return {
        "bound": bound,
        "path": path,
        "evidence_order": [e for e, _ in drift_stream],
        "crossed": False,
        "cross_step": steps,
        "margin": 0.0,
        "total_evidence": mass,
        "direction": 1 if x >= 0 else -1,
    }


def _logistic(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def confidence_from_trace(trace: dict) -> float:
    """confidence = f(crossing margin, total evidence, accumulation time).

    Fast crossing on strong drift → high confidence. Slow grind near the
    bound → low confidence. Contradictory evidence (low decisiveness)
    pulls it down even when the bound is crossed. No crossing →
    undecided (0.35), never 0: an undecided option still holds the prior
    evidence mass.

    z combines: margin-per-bound-per-step (speed), net/total drift
    (decisiveness: 1.0 when all evidence agrees, 0 when balanced),
    saturating evidence mass, and a per-step time penalty. Logistic maps
    to 0..1. Coefficients are v0.3 priors — the eval harness tunes them.
    """
    if not trace["crossed"]:
        return 0.35
    bound = trace["bound"]
    margin = trace["margin"]
    steps = trace["cross_step"]
    mass = trace["total_evidence"]
    net = abs(trace["path"][-1])          # drift at crossing
    decisiveness = (net / mass) if mass > 0 else 0.0
    speed = margin / (bound * (1 + steps))
    z = (4.0 * speed
         + 2.0 * decisiveness
         + 0.3 * math.log1p(mass)
         - 0.08 * steps
         - 1.4)
    return _logistic(z)


# ---------------------------------------------------------------------------
# Phase-2 controller tunables (§3b, §3c) — v0.4 Phase 2 (2026-10-16)
# ---------------------------------------------------------------------------
# KAPPA: §3b conflict-penalty scale. Penalty = κ × M × (1 − P).
# LAMBDA: §3c bound-raise rate. Effective bound = stakes_bound + λ × M.
# TEMP: post-hoc confidence recalibration (temperature scaling).
#   p_calibrated = logistic(logit(p) / TEMP). Fixes overconfidence from
#   the combined κ+λ intervention (gate-(b) fix, 2026-10-16; T=2.0 tuned
#   on seed-7 bench, Brier 0.242 vs uncalibrated).
# All are tunable priors — the tuning step refines them on non-gate data
# and the frozen values are recorded in the gate-(d) preregistration.
# Gate (b) factorial: §3b "off" = kappa=0; §3c "off" = lambda_=0.
# FROZEN 2026-10-16 (tuned on seed-7 bench + held-out 120, non-gate data):
#   κ=0.25, λ=2.5 → conflicting acc 0.413→0.683 (bench), 0.275→0.692
#   (held-out); standard no regression (0.624). λ plateaus ≥2.5.

KAPPA = 0.25
LAMBDA = 2.5
TEMP = 2.0


def recalibrate(p: float, temp: float = TEMP) -> float:
    """Temperature scaling for confidence recalibration.

    p_calibrated = logistic(logit(p) / temp). temp > 1 softens
    overconfident predictions; temp = 1 is identity. Applied to the final
    confidence after the metacognitive pass (Phase-2 pipeline).
    """
    p = max(1e-6, min(1 - 1e-6, p))
    return _logistic(math.log(p / (1 - p)) / temp)


def evidence_precision(evidence: list[RankedEvidence],
                       drift_stream: list[tuple[str, float]]) -> float:
    """Evidence precision P for one option (§3b).

    P = provenance.confidence × recency_weight × corroboration, each 0..1:
    - provenance.confidence: mean source reliability over supporting evidence
      (Provenance.confidence, default 1.0).
    - recency_weight: mean RankedEvidence.score over supporting evidence
      (score already combines recency × salience × fusion).
    - corroboration: supporting drift mass / total absolute drift mass
      (fraction of the evidence stream agreeing with this option).

    Supporting = drift > 0 for this option. Returns 0.0 when nothing
    supports the option (maximal penalty) — never negative, never > 1.
    """
    if not drift_stream:
        return 0.0
    supporting = [(ev_id, d) for ev_id, d in drift_stream if d > 0]
    if not supporting:
        return 0.0
    ev_by_id = {ev.record.id: ev for ev in evidence}
    sup_evs = [ev_by_id[ev_id] for ev_id, _ in supporting if ev_id in ev_by_id]
    if not sup_evs:
        return 0.0
    prov_conf = sum(ev.record.provenance.confidence for ev in sup_evs) / len(sup_evs)
    recency_w = sum(ev.score for ev in sup_evs) / len(sup_evs)
    total_abs = sum(abs(d) for _, d in drift_stream)
    corroboration = (sum(d for _, d in supporting) / total_abs) if total_abs > 0 else 0.0
    return max(0.0, min(1.0, prov_conf * recency_w * corroboration))


# ---------------------------------------------------------------------------
# Calibration infrastructure: (stated confidence, outcome) pairs
# ---------------------------------------------------------------------------

class CalibrationLog:
    """Append-only log of (stated confidence, observed outcome) pairs.

    Binned reliability: bin index = int(stated * 10). `reliability(bin)`
    returns the empirical hit-rate in that bin, or None when the bin has
    fewer than `min_samples` observations (calibration needs data).
    Persist with to_json / load_json.
    """

    def __init__(self, min_samples: int = 5):
        self.min_samples = min_samples
        self.pairs: list[tuple[float, bool]] = []
        # HD-2 supporting change (2026-10-20): per-pair conflict score M,
        # parallel to pairs (None when unknown). Real decision pairs need
        # their M to feed the per-M-band isotonic fit; without it the
        # real-data contract cannot be banded. Additive: old payloads
        # load with all-None M.
        self.m_values: list[float | None] = []

    def record(self, stated_confidence: float, outcome: bool,
               m: float | None = None) -> None:
        self.pairs.append((float(stated_confidence), bool(outcome)))
        self.m_values.append(None if m is None else float(m))

    def triples(self) -> list[tuple[float, bool, float]]:
        """(stated, outcome, m) for pairs whose M is known - the input
        shape IsotonicCalibrator.fit() takes."""
        return [(s, o, m) for (s, o), m in zip(self.pairs, self.m_values)
                if m is not None]

    def _bin(self, stated: float) -> int:
        return max(0, min(9, int(float(stated) * 10)))

    def reliability(self, stated: float) -> float | None:
        b = self._bin(stated)
        hits = [o for s, o in self.pairs if self._bin(s) == b]
        if len(hits) < self.min_samples:
            return None
        return sum(hits) / len(hits)

    def overall(self) -> dict:
        if not self.pairs:
            return {"n": 0}
        bins = {}
        for i in range(10):
            hits = [o for s, o in self.pairs if self._bin(s) == i]
            if hits:
                bins[i] = {"n": len(hits), "hit_rate": sum(hits) / len(hits)}
        return {"n": len(self.pairs), "bins": bins}

    def to_json(self) -> str:
        return json.dumps({"min_samples": self.min_samples,
                           "pairs": self.pairs,
                           "m_values": self.m_values})

    @classmethod
    def load_json(cls, payload: str) -> "CalibrationLog":
        data = json.loads(payload)
        log = cls(min_samples=data.get("min_samples", 5))
        log.pairs = [(float(s), bool(o)) for s, o in data["pairs"]]
        mv = data.get("m_values", [None] * len(log.pairs))
        log.m_values = [None if m is None else float(m) for m in mv]
        return log


# ---------------------------------------------------------------------------
# Second-order (metacognitive) pass
# ---------------------------------------------------------------------------
# The metacognitive scorer never asks the decider how sure it is. It
# reviews only the trace: crossing speed, margin, conflict score, and the
# historical accuracy of *similar past decisions* from the calibration log
# (binned by speed×margin bucket). Adjustment is shrinkage toward history:
#   conf2 = 0.7 * conf1 + 0.3 * historical_accuracy
# plus a conflict penalty. When there is no calibration history, the pass
# only applies the conflict penalty and reports that history was absent.

def metacognitive_review(
    raw_confidence: float,
    trace: dict,
    conflict_score: float = 0.0,
    precision: float = 1.0,
    kappa: float = KAPPA,
    calibration: CalibrationLog | None = None,
) -> dict:
    """Second-order review of a decision trace. Returns adjusted score.

    v0.4 Phase 2 (§3b): the flat 0.3 × conflict penalty is replaced by the
    precision-weighted penalty κ × M × (1 − P).
    - conflict_score: the monitor's graded conflict magnitude M (0..1).
    - precision: evidence precision P for this option (0..1) — when the
      winning side's evidence is precise (P → 1), conflict is resolved
      disagreement and barely dents confidence; when both sides are mushy
      (P → 0), the full κ × M penalty applies.
    - kappa: penalty scale (0 disables the §3b intervention — gate (b) "off").
    """
    hist = calibration.reliability(raw_confidence) if calibration else None
    adjusted = raw_confidence
    notes = []
    if hist is not None:
        adjusted = 0.7 * raw_confidence + 0.3 * hist
        notes.append(f"shrank toward historical accuracy {hist:.2f}")
    else:
        notes.append("no calibration history; score unadjusted by history")
    if conflict_score > 0 and kappa > 0:
        penalty = kappa * conflict_score * (1.0 - precision)
        adjusted = max(0.05, adjusted - penalty)
        notes.append(f"conflict penalty -{penalty:.2f} "
                     f"(κ={kappa}, M={conflict_score:.2f}, P={precision:.2f})")
    return {
        "raw_confidence": raw_confidence,
        "adjusted_confidence": adjusted,
        "historical_accuracy": hist,
        "conflict_score": conflict_score,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# The scorer: prune → valuate → accumulate → metacognition → rank
# ---------------------------------------------------------------------------

def _constraint_matches(constraint: NegativeConstraint, option: CandidateOption) -> bool:
    """Known-bad pattern matching: substring, case-insensitive.

    First-cut matcher (ARCHITECTURE.md §3 open question: task_signature
    granularity). Conservative direction: matches must be literal enough
    to audit — a human can read the pattern and the option side by side.
    """
    haystack = (option.action + " " + option.description).lower()
    return constraint.failed_pattern.lower() in haystack


def score_options(
    options: list[CandidateOption],
    evidence: list[RankedEvidence],
    constraints: list[NegativeConstraint] | None = None,
    *,
    stakes: str = "medium",
    link_fn=default_link,
    conflict_score: float = 0.0,
    calibration: CalibrationLog | None = None,
    kappa: float = KAPPA,
    lambda_: float = LAMBDA,
    temp: float = TEMP,
) -> list[ScoredOption]:
    """Score and rank candidate options by calibrated confidence.

    Pipeline: prune options matching negative constraints → run the
    conflict monitor (measurement) → valuate each surviving option's
    evidence to a drift stream (OFC-style) → accumulate per candidate to
    the caution bound (DDM, §3c-raised under conflict) → confidence from
    the trace → metacognitive pass (§3b precision-weighted conflict
    penalty) → rank descending.

    v0.4 Phase 2: the monitor's M now FEEDS the decision (was
    measurement-only in Phase 1):
    - §3b: metacognitive_review applies κ × M × (1 − P) instead of the
      flat 0.3 × conflict_score. kappa=0 disables the cut (gate (b) off).
    - §3c: the DDM caution bound is raised by λ × M — the system
      deliberates longer under conflict. lambda_=0 disables the raise.
    The legacy `conflict_score` kwarg is superseded by the monitor's M;
    kept for backward compatibility.

    Pruned options are returned too, marked with `pruned_by_constraint`
    and confidence 0.0, so a human can audit and overrule.

    Returns options ranked by confidence descending.
    """
    # v0.4 Phase 2: the conflict monitor's M feeds the controller.
    # W11 invariant holds: M itself is stakes-invariant (no stakes
    # multiplier in the measurement); stakes scales the RESPONSE here
    # (the DDM caution bound), never the measurement.
    monitor_report = _conflict_monitor([e.record for e in evidence],
                                       stakes=stakes)
    m_score = monitor_report.score
    # §3c: raise the caution bound under conflict (EVC — slow down).
    bound = bound_for_stakes(stakes) + lambda_ * m_score
    # Recalibration applies only when the controller is active; with the
    # controller off (kappa=0, lambda_=0), the v0.3 calibration holds.
    if kappa == 0 and lambda_ == 0:
        temp = 1.0
    monitor_trace = {
        "score": monitor_report.score,
        "raw_score": monitor_report.raw_score,
        "contradiction_count": monitor_report.contradiction_count,
        "severity": monitor_report.severity,
        "stakes": monitor_report.stakes,
        "stakes_weight": monitor_report.stakes_weight,
        "pairs": [list(p) for p in monitor_report.pairs],
        "dangling_refs": monitor_report.dangling_refs,
        "notes": monitor_report.notes,
        "bound_raise": round(lambda_ * m_score, 4),
        "kappa": kappa,
    }
    scored: list[ScoredOption] = []
    for option in options:
        pruned = ""
        if constraints:
            for c in constraints:
                if _constraint_matches(c, option):
                    pruned = c.id
                    break
        if pruned:
            scored.append(ScoredOption(
                option=option,
                confidence=0.0,
                rationale=f"Pruned by negative constraint {pruned}: "
                          "matches a known-failed pattern. Human overrule "
                          "available from this trail.",
                pruned_by_constraint=pruned,
                crossed=False,
                ddm_trace={"conflict_monitor": monitor_trace},
            ))
            continue

        # Valuation → drift stream, strongest evidence first.
        stream: list[tuple[str, float]] = []
        for ev in evidence:
            relevance = link_fn(ev, option)
            drift = valuate(ev, relevance)
            stream.append((ev.record.id, drift))
        stream.sort(key=lambda t: abs(t[1]), reverse=True)

        trace = accumulate(stream, bound)
        raw = confidence_from_trace(trace)
        # §3b: precision-weighted conflict penalty — P from THIS option's
        # evidence, M from the monitor (shared across options).
        precision = evidence_precision(evidence, stream)
        review = metacognitive_review(
            raw, trace,
            conflict_score=m_score,
            precision=precision,
            kappa=kappa,
            calibration=calibration,
        )
        conf = recalibrate(review["adjusted_confidence"], temp)

        ev_ids = trace["evidence_order"]
        top3 = ", ".join(ev_ids[:3]) if ev_ids else "no evidence"
        rationale = (
            f"DDM: {'crossed' if trace['crossed'] else 'no crossing'} the "
            f"{stakes}-stakes bound ({bound}) at step {trace['cross_step']} "
            f"with margin {trace['margin']:.2f}; evidence mass "
            f"{trace['total_evidence']:.2f}. Top evidence: {top3}. "
            + "; ".join(review["notes"]) + "."
            + f" Conflict monitor (Phase-2 controller): M={m_score:.2f} "
            f"({monitor_report.contradiction_count} contradictions), "
            f"P={precision:.2f}, bound raised +{monitor_trace['bound_raise']:.2f}."
        )
        scored.append(ScoredOption(
            option=option,
            confidence=round(conf, 4),
            evidence_ids=ev_ids,
            rationale=rationale,
            ddm_trace={
                "bound": bound,
                "stakes": stakes,
                "path": [round(x, 4) for x in trace["path"]],
                "evidence_order": ev_ids,
                "cross_step": trace["cross_step"],
                "margin": round(trace["margin"], 4),
                "total_evidence": round(trace["total_evidence"], 4),
                "metacognition": review,
                "conflict_monitor": monitor_trace,
            },
            crossed=trace["crossed"],
        ))

    # Rank: crossed options by confidence desc; non-crossed after; pruned last.
    scored.sort(key=lambda s: (
        0 if s.crossed and not s.pruned_by_constraint else
        1 if s.crossed else 2,
        -s.confidence,
    ))
    return scored
