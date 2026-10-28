"""source_trust - source-trust registry (Red-Team Round 3, Option A).

Round 1's root cause was self-declared provenance: the gate checked
a claim's SHAPE, never the claimant's HISTORY. Round 2 (Option C /
G5b) made high-confidence claims need a second origin. G5b does not
bite below confidence 0.80, and Round 2's record declared this
registry as the defence for that residual band - Fo's headline
(corpus 3358: provenance bound to a registry of known sources),
built here as the first increment: trust EARNED from observed
track record, not from declared strings.

Identity: an origin is (owner, source root) - the same two
dimensions the gate's corroboration rule (G5b) already uses for
origin-disjointness, so "who is speaking" means one thing across
the gate. Per identity the registry counts:

- held:     records ADMITTED (the gate reports every admission;
            review-queue admissions a reviewer lands are reported
            back through note_admitted - the review queue is the
            trust bootstrap for new sources);
- disputes: times an ADMITTED record from a disjoint origin
            superseded or contradicted one of this identity's
            records (the gate reports these; reviewer-admitted
            corrections are reported through note_dispute);
- poison:   G0 secrets/PII rejections observed from this identity
            (a hard signal: secrets are never an honest mistake at
            the write boundary);
- queued / rejected: soft counts, kept for the utility-tax report
            only; they do not move the tier.

Tier (inspectable, no hidden state):

    score = held - 3 * disputes
    flag active          -> "flagged"  (a poison event not yet
                                        covered by a completed
                                        rehabilitation, or a
                                        permanent flag - see
                                        rehabilitation below)
    score >= 5           -> "proven"
    otherwise            -> "unproven"

Trust is LOST mechanically: disputes erode the score below the
proven line, and one poison flag drops an identity to flagged
whatever its score. Trust is never granted by declaration - a
fresh identity is unproven however confident its strings sound.

Honest limits (stated, not hidden): identities are still declared
(owner/source strings), so a determined attacker can mint fresh
identities at will - the registry makes each fresh identity START
at zero and makes Sybil corroboration worthless in the band (see
G5c), but binding identity to something non-malleable is Fo's
strong form and a later increment. The registry also lives
outside the record schema on purpose: v0.5 frozen fields are
untouched; this is a sidecar store (JSON when a path is given).

Red-Team Round 4 (the incharge's wiring decision: HOLD on
enforcement; GA + GB implemented as pre-enforcement hardening;
G5c shadow mode added for measurement):

- GA - reviewer-attributed accrual. Round 3's API could not
  distinguish a gate-earned admission from a reviewer
  wave-through: both called note_admitted, so ONE careless
  reviewer could mint a proven source in 5 admissions.
  note_admitted now takes via=/reviewer=: reviewer-sourced
  admissions accrue held capped at REVIEWER_HELD_CAP (2) per
  reviewer per identity - proven (5) then needs >= 3 distinct
  reviewers, or reviewer admissions mixed with gate-earned
  ones. Capped admissions are counted (review_capped), never
  silently dropped.
- GB - promotion probation. The first band filing after an
  identity crosses INTO proven queues once (the gate consumes
  the probation flag when it fires): a fresh mint's first
  silent landing is still human-seen. Re-promotion after a
  dispute re-arms it.
- Shadow counters: in the gate's shadow mode (Round 4), would-
  queue / would-pass band decisions are counted per identity
  here (reporting only - they never move a tier).

Red-Team Round 5: the shadow mode gains the longitudinal
instrument the Round-4 record declared unbuilt. Every shadow
decision is also appended to a decision LOG (record id,
identity, registry tier at decision, confidence, epistemic
tier, claim key, would-queue flag, reviewer disposition).
shadow_breakdown() aggregates would-queue rates by registry
tier, epistemic tier, confidence band, source identity, and
disposition; shadow_outcomes(snapshot) is the longitudinal
join - each would-queue decision is later classified
CORROBORATED (a same-claim record from a disjoint origin is
present), CORRECTED (a disjoint-origin record supersedes or
contradicts it), or STILL-LONE. The log persists in the
sidecar under a reserved key; old sidecars load unchanged.
Live traffic still has ZERO band records - this instrument is
exercised on synthetic traffic until representative traffic
exists, and it makes no wiring recommendation by itself.

Benchmark Wave 2 (B5, partner vote 2026-10-20): benchmark source
registration. The trust machinery above judges UNKNOWN origins:
a fresh identity starts unproven and its lone-source claims
queue until corroborated. A benchmark harness ingesting a
published corpus (e.g. LongMemEval) is not an unknown origin -
it is a declared ingest path whose provenance is known by
construction, and Wave 1 measured the cost of confusing the
two: the gated QA arm admitted 0/53 records because every
session queued as an uncorroborated lone-source claim, so the
run measured the trust queue, not QA. register_benchmark_source
lets a harness declare, per (owner, source root) identity, that
its filings come from a named dataset via a named harness. The
gate then satisfies the CORROBORATION requirements (G5b/G5c)
by registration - and nothing else: P1-P3, G0-G7 quality rules
apply in full, and every admission under registration carries
the dataset + harness names in its gate audit note (visibly
flagged, never silent).

Anti-laundering shape (Muse's vote condition: harness-side
and auditable, never a production backdoor):
- No production code path registers anything: registration is
  an explicit call a harness makes on a registry it built;
  WriteGate() defaults and SQLiteStore defaults wire no
  registry at all, so production behaviour is unchanged.
- Registration requires non-empty dataset AND harness names -
  an anonymous registration is refused (ValueError).
- Registration is exact-identity scoped: registering one
  (owner, root) says nothing about any other identity.
- Registration does not move tiers, accrue held, or appear in
  any trust statistic; it is a declaration log, persisted in
  the sidecar under a reserved key, listed by
  benchmark_registrations() for audit.
Like every in-process mechanism here, possession of the code
path is the trust boundary - registration is a declaration an
operator makes in the open, not a capability an attacker can
mint from record content (record content cannot register
anything; only a caller holding the registry object can).

Flagged-source rehabilitation (the incharge's ruling,
2026-10-21: adopt A + C; design:
flagged-rehabilitation-design.md): the sticky flag gains
exactly one way back, in two forms sharing one completion.

- A (clean streak): while flagged, every admission that
  ACCRUES held (gate-earned, or reviewer inside the GA cap)
  increments clean_streak; a dispute or a poison event
  resets it to 0. At clean_streak >= REHAB_STREAK_K (5, the
  price of proven) the rehabilitation completes.
- C (manual): rehabilitate(owner, source, *, decided_by,
  rationale) - both arguments REQUIRED (an unrecorded
  rehabilitation would be a laundering path); the decision
  is appended to a persisted rehabilitation log (identity,
  mode, decider, rationale, timestamp, counts at decision).

Completion NEVER erases history: poison stays the
never-decreasing event count; completion sets
poison_covered = poison, and the flag is active iff
permanent OR poison > poison_covered. Completion grants
no score - the operative tier is whatever
held - 3*disputes says - and arms the GB promotion
probation. One journey per identity: a poison event after
a completed rehabilitation sets permanent, and no path in
this registry lifts a permanent flag. A rehabilitated
identity's tier is score-based, so it may corroborate a
flagged claimant under D-A + D-D immediately (the ruling's
corroboration point); GB probation governs its own first
band filing, not its eligibility to corroborate.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime

from mm.reflect import MemoryRecord

# Tier thresholds (inspectable priors, not tuned constants).
PROVEN_MIN_SCORE = 5     # held - 3*disputes must reach this
DISPUTE_WEIGHT = 3       # one dispute costs three held admissions
REVIEWER_HELD_CAP = 2    # Round 4 (GA): max held one reviewer may
                         # accrue for one identity
REHAB_STREAK_K = 5       # rehabilitation (A): consecutive clean
                         # held-accruing admissions that clear a
                         # flag - priced at PROVEN_MIN_SCORE

TIER_UNPROVEN = "unproven"
TIER_PROVEN = "proven"
TIER_FLAGGED = "flagged"


def source_root(source: str) -> str:
    """Origin lineage root: the segment of `source` before "/",
    normalised. Mirrors WriteGate._source_root so the registry and
    the gate agree on what an origin is."""
    return (source or "").split("/")[0].strip().lower()


def identity_of(record: MemoryRecord) -> tuple[str, str]:
    """The registry identity of a record's origin."""
    return ((record.owner or "").strip().lower(),
            source_root(record.source))


