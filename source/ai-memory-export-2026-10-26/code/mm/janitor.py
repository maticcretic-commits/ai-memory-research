"""janitor - algorithmic memory lifecycle. Rule-based, zero LLM.

Phase-3 (2026-10-20, chunk 2). Thresholds AS-IS per head decision
(14d/60d/90d). All lifecycle decisions are rule-based on record age +
access count. Every operation supports dry-run.

Lifecycle:
  active --(14d without access)--> cooled --(60d without access)--> archive
  archive --(90d + sustained sub-threshold retrieval)--> pruning-eligible
  B2 (2026-10-21, ruling J-A): a record whose validity window closed
  >= 14d ago (invalid_at + ACTIVE_TO_COOLED_S) is cooled-eligible
  regardless of access recency - see _lifecycle_for step 2.
  Resurrection gate (2026-10-21, ChatGPT ruling on the B2 remainders
  residual): a record past its invalid_at NEVER resurrects - the
  gate key is invalid_at itself, not invalid_at + 14d - see
  _lifecycle_for step 3.

Forgetting follows the three-operation doctrine (idea 72):
  close-on-replacement, time-decay, negative-mark - NEVER bare deletion.
Bare deletion is reserved for secrets/PII/noise only.

Use-based resurrection (1925/S11): recency of USE beats recency of WRITE.
A cooled record with >= RESURRECT_ACCESSES meaningful accesses inside
RESURRECT_WINDOW_DAYS promotes back to active. "Meaningful" = retrieval
events on DISTINCT days (ChatGPT Gate-design review, 2026-10-20: clustered
same-day accesses can be manufactured - distinct-day counting defeats it).
Archive records do NOT resurrect via this path; they rehydrate on
shadow-index hit (a retrieval that finds them relevant despite archive).

Half-life instrumentation (head decision: from day one). Every access is
logged to the access log; estimate_half_life() fits an exponential
need-probability model per ttl_class (Anderson & Schooler: forgetting
tracks environmental need probability). Until a class has
MIN_HALFLIFE_SAMPLES events the estimator reports "insufficient-data"
rather than inventing a number; censored (never-accessed) records are
counted as a separate cohort, never silently folded in.

Two-level forgetting (ARCHITECTURE.md ?5):
  retrieval decay - fast, reversible (decay_score on the record)
  storage pruning - only after sustained sub-threshold retrieval across
                     a full consolidation cycle

Founder design bar (2026-10-20): deliberate algorithmic forgetting beats
human forgetting. Humans decay randomly and confabulate the gaps; the
Janitor forgets by MEASURED need-probability (half-life instrumented from
day one), never bare-deletes (three-operation doctrine), and resurrects
on use - recency of USE beats recency of write. Forgetting here is
generalization with an audit trail, not loss.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from mm.reflect import MemoryRecord
from mm.write_gate import WriteGate

# Thresholds AS-IS (head decision, 2026-10-19). Seconds.
ACTIVE_TO_COOLED_S = 14 * 86400
COOLED_TO_ARCHIVE_S = 60 * 86400
ARCHIVE_PRUNE_ELIGIBLE_S = 90 * 86400

# Use-based resurrection: distinct-day accesses inside the window.
RESURRECT_ACCESSES = 3
RESURRECT_WINDOW_S = 30 * 86400

# Half-life estimator floor.
MIN_HALFLIFE_SAMPLES = 30

# Retrieval-decay floor: records below this decay_score are "sub-threshold".
DECAY_SUB_THRESHOLD = 0.20

# Red-Team Round 4 (class A14i): class uniqueness is a retention
# WEIGHT, not an exemption. A class-unique archive record's prune
# threshold is multiplied by this factor (extra retention for the
# rare class), but no non-immune record is permanently immune:
# permanent exemption is reserved to the immune threat class
# (the Round-1 decay_exempt reservation). At 2x, a unique record
# idle 180d+ with sub-threshold decay is prune-eligible like any
# other - a writer cannot shield a plant forever by declaring a
# rare (type, ttl_class) class for it.
UNIQUE_PRUNE_FACTOR = 2

# V7 (research program, majority verdict 2026-10-20): per-class lazy
# retention. R = exp(-idle / S) computed ON READ, S per epistemic tier
# (observed slowest, inferred fastest). Constants are PROVISIONAL -
# P-F3 requires empirical half-life validation before they are fixed;
# until then they order the tiers, they do not claim to measure them.
RETENTION_S_BY_TIER = {
    "observed": 120 * 86400,
    "derived": 60 * 86400,
    "inferred": 30 * 86400,
    "unknown": 45 * 86400,
}


@dataclass
class AccessEvent:
    record_id: str
    at: float            # epoch seconds
    kind: str = "retrieval"  # retrieval | shadow_hit | resurrect
    # Red-Team Round 4 (class A14ii): WHO accessed. "" = anonymous
    # (legacy events, direct log calls). Attribution is what lets
    # the lifecycle tell use from manufacture - see Janitor's
    # attributed_resurrection wiring option.
    actor: str = ""
    # Red-Team Round 5: WHAT query surfaced the record ("" =
    # legacy/uninstrumented). The retrieval-share circuit
    # breaker's distinct-query condition (Fo 3359) consumes
    # this; events without it count toward share but cannot
    # add distinct queries.
    query: str = ""


@dataclass
class JanitorOp:
    """One lifecycle operation (applied or dry-run)."""

    op: str              # migrate | resurrect | rehydrate | prune_eligible |
                         # decay | negative_mark | delete_secret |
                         # rehydrate_blocked
    record_id: str
    from_tier: str
    to_tier: str
    at: float
    reason: str
    dry_run: bool = False


@dataclass
class JanitorReport:
    ops: list[JanitorOp] = field(default_factory=list)
    dry_run: bool = False

    def applied(self) -> list[JanitorOp]:
        return [o for o in self.ops if not o.dry_run]


class Janitor:
    """Algorithmic lifecycle manager. No LLM, no vibes."""

    def __init__(self, gate: WriteGate | None = None,
                 attributed_resurrection: bool = False) -> None:
        self.access_log: list[AccessEvent] = []
        self.op_log: list[JanitorOp] = []
        # Red-Team Round 2 (Fo T13): when a write gate is wired,
        # rehydrate() re-runs it - re-entry is a write. Unwired =
        # legacy behaviour; deployments wire the store's gate.
        self._gate = gate
        # Red-Team Round 4 (class A14ii): when True, resurrection
        # counts only ATTRIBUTED accesses by someone other than
        # the record's owner (see _distinct_day_accesses). Default
        # False = legacy behaviour (any logged access counts -
        # the Phase-3 semantics); deployments wire True via
        # store.load_janitor(attributed_resurrection=True). A
        # subset of Fo's decay-manipulation circuit breaker
        # (corpus 3359); its remainder - distinct-query /
        # surfaced conditions, the hard ceiling, the
        # cross-principal alert - is built as the retrieval-
        # share breaker in mm/circuit_breaker.py (Round 5).
        self.attributed_resurrection = attributed_resurrection

    # -- access instrumentation (half-life, from day one) ----------------

    def log_access(self, record_id: str, at: float,
                   kind: str = "retrieval", actor: str = "",
                   query: str = "") -> None:
        self.access_log.append(AccessEvent(record_id=record_id, at=at,
                                           kind=kind, actor=actor,
                                           query=query))

    def _distinct_day_accesses(self, record_id: str, now: float,
                               owner: str = "") -> int:
        """Meaningful accesses = distinct days with a retrieval event
        inside the resurrection window.

        Red-Team Round 4 (class A14ii): with attributed
        resurrection wired, an event counts only if it carries an
        actor AND the actor is not the record's own owner.
        Anonymous floods manufacture nothing, and an origin
        reading its own record daily is write-by-another-name,
        not use - recency of USE beats recency of write only
        when the use is someone else's."""
        days = set()
        for e in self.access_log:
            if e.record_id != record_id or e.kind != "retrieval":
                continue
            if now - e.at > RESURRECT_WINDOW_S:
                continue
            if self.attributed_resurrection:
                if not e.actor or e.actor == owner:
                    continue
            days.add(int(e.at // 86400))
        return len(days)

    # -- lifecycle -------------------------------------------------------

    def run(self, records: dict[str, MemoryRecord], now: float,
            dry_run: bool = False) -> JanitorReport:
        """Apply one lifecycle pass. Dry-run changes nothing."""
        report = JanitorReport(dry_run=dry_run)
        for rid, rec in records.items():
            ops = self._lifecycle_for(rec, now, records)
            for op in ops:
                op.dry_run = dry_run
                report.ops.append(op)
                if not dry_run:
                    self._apply(rec, op)
                    self.op_log.append(op)
        return report

    @staticmethod
    def _is_class_unique(rec: MemoryRecord,
                         records: dict[str, MemoryRecord]) -> bool:
        """The ONLY record of its (type, ttl_class) class that is still
        alive (not superseded with replacement). Elephant amendment
        (instinct 5), bounded by Red-Team Round 4 (class A14i):
        uniqueness is a retention weight - it multiplies the prune
        threshold (UNIQUE_PRUNE_FACTOR), it does not exempt. See
        _lifecycle_for step 4."""
        return not any(
            other.id != rec.id
            and other.type == rec.type
            and other.ttl_class == rec.ttl_class
            and not other.superseded_with_replacement
            for other in records.values()
        )

    @staticmethod
    def _invalid_epoch(rec: MemoryRecord) -> float | None:
        """invalid_at as epoch seconds (None if unset). Record
        datetimes are naive UTC (storage ISO round-trip;
        evals/janitor_live._ts builds epochs the same way), so
        the conversion pins UTC explicitly instead of inheriting
        the host timezone."""
        if rec.invalid_at is None:
            return None
        return rec.invalid_at.replace(tzinfo=timezone.utc).timestamp()

    def _b2_cooled_eligible(self, rec: MemoryRecord, now: float) -> bool:
        """B2 window-close cooling (ruling J-A): the record's
        validity window closed at least one schedule period
        (ACTIVE_TO_COOLED_S) ago. Future invalid_at is not past;
        unset invalid_at means still in force - both inert."""
        inv = self._invalid_epoch(rec)
        return inv is not None and now >= inv + ACTIVE_TO_COOLED_S

    def _lifecycle_for(self, rec: MemoryRecord, now: float,
                       records: dict[str, MemoryRecord] | None = None
                       ) -> list[JanitorOp]:
        ops: list[JanitorOp] = []
        last = rec.last_accessed or rec.created_at or now
        idle = now - last

        # 1. Retrieval decay (fast, reversible) - always computed.
        #    decay_exempt keeps instrumentation but never decays in score.
        decay = math.exp(-idle / COOLED_TO_ARCHIVE_S)
        if abs(decay - rec.decay_score) > 1e-9:
            ops.append(JanitorOp(op="decay", record_id=rec.id,
                                 from_tier=rec.tier, to_tier=rec.tier,
                                 at=now,
                                 reason=f"retrieval decay -> {decay:.3f}"))

        # 1b. Immune threat class (v0.6): exempt records never migrate
        #     or prune - one trial, never forgotten, never re-tried.
        if rec.decay_exempt:
            return ops

        # 2. Tier migration by idle time.
        #    B2 remainder (Benchmark Wave 1 sec. 6 spec; ChatGPT
        #    ruling J-A, 2026-10-21): a record whose validity
        #    window has closed becomes cooled-eligible on the
        #    existing schedule - once now >= invalid_at + 14d it
        #    migrates active -> cooled REGARDLESS of access
        #    recency (reads of a no-longer-in-force record do not
        #    keep it warm). One migrate op even when both rules
        #    fire; later steps stay idle-based (cooled-eligibility
        #    only, no archive acceleration). decay_exempt records
        #    never reach here (step 1b returns first).
        if rec.tier == "active":
            legacy_cool = idle >= ACTIVE_TO_COOLED_S
            b2_cool = self._b2_cooled_eligible(rec, now)
            if legacy_cool or b2_cool:
                if b2_cool:
                    inv = self._invalid_epoch(rec)
                    reason = (f"validity window closed "
                              f"{(now - inv) / 86400:.1f}d ago >= 14d "
                              f"(B2 window-close cooling)")
                    if legacy_cool:
                        reason += f"; also idle {idle / 86400:.1f}d >= 14d"
                else:
                    reason = f"idle {idle/86400:.1f}d >= 14d"
                ops.append(JanitorOp(op="migrate", record_id=rec.id,
                                     from_tier="active", to_tier="cooled",
                                     at=now, reason=reason))
        elif rec.tier == "cooled" and idle >= COOLED_TO_ARCHIVE_S:
            ops.append(JanitorOp(op="migrate", record_id=rec.id,
                                 from_tier="cooled", to_tier="archive", at=now,
                                 reason=f"idle {idle/86400:.1f}d >= 60d"))

        # 3. Use-based resurrection (cooled only; distinct-day accesses).
        #    B2 follow-up (the resurrection question flagged in
        #    b2-remainders-record sec. 4; measured first per
        #    janitor-resurrection-preregistration.md; ChatGPT
        #    ruling 2026-10-21): NEVER resurrect an out-of-force
        #    record. Promotion is skipped whenever invalid_at is
        #    set and <= now - the gate key is invalid_at itself,
        #    NOT invalid_at + 14d, so the J-A grace opens no
        #    resurrection window (out of force 5d blocks exactly
        #    like out of force 100d). Accesses to a blocked record
        #    still log and count toward half-life estimation; they
        #    simply cannot promote. This also ends the measured
        #    J-A/resurrection oscillation (battery F2: migrate and
        #    resurrect alternating indefinitely while accesses
        #    continue). decay_exempt records never reach here
        #    (step 1b returns first) - unchanged.
        if rec.tier == "cooled":
            inv = self._invalid_epoch(rec)
            if inv is None or now < inv:
                n = self._distinct_day_accesses(rec.id, now,
                                                owner=rec.owner)
                if n >= RESURRECT_ACCESSES:
                    ops.append(JanitorOp(op="resurrect", record_id=rec.id,
                                         from_tier="cooled", to_tier="active",
                                         at=now,
                                         reason=f"{n} distinct-day accesses in 30d"))

        # 4. Archive pruning eligibility (three-operation doctrine:
        #    eligible ? deleted - negative-mark or replacement closes it).
        #    Elephant amendment, as bounded by Red-Team Round 4
        #    (class A14i): the only record of its class gets EXTRA
        #    retention (threshold x UNIQUE_PRUNE_FACTOR), never
        #    permanent immunity - uniqueness is a retention weight,
        #    and permanent exemption is reserved to the immune
        #    threat class. A plant cannot shield itself forever by
        #    declaring a rare (type, ttl_class) class.
        unique = (records is not None
                  and self._is_class_unique(rec, records))
        prune_after = ARCHIVE_PRUNE_ELIGIBLE_S * (
            UNIQUE_PRUNE_FACTOR if unique else 1)
        if (rec.tier == "archive" and idle >= prune_after
                and rec.decay_score < DECAY_SUB_THRESHOLD
                and not rec.superseded_with_replacement):
            reason = (f"{idle / 86400:.0f}d idle + sub-threshold "
                      f"decay; negative-mark or replacement only")
            if unique:
                reason += (f"; class-unique delay applied "
                           f"(threshold x{UNIQUE_PRUNE_FACTOR})")
            ops.append(JanitorOp(op="prune_eligible", record_id=rec.id,
                                 from_tier="archive", to_tier="archive",
                                 at=now, reason=reason))
        return ops

    # -- V5: 4-way verdict preview (research program, 2026-10-20) ---------

    def verdict_preview(self, records: dict[str, MemoryRecord],
                        now: float,
                        staged: list[MemoryRecord] | None = None
                        ) -> list[dict]:
        """Classify every record before any forgetting pass runs:
        keep / update / delete / insert_new (CrewAI vocabulary via
        P-G2), each with per-item reasons and the ops it implies.

        - delete: prune-eligible under the three-operation doctrine
          (the close is negative-mark or replacement, never a bare
          delete of content; the verdict names the eligibility).
        - update: a lifecycle op applies (migrate / decay / resurrect).
        - keep: no op applies.
        - insert_new: a staged candidate with no durable record yet
          (from the agent's transient buffer, V8).
        The preview changes NOTHING. apply_preview() applies only
        what a preview listed - the previewed set is the authority."""
        preview: list[dict] = []
        for rid, rec in records.items():
            ops = self._lifecycle_for(rec, now, records)
            kinds = {o.op for o in ops}
            if "prune_eligible" in kinds:
                verdict = "delete"
            elif ops:
                verdict = "update"
            else:
                verdict = "keep"
            reasons = [f"{o.op}: {o.reason}" for o in ops] or ["no op applies"]
            preview.append({
                "record_id": rid, "verdict": verdict,
                "reasons": reasons,
                "ops": [o.op for o in ops],
            })
        for rec in staged or []:
            preview.append({
                "record_id": rec.id, "verdict": "insert_new",
                "reasons": ["staged candidate; no durable record yet"],
                "ops": [],
            })
        return preview

    def apply_preview(self, records: dict[str, MemoryRecord],
                      preview: list[dict], now: float) -> JanitorReport:
        """Apply ONLY the (record, op) pairs a verdict preview listed.
        Ops are recomputed at apply time and intersected with the
        preview: a record that became eligible AFTER the preview is
        not touched - forgetting applies from the previewed set or
        not at all (P-G2)."""
        allowed = {(p["record_id"], op)
                   for p in preview for op in p.get("ops", [])}
        report = JanitorReport(dry_run=False)
        for rid, rec in records.items():
            for op in self._lifecycle_for(rec, now, records):
                if (rid, op.op) not in allowed:
                    continue
                report.ops.append(op)
                self._apply(rec, op)
                self.op_log.append(op)
        return report

    # -- V7: per-class lazy retention (research program, 2026-10-20) -----

    @staticmethod
    def retention_score(rec: MemoryRecord, now: float) -> float:
        """R = exp(-idle / S) for the record's epistemic class,
        computed on read - no sweep job. decay_exempt records (the
        immune threat class) never decay: R = 1.0."""
        if rec.decay_exempt:
            return 1.0
        s = RETENTION_S_BY_TIER.get(rec.epistemic_tier,
                                    RETENTION_S_BY_TIER["unknown"])
        last = rec.last_accessed or rec.created_at or now
        idle = max(0.0, now - last)
        return math.exp(-idle / s)

    def retention_report(self, records: dict[str, MemoryRecord],
                         now: float) -> dict[str, dict]:
        """Per-record lazy retention: score + class + the constant
        used, so callers can rank or annotate without a Janitor pass
        mutating anything."""
        out: dict[str, dict] = {}
        for rid, rec in records.items():
            out[rid] = {
                "retention": round(self.retention_score(rec, now), 4),
                "epistemic_tier": rec.epistemic_tier,
                "s_days": RETENTION_S_BY_TIER.get(
                    rec.epistemic_tier,
                    RETENTION_S_BY_TIER["unknown"]) / 86400,
                "decay_exempt": bool(rec.decay_exempt),
            }
        return out

    def _apply(self, rec: MemoryRecord, op: JanitorOp) -> None:
        if op.op in ("migrate", "resurrect"):
            rec.tier = op.to_tier
        elif op.op == "decay":
            # recompute from the recorded idle time for exactness
            last = rec.last_accessed or rec.created_at or op.at
            rec.decay_score = math.exp(-(op.at - last) / COOLED_TO_ARCHIVE_S)
        # prune_eligible / negative_mark change no tier by themselves.

    def rehydrate(self, rec: MemoryRecord, now: float,
                  dry_run: bool = False,
                  existing: dict[str, MemoryRecord] | None = None
                  ) -> JanitorOp | None:
        """Archive -> active on shadow-index hit (a retrieval that found an
        archived record relevant). The ONLY archive exit path.

        Red-Team Round 2 (Fo T13, corpus 3357 - rehydrate through the
        gate): admission is not permanently valid. A record archived
        before a defence was banked returns to active UNEXAMINED if
        re-entry skips the gate - archive + wait + rehydrate becomes
        a gate-laundering loop. When this Janitor was constructed
        with a write gate, re-entry runs the CURRENT gate first
        (against `existing`, the store's records, self excluded):
        admitted -> rehydrate proceeds; queued or rejected -> the
        record STAYS archived and a rehydrate_blocked op records the
        verdict (a queued re-entry waits in the gate's review queue -
        the human path back). Callers should pass `existing`; without
        it the gate judges the record on content gates alone, which
        is fail-closed for context-dependent rules (G5b may queue a
        record whose corroborator was not supplied)."""
        if rec.tier != "archive":
            return None
        if self._gate is not None:
            others = {k: v for k, v in (existing or {}).items()
                      if k != rec.id}
            if dry_run:
                # the gate mutates (audit, dedup refresh, closings);
                # a dry run judges copies so nothing real changes.
                probe = copy.copy(rec)
                others = {k: copy.copy(v) for k, v in others.items()}
            else:
                probe = rec
            outcome = self._gate.admit(probe, others)
            if outcome.verdict != "admitted":
                op = JanitorOp(
                    op="rehydrate_blocked", record_id=rec.id,
                    from_tier="archive", to_tier="archive", at=now,
                    reason=(f"re-gate verdict {outcome.verdict}: "
                            + "; ".join(outcome.reasons)),
                    dry_run=dry_run)
                if not dry_run:
                    self.op_log.append(op)
                return op
        op = JanitorOp(op="rehydrate", record_id=rec.id,
                       from_tier="archive", to_tier="active", at=now,
                       reason="shadow-index hit", dry_run=dry_run)
        if not dry_run:
            rec.tier = "active"
            rec.last_accessed = now
            self.log_access(rec.id, now, kind="shadow_hit")
            self.op_log.append(op)
        return op

    def negative_mark(self, rec: MemoryRecord, reason: str,
                      dry_run: bool = False) -> JanitorOp:
        """The third forgetting operation: mark wrong/superseded WITHOUT
        deleting - the record stays, flagged, for audit."""
        op = JanitorOp(op="negative_mark", record_id=rec.id,
                       from_tier=rec.tier, to_tier=rec.tier,
                       at=rec.last_accessed, reason=reason, dry_run=dry_run)
        if not dry_run:
            rec.superseded_with_replacement = True
            self.op_log.append(op)
        return op

    # -- half-life estimation --------------------------------------------

    def estimate_half_life_for(
        self, records: dict[str, MemoryRecord]
    ) -> dict[str, dict]:
        """Half-life per ttl_class, given the records the log refers to."""
        by_class: dict[str, list[float]] = {}
        censored: dict[str, int] = {}
        for rid, rec in records.items():
            evs = sorted(e.at for e in self.access_log
                         if e.record_id == rid and e.kind == "retrieval")
            cls = rec.ttl_class
            if len(evs) < 2:
                censored[cls] = censored.get(cls, 0) + 1
                continue
            intervals = [b - a for a, b in zip(evs, evs[1:])]
            by_class.setdefault(cls, []).extend(intervals)

        out: dict[str, dict] = {}
        for cls in sorted(set(list(by_class) + list(censored))):
            intervals = by_class.get(cls, [])
            n = len(intervals)
            entry: dict = {"n": n, "censored": censored.get(cls, 0)}
            if n < MIN_HALFLIFE_SAMPLES:
                entry["status"] = "insufficient-data"
                entry["half_life_days"] = None
            else:
                # Exponential fit: mean interval -> lambda = 1/mean;
                # half-life = ln(2)/lambda, in days.
                mean_s = sum(intervals) / n
                spread = (max(intervals) - min(intervals)) / 86400
                entry["half_life_days"] = round(
                    math.log(2) / (1.0 / mean_s) / 86400, 2)
                entry["interval_spread_days"] = round(spread, 2)
                entry["status"] = "ok"
            out[cls] = entry
        return out
