"""reflect - memory -> conclusion.

v0.1 STUB: interface only. Not implemented.

The core differentiator of the milestone. Instead of returning retrieved
context for the agent to interpret, `reflect` *reasons over memories to a
conclusion*: answers, dispositions, standing judgments. Frequently asked
standing questions get cached answers ("mental models") that are rewritten in
the background as memory evolves - so a deciding agent boots from settled
answers, not raw recall.

Pattern inspiration (Wave 1): hindsight's `reflect` operation - the only
first-class memory->conclusion mechanism found - plus its mental models as
cached standing answers and background knowledge-page reconciliation
("what holds *now*"). Reimplemented from scratch; no hindsight code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Provenance:
    """Mnemonic-pattern provenance primitives for one memory record.

    v0.4 Phase 1 (ADDED): the conflict monitor (mm.resolver) counts
    *declared* contradictions purely over these fields - deterministic,
    no LLM, no content analysis. Nothing here is inferred: a contradiction
    exists only when a record's provenance names it.

    Fields follow the mnemonic pattern cited in ARCHITECTURE.md ?4:
    per-record `provenance.confidence` + `supersedes` relation +
    bi-temporal (valid_from / recorded_at) triad.
    """

    confidence: float = 1.0          # 0..1 - source reliability as recorded
    contradicts: list[str] = field(default_factory=list)  # record ids this record contradicts
    supersedes: list[str] = field(default_factory=list)   # record ids this record replaces
    valid_from: datetime | None = None    # bi-temporal: when the claim became true
    recorded_at: datetime | None = None   # bi-temporal: when the claim was recorded


@dataclass
class MemoryRecord:
    """A single unit of memory entering reflection.

    v0.5 (Phase-3 FROZEN, 2026-10-19): schema extended additively per
    phase3-freeze-v0.5.md. All new fields defaulted - v0.4 records
    upgrade without migration. No destructive migration without the
    founder's explicit approval gate (standing boundary).
    """

    id: str
    text: str
    timestamp: datetime
    source: str = ""          # e.g. "episodic/session-42", "sop/distilled"
    salience: float = 0.5     # 0..1, importance independent of recency
    provenance: Provenance = field(default_factory=Provenance)  # v0.4: conflict primitives
    # --- v0.5 additions (all defaulted) ---
    content: str = ""         # canonical content; write gate sets text+content together
    type: str = "fact"        # decision|learning|error_fix|pattern|procedure|
                              # preference|fact|solution|episodic (S3 taxonomy)
    epistemic_tier: str = "unknown"  # observed|derived|inferred|unknown (1504)
    explicit: bool = False    # user-stored vs auto-extracted (1918/S4)
    owner: str = ""           # (1509) who/what the record belongs to
    gathered_how: str = ""    # REA-17: how the evidence was gathered
    consent_scope: str = ""   # retention consent scope (authorization gate)
    tier: str = "active"      # active|cooled|archive (Janitor-managed)
    created_at: float = 0.0   # epoch seconds; 0.0 = unset
    last_accessed: float = 0.0
    access_count: int = 0
    decay_score: float = 1.0  # maintained by Janitor (idea 72); 1.0 = fresh
    ttl_class: str = "session"  # ephemeral|session|unverified-days|verified-no-ttl
    invalidation_contract: str = ""  # conditions + lifetime (1506)
    superseded_with_replacement: bool = False  # (idea 72)
    episodic_record_id: str | None = None  # semantic->episode pointer (idea 70)
    write_audit: dict = field(default_factory=dict)  # gate outcomes (1916/S2)

    # --- v0.6 additions (all defaulted, additive only) ---
    decay_exempt: bool = False  # immune threat class (instinct 2): a record
                                # that must never lifecycle-decay. Set by the
                                # immune write defence only; default False.
    # Benchmark Wave 2 (B2 spec, voted 2026-10-20): bi-temporal
    # validity window - [valid_at, invalid_at) is the interval
    # this record is IN FORCE. Distinct from the provenance
    # triad (valid_from/recorded_at describe the claim's own
    # timeline); the window governs retrieval: as-of recall
    # (mm.episodic) never surfaces a record outside its window.
    # Ingest stamps valid_at = record timestamp when unset;
    # supersession stamps invalid_at on the superseded record
    # through the storage lifecycle whitelist - the only
    # post-seal write the window ever takes. None = unbounded.
    valid_at: datetime | None = None
    invalid_at: datetime | None = None
    # Design consult (2026-10-21, ChatGPT ruling T1/T2 - DT-A):
    # ids of CURRENTLY OPEN cross-shard disputes naming this
    # record. A cache of dispute open-ness projected onto the
    # record so shard-local readers can see the flag without
    # the mesh; the dispute record + audit trail in mm.shards
    # stays authoritative. Written ONLY by the mesh (Core),
    # through the storage lifecycle whitelist; [] = not
    # currently disputed. History lives on the dispute record,
    # never here.
    dispute_refs: list[str] = field(default_factory=list)


@dataclass
class Conclusion:
    """The output of reflection: a conclusion, not a context dump."""

    text: str
    confidence: float                    # 0..1 (calibration is an open question)
    evidence_ids: list[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    disposition: str = "neutral"         # decision posture used, e.g. "skeptical"


@dataclass
class MentalModel:
    """A cached standing answer to a standing question."""

    question: str
    answer: Conclusion
    last_refreshed: datetime
    invalidated: bool = False


def reflect(
    records: list[MemoryRecord],
    question: str,
    disposition: str = "skeptical",
) -> Conclusion:
    """Reason over memories to a conclusion for `question`.

    This is memory -> conclusion, not memory -> context. The implementation
    must weigh evidence, reconcile contradictions (via mm.resolver upstream),
    and return a conclusion with cited evidence - never a raw context dump.

    TODO (research): what exactly should reflect compute - free-text
    conclusion, structured disposition-aware answer, or both? What is the
    output contract? See ARCHITECTURE.md ?1.
    """
    raise NotImplementedError(
        "v0.1 stub - implement once the reflect output contract is defined "
        "(ARCHITECTURE.md ?1, open questions)."
    )


def get_mental_model(question: str) -> MentalModel | None:
    """Return the cached standing answer for a standing question, if fresh.

    TODO (research): invalidation policy - contradiction arrival? temporal
    decay? explicit agent edit? See ARCHITECTURE.md ?1.
    """
    raise NotImplementedError(
        "v0.1 stub - implement once the mental-model invalidation policy "
        "is defined (ARCHITECTURE.md ?1, open questions)."
    )


def refresh_models() -> list[MentalModel]:
    """Background job: rewrite cached standing answers from current memory.

    TODO (research): schedule/trigger policy - on contradiction? on schedule?
    See ARCHITECTURE.md ?1.
    """
    raise NotImplementedError(
        "v0.1 stub - implement once the refresh trigger policy is defined."
    )