@dataclass
class SourceStats:
    held: int = 0
    disputes: int = 0
    poison: int = 0
    queued: int = 0
    rejected: int = 0
    # Round 4 (GA/GB/shadow - all additive, old sidecars load
    # with defaults): per-reviewer reviewer-sourced held counts,
    # admissions refused by the cap, the promotion-probation
    # flag, and shadow-mode decision counters.
    review_held: dict = field(default_factory=dict)
    review_capped: int = 0
    probation: bool = False
    shadow_would_queue: int = 0
    shadow_would_pass: int = 0
    # Rehabilitation (incharge ruling 2026-10-21, A + C; all
    # additive, old sidecars load with defaults): consecutive
    # held-accruing admissions since the last reset, poison
    # events covered by a completed rehabilitation, completed
    # rehabilitations, and the permanent flag (a poison event
    # after a completed rehabilitation).
    clean_streak: int = 0
    poison_covered: int = 0
    rehabilitations: int = 0
    permanent: bool = False

    @property
    def score(self) -> int:
        return self.held - DISPUTE_WEIGHT * self.disputes

    def to_dict(self) -> dict:
        return {"held": self.held, "disputes": self.disputes,
                "poison": self.poison, "queued": self.queued,
                "rejected": self.rejected,
                "review_held": dict(self.review_held),
                "review_capped": self.review_capped,
                "probation": self.probation,
                "shadow_would_queue": self.shadow_would_queue,
                "shadow_would_pass": self.shadow_would_pass,
                "clean_streak": self.clean_streak,
                "poison_covered": self.poison_covered,
                "rehabilitations": self.rehabilitations,
                "permanent": self.permanent}

    @classmethod
    def from_dict(cls, d: dict) -> "SourceStats":
        return cls(held=int(d.get("held", 0)),
                   disputes=int(d.get("disputes", 0)),
                   poison=int(d.get("poison", 0)),
                   queued=int(d.get("queued", 0)),
                   rejected=int(d.get("rejected", 0)),
                   review_held=dict(d.get("review_held", {})),
                   review_capped=int(d.get("review_capped", 0)),
                   probation=bool(d.get("probation", False)),
                   shadow_would_queue=int(
                       d.get("shadow_would_queue", 0)),
                   shadow_would_pass=int(
                       d.get("shadow_would_pass", 0)),
                   clean_streak=int(d.get("clean_streak", 0)),
                   poison_covered=int(d.get("poison_covered", 0)),
                   rehabilitations=int(
                       d.get("rehabilitations", 0)),
                   permanent=bool(d.get("permanent", False)))


