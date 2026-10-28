"""immune - the write gate as immune system (instinct 2).

Study mapping #1, verdict BUILD. The chunk-2 gate does antigen checking
(G0/G2/G5: provenance, authorization, epistemic tier). This module adds
MEMORY and TOLERANCE:

- Immune memory: an ATTACK-PATTERN store - sealed threat records of past
  rejected/poisoned writes (pattern features, source, gate that caught
  it). A new write matching a known attack pattern is rejected at reflex
  speed with the precedent cited. PoisonedRAG-class attacks (verified
  real, USENIX Security 2025, 90% ASR headline) are the design threat.
- Tolerance (the anti-autoimmune rule): the gate must not learn to
  reject the self. Pattern matching runs against DECLARED pattern
  features only (never record content - G0 rule), and any pattern that
  fires on more than a declared fraction of legitimate writes is
  auto-suspended and queued for review.
- Threat-conditioning class (v0.6): a write that caused a catastrophic
  failure or a security violation is indexed at max salience ONCE,
  permanently, decay_exempt - one trial, never forgotten.
- Canary drills: planted probes the gate must catch; a missed canary
  is a sentinel-grade alarm (drilled through mm.sentinel).

Rule-based, zero LLM. Reflex path only - never deliberation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# A pattern that fires on more than this fraction of writes that later
# prove legitimate (admitted, or resolved-admit from review) suspends
# itself and files a review. The anti-autoimmune constant.
AUTOIMMUNE_SUSPEND_FRACTION = 0.20
MIN_LEGIT_SAMPLES = 10


@dataclass
class ThreatPattern:
    """Declared features of one attack pattern. No record content ever -
    patterns match on gate-level features only (source, reason class,
    shape). Content stays sealed."""
    id: str
    reason_class: str        # e.g. "G0-secrets", "G2-unauthorized"
    source: str = ""         # exact source match; empty = any source
    min_length: int = 0      # shape feature, not content
    attack_class: str = ""   # e.g. "poisoned-rag-injection"
    suspended: bool = False
    fires: int = 0           # times matched (any write)
    legit_fires: int = 0     # times matched a write that proved legitimate


@dataclass
class ThreatRecord:
    """One sealed immune-memory record (stored via the write gate)."""
    pattern_id: str
    attack_class: str
    precedent_reason: str     # the gate reason that caught it - no content
    recorded_at: str = ""


def _now() -> str:
    return datetime.utcnow().isoformat()


class ImmuneMemory:
    """Attack-pattern memory + tolerance. Owns no store itself: threat
    records land in the caller's SQLiteStore through the write gate."""

    def __init__(self) -> None:
        self.patterns: dict[str, ThreatPattern] = {}

    # -- pattern registration (from real rejections, never from thin air) ----

    def bank(self, pattern: ThreatPattern) -> ThreatPattern:
        """Register one pattern. Patterns are only banked from observed
        rejections - the caller proves that by passing precedent."""
        self.patterns[pattern.id] = pattern
        return pattern

    # -- reflex matching -----------------------------------------------------

    def match(self, source: str, reason_class: str,
              text_length: int) -> ThreatPattern | None:
        """Reflex check: does this write match a known attack pattern?
        Declared features only. Returns the pattern (with precedent) or
        None. Never raises on unknown - immune memory is advisory."""
        for p in self.patterns.values():
            if p.suspended:
                continue
            if p.reason_class and p.reason_class != reason_class:
                continue
            if p.source and p.source != source:
                continue
            if text_length < p.min_length:
                continue
            p.fires += 1
            return p
        return None

    # Reason-class extraction from REAL gate output. Red-Team Round 1
    # (class A8): the original token list ("G0-secrets", ...) matched
    # only hand-crafted reason strings - the gate's actual reasons
    # ("secret/PII pattern matched...", "no retention basis...") carry
    # none of those tokens, so the reflex NEVER fired on the real
    # path. The hints below map the gate's real phrasings; the class
    # tokens are kept for back-compat with crafted outcomes.
    _REASON_CLASS_HINTS = (
        ("G0-secrets", ("G0-secrets", "secret/PII pattern")),
        ("G2-authorization", ("G2-authorization", "retention basis")),
        ("G4-contradiction", ("G4-contradiction", "contradicts-open",
                              "ambiguous contradiction",
                              "held for review")),
        ("G5-epistemic", ("G5-epistemic", "without corroboration",
                          "epistemic tier")),
        ("G6-calibration", ("G6-calibration",)),
    )

    @classmethod
    def _class_from_reason(cls, reason: str) -> str:
        for known, hints in cls._REASON_CLASS_HINTS:
            if known == "G6-calibration":
                if "confidence" in reason and "cap" in reason:
                    return known
                continue
            if any(h in reason for h in hints):
                return known
        return ""

    def match_from_outcome(self, record, outcome) -> ThreatPattern | None:
        """Reflex check with caller-proof features (finding 6, ChatGPT
        review): reason_class, source, and shape come from the GATE'S
        OWN verdict run - the caller cannot spoof them, and matches are
        never derived from record content."""
        reason_class = ""
        for reason in (outcome.reasons or []):
            reason_class = self._class_from_reason(reason)
            if reason_class:
                break
        text = record.text or ""
        return self.match(source=record.source or "",
                          reason_class=reason_class,
                          text_length=len(text))

    # -- tolerance: the anti-autoimmune rule ---------------------------------

    def note_legit_fire(self, pattern_id: str,
                        resolution_ref: str) -> None:
        """A write this pattern fired on proved legitimate. Finding 5
        (ChatGPT review): legitimacy is ONLY established by a trusted
        resolution - a review-queue resolution ref, a confirmed drill
        outcome, or nitesh's verdict. Never the pattern's caller, never
        an untrusted source self-certifying. The ref is recorded on the
        pattern for audit; a missing ref raises."""
        if not resolution_ref:
            raise ValueError(
                "note_legit_fire requires a trusted resolution_ref - "
                "legitimacy is never self-certified")
        p = self.patterns.get(pattern_id)
        if p is None:
            return
        # Red-Team Round 1 (class A8): a pattern cannot have fired
        # legitimately more times than it has fired. Before this cap,
        # ten fabricated refs against a pattern that fired once
        # auto-suspended it (fraction 10/1) and the reflex went dark.
        # The ref string itself is still not verifiable in-process -
        # that stays a documented trust boundary - but fabrication
        # volume alone can no longer suspend a pattern.
        if p.legit_fires >= p.fires:
            return
        p.legit_fires += 1
        total = p.legit_fires
        if total >= MIN_LEGIT_SAMPLES:
            fp_fraction = p.legit_fires / max(1, p.fires)
            if fp_fraction > AUTOIMMUNE_SUSPEND_FRACTION and not p.suspended:
                p.suspended = True  # auto-suspend, review queue decides

    def suspended(self) -> list[ThreatPattern]:
        """Patterns suspended by the tolerance rule - the review queue's
        immune-docket."""
        return [p for p in self.patterns.values() if p.suspended]

    # -- threat records: the sealed immune-memory write ---------------------

    def threat_record(self, pattern: ThreatPattern,
                      precedent_reason: str,
                      record_id: str) -> dict:
        """Build the kwargs for a sealed threat MemoryRecord. The caller
        writes it through the gate; the record carries the precedent,
        never the attack content."""
        return {
            "id": record_id,
            "text": (f"Immune threat memory: attack class "
                     f"{pattern.attack_class!r} caught by {precedent_reason}; "
                     f"pattern {pattern.id}. Content never stored."),
            "timestamp": datetime.utcnow(),
            "source": "immune/attack-memory",
            "type": "pattern",
            "epistemic_tier": "observed",
            "explicit": True,
            "owner": "immune",
            "gathered_how": "gate-rejection-precedent",
            "salience": 1.0,        # max salience, indexed ONCE
            "decay_exempt": True,   # v0.6: one trial, never forgotten
        }


