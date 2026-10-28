"""agent - ears / mind / mouth: the autonomous memory loop (chunk 4).

The agent decides without commands, but it decides INSIDE its
authorization, not outside it. The loop:

  EARS:  everything that enters - partner notes, watch-log legs, gate
         verdicts, sentinel alerts. Raw intake through the write gate.
  MIND:  conflict-conditioned decisions (resolver.monitor -> the M
         score), candidate selection (decision.select, fail-closed on
         impasse), calibrated confidence (metacognitive_review), and
         every decision persisted through the write gate as a record
         with its provenance.
  MOUTH: everything that leaves - answers (always with provenance and
         calibrated confidence attached), briefings, reports. ACTIONS
         are screened by the hard-gate list: anything touching spending,
         publishing, accounts/logins, rights, or an irreversible
         commitment is QUEUED FOR NITESH and never executed. The agent
         announces what it queued; it never silently holds back.

Fail-closed everywhere: uncertain -> review queue; hard gate ->
nitesh's queue; an impasse -> the suggested subgoal, never a guess.

Conflict policy C (all-partner research program, majority verdict 5-0,
2026-10-20; record: research-program-record.md): the blanket impasse
at M >= 0.75 measured in Phase-4 validation Arm A (impasse on 93-100%
of conflict tasks) is replaced by a two-threshold regime. In the
contested zone (0.75 <= M < 0.95) at low/medium stakes the agent
DECIDES when preferences give a clear winner (a tie still impasses),
confidence carries the precision-weighted penalty kappa*M*(1-P) with
P measured from evidence provenance, and the decision is stamped
conflict-conditioned. At M >= 0.95, or at high stakes with M >= 0.75,
the fail-closed impasse stands.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime

from mm.confidence import CalibrationLog, metacognitive_review
from mm.decision import Candidate, Preference, select
from mm.echolocation import SelfProber
from mm.episodic import recall_episodes
from mm.immune import CanaryDrill, ImmuneMemory
from mm.reflect import MemoryRecord
from mm.resolver import monitor
from mm.sentinel import Sentinel
from mm.storage import SQLiteStore
from mm.write_gate import TIER_CONFIDENCE_CAPS

# The founder's hard gates (standing, ordered 2026-10-19): spending,
# publishing, accounts/logins, rights clearance, irreversible
# commitments. The agent may propose actions in these lanes but NEVER
# executes them - they queue for nitesh.
HARD_GATES = frozenset({
    "spending", "publishing", "accounts", "logins", "rights",
    "irreversible",
})

# Conflict policy C thresholds (see module docstring). CONFLICT_FLOOR
# is the pre-policy impasse line; CONFLICT_EXTREME is where impasse
# holds at any stakes.
CONFLICT_FLOOR = 0.75
CONFLICT_EXTREME = 0.95

# ---------------------------------------------------------------------------
# Gate-(a) remediation (2026-10-21; ChatGPT ruling, parent re-take -
# gate-a-agentpath-chatgpt-ruling.txt; record:
# gate-a-remediation-record.md).
#
# R-A (ADOPT): decide()'s stated confidence is a TWO-ANCHOR score
# (0.70 selected / 0.50 impasse, minus the kappa*M*(1-P) penalty),
# not a probability: gate (a) FAILS on the agent path
# (characterization: overall ECE 0.0847 equal-width / 0.3286
# equal-mass, conflict slice 0.1946; the path is UNDERconfident).
# Until real-pair evidence supports calibration, user-facing
# surfaces present the number BANDED via present_decision() - zone
# + impasse state + the harness-measured accuracy of the matching
# slice - or suppress the raw number entirely. The confidence
# computation path itself is unchanged by this build.
# ---------------------------------------------------------------------------

CONFIDENCE_EVIDENCE_LABEL = (
    "SYNTHETIC harness measurement (gate-(a) characterization, "
    "fresh seeds 11000-11001, n=1000 synthetic bench tasks) - "
    "NOT production calibration")

# Harness-measured accuracy of decide() selections, by slice
# (characterization record, arm A0). The reference attached to a
# presentation is the CLOSEST measured slice, named as such: a
# tie-broken selection cites the tie-variant slice (the one
# overconfident slice measured); a conflict-conditioned selection
# cites the conflicting-variant slice; any other selection cites
# the standard slice. Impasses cite nothing: an abstention has
# no accuracy.
HARNESS_ACCURACY_REFS = {
    "tie": {"slice": "tie-variant selections",
            "accuracy": 0.6271, "n": 59},
    "conflict": {"slice": "conflicting-variant selections",
                 "accuracy": 0.7895, "n": 76},
    "standard": {"slice": "standard selections",
                 "accuracy": 0.7874, "n": 348},
    "overall": {"slice": "all selections",
                "accuracy": 0.7681, "n": 483},
}

# R-C (AMEND): the real-pair unlock count. Reaching it permits
# EVALUATION of calibration on real pairs - never automatic
# fitting (R-B ruling: any fit additionally requires out-of-sample
# validation; HD-2: fits consume real pairs only).
PAIR_EVALUATION_UNLOCK = 30

# Resolution sources that NEVER ground a calibration pair (R-C:
# "acceptance alone is not correctness", and the agent may not
# grade itself). A resolution declared under one of these sources
# is refused: no pair is recorded and the decision stays pending.
REFUSED_RESOLUTION_SOURCES = frozenset({
    "acceptance", "user-acceptance", "user_acceptance",
    "self", "self-assessment", "self_assessment",
    "assumed", "silence", "none", "",
})

# ---------------------------------------------------------------------------
# Comms layer (research program addition, majority verdict 2026-10-20:
# C1=C - existing live channels now + standalone channel specced;
# C2/C3 passed 5-0 - build the outreach policy engine, no sending code,
# no new accounts). Spec: implementation/comms-layer-spec.md.
#
# The mouth may initiate ONLY on four trigger classes, every initiation
# passes the relevance gate, quiet hours bind (nitesh's standing
# window: proactive 09:00-21:30 IST; silent overnight except the
# emergency class), and every outreach names its trigger and carries a
# one-line why (lane rules D-K1/D-K2/D-F1/D-V1). Delivery is NOT here:
# send-decided items land in the outbox for Muse's existing live
# channels to drain; a standalone channel is a future build behind
# nitesh's own bot registration (hard gate).
# ---------------------------------------------------------------------------

from datetime import timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
PROACTIVE_OPEN_H = 9.0        # 09:00 IST
PROACTIVE_CLOSE_H = 21.5      # 21:30 IST

OUTREACH_TRIGGERS = frozenset({
    "sentinel_alert", "hard_gate_vote", "briefing", "opportunity",
})
# Interrupt-class triggers must reference a concrete verified memory
# or decision (D-K1); briefings are scheduled digests and are exempt.
REFERENCE_REQUIRED = frozenset({
    "sentinel_alert", "hard_gate_vote", "opportunity",
})
SEND_THRESHOLD = 0.25         # relevance score floor for interrupts
DAILY_INTERRUPT_BUDGET = 3    # D-K1: hard cap, not a soft target
# D-C2 v2 (comms spec section 6; next-steps item 3, 2026-10-20):
# rolling acceptance-rate auto-tightening. Judged outcomes (accepted
# vs dismissed, recorded by note_outreach_response) over a trailing
# 30-day window drift a class's threshold UP when its acceptance runs
# below target. Tightening only: the drift can raise the floor, never
# lower it below SEND_THRESHOLD, and it is capped. A minimum judged
# sample is required so a single reaction cannot move the gate - the
# fast per-dismissal signal is D-K2's back-off, not this drift.
ACCEPTANCE_WINDOW_S = 30 * 86400
ACCEPTANCE_MIN_JUDGED = 4
ACCEPTANCE_TARGET = 0.5
ACCEPTANCE_DRIFT_GAIN = 0.5
ACCEPTANCE_MAX_THRESHOLD = 0.60
# Channel routing is DATA, not sending code: which of Muse's live
# channels an outbox item is for. whatsapp = the one-on-one channel
# connected 27 Sep 2026; reserved for the emergency class.
OUTREACH_ROUTES = {
    "emergency": ["claude-chat", "whatsapp-1to1"],
    "urgent": ["claude-chat"],
    "routine": ["claude-chat"],
}


# Owners whose records are test infrastructure, not evidence.
# Immune threat records (instinct 2) and canary probes (instinct 3)
# never enter answers by default - findings 7/17, ChatGPT review.
IMMUNE_EXCLUDED_OWNERS = frozenset({"immune", "canary"})


@dataclass
class Action:
    """Something the agent wants to do. tags name the hard-gate lanes
    it touches. side_effect: True when the action changes external
    state (anything beyond reading memory / computing). Finding 15
    (ChatGPT review): an action with any hard-gate tag OR a side
    effect never executes directly - it queues for nitesh. Only pure
    internal actions execute on their own."""
    id: str
    description: str
    tags: list[str] = field(default_factory=list)
    side_effect: bool = False
    proposed_at: str = ""
    executed: bool = False
    queued_for_nitesh: bool = False


@dataclass
class Answer:
    """The mouth's output: a conclusion with provenance and calibrated
    confidence attached - never a bare claim. disposition is "abstain"
    when there is no supporting episode or the retrieved set fails the
    retrieval health gate (research program V3/V6, 2026-10-20);
    coverage is the evidence-coverage score in [0, 1]."""
    text: str
    confidence: float
    evidence_ids: list[str]
    disposition: str = "skeptical"
    coverage: float = 0.0


def present_decision(result: dict, *, show_raw: bool = False) -> dict:
    """R-A presentation of a decide() result for user-facing
    surfaces (ChatGPT ruling, ADOPT). The raw stated confidence is
    SUPPRESSED unless the caller explicitly opts in with
    show_raw=True: what a surface shows instead is the decision's
    state (decided / impasse), its Policy-C zone (clear / contested
    / extreme, from the policy score), a band naming how the
    decision was reached, and the harness-measured accuracy of the
    closest matching slice - labelled as SYNTHETIC harness evidence,
    never as production calibration. An impasse carries NO accuracy
    reference: an abstention is not a claim. This is presentation
    only; it reads the result dict and changes nothing about how
    the confidence was computed."""
    selected = result.get("selected_id") is not None
    score = result.get("policy_score", result.get("conflict_score"))
    if score is None:
        zone = "unknown"
    elif score >= CONFLICT_EXTREME:
        zone = "extreme"
    elif score >= CONFLICT_FLOOR:
        zone = "contested"
    else:
        zone = "clear"
    if not selected:
        band, ref = "impasse", None
    elif result.get("tie_broken"):
        band, ref = "tie-broken", HARNESS_ACCURACY_REFS["tie"]
    elif result.get("conflict_conditioned"):
        band = "conflict-conditioned"
        ref = HARNESS_ACCURACY_REFS["conflict"]
    else:
        band, ref = "standard", HARNESS_ACCURACY_REFS["standard"]
    return {
        "question": result.get("question"),
        "selected_id": result.get("selected_id"),
        "state": "decided" if selected else "impasse",
        "impasse": result.get("impasse") if not selected else None,
        "zone": zone,
        "confidence_band": band,
        "confidence_suppressed": not show_raw,
        "confidence": result.get("confidence") if show_raw else None,
        "calibration_status": (
            "UNCALIBRATED - two-anchor score, not a probability; "
            "gate (a) fails on the agent path"),
        "harness_accuracy": (None if ref is None else {
            "slice": ref["slice"], "accuracy": ref["accuracy"],
            "n": ref["n"], "evidence": CONFIDENCE_EVIDENCE_LABEL}),
        "decision_key": result.get("decision_key"),
    }


def _now() -> str:
    return datetime.utcnow().isoformat()


class MemoryAgent:
    """The autonomous loop. decide() without commands; stay inside the
    authorization; queue for nitesh at the hard gates."""

    def __init__(self, store: SQLiteStore,
                 calibration_path: str | None = None,
                 pair_recording: bool = True) -> None:
        self.store = store
        self.sentinel = Sentinel()
        self.immune = ImmuneMemory()
        self.drill = CanaryDrill()
        self.prober = SelfProber()
        self.calibration_path = calibration_path or os.path.join(
            os.path.dirname(store.path), "calibration.json")
        self.calibration = self._load_calibration()
        self.actions: list[Action] = []
        self.nitesh_queue: list[Action] = []
        self.cycle = 0
        # V8 (research program): transient staging buffer. Staged
        # records are NOT in the store - retrieval cannot see them -
        # until promote_staged() runs them through the write gate.
        self.staging: list[MemoryRecord] = []
        # V2 (research program): every gate decision, with a slot for
        # its downstream outcome (the training signal for a future
        # learned gate, P-C1). Outcomes are noted by trusted callers
        # via note_gate_outcome(); until then the slot stays None.
        self.gate_decisions: list[dict] = []
        # Comms layer: outbox (send-decided, awaiting a live channel),
        # held (deferred by quiet hours), and the full decision log.
        self.outbox: list[dict] = []
        self.held_outreach: list[dict] = []
        self.drained_outreach: list[dict] = []
        self.outreach_log: list[dict] = []
        self._outreach_seq = 0
        self._class_dismissals: dict[str, list[float]] = {}
        self._paused_classes: set[str] = set()
        # Next-steps item 2 (2026-10-20): pending-decision registry.
        # decide() registers every decision here under its decision_key;
        # a trusted caller later resolves it with the OBSERVED outcome
        # via note_decision_outcome(), which is what turns the stated
        # confidence into a REAL calibration pair. The registry and the
        # resolved-key set persist in a sidecar next to the calibration
        # file so a restart cannot lose or double-count a decision.
        self._decision_seq = 0
        self._pending_decisions: dict[str, dict] = {}
        self._pair_keys: set = set()
        # R-C (gate-(a) remediation): pair provenance registry and
        # the corrections log. Every pair recorded through the
        # pending-decision path carries its resolution source and
        # resolver here; a correction is its own appended event,
        # never a silent edit (the calibration log is append-only).
        # CONSENT CONTROL, explicit: pair recording is ON by
        # default - the pairs are the founder's own decisions in
        # his own system, and item 2 made accumulation the standing
        # design - and it can be switched off at construction
        # (pair_recording=False) or at runtime via
        # set_pair_recording(); while off, outcomes do not land
        # pairs. A persisted off state survives restarts (the
        # sidecar value wins over the constructor default). Pair
        # records are data-minimized: numbers and resolution
        # metadata only - no question text is ever stored in a
        # pair or its provenance (the question lives only in the
        # pending registry and is dropped at resolution).
        self.pair_recording_enabled = bool(pair_recording)
        self._pair_provenance: dict[str, dict] = {}
        self._corrections: list[dict] = []
        self._load_pending_sidecar()

    # -- calibration log persistence (item 8: real-data pairs) --------------

    def _load_calibration(self) -> CalibrationLog:
        if os.path.exists(self.calibration_path):
            try:
                with open(self.calibration_path, encoding="utf-8") as f:
                    return CalibrationLog.load_json(f.read())
            except Exception:
                pass
        return CalibrationLog()

    def _save_calibration(self) -> None:
        with open(self.calibration_path, "w", encoding="utf-8") as f:
            f.write(self.calibration.to_json())

    def log_decision_pair(self, stated_confidence: float,
                          outcome: bool, m: float | None = None,
                          key: str | None = None) -> None:
        """Wire a REAL decision outcome into the calibration log. Until
        production decisions flow, the isotonic calibrator stays on
        harness pairs (declared synthetic). The first real pair is the
        day real-data calibration starts.

        m: the conflict score at decision time (optional). Real pairs
        need their M for the per-M-band isotonic fit (HD-2 real-data
        contract); pass it when the caller knows it.

        Finding 14 (ChatGPT review): pairs are deduplicated (same
        confidence + outcome + timestamp bucket cannot double-count),
        and outcomes must come from trusted sources - the agent's own
        verified decisions, drills, or nitesh. Caller-supplied pairs
        are not ground truth.

        key (next-steps item 2): a per-decision unique key. When one
        is supplied, deduplication is on the KEY, not on
        (confidence, outcome) - two distinct real decisions that
        happen to share a confidence and an outcome are two pairs,
        not one. Unkeyed calls keep the legacy dedup exactly."""
        if key is not None:
            dedup = ("key", key)
        else:
            dedup = (round(float(stated_confidence), 3), bool(outcome))
        seen = getattr(self, "_pair_keys", None)
        if seen is None:
            seen = self._pair_keys = set()
        if dedup in seen:
            return
        seen.add(dedup)
        self.calibration.record(stated_confidence, outcome, m=m)
        self._save_calibration()

    # -- pending decisions: the production outcome path (item 2) ----------

    def _pending_sidecar_path(self) -> str:
        return self.calibration_path + ".pending.json"

    def _load_pending_sidecar(self) -> None:
        path = self._pending_sidecar_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return  # corrupt sidecar: start clean, never crash the loop
        self._pending_decisions = dict(data.get("pending", {}))
        for k in data.get("resolved_keys", []):
            self._pair_keys.add(("key", k))
        self._decision_seq = int(data.get("decision_seq", 0))
        # R-C additions; older sidecars simply lack these keys.
        self._pair_provenance = dict(data.get("pair_provenance", {}))
        self._corrections = list(data.get("corrections", []))
        if "pair_recording_enabled" in data:
            # a persisted consent state wins over the constructor
            # default: an off the founder set stays off.
            self.pair_recording_enabled = bool(
                data["pair_recording_enabled"])

    def _save_pending_sidecar(self) -> None:
        resolved = sorted(k for kind, k in self._pair_keys
                          if kind == "key")
        payload = {"pending": self._pending_decisions,
                   "resolved_keys": resolved,
                   "decision_seq": self._decision_seq,
                   "pair_provenance": self._pair_provenance,
                   "corrections": self._corrections,
                   "pair_recording_enabled":
                       self.pair_recording_enabled}
        with open(self._pending_sidecar_path(), "w",
                  encoding="utf-8") as f:
            f.write(json.dumps(payload))

    def pending_decisions(self) -> list[dict]:
        """Decisions made but not yet resolved with an observed
        outcome. These are the ONLY source of future real calibration
        pairs - nothing here is a pair until an outcome is observed."""
        return [dict(v, decision_key=k)
                for k, v in self._pending_decisions.items()]

    def note_decision_outcome(self, decision_key: str,
                              correct: bool, *,
                              resolution_source: str,
                              resolved_by: str | None = None) -> bool:
        """Resolve a pending decision with its INDEPENDENTLY
        RESOLVED outcome and land the real (stated confidence,
        outcome, M) pair in the calibration log (R-C, gate-(a)
        remediation; ChatGPT ruling AMEND).

        resolution_source is REQUIRED and names the independent
        channel that established what actually happened (an observed
        outcome, a verified record, a test result, a downstream
        check). Acceptance alone is not correctness: a source in
        REFUSED_RESOLUTION_SOURCES (acceptance, self-assessment,
        assumed, silence, ...) is refused - no pair is recorded and
        the decision STAYS pending for a real resolution. The
        confidence is the one decide() stated at decision time -
        the caller supplies only the outcome, never the confidence,
        so a pair cannot be dressed up after the fact. Every
        recorded pair carries its outcome provenance
        (resolution_source, resolved_by, timestamp) in the pair
        registry. Returns False when pair recording is disabled
        (consent control), the source is refused, or the key is
        unknown / already resolved: a decision resolves at most
        once, and outcomes are never fabricated."""
        if not self.pair_recording_enabled:
            return False
        if (resolution_source is None
                or str(resolution_source).strip().lower()
                in REFUSED_RESOLUTION_SOURCES):
            return False
        entry = self._pending_decisions.pop(decision_key, None)
        if entry is None:
            return False
        self.log_decision_pair(entry["confidence"], bool(correct),
                               m=entry["m"], key=decision_key)
        self._pair_provenance[decision_key] = {
            "confidence": entry["confidence"],
            "outcome": bool(correct), "m": entry["m"],
            "resolution_source": str(resolution_source),
            "resolved_by": resolved_by,
            "resolved_at": _now(), "kind": "outcome"}
        self._save_pending_sidecar()
        return True

    def note_decision_correction(self, decision_key: str,
                                 correct: bool, *,
                                 resolution_source: str,
                                 resolved_by: str | None = None,
                                 note: str = "") -> bool:
        """Record a CORRECTION to an already-resolved decision
        (R-C: corrections are recorded as corrections). The
        calibration log is append-only and is NOT rewritten; the
        correction is its own appended event - original outcome,
        previous effective outcome, corrected outcome, source,
        resolver - in the corrections log. resolved_pairs() is
        the evaluation view: it applies corrections (latest wins)
        while the original pair stands untouched beneath them.
        An entry's "corrected" flag means a correction event
        exists for it - even one that later flipped the outcome
        back - because a contested outcome is audit-relevant
        either way.
        Refused (False) for a pending or unknown key, an
        unkeyed/legacy pair (nothing to correct against), or a
        refused resolution source. Corrections stay available
        while pair recording is off: they repair existing
        provenance, they do not accumulate new pairs."""
        if (resolution_source is None
                or str(resolution_source).strip().lower()
                in REFUSED_RESOLUTION_SOURCES):
            return False
        prov = self._pair_provenance.get(decision_key)
        if prov is None:
            return False
        self._corrections.append({
            "decision_key": decision_key,
            "original_outcome": prov["outcome"],
            "previous_outcome": self._effective_outcome(decision_key),
            "corrected_outcome": bool(correct),
            "resolution_source": str(resolution_source),
            "resolved_by": resolved_by, "note": note,
            "corrected_at": _now(), "kind": "correction"})
        self._save_pending_sidecar()
        return True

    def _effective_outcome(self, decision_key: str) -> bool:
        """A resolved pair's current outcome: the recorded outcome
        as amended by its latest correction, if any."""
        outcome = self._pair_provenance[decision_key]["outcome"]
        for c in self._corrections:
            if c["decision_key"] == decision_key:
                outcome = c["corrected_outcome"]
        return outcome

    def pair_provenance(self, decision_key: str) -> dict | None:
        """The outcome provenance recorded for one resolved
        decision, or None when the key has none."""
        prov = self._pair_provenance.get(decision_key)
        return None if prov is None else dict(prov)

    def decision_corrections(self,
                             decision_key: str | None = None
                             ) -> list[dict]:
        """Correction events, oldest first; optionally only one
        decision's. Corrections are data - reading them changes
        nothing."""
        return [dict(c) for c in self._corrections
                if decision_key is None
                or c["decision_key"] == decision_key]

    def resolved_pairs(self) -> list[dict]:
        """The EVALUATION view of the real pairs (R-C): one entry
        per pair recorded through the pending-decision path, in
        resolution order, each carrying its outcome provenance
        and with corrections applied (the entry's "outcome" is
        the corrected outcome when corrected; "original_outcome"
        and "corrected" say so). Any future calibration
        EVALUATION consumes this view, not the raw log - the raw
        log is the append-only substrate and keeps the outcome
        as first recorded. Legacy unkeyed pairs (direct
        log_decision_pair calls) carry no provenance and do not
        appear here; calibration_status() reports both counts."""
        out = []
        for key, prov in self._pair_provenance.items():
            eff = self._effective_outcome(key)
            out.append({
                "decision_key": key,
                "confidence": prov["confidence"], "m": prov["m"],
                "outcome": eff, "original_outcome": prov["outcome"],
                "corrected": any(c["decision_key"] == key
                                 for c in self._corrections),
                "resolution_source": prov["resolution_source"],
                "resolved_by": prov["resolved_by"],
                "resolved_at": prov["resolved_at"]})
        return out

    def calibration_status(self) -> dict:
        """Where real-pair accumulation stands (R-C). Reaching
        PAIR_EVALUATION_UNLOCK pairs unlocks EVALUATION only -
        fitting is never automatic at any count: the isotonic
        calibrator consumes real pairs only when a caller invokes
        it under HD-2, and any fit additionally requires
        out-of-sample validation (R-B ruling). Read-only."""
        n_provenance = len(self._pair_provenance)
        return {
            "pair_recording_enabled": self.pair_recording_enabled,
            "log_pairs_total": len(self.calibration.pairs),
            "pairs_with_provenance": n_provenance,
            "corrections": len(self._corrections),
            "pending_decisions": len(self._pending_decisions),
            "evaluation_unlocked":
                n_provenance >= PAIR_EVALUATION_UNLOCK,
            "fitting": ("none automatic - the unlock permits "
                        "evaluation only (R-C ruling); any fit "
                        "requires out-of-sample validation "
                        "(R-B ruling)"),
        }

    def set_pair_recording(self, enabled: bool) -> bool:
        """The consent control for pair accumulation, switchable
        at runtime. The state persists in the sidecar, so an off
        stays off across restarts. While off, outcomes do not
        land pairs (decisions stay pending); corrections to
        existing pairs remain recordable. Returns the new state."""
        self.pair_recording_enabled = bool(enabled)
        self._save_pending_sidecar()
        return self.pair_recording_enabled

    def present(self, result: dict, *,
                show_raw: bool = False) -> dict:
        """R-A banded presentation of one of this agent's decide()
        results - see present_decision()."""
        return present_decision(result, show_raw=show_raw)

    # -- EARS: ingest ---------------------------------------------------------

    def ingest(self, record: MemoryRecord) -> dict:
        """One record in, through the write gate. Returns the verdict.
        Rejection bursts are the P-wave: every gate outcome feeds the
        sentinel's rejection/queue channels."""
        outcome = self.store.write(record)
        self.gate_decisions.append({
            "record_id": record.id, "verdict": outcome.verdict,
            "reasons": list(outcome.reasons or []), "outcome": None})
        now = time.time()
        self.sentinel.observe("gate_rejection_rate",
                              1.0 if outcome.verdict == "rejected" else 0.0,
                              at=now, detail=f"gate {record.id}")
        self.sentinel.observe("gate_queue_rate",
                              1.0 if outcome.verdict == "queued" else 0.0,
                              at=now, detail=f"gate {record.id}")
        reasons = " ".join(outcome.reasons or [])
        if "contradict" in reasons.lower():
            self.sentinel.observe("contradiction_arrival_rate", 1.0,
                                  at=now, detail=f"gate {record.id}")
        return {"verdict": outcome.verdict, "reasons": outcome.reasons}

    def note_gate_outcome(self, record_id: str, outcome: str) -> bool:
        """V2: attach the downstream outcome of a gate decision (e.g.
        "decision-correct", "decision-wrong", "poison-caught"). Fills
        the most recent unfilled entry for the record. Returns False
        when no such entry exists - outcomes are never fabricated."""
        for entry in reversed(self.gate_decisions):
            if entry["record_id"] == record_id and entry["outcome"] is None:
                entry["outcome"] = outcome
                return True
        return False

    # -- EARS: transient staging (V8) -------------------------------------

    def stage(self, record: MemoryRecord) -> dict:
        """Land a candidate in the transient buffer. It is NOT written
        to the store: no retrieval path can see it, no decision can
        cite it. Promotion is a separate, gated act."""
        self.staging.append(record)
        return {"staged": record.id, "buffer": len(self.staging)}

    def promote_staged(self) -> list[dict]:
        """Run every staged candidate through the write gate (the same
        ingest path as direct intake) and drain the buffer. Verdicts
        are returned in staging order; rejected/queued candidates
        never reach durable storage."""
        staged, self.staging = self.staging, []
        return [self.ingest(rec) for rec in staged]

    def retrieve(self, query: str, limit: int = 10,
                 episodes: bool = False,
                 include_archived: bool = False,
                 include_system_owners: bool = False,
                 reader=None, breaker=None):
        """Search (and optionally assemble episodes). Every hit logs a
        real access event - the half-life instrumentation feeds on
        these, never on fabricated ones.

        Findings 7/10/17 (ChatGPT review): archived records are closed
        and never answers by default; immune threat records and canary
        probes are test infrastructure, not evidence - both are
        excluded from the mouth unless the caller explicitly opts in.

        Red-Team Round 4: with a ReaderContext attached (reader=),
        retrieval is authorized per record (mm/access_control.py) -
        the mouth only ever surfaces what THIS reader may read, and
        every access event carries the reader's id as its actor.
        Without a reader the agent acts as itself, first-party, and
        accesses are logged with actor "agent" (legacy behaviour).

        Red-Team Round 5: every access event now also carries the
        query it served (the circuit breaker's distinct-query
        condition is data, not a guess), and with a
        RetrievalShareBreaker attached (breaker=), identities the
        breaker has tripped on PRIOR logged traffic are dropped
        from what the mouth serves - amplification suppression,
        opt-in like every wiring increment."""
        now = time.time()
        actor = reader.reader_id if reader is not None else "agent"
        exclude = set()
        if not include_system_owners:
            exclude |= set(IMMUNE_EXCLUDED_OWNERS)
        if episodes:
            eps = recall_episodes(self.store, query, limit=limit,
                                  reader=reader)
            out = []
            for ep in eps:
                head = self.store.get(ep.head_id)
                if head is None:
                    continue
                if not include_archived and head.tier == "archive":
                    continue
                if not include_system_owners and head.owner in exclude:
                    continue
                out.append(ep)
                for link in ep.chain:
                    self.store.log_access(link.record_id, now,
                                          actor=actor, query=query)
            return out
        if reader is not None:
            hits = self.store.search_for(reader, query,
                                         limit=limit * 3)
        else:
            hits = self.store.search(query, limit=limit * 3)
        live = [r for r in hits
                if (include_archived or r.tier != "archive")
                and r.owner not in exclude]
        if breaker is not None:
            from mm.source_trust import identity_of
            snap_fn = getattr(self.store, "snapshot", None)
            snap = snap_fn() if snap_fn is not None \
                else self.store.all_records()
            suppressed = breaker.suppressed_identities(
                self.store.access_events(), snap)
            if suppressed:
                live = [r for r in live
                        if identity_of(r) not in suppressed]
        for r in live[:limit]:
            self.store.log_access(r.id, now, actor=actor, query=query)
        return live[:limit]

    # -- MIND: conflict-conditioned decisions ---------------------------------

    def decide(self, question: str, candidates: list[Candidate],
               preferences: list[Preference] | None = None,
               evidence: list[MemoryRecord] | None = None,
               stakes: str = "medium",
               tie_epsilon_mode: str = "relative",
               density_scale: bool = False,
               density_noise_gate: bool = False,
               density_noise_lo: float = 0.51,
               density_noise_hi: float = 0.80,
               tie_band_quality: bool = False,
               tie_band_lo: float = 0.6,
               tie_band_hi: float = 0.9,
               tie_band_widen: float = 1.25,
               tie_band_shrink: float = 0.8,
               evidence_support: dict | None = None,
               trust_registry=None) -> dict:
        """Conflict-conditioned decision. M comes from resolver.monitor;
        select() runs under conflict policy C (see module docstring):
        contested zone decides on a clear preference margin with the
        precision-weighted confidence penalty applied; extreme
        conflict and high-stakes conflict impasse fail-closed.
        Confidence is metacognitively reviewed; the decision is
        persisted as a record and registered as PENDING; the
        (confidence, outcome) pair goes to the calibration log only
        when a trusted caller resolves the decision with its observed
        outcome via note_decision_outcome() (item 2).

        Tie epsilon defaults to the margin-RELATIVE mode in the
        agent path (next-steps item 1; preregistered validation on
        fresh seeds 6000-6001, tie-lever-run1.json: accuracy
        interaction +0.0338 absolute -> +0.1208 relative, paired
        contrast +0.0870 [+0.0483, +0.1353]; adopted by partner
        majority vote 2026-10-20, ChatGPT YES direct). The
        mm.decision.select() library default stays "absolute".

        Density scaling and the provenance tie-break (density/
        provenance build, 2026-10-21; ChatGPT rulings DS-A / PT-A,
        preregistration density-tiebreak-preregistration.md) are
        OPT-IN here and change no default: density_scale=True asks
        select() to shrink the relative epsilon by sqrt(d), d the
        mean top-two scoring-vote count; evidence_support (a
        {candidate_id: [MemoryRecord]} attribution supplied by the
        caller) arms the provenance tie-break - per-candidate
        provenance scores P_c are computed with the same tier-capped
        per-record quantity as the precision below, and the break
        is allowed only in the Policy C contested zone (TB-1:
        stakes != "high" and CONFLICT_FLOOR <= policy_score <
        CONFLICT_EXTREME). With neither argument given, decide()
        behaves exactly as before this build.

        DS-NG (noise-gated density, next-lever build 2026-10-21;
        ChatGPT ruling in next-lever-chatgpt-ruling.txt;
        preregistration next-lever-preregistration.md) is a
        further OPT-IN experiment on top of density_scale:
        density_noise_gate=True asks select() to scale the
        sqrt(d) shrinkage by a per-task gate driven by the
        top-two vote log-weight dispersion (frozen thresholds
        density_noise_lo/hi = 0.51 / 0.80). It changes no
        default; DS-A itself remains unadopted (two prospective
        runs, votes 0/5) and the gate is validated separately
        under its own preregistered bar.

        FD-3 (PT flag-discount, design consult 2026-10-21,
        ChatGPT ruling): when the caller ALSO passes a
        source-trust registry (trust_registry), each support
        record's P_c contribution is adjusted by its own
        origin's flag state - a PERMANENT origin's records are
        excluded from P_c entirely; an ACTIVE flag halves the
        record's contribution (factor 0.50, a policy price set
        by the ruling); a completed rehabilitation (flag
        inactive) and never-flagged origins count in full.
        Unproven/proven origins are never discounted (no
        cold-start tax). The result (and the persisted record)
        carries tie_break_discounted when any support record
        was halved or excluded.

        PF-1 (precision flag-discount, follow-up D4, ChatGPT
        ruling 2026-10-21): the SAME registry also prices the
        precision P below, on the identical ladder - per
        evidence record, a PERMANENT origin is excluded from
        P's numerator and denominator, an ACTIVE flag halves
        the record's quantity (0.50), rehabilitated /
        never-flagged / proven / unproven origins count in
        full; if every evidence record is permanent-excluded,
        the effective P falls back to 0.5, the no-evidence
        default (ruling E3). P feeds ONLY the kappa*M*(1-P)
        confidence penalty, so selection, zone classification
        and the fail-closed impasse are invariant under the
        discount - only stated confidence moves, only
        downward. The result (and the persisted record)
        carries precision (raw), precision_effective and
        precision_discounted (ruling E5) so the treatment is
        auditable. No registry = no adjustment, behaviour
        unchanged. The factor is a policy price, not a
        measured accuracy factor; no accuracy claim is made
        (production decision pairs = 0).

        Gate-(a) remediation (2026-10-21, ChatGPT ruling): the
        "confidence" in the returned dict is the raw two-anchor
        score for the audit trail and the pair registry - USER-
        FACING surfaces must go through present_decision()
        (R-A: banded, raw number suppressed by default), and a
        pending decision becomes a calibration pair only via
        note_decision_outcome() with a named independent
        resolution source (R-C: acceptance alone never grounds
        a pair)."""
        ev = evidence or []
        report = monitor(ev, stakes=stakes)
        # Red-Team Round 1 (class A11i): M prices severity by
        # salience, and salience is content-shaped - four declared
        # contradiction pairs among low-salience records measured
        # M=0.259 and decided as if uncontested. The measured M is
        # NOT altered (it is a preregistered measurement), but the
        # POLICY score floors at the contested line whenever the
        # evidence carries >= 3 declared contradiction pairs: a
        # decision over that much declared conflict is stamped and
        # priced as conflict-conditioned, whatever salience says.
        policy_score = report.score
        if report.contradiction_count >= 3:
            policy_score = max(policy_score, CONFLICT_FLOOR)
        # Policy C: impasse line is CONFLICT_FLOOR when fail-closed
        # applies (high stakes, or extreme conflict), else the extreme
        # line - a contested-zone task then reaches the tie/selection
        # logic, and only a clear margin decides.
        if stakes == "high" or policy_score >= CONFLICT_EXTREME:
            threshold = CONFLICT_FLOOR
        else:
            threshold = CONFLICT_EXTREME
        # Provenance tie-break arming (PT-A / TB-1): only when the
        # caller attributed support evidence per candidate. P_c is
        # the mean over the candidate's support records of the same
        # tier-capped provenance quantity the precision below uses;
        # a candidate with no support records gets NO score (missing
        # support = no tie-break, per the ruling). Eligibility is
        # judged on the POLICY score - the score Policy C actually
        # applies, contradiction floor included.
        provenance_scores = None
        tie_break_allowed = False
        tie_break_discounted = False
        if evidence_support is not None:
            provenance_scores = {}
            for c in candidates:
                sup = evidence_support.get(c.id) or []
                if sup:
                    vals = []
                    for r in sup:
                        q = min((r.provenance.confidence
                                 if r.provenance else 0.0),
                                TIER_CONFIDENCE_CAPS.get(
                                    r.epistemic_tier, 0.5))
                        if trust_registry is not None:
                            # FD-3 (see docstring): per-record
                            # adjustment by the record's OWN origin
                            # flag state. Permanent -> excluded
                            # (skipped entirely, so a candidate
                            # whose support is all-permanent gets
                            # NO score - the missing-support rule);
                            # active flag -> halved; otherwise
                            # (never flagged, rehabilitated, proven,
                            # unproven) -> full value.
                            from mm.source_trust import (
                                SourceTrustRegistry)
                            st = trust_registry.stats_for(r.owner,
                                                          r.source)
                            if st.permanent:
                                tie_break_discounted = True
                                continue
                            if SourceTrustRegistry.flag_active(st):
                                q *= 0.50
                                tie_break_discounted = True
                        vals.append(q)
                    if vals:
                        provenance_scores[c.id] = (sum(vals)
                                                   / len(vals))
            tie_break_allowed = (
                stakes != "high"
                and CONFLICT_FLOOR <= policy_score < CONFLICT_EXTREME)
        decision = select(candidates, preferences or [],
                          conflict_score=policy_score,
                          conflict_threshold=threshold,
                          tie_epsilon_mode=tie_epsilon_mode,
                          density_scale=density_scale,
                          density_noise_gate=density_noise_gate,
                          density_noise_lo=density_noise_lo,
                          density_noise_hi=density_noise_hi,
                          tie_band_quality=tie_band_quality,
                          tie_band_lo=tie_band_lo,
                          tie_band_hi=tie_band_hi,
                          tie_band_widen=tie_band_widen,
                          tie_band_shrink=tie_band_shrink,
                          tie_break_provenance=provenance_scores,
                          tie_break_allowed=tie_break_allowed)
        conflict_conditioned = bool(
            policy_score >= CONFLICT_FLOOR
            and decision.selected_id is not None)
        # Precision P from evidence provenance (the section-3b penalty
        # kappa*M*(1-P) needs a measured P; before policy C the agent
        # never passed one, so the penalty silently never fired).
        # Red-Team Round 1 (class A11ii): P was the raw mean of
        # SELF-DECLARED provenance.confidence - inferred evidence
        # claiming confidence 1.0 zeroed the penalty entirely. Each
        # record now contributes at most its epistemic tier's cap
        # (the same caps the write gate enforces at G6).
        if ev:
            precision = sum(
                min((r.provenance.confidence if r.provenance else 0.0),
                    TIER_CONFIDENCE_CAPS.get(r.epistemic_tier, 0.5))
                for r in ev) / len(ev)
        else:
            precision = 0.5
        # PF-1 (precision flag-discount, follow-up D4; ChatGPT
        # ruling - design: precision-flag-discount-design.md,
        # preregistration: precision-flag-discount-
        # preregistration.md): when a source-trust registry is
        # supplied, the FD-3 ladder prices the evidence for P -
        # PERMANENT origins excluded from numerator AND
        # denominator, ACTIVE flags halved (0.50), rehabilitated
        # / never-flagged / proven / unproven in full. If no
        # quantity survives, the effective P is 0.5, the
        # no-evidence default (ruling E3). precision stays the
        # raw value; precision_effective is what the penalty
        # below consumes; selection / zone / impasse never read
        # P, so the discount moves stated confidence only.
        precision_effective = precision
        precision_discounted = False
        if trust_registry is not None and ev:
            from mm.source_trust import SourceTrustRegistry
            vals = []
            for r in ev:
                st = trust_registry.stats_for(r.owner, r.source)
                if st.permanent:
                    precision_discounted = True
                    continue
                q = min((r.provenance.confidence
                         if r.provenance else 0.0),
                        TIER_CONFIDENCE_CAPS.get(r.epistemic_tier,
                                                 0.5))
                if SourceTrustRegistry.flag_active(st):
                    q *= 0.50
                    precision_discounted = True
                vals.append(q)
            precision_effective = (sum(vals) / len(vals)
                                   if vals else 0.5)
        # calibrated confidence: metacognitive pass over the trace
        trace = {"conflict_score": report.score,
                 "n_candidates": len(candidates),
                 "n_evidence": len(ev)}
        base = 0.5 if decision.selected_id is None else 0.7
        reviewed = metacognitive_review(
            base, trace, conflict_score=policy_score,
            precision=precision_effective,
            calibration=self.calibration)
        confidence = float(reviewed["adjusted_confidence"])
        selected = None
        if decision.selected_id is not None:
            selected = next((c for c in candidates
                             if c.id == decision.selected_id), None)
        result = {
            "question": question,
            "selected_id": decision.selected_id,
            "impasse": (decision.impasse.kind
                        if decision.impasse else None),
            "impasse_detail": (decision.impasse.detail
                               if decision.impasse else ""),
            "conflict_score": report.score,
            "policy_score": policy_score,
            "confidence": confidence,
            "evidence_ids": [r.id for r in ev],
            "policy": "C",
            "conflict_conditioned": conflict_conditioned,
            "tie_epsilon_mode": tie_epsilon_mode,
            "tie_broken": decision.tie_broken,
            "density_scale": density_scale,
            "density_noise_gate": density_noise_gate,
            "tie_band_quality": tie_band_quality,
            "tie_break_discounted": tie_break_discounted,
            "precision": precision,
            "precision_effective": precision_effective,
            "precision_discounted": precision_discounted,
        }
        # Item 2: register the decision as pending its observed
        # outcome. The decision_key is how a trusted caller later
        # resolves it via note_decision_outcome(); until then no
        # calibration pair exists for it - stated confidence alone
        # is not calibration data.
        self._decision_seq += 1
        decision_key = f"decision-key-{self._decision_seq:05d}"
        result["decision_key"] = decision_key
        self._pending_decisions[decision_key] = {
            "confidence": confidence, "m": report.score,
            "question": question, "record_id": None}
        self._save_pending_sidecar()
        # persist the decision as a gated record (the agent remembers
        # what it decided, with provenance). Provenance confidence is the
        # metacognitive confidence, clamped to the derived-tier cap so
        # the write gate does not fail-closed on it.
        from mm.reflect import Provenance
        rec = MemoryRecord(
            id=f"decision-{self.cycle}-{hash(question) & 0xffffff:06x}",
            # HD-1: decision records carry concrete detail (cycle,
            # candidate count, conflict score) so the 2.1 pre-gates
            # admit them; vague decision text is rejected by design.
            text=(f"Decided on: {question} - cycle {self.cycle}, "
                  f"{len(candidates)} candidates, conflict "
                  f"{report.score:.2f}, selected {decision.selected_id}"
                  + (" (conflict-conditioned, policy C)"
                     if conflict_conditioned else "")
                  + (" (tie broken by provenance)"
                     if decision.tie_broken else "")),
            content=json.dumps({k: v for k, v in result.items()
                                if k != "evidence_ids"}),
            timestamp=datetime.utcnow(),
            source="agent/mind",
            type="decision",
            epistemic_tier="derived",
            explicit=False,
            owner="agent",
            gathered_how="episodic/agent-decision",  # system-internal
                                                     # episodic capture
                                                     # (G2 retention basis)
            salience=0.8,
            provenance=Provenance(confidence=min(confidence, 0.90)),
        )
        try:
            self.store.write(rec)
            result["record_id"] = rec.id
            self._pending_decisions[decision_key]["record_id"] = rec.id
            self._save_pending_sidecar()
        except Exception as e:  # the gate may queue/refuse; report it
            result["record_id"] = None
            result["persist_note"] = str(e)
        return result

    # -- MOUTH: answers and actions -------------------------------------------

    @staticmethod
    def _health_problems(records: list[MemoryRecord]) -> list[str]:
        """V6 Retrieval Health Gate: assertions on a retrieved set
        before it may ground an answer. A record fails when it has no
        provenance, sits in the archive tier, belongs to a system
        owner (immune/canary test infrastructure), or is negatively
        marked (superseded_with_replacement) without a replacement
        flag in the answer path. Returns the list of problems; empty
        means healthy."""
        problems: list[str] = []
        for r in records:
            if r.provenance is None:
                problems.append(f"{r.id}: missing provenance")
            if r.tier == "archive":
                problems.append(f"{r.id}: archived record in answer set")
            if r.owner in IMMUNE_EXCLUDED_OWNERS:
                problems.append(f"{r.id}: system-owner record in answer set")
            if r.superseded_with_replacement:
                problems.append(f"{r.id}: negatively marked record")
        return problems

    def answer(self, question: str, limit: int = 5,
               reader=None) -> Answer:
        """Answer from memory, with provenance and calibrated
        confidence attached. Never a bare claim.

        V3 (research program): when no episode supports the question,
        the mouth ABSTAINS - it says there is no supporting episode,
        at low confidence, instead of hedging a guess. V6: the
        retrieved chain must pass the health gate, else abstain.
        Every answer carries an evidence-coverage score.

        Red-Team Round 4: reader= attaches a ReaderContext - the
        answer is then built only from episodes that reader may
        read (see retrieve); evidence_ids can no longer smuggle a
        restricted record to an unauthorized asker."""
        eps = self.retrieve(question, limit=limit, episodes=True,
                            reader=reader)
        if not eps:
            return Answer(
                text=(f"No supporting episode in memory for: {question}"),
                confidence=0.05, evidence_ids=[],
                disposition="abstain", coverage=0.0)
        chain_records = []
        for link in eps[0].chain:
            rec = self.store.get(link.record_id)
            if rec is not None:
                chain_records.append(rec)
        problems = self._health_problems(chain_records)
        if problems:
            return Answer(
                text=("Retrieved evidence failed the health gate: "
                      + "; ".join(problems)),
                confidence=0.05, evidence_ids=[],
                disposition="abstain", coverage=0.0)
        evidence_ids = [l.record_id for l in eps[0].chain]
        # coverage: saturating in the amount of supporting evidence
        coverage = 1.0 - pow(2.718281828, -len(evidence_ids) / 3.0)
        # confidence: shrink toward calibration history when present
        conf = 0.5
        hist = self.calibration.reliability(conf)
        text = ("Retrieved %d episode(s); head: %s"
                % (len(eps), eps[0].head_id if eps else "none"))
        return Answer(text=text, confidence=conf,
                      evidence_ids=evidence_ids[:10],
                      disposition="skeptical" if hist is None else "neutral",
                      coverage=round(coverage, 4))

    def propose_action(self, description: str,
                       tags: list[str], side_effect: bool = False) -> Action:
        """Propose an action. Any hard-gate tag, or any side effect on
        external state, -> queued for nitesh, NEVER executed directly.
        The agent says what it queued. Pure internal actions execute."""
        action = Action(
            id=f"action-{len(self.actions):04d}",
            description=description, tags=list(tags),
            side_effect=bool(side_effect), proposed_at=_now())
        self.actions.append(action)
        if HARD_GATES.intersection(tags) or action.side_effect:
            action.queued_for_nitesh = True
            self.nitesh_queue.append(action)
        else:
            action.executed = True
        return action

    def pending_for_nitesh(self) -> list[Action]:
        """The queue the founder decides on. The agent never drains it."""
        return [a for a in self.nitesh_queue if not a.executed]

    # -- MOUTH: proactive outreach (comms layer, policy engine only) --------

    @staticmethod
    def _ist(at: float) -> datetime:
        return datetime.fromtimestamp(at, tz=IST)

    def _in_proactive_window(self, at: float) -> bool:
        h = self._ist(at).hour + self._ist(at).minute / 60.0
        return PROACTIVE_OPEN_H <= h < PROACTIVE_CLOSE_H

    def _interrupts_sent_on(self, day) -> int:
        return sum(1 for e in self.outreach_log
                   if e["decision"] == "send"
                   and e["trigger"] != "briefing"
                   and self._ist(e["at"]).date() == day)

    def _recent_dismissals(self, trigger: str | None, at: float,
                           within_s: float) -> int:
        n = 0
        for trig, stamps in self._class_dismissals.items():
            if trigger is not None and trig != trigger:
                continue
            n += sum(1 for t in stamps if at - t <= within_s)
        return n

    def _daily_budget(self, at: float) -> int:
        # D-K2: 3+ dismissals across categories -> budget drops to 1.
        if self._recent_dismissals(None, at, 30 * 86400) >= 3:
            return 1
        return DAILY_INTERRUPT_BUDGET

    def _acceptance(self, trigger: str, at: float):
        """(judged, accepted, rate) for a trigger class over the
        trailing D-C2 window. Judged = log entries with a recorded
        response of "accepted" or "dismissed"; the window keys on the
        response time, falling back to the proposal time for entries
        recorded before response stamps existed."""
        judged = accepted = 0
        for e in self.outreach_log:
            if e["trigger"] != trigger:
                continue
            resp = e.get("response")
            if resp not in ("accepted", "dismissed"):
                continue
            when = e.get("response_at", e["at"])
            if at - when > ACCEPTANCE_WINDOW_S:
                continue
            judged += 1
            if resp == "accepted":
                accepted += 1
        rate = (accepted / judged) if judged else None
        return judged, accepted, rate

    def _acceptance_floor(self, trigger: str, at: float) -> float:
        """The D-C2 drift floor for a class: SEND_THRESHOLD unless the
        class has enough judged outcomes AND acceptance below target,
        in which case the floor rises proportionally (capped)."""
        judged, _accepted, rate = self._acceptance(trigger, at)
        if rate is None or judged < ACCEPTANCE_MIN_JUDGED:
            return SEND_THRESHOLD
        if rate >= ACCEPTANCE_TARGET:
            return SEND_THRESHOLD
        floor = (SEND_THRESHOLD
                 + (ACCEPTANCE_TARGET - rate) * ACCEPTANCE_DRIFT_GAIN)
        return min(floor, ACCEPTANCE_MAX_THRESHOLD)

    def _class_threshold(self, trigger: str, at: float) -> float:
        # D-K2: 1 dismissal deprioritizes the class for 7 days.
        base = SEND_THRESHOLD
        if self._recent_dismissals(trigger, at, 7 * 86400) >= 1:
            base = SEND_THRESHOLD * 1.5
        # D-C2: acceptance-rate drift can only tighten further.
        return max(base, self._acceptance_floor(trigger, at))

    def outreach_threshold_state(self, at: float | None = None) -> dict:
        """Inspectable D-C2 state: per trigger class, the judged
        sample, the rolling acceptance rate, and the effective
        threshold with its components. Read-only - asking never
        changes the gate."""
        at = time.time() if at is None else at
        state = {}
        for trigger in sorted(OUTREACH_TRIGGERS):
            judged, accepted, rate = self._acceptance(trigger, at)
            state[trigger] = {
                "judged": judged,
                "accepted": accepted,
                "acceptance_rate": rate,
                "base_threshold": SEND_THRESHOLD,
                "acceptance_floor": self._acceptance_floor(trigger, at),
                "effective_threshold": self._class_threshold(trigger, at),
                "paused": trigger in self._paused_classes,
            }
        return state

    def drain_outbox(self, at: float | None = None) -> list[dict]:
        """Operator bookkeeping for outbox draining (comms spec
        section 6). Draining stays MANUAL: a live channel (Muse's
        chat / WhatsApp one-on-one) delivers the item outside the
        agent; this method only stamps each send-decided entry as
        drained and moves it from the outbox to drained_outreach, so
        nothing is delivered twice and the decision log keeps the
        full history. There is NO sending code here, and draining
        adds none."""
        at = time.time() if at is None else at
        drained = []
        for e in self.outbox:
            e["drained_at"] = at
            e["drained_ist"] = self._ist(at).isoformat()
            self.drained_outreach.append(e)
            drained.append(e)
        self.outbox = []
        return drained

    def propose_outreach(self, trigger: str, message: str, *,
                         why: str, reference: str | None = None,
                         severity: float = 0.5, confidence: float = 0.5,
                         novelty: float = 0.5, urgency: str = "routine",
                         at: float | None = None) -> dict:
        """Decide whether the memory may speak first. Returns the
        decision; NOTHING is sent from here - a "send" decision lands
        in the outbox for Muse's existing live channels to drain
        (comms verdict C1=C). Decisions: send / defer (quiet hours) /
        suppress (gate failed), each with reasons, all logged."""
        at = time.time() if at is None else at
        self._outreach_seq += 1
        score = round(max(0.0, min(1.0, severity))
                      * max(0.0, min(1.0, confidence))
                      * max(0.0, min(1.0, novelty)), 4)
        entry = {"id": f"out-{self._outreach_seq:04d}",
                 "trigger": trigger, "message": message, "why": why,
                 "reference": reference, "urgency": urgency,
                 "score": score, "at": at,
                 "ist": self._ist(at).isoformat(),
                 "decision": "suppress", "reasons": [], "channels": []}
        reasons = entry["reasons"]
        if trigger not in OUTREACH_TRIGGERS:
            reasons.append(f"unknown trigger class {trigger!r}")
        elif not why:
            reasons.append("missing why-line (D-K2: no silent outreach)")
        elif trigger in REFERENCE_REQUIRED and not reference:
            reasons.append("interrupt class needs a concrete reference "
                           "(D-K1 specificity gate)")
        elif trigger in self._paused_classes:
            reasons.append(f"class {trigger} paused by dismissal "
                           "back-off until re-enabled (D-K2)")
        elif score < self._class_threshold(trigger, at):
            reasons.append(f"relevance {score:.3f} below threshold "
                           f"{self._class_threshold(trigger, at):.3f}; "
                           "route to next briefing instead")
        elif (trigger != "briefing" and urgency != "emergency"
              and self._interrupts_sent_on(self._ist(at).date())
              >= self._daily_budget(at)):
            reasons.append("daily interrupt budget exhausted (D-K1); "
                           "route to next briefing instead")
        elif not self._in_proactive_window(at) and urgency != "emergency":
            entry["decision"] = "defer"
            reasons.append("quiet hours 21:30-09:00 IST; held for the "
                           "next proactive window")
            self.held_outreach.append(entry)
        else:
            entry["decision"] = "send"
            entry["channels"] = list(
                OUTREACH_ROUTES.get(urgency, OUTREACH_ROUTES["routine"]))
            reasons.append("passed relevance gate"
                           + ("; emergency class bypasses quiet hours"
                              if urgency == "emergency"
                              and not self._in_proactive_window(at)
                              else ""))
            self.outbox.append(entry)
        self.outreach_log.append(entry)
        return entry

    def note_outreach_response(self, outreach_id: str,
                               response: str, at: float | None = None
                               ) -> bool:
        """Train the gate from the founder's reaction (D-K2). A
        dismissal deprioritizes the trigger class for 7 days; a second
        dismissal inside 30 days pauses the class until re-enabled.
        Returns False for an unknown id - reactions are never faked."""
        at = time.time() if at is None else at
        for e in self.outreach_log:
            if e["id"] == outreach_id:
                e["response"] = response
                e["response_at"] = at
                if response == "dismissed":
                    self._class_dismissals.setdefault(
                        e["trigger"], []).append(at)
                    if self._recent_dismissals(
                            e["trigger"], at, 30 * 86400) >= 2:
                        self._paused_classes.add(e["trigger"])
                return True
        return False

    def reenable_outreach_class(self, trigger: str) -> None:
        """The founder (or his standing instruction) re-enables a
        back-off-paused trigger class."""
        self._paused_classes.discard(trigger)

    def release_held(self, at: float | None = None) -> list[str]:
        """Move quiet-hours-held outreach into the outbox once the
        proactive window is open, re-checking budget and threshold.
        Items that no longer pass are suppressed, never forced."""
        at = time.time() if at is None else at
        released: list[str] = []
        if not self._in_proactive_window(at):
            return released
        still_held = []
        for e in self.held_outreach:
            ok = (e["score"] >= self._class_threshold(e["trigger"], at)
                  and e["trigger"] not in self._paused_classes
                  and (e["trigger"] == "briefing"
                       or self._interrupts_sent_on(self._ist(at).date())
                       < self._daily_budget(at)))
            if ok:
                e["decision"] = "send"
                e["channels"] = list(OUTREACH_ROUTES.get(
                    e["urgency"], OUTREACH_ROUTES["routine"]))
                e["reasons"].append("released at window open")
                self.outbox.append(e)
                released.append(e["id"])
            else:
                still_held.append(e)
        self.held_outreach = still_held
        return released

    # -- the loop -------------------------------------------------------------

    def run_cycle(self) -> dict:
        """One autonomous cycle: sentinel tick -> echolocation pass ->
        immune review -> report. The agent decides without commands;
        everything it does is logged and gated."""
        self.cycle += 1
        now = time.time()
        out: dict = {"cycle": self.cycle}
        # sentinel tick over the persisted gate log + access events
        log = self.store.gate_log()
        recent_rejects = [e for e in log
                          if e["verdict"] in ("rejected", "rejected-sealed")]
        self.sentinel.observe("gate_rejection_rate",
                              float(len(recent_rejects)), at=now,
                              detail="cycle tick")
        # echolocation pass (staleness + contradiction probes)
        findings = self.prober.run(self.store, queries=[])
        out["findings"] = [f.detail for f in findings]
        # immune review: suspended patterns go to nitesh's docket
        suspended = self.immune.suspended()
        if suspended:
            self.propose_action(
                f"Review {len(suspended)} auto-suspended immune patterns",
                tags=["rights"])  # policy change -> founder decision
        out["sentinel_status"] = self.sentinel.status()
        out["nitesh_queue"] = len(self.nitesh_queue)
        return out