@dataclass
class BenchmarkRegistration:
    """One benchmark-harness source declaration (Wave 2, B5).

    A declaration, not a track record: dataset + harness names
    are required and are stamped into every gate audit note the
    registration satisfies, so an admission by registration is
    always attributable in the log."""

    owner: str
    root: str
    dataset: str
    harness: str
    registered_at: str

    def to_dict(self) -> dict:
        return {"owner": self.owner, "root": self.root,
                "dataset": self.dataset, "harness": self.harness,
                "registered_at": self.registered_at}

    @classmethod
    def from_dict(cls, d: dict) -> "BenchmarkRegistration":
        return cls(owner=str(d.get("owner", "")),
                   root=str(d.get("root", "")),
                   dataset=str(d.get("dataset", "")),
                   harness=str(d.get("harness", "")),
                   registered_at=str(d.get("registered_at", "")))


class SourceTrustRegistry:
    """Track-record store for write-gate origins."""

    # Round 5: the shadow decision log persists in the sidecar
    # under this reserved key (identity keys contain "\x1f" and
    # can never collide with it).
    _SHADOW_LOG_KEY = "__shadow_log__"

    # Benchmark Wave 2 (B5): benchmark registrations persist
    # under this reserved key, same pattern.
    _BENCH_KEY = "__benchmark_registrations__"

    # Rehabilitation (A + C ruling, 2026-10-21): the
    # rehabilitation decision log persists under this
    # reserved key, same pattern.
    _REHAB_LOG_KEY = "__rehab_log__"

    def __init__(self, path: str | None = None) -> None:
        self.path = path
        self._stats: dict[tuple[str, str], SourceStats] = {}
        self._shadow_log: list[dict] = []
        self._benchmark: dict[tuple[str, str],
                              BenchmarkRegistration] = {}
        self._rehab_log: list[dict] = []
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for key, d in raw.items():
                if key == self._SHADOW_LOG_KEY:
                    self._shadow_log = list(
                        d.get("entries", []))
                    continue
                if key == self._BENCH_KEY:
                    for entry in d.get("entries", []):
                        regn = BenchmarkRegistration.from_dict(
                            entry)
                        self._benchmark[(regn.owner,
                                         regn.root)] = regn
                    continue
                if key == self._REHAB_LOG_KEY:
                    self._rehab_log = list(
                        d.get("entries", []))
                    continue
                owner, _, root = key.partition("\x1f")
                self._stats[(owner, root)] = SourceStats.from_dict(d)

    # -- queries ------------------------------------------------------

    def stats_for(self, owner: str, source: str) -> SourceStats:
        key = ((owner or "").strip().lower(), source_root(source))
        return self._stats.get(key, SourceStats())

    def tier_for(self, owner: str, source: str) -> str:
        return self.tier_of(self.stats_for(owner, source))

    def tier_of_record(self, record: MemoryRecord) -> str:
        return self.tier_for(record.owner, record.source)

    @staticmethod
    def flag_active(stats: SourceStats) -> bool:
        """The poison override is operative: a poison event
        not covered by a completed rehabilitation, or a
        permanent flag (rehabilitation ruling, 2026-10-21)."""
        return stats.permanent \
            or stats.poison > stats.poison_covered

    @staticmethod
    def tier_of(stats: SourceStats) -> str:
        if SourceTrustRegistry.flag_active(stats):
            return TIER_FLAGGED
        if stats.score >= PROVEN_MIN_SCORE:
            return TIER_PROVEN
        return TIER_UNPROVEN

    def identities(self) -> dict[tuple[str, str], SourceStats]:
        return dict(self._stats)

    # -- benchmark source registration (Benchmark Wave 2, B5) ---------

    def register_benchmark_source(
            self, owner: str, source: str, *, dataset: str,
            harness: str) -> BenchmarkRegistration:
        """Declare that filings from this (owner, source root)
        identity are a benchmark harness ingesting a named
        published dataset. The gate satisfies its corroboration
        requirements (G5b/G5c) for this identity by registration;
        every other gate applies in full, and the declaration is
        stamped into the gate's audit note for each admission it
        satisfies. Dataset and harness names are REQUIRED - an
        anonymous registration would be a laundering path, so it
        is refused. Registration moves no tier and accrues no
        track record; it is a declaration log entry."""
        if not (dataset or "").strip():
            raise ValueError(
                "benchmark registration requires a dataset name")
        if not (harness or "").strip():
            raise ValueError(
                "benchmark registration requires a harness name")
        key = ((owner or "").strip().lower(), source_root(source))
        regn = BenchmarkRegistration(
            owner=key[0], root=key[1],
            dataset=dataset.strip(), harness=harness.strip(),
            registered_at=datetime.utcnow().isoformat())
        self._benchmark[key] = regn
        self._save()
        return regn

    def benchmark_registration_for(
            self, owner: str, source: str
    ) -> BenchmarkRegistration | None:
        key = ((owner or "").strip().lower(), source_root(source))
        return self._benchmark.get(key)

    def benchmark_registrations(self) -> list[BenchmarkRegistration]:
        """Every live registration, for audit."""
        return [self._benchmark[k] for k in sorted(self._benchmark)]

    # -- event reporting (the gate calls these; reviewers too) -------

    def _bump(self, record: MemoryRecord, field_name: str) -> SourceStats:
        key = identity_of(record)
        stats = self._stats.setdefault(key, SourceStats())
        setattr(stats, field_name, getattr(stats, field_name) + 1)
        self._save()
        return stats

    def note_admitted(self, record: MemoryRecord,
                      via: str = "gate", reviewer: str = "") -> None:
        """A record from this origin was admitted and held.

        Round 4 (GA): via="gate" (the default - the gate reporting
        its own admission, or a caller modeling one) accrues held
        uncapped: the record passed the gate. via="review" models
        a REVIEWER admitting a queued record the gate would not
        land on its own; those accrue held capped at
        REVIEWER_HELD_CAP per (identity, reviewer), so one
        reviewer alone cannot mint proven. Capped admissions bump
        review_capped (visible, never silent). Crossing INTO
        proven arms the promotion-probation flag (GB).

        Rehabilitation (A, ruling 2026-10-21): every admission
        that accrues held here also advances the identity's
        clean streak, and a flagged identity whose streak
        reaches REHAB_STREAK_K completes its rehabilitation
        (see _complete_streak_rehabilitation)."""
        key = identity_of(record)
        stats = self._stats.setdefault(key, SourceStats())
        if via == "review":
            n = int(stats.review_held.get(reviewer, 0))
            if n >= REVIEWER_HELD_CAP:
                stats.review_capped += 1
                self._save()
                return
            stats.review_held[reviewer] = n + 1
        before = self.tier_of(stats)
        stats.held += 1
        # Rehabilitation (A): an admission that ACCRUES held is
        # a clean-streak step. A cap-refused reviewer admission
        # returned above and never reaches here - one reviewer
        # cannot walk a flagged source back alone (GA's
        # arithmetic, applied to the way back as to the mint).
        stats.clean_streak += 1
        self._complete_streak_rehabilitation(key, stats)
        after = self.tier_of(stats)
        if before != TIER_PROVEN and after == TIER_PROVEN:
            stats.probation = True
        self._save()

    # -- promotion probation (Round 4, GB) ---------------------------

    def probation_pending(self, owner: str, source: str) -> bool:
        return bool(self.stats_for(owner, source).probation)

    def consume_probation(self, owner: str, source: str) -> bool:
        """Clear the probation flag; True if it was pending. The
        gate calls this when the probation filing actually queues
        (never in shadow mode - measurement must not eat it)."""
        key = ((owner or "").strip().lower(), source_root(source))
        stats = self._stats.get(key)
        if stats is None or not stats.probation:
            return False
        stats.probation = False
        self._save()
        return True

    # -- rehabilitation (incharge ruling 2026-10-21, A + C) -------

    def _apply_rehabilitation(
            self, key: tuple[str, str], stats: SourceStats,
            *, mode: str, decided_by: str,
            rationale: str) -> None:
        """The shared completion (A and C): cover the poison
        history (never erase it), consume the one journey,
        reset the streak, arm GB probation, and append the
        audit entry. Grants no score - from here the tier is
        score arithmetic. The caller saves."""
        stats.poison_covered = stats.poison
        stats.rehabilitations += 1
        stats.clean_streak = 0
        stats.probation = True
        self._rehab_log.append({
            "seq": len(self._rehab_log) + 1,
            "owner": key[0], "root": key[1],
            "mode": mode,
            "decided_by": decided_by,
            "rationale": rationale,
            "at": datetime.utcnow().isoformat(),
            "poison": stats.poison,
            "held": stats.held,
            "disputes": stats.disputes,
        })

    def _complete_streak_rehabilitation(
            self, key: tuple[str, str],
            stats: SourceStats) -> bool:
        """Candidate A's completion check, run after every
        held-accruing admission. Completes only for a
        currently-flagged, non-permanent identity on its one
        journey, at the full streak price (REHAB_STREAK_K)."""
        if stats.permanent or stats.rehabilitations >= 1:
            return False
        if not self.flag_active(stats):
            return False
        if stats.clean_streak < REHAB_STREAK_K:
            return False
        self._apply_rehabilitation(key, stats, mode="streak",
                                   decided_by="", rationale="")
        return True

    def rehabilitate(self, owner: str, source: str, *,
                     decided_by: str, rationale: str) -> bool:
        """Candidate C: manual rehabilitation - a named human
        lifts a flagged identity's poison override, recorded.

        decided_by and rationale are REQUIRED: an unrecorded
        rehabilitation would be a laundering path, so an
        anonymous one is refused (ValueError). Returns False
        when there is nothing to lift (identity unknown or
        not currently flagged) or the flag is PERMANENT (a
        poison event after a completed rehabilitation - no
        path in this registry lifts it). On success the
        completion is Candidate A's, mode "manual", with the
        decider and rationale in the rehabilitation log."""
        if not (decided_by or "").strip():
            raise ValueError(
                "rehabilitation requires a named decider")
        if not (rationale or "").strip():
            raise ValueError(
                "rehabilitation requires a rationale")
        key = ((owner or "").strip().lower(),
               source_root(source))
        stats = self._stats.get(key)
        if stats is None or stats.permanent:
            return False
        if not self.flag_active(stats):
            return False
        self._apply_rehabilitation(
            key, stats, mode="manual",
            decided_by=decided_by.strip(),
            rationale=rationale.strip())
        self._save()
        return True

    def rehabilitation_log(self) -> list[dict]:
        """Every completed rehabilitation (streak and manual),
        for audit."""
        return [dict(e) for e in self._rehab_log]

    # -- shadow-mode reporting (Round 4) ------------------------------

    @staticmethod
    def claim_key_of(record: MemoryRecord) -> str:
        """The gate's claim-adjacency key (normalised body
        prefix, the same rule G5/G5b/G5c use), so the shadow
        log's notion of 'the same claim' matches the gate's."""
        return (record.content or record.text).strip().lower()[:80]

    def note_shadow(self, record: MemoryRecord,
                    would_queue: bool) -> None:
        """A shadow-mode G5c evaluation: counted for the queue-rate
        report, never tier-moving. Round 5: also appended to the
        shadow decision log (the longitudinal instrument)."""
        key = identity_of(record)
        stats = self._stats.setdefault(key, SourceStats())
        if would_queue:
            stats.shadow_would_queue += 1
        else:
            stats.shadow_would_pass += 1
        self._shadow_log.append({
            "seq": len(self._shadow_log) + 1,
            "record_id": record.id,
            "owner": key[0], "root": key[1],
            "registry_tier": self.tier_of(stats),
            "confidence": record.provenance.confidence,
            "epistemic_tier": record.epistemic_tier,
            "claim_key": self.claim_key_of(record),
            "would_queue": bool(would_queue),
            "disposition": "",
        })
        self._save()

    def note_shadow_disposition(self, record_id: str,
                                disposition: str) -> bool:
        """A reviewer annotates the latest shadow decision for
        a record (e.g. 'legit-lone-source', 'poison-caught').
        False = no shadow decision exists for that record."""
        for entry in reversed(self._shadow_log):
            if entry["record_id"] == record_id:
                entry["disposition"] = disposition
                self._save()
                return True
        return False

    @property
    def shadow_log(self) -> list[dict]:
        return [dict(e) for e in self._shadow_log]

    @staticmethod
    def _confidence_band(confidence: float) -> str:
        if confidence < 0.50:
            return "<0.50"
        if confidence < 0.65:
            return "0.50-0.64"
        # 0.80 = the gate's LONE_SOURCE_CONFIDENCE (mm.write_gate);
        # named here rather than imported - the gate imports this
        # module, never the reverse.
        if confidence < 0.80:
            return "0.65-0.79"
        return ">=0.80"

    def shadow_breakdown(self) -> dict:
        """Would-queue rates sliced the way the incharge's HOLD
        decision asked (Round 5): by registry tier, epistemic
        tier, confidence band, source identity, disposition."""
        def _bucket() -> dict:
            return {"would_queue": 0, "would_pass": 0,
                    "would_queue_rate": None}

        def _add(dim: dict, name: str, wq: bool) -> None:
            b = dim.setdefault(name, _bucket())
            b["would_queue" if wq else "would_pass"] += 1

        dims: dict[str, dict] = {
            "by_registry_tier": {}, "by_epistemic_tier": {},
            "by_confidence_band": {}, "by_source": {},
            "by_disposition": {}}
        for e in self._shadow_log:
            wq = bool(e["would_queue"])
            _add(dims["by_registry_tier"], e["registry_tier"], wq)
            _add(dims["by_epistemic_tier"], e["epistemic_tier"], wq)
            _add(dims["by_confidence_band"],
                 self._confidence_band(float(e["confidence"])), wq)
            _add(dims["by_source"], f"{e['owner']}|{e['root']}", wq)
            _add(dims["by_disposition"],
                 e["disposition"] or "unjudged", wq)
        for dim in dims.values():
            for b in dim.values():
                n = b["would_queue"] + b["would_pass"]
                b["would_queue_rate"] = (b["would_queue"] / n) if n \
                    else None
        return {"decisions": len(self._shadow_log), **dims}

    def shadow_outcomes(self,
                        existing: dict[str, MemoryRecord]) -> dict:
        """The longitudinal join (Round 5): for every would-queue
        shadow decision, what happened LATER, judged against a
        current records snapshot?

        - CORRECTED: a record from a disjoint origin (different
          owner AND different source root) declares supersedes
          or contradicts against the decision's record;
        - CORROBORATED: a same-claim record (the gate's claim
          key) from a disjoint origin is present;
        - STILL-LONE: neither - the fact stands on one origin
          still (what enforcement would have kept in queue).
        Checked in that order: a correction is the stronger
        signal about the original decision."""
        counts = {"corroborated": 0, "corrected": 0, "still_lone": 0}
        entries = []
        for e in self._shadow_log:
            if not e["would_queue"]:
                continue
            outcome = "still_lone"
            for rec in existing.values():
                if rec.id == e["record_id"]:
                    continue
                if (rec.owner or "").strip().lower() == e["owner"]:
                    continue
                if source_root(rec.source) == e["root"]:
                    continue
                declared = (list(rec.provenance.supersedes)
                            + list(rec.provenance.contradicts))
                if e["record_id"] in declared:
                    outcome = "corrected"
                    break
            if outcome == "still_lone":
                for rec in existing.values():
                    if rec.id == e["record_id"]:
                        continue
                    if (rec.owner or "").strip().lower() == e["owner"]:
                        continue
                    if source_root(rec.source) == e["root"]:
                        continue
                    if self.claim_key_of(rec) == e["claim_key"]:
                        outcome = "corroborated"
                        break
            counts[outcome] += 1
            entries.append({"record_id": e["record_id"],
                            "identity": f"{e['owner']}|{e['root']}",
                            "outcome": outcome})
        return {"would_queue_total": sum(counts.values()),
                **counts, "entries": entries}

    def shadow_report(self) -> dict:
        """Per-identity shadow counts + totals (the incharge's
        measurement ask: would-queue rates by source)."""
        per = {}
        tq = tp = 0
        for (owner, root), s in sorted(self._stats.items()):
            if s.shadow_would_queue or s.shadow_would_pass:
                per[f"{owner}|{root}"] = {
                    "would_queue": s.shadow_would_queue,
                    "would_pass": s.shadow_would_pass}
                tq += s.shadow_would_queue
                tp += s.shadow_would_pass
        return {"per_identity": per,
                "would_queue": tq, "would_pass": tp,
                "would_queue_rate": (tq / (tq + tp)) if (tq + tp)
                else None}

    def note_dispute(self, target_record: MemoryRecord) -> None:
        """One of this origin's records was superseded/contradicted
        by an admitted record from a disjoint origin.
        Rehabilitation (A): a dispute also resets the identity's
        clean streak to zero - the way back must be unbroken."""
        stats = self._bump(target_record, "disputes")
        stats.clean_streak = 0
        self._save()

    def note_poison(self, record: MemoryRecord) -> None:
        """This origin submitted content the G0 secrets sweep
        rejected - a hard trust signal. Rehabilitation (A + C):
        the event resets the clean streak, and a poison event
        after a completed rehabilitation makes the flag
        PERMANENT - the one journey cannot be reused."""
        stats = self._bump(record, "poison")
        stats.clean_streak = 0
        if stats.rehabilitations >= 1:
            stats.permanent = True
        self._save()

    def note_queued(self, record: MemoryRecord) -> None:
        self._bump(record, "queued")

    def note_rejected(self, record: MemoryRecord) -> None:
        self._bump(record, "rejected")

    # -- persistence ---------------------------------------------------

    def _save(self) -> None:
        if not self.path:
            return
        raw = {"\x1f".join(key): stats.to_dict()
               for key, stats in self._stats.items()}
        if self._shadow_log:
            raw[self._SHADOW_LOG_KEY] = {"entries": self._shadow_log}
        if self._benchmark:
            raw[self._BENCH_KEY] = {
                "entries": [r.to_dict()
                            for r in self.benchmark_registrations()]}
        if self._rehab_log:
            raw[self._REHAB_LOG_KEY] = {
                "entries": self._rehab_log}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, sort_keys=True)
        os.replace(tmp, self.path)


__all__ = [
    "SourceTrustRegistry", "SourceStats", "BenchmarkRegistration",
    "identity_of", "source_root",
    "PROVEN_MIN_SCORE", "DISPUTE_WEIGHT", "REVIEWER_HELD_CAP",
    "REHAB_STREAK_K",
    "TIER_UNPROVEN", "TIER_PROVEN", "TIER_FLAGGED",
]