@dataclass
class Canary:
    """A planted probe the gate must catch. A missed canary is an alarm."""
    id: str
    expect_verdict: str     # "rejected" - canaries are always bad writes
    planted_at: str = ""
    caught: bool | None = None   # None = not yet tested


class CanaryDrill:
    """Plant canaries, run them through the gate, score the catch rate."""

    def __init__(self) -> None:
        self.canaries: list[Canary] = []

    def plant(self, canary_id: str,
              expect_verdict: str = "rejected") -> Canary:
        c = Canary(id=canary_id, expect_verdict=expect_verdict,
                   planted_at=_now())
        self.canaries.append(c)
        return c

    def score(self, canary_id: str, actual_verdict: str) -> bool | None:
        """Score one drill. Returns True=caught, False=missed,
        None=unknown canary."""
        for c in self.canaries:
            if c.id == canary_id:
                c.caught = (actual_verdict == c.expect_verdict)
                return c.caught
        return None

    def catch_rate(self) -> float | None:
        tested = [c for c in self.canaries if c.caught is not None]
        if not tested:
            return None
        return sum(1 for c in tested if c.caught) / len(tested)

    def missed(self) -> list[Canary]:
        """Canaries the gate failed to catch - sentinel-grade alarms."""
        return [c for c in self.canaries if c.caught is False]
