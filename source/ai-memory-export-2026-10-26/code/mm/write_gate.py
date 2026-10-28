"""write_gate - quality-gated write path. FAIL-CLOSED.

Phase-3 (2026-10-20, chunk 2). Every memory passes through gates before
it lands. Uncertain writes go to a review queue - they are NEVER silently
admitted and NEVER silently dropped (both outcomes are logged).

Gate order (ChatGPT Gate-design review, 2026-10-20: dedup BEFORE
contradiction so an identical record is a duplicate, not a conflict;
provenance/authorization added as G2):
  P1 actionability        - 2.1 regex: action verbs / when-if-then /
                              instead-of / error-fix patterns (HD-1)
  P2 specificity          - 2.1 regex: >=2 concrete-detail signals
                              (numbers, versions, codes, refs) (HD-1)
  P3 relevance            - 2.1 regex: negative filter on casual-opinion
                              openers (HD-1)
  G1 schema validity        - required fields, enum values, types
  G2 provenance/authorization - source validity, retention basis
                              (explicit=True, or consent_scope, or
                              system-internal gathered_how)
  G3 exact dedup            - (owner, type, content-prefix, explicit);
                              LLM semantic dedup is OUT (head decision)
  G4 declared contradiction - provenance-declared only (deterministic,
                              via the same rule as mm.resolver.monitor);
                              supersedes -> close-on-replacement;
                              contradicts-without-supersedes -> review
  G5 epistemic tier         - inferred claims need corroboration or review
  G5b lone-source corroboration - claims at confidence >= 0.80 need a
                              disjoint-origin corroborator (Round 2,
                              Option C); same-owner corrections exempt
                              per the incharge's Round-3 ruling C,
                              EXCEPT when the claimant is registry-
                              flagged (Ruling A amendment, 2026-10-21);
                              a registry-flagged claimant needs TWO
                              non-flagged, pairwise-disjoint
                              corroborators (Round 6 follow-up, the
                              incharge's ruling D-A + D-D), and a
                              flagged identity never counts as a
                              corroborator for any claimant (Ruling A)
  G5c source trust          - the band below 0.80 is judged by the
                              origin's source-trust registry tier
                              (Round 3, Option A); inert unless a
                              registry is wired into the gate
  G6 claim calibration     - provenance.confidence plausible for the tier
  G7 salience scoring       - write-time importance (S3); scoring, not a gate

Outcomes: ADMITTED (all gates pass) / QUEUED (uncertain - needs review) /
REJECTED (hard fail, e.g. schema invalid or secrets/PII detected).
Every outcome writes write_audit on the record and appends to the log.

Founder design bar (2026-10-20): this memory must beat a human mind, not
copy it. The write gate is where that starts:
- Perfect verbatim recall with provenance: admitted records are SEALED -
  never edited in place. A correction arrives as a NEW record with
  provenance.supersedes; the old record stays, flagged, forever
  retrievable. Humans confabulate and overwrite; this store doesn't.
- Conflict-conditioned decisions: contradictions are declared, measured,
  and either closed deterministically (supersession) or routed to review
  - never silently picked-a-side.
- Honest confidence: G6 caps confidence at what the evidence tier
  supports. The gate would rather queue than let an overconfident claim
  land.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from mm.reflect import MemoryRecord
from mm.source_trust import (
    SourceTrustRegistry,
    TIER_FLAGGED,
    TIER_PROVEN,
    identity_of as trust_identity_of,
)

# ---------------------------------------------------------------------------
# Constants (inspectable priors, not tuned constants)
# ---------------------------------------------------------------------------

VALID_TYPES = {
    "decision", "learning", "error_fix", "pattern", "procedure",
    "preference", "fact", "solution", "episodic",
}
VALID_EPISTEMIC_TIERS = {"observed", "derived", "inferred", "unknown"}
VALID_TIERS = {"active", "cooled", "archive"}
VALID_TTL = {"ephemeral", "session", "unverified-days", "verified-no-ttl"}

# Tier-implied confidence caps (G6): a claim may not be MORE confident than
# its evidence tier allows. Exceeding the cap -> review, not rejection.
TIER_CONFIDENCE_CAPS = {
    "observed": 1.00,
    "derived": 0.90,
    "inferred": 0.70,
    "unknown": 0.50,
}

# Lone-source corroboration threshold (G5b, Red-Team Round 2): a claim
# at or above this declared confidence, from an observed/derived tier,
# must be corroborated from a disjoint origin or it queues.
LONE_SOURCE_CONFIDENCE = 0.80

# Write-time importance (G7, S3 taxonomy weights) + language markers.
TYPE_WEIGHTS = {
    "decision": 1.00, "error_fix": 0.95, "learning": 0.80,
    "pattern": 0.70, "procedure": 0.65, "preference": 0.60,
    "solution": 0.55, "fact": 0.50, "episodic": 0.30,
}
MARKER_BONUS = 0.10  # per language marker, capped
EXPLICIT_BOOST = 0.15  # 1918/S4: user-stored outranks auto-extracted
_LANGUAGE_MARKERS = ("decided to", "root cause", "always", "never")

# Secrets/PII patterns -> hard reject (never stored, never queued).
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)(api[_-]?key|password|passwd|secret)\s*[:=]\s*\S+"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    # Red-Team Round 1 (2026-10-20): the original trio let 10/10 canary
    # formats through (evals/redteam_round1.py class A1). The formats
    # below are the measured evasions, added as patterns; card numbers
    # and base64-encoded secrets are checked structurally in
    # _scan_secrets (Luhn + decode-and-scan), not by regex.
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),            # AWS key id
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),           # GitHub token
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),         # GitHub PAT v2
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),          # Slack token
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
               r"\.[A-Za-z0-9_-]{5,}\b"),                     # JWT
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|password|passwd|secret)"
               r"\s+is\s+\S+"),                              # "password is X"
    re.compile(r"(?i)pass[\s-]?word\s*[:=]\s*\S+"),          # "pass word: X"
    re.compile(r"\b\d{4} \d{4} \d{4}\b"),                     # 12-digit grouped ID
)

# Structural secret checks (Red-Team Round 1): a Luhn-valid 13-19 digit
# sequence is a card number whatever its label; a long base64 token
# that DECODES to text naming a secret is a secret whatever its label.
_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_B64_CANDIDATE = re.compile(r"\b[A-Za-z0-9+/]{20,}={0,2}\b")
_B64_SECRET_WORDS = ("password", "passwd", "secret", "api_key",
                     "api-key", "apikey", "credential", "private_key")


def _luhn_ok(digits: str) -> bool:
    total = 0
    alt = False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if d < 0 or d > 9:
            return False
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0

# --- 2.1 regex pre-storage gates (HD-1, head decision 2026-10-20) -----------
# Three cheap regex gates run BEFORE G1 on every write (<50ms target).
# Any gate fails -> rejected, never stored. Frozen spec 2.1 stands; the
# G1-G7 set runs after them. Rationale (HD-1): G7 salience scores but
# never rejects, so 2.1 adds the reject-on-irrelevance filtering the
# G-set lacks. These are heuristics, not parsers: they catch vague,
# unactionable, unspecific, casual content at the write boundary.

# P1 actionability: action verbs, when/if...then conditionals,
# "instead of" comparisons, error-fix patterns.
_P21_ACTION_VERBS = re.compile(r"""
    \b(
      fix|fixe[sd]|fixing|
      deploy\w*|set|sets|setting|
      run|ran|running|
      writ\w*|wrot\w*|
      updat\w*|install\w*|configur\w*|
      add\w*|remov\w*|delet\w*|
      creat\w*|enabl\w*|disabl\w*|
      restart\w*|reboot\w*|test\w*|check\w*|verif\w*|
      avoid\w*|use[sd]?|using|uses|apply|appl\w*|
      build|built|building|
      migrat\w*|backup|backups|backing[-\s]?up|
      monitor\w*|alert\w*|patch\w*|resolv\w*|
      decid\w*|choos\w*|chos\w*|vot\w*|
      clos\w*|open\w*|shut\w*|
      send|sent|sending|call\w*|
      improv\w*|freez\w*|froz\w*|
      match\w*|suspend\w*|block\w*|reject\w*|admit\w*|
      correct\w*|
      seal\w*|log\w*|record\w*|fil\w*|
      stop\w*|start\w*|keep\w*|requir\w*|need\w*|
      rotat\w*|rais\w*|serv\w*|catch|caught|
      ship\w*|paus\w*
    )\b
""", re.IGNORECASE | re.VERBOSE)
_P21_WHEN_THEN = re.compile(r"\b(when|if)\b.{0,120}?\bthen\b",
                            re.IGNORECASE | re.DOTALL)
_P21_INSTEAD_OF = re.compile(r"\binstead of\b", re.IGNORECASE)
_P21_ERRORFIX = re.compile(
    r"\b(error|bug|defect|failure|failed|fails|broken|crash\w*|"
    r"exception|incident|regression|workaround|hotfix)\b", re.IGNORECASE)

# P2 specificity: >=2 concrete-detail signals (numbers, versions, codes,
# refs). Spans are merged so "v2.3" counts once, not as version + number.
_P21_VERSION = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
_P21_NUMBER = re.compile(r"\b\d+(?::\d+)+\b|\b\d+\b")
_P21_CODE = re.compile(r"\b[\w.\-]*\d[\w.\-]*\b")
_P21_REF = re.compile(r"https?://\S+|\b[\w.\-]+/[\w.\-]+\b|\u00a7\s?\d+|#\d+\b")
_P21_SPECIFICITY_PATTERNS = (_P21_VERSION, _P21_NUMBER, _P21_CODE, _P21_REF)
_P21_MIN_SIGNALS = 2

# P3 relevance: negative filter on casual-opinion openers (start of text).
_P21_OPENER = re.compile(r"""^\s*(
    i\s+think|imo|in\s+my\s+opinion|to\s+me|
    maybe|perhaps|possibly|
    just\s+wondering|random\s+thought|quick\s+thought|shower\s+thought|
    lol|btw|hmm+|uh+|idk|i\s+dunno|tbh|fwiw|
    not\s+sure\s+if|i\s+guess|i\s+feel|i\s+believe
)\b""", re.IGNORECASE | re.VERBOSE)


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

@dataclass
class GateOutcome:
    """The write gate's verdict for one record."""

    verdict: str                 # "admitted" | "queued" | "rejected"
    reasons: list[str] = field(default_factory=list)
    record: MemoryRecord | None = None

    @property
    def admitted(self) -> bool:
        return self.verdict == "admitted"

    @property
    def queued(self) -> bool:
        return self.verdict == "queued"


@dataclass
class ReviewItem:
    """One queued write awaiting human/agent review."""

    record: MemoryRecord
    reasons: list[str]
    queued_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution: str = ""


class ReviewQueue:
    """Fail-closed holding area: uncertain writes wait here, never land silently."""

    def __init__(self) -> None:
        self._items: list[ReviewItem] = []

    def add(self, record: MemoryRecord, reasons: list[str]) -> ReviewItem:
        item = ReviewItem(record=record, reasons=list(reasons))
        self._items.append(item)
        return item

    def pending(self) -> list[ReviewItem]:
        return [i for i in self._items if not i.resolved]

    def resolve(self, record_id: str, resolution: str) -> bool:
        """Mark an item resolved ('admit' or 'drop'); returns False if unknown id."""
        for item in self._items:
            if item.record.id == record_id and not item.resolved:
                item.resolved = True
                item.resolution = resolution
                return True
        return False


class WriteGate:
    """The quality-gated write path."""

    def __init__(
        self, trust_registry: SourceTrustRegistry | None = None,
        trust_shadow: bool = False
    ) -> None:
        self.review_queue = ReviewQueue()
        self.log: list[dict] = []  # every outcome, admitted or not
        # Red-Team Round 3 (Option A): optional source-trust registry.
        # Default None = legacy behaviour (G5c inert, no outcome
        # tracking); deployments wire a registry to activate both.
        self.trust_registry = trust_registry
        # Red-Team Round 4 (the incharge's HOLD decision): shadow
        # mode. With a registry wired AND trust_shadow=True, G5c
        # still evaluates and the registry records the would-be
        # decision (note_shadow), but the verdict NEVER changes -
        # measurement before enforcement. Enforcement stays off
        # until the incharge lifts the hold.
        self.trust_shadow = trust_shadow

    # -- public API ------------------------------------------------------

    def admit(
        self,
        record: MemoryRecord,
        existing: dict[str, MemoryRecord],
    ) -> GateOutcome:
        """Run the gate pipeline. Fail-closed: uncertain -> review queue.

        When a source-trust registry is wired, every outcome is
        reported to it (Round 3): admissions build the origin's
        track record, an admitted record's declared supersessions /
        contradictions of disjoint-origin records register as
        disputes against those origins, and a G0 secrets rejection
        registers as a poison flag."""
        outcome = self._admit(record, existing)
        if self.trust_registry is not None:
            self._track_outcome(record, existing, outcome)
        return outcome

    def _track_outcome(
        self,
        record: MemoryRecord,
        existing: dict[str, MemoryRecord],
        outcome: GateOutcome,
    ) -> None:
        reg = self.trust_registry
        assert reg is not None
        if outcome.verdict == "admitted":
            reg.note_admitted(record)
            own = trust_identity_of(record)
            seen: set[tuple[str, str]] = set()
            declared = (list(record.provenance.supersedes)
                        + list(record.provenance.contradicts))
            for tid in declared:
                target = existing.get(tid)
                if target is None or tid == record.id:
                    continue
                ident = trust_identity_of(target)
                if ident == own or ident in seen:
                    continue
                seen.add(ident)
                reg.note_dispute(target)
        elif outcome.verdict == "rejected":
            audit = record.write_audit or {}
            g0_failed = any(
                g.get("gate") == "G0-secrets" and not g.get("pass")
                for g in audit.get("gates", []))
            if g0_failed:
                reg.note_poison(record)
            reg.note_rejected(record)
        else:
            reg.note_queued(record)

    def _admit(
        self,
        record: MemoryRecord,
        existing: dict[str, MemoryRecord],
    ) -> GateOutcome:
        """The gate pipeline itself (see admit() for the contract)."""
        audit: dict = {"gates": [], "at": datetime.utcnow().isoformat()}
        queued_reasons: list[str] = []

        # Red-Team Round 1 (class A16, Fo hypothesis T16): decay_exempt
        # is the immune threat class's flag (v0.6) - a writer granting
        # it to its own record opts out of forgetting forever (at
        # +200d the janitor could not even cool it). Only immune
        # threat records (owner "immune", source "immune/...") may
        # carry it; anyone else's flag is cleared here and the
        # clearing is written into the audit trail.
        if record.decay_exempt and not (
                record.owner == "immune"
                and record.source.startswith("immune/")):
            record.decay_exempt = False
            audit["decay_exempt_cleared"] = (
                "decay_exempt is reserved to the immune threat class")

        # P-stage (HD-1): 2.1 regex pre-storage gates run BEFORE G1.
        # Any gate fails -> rejected, never stored (fail-closed).
        p_results = self._check_pregates(record)
        p_failed = [f"{name} failed: {detail}"
                    for name, passed, detail in p_results if not passed]
        for name, passed, detail in p_results:
            audit["gates"].append({"gate": name, "pass": passed,
                                   "detail": detail})
        if p_failed:
            return self._reject(record, audit, p_failed)

        # G1 schema validity (hard gate)
        problems = self._check_schema(record)
        audit["gates"].append({"gate": "G1-schema", "pass": not problems,
                               "detail": problems or "ok"})
        if problems:
            return self._reject(record, audit, problems)

        # G0 secrets/PII sweep (hard gate - never stored, never queued)
        secrets = self._scan_secrets(record)
        audit["gates"].append({"gate": "G0-secrets", "pass": not secrets,
                               "detail": secrets or "clean"})
        if secrets:
            return self._reject(record, audit, secrets)

        # G2 provenance / authorization
        auth_ok, auth_note = self._check_authorization(record)
        audit["gates"].append({"gate": "G2-authorization", "pass": auth_ok,
                               "detail": auth_note})
        if not auth_ok:
            queued_reasons.append(auth_note)

        # G3 exact dedup (before contradiction - identical = duplicate)
        dup_id = self._find_duplicate(record, existing)
        audit["gates"].append({"gate": "G3-dedup", "pass": dup_id is None,
                               "detail": f"duplicate-of {dup_id}" if dup_id else "unique"})
        if dup_id:
            # Duplicate: do not create a second record; refresh the original's
            # access metadata (recency of use beats recency of write).
            orig = existing[dup_id]
            orig.access_count += 1
            return self._finish(record, audit, "rejected",
                                [f"exact duplicate of {dup_id}; refreshed original"])

        # G4 declared contradiction
        contra = self._check_contradictions(record, existing)
        audit["gates"].append({"gate": "G4-contradiction", "pass": contra["pass"],
                               "detail": contra["detail"]})
        if contra["superseded"]:
            for loser_id in contra["superseded"]:
                loser = existing[loser_id]
                loser.superseded_with_replacement = True
                loser.tier = "archive"
            audit["close_on_replacement"] = contra["superseded"]
        if contra["held"]:
            audit["supersession_held"] = contra["held"]
            queued_reasons.append(
                "cross-owner supersession of high-standing record(s) "
                f"{contra['held']} held for review - NOT closed "
                "(Red-Team Round 1: supersession is not a delete "
                "capability for foreign owners)")
        if contra["review"]:
            queued_reasons.append(contra["detail"])

        # G5 epistemic tier
        tier_ok, tier_note = self._check_epistemic_tier(record, existing)
        audit["gates"].append({"gate": "G5-epistemic", "pass": tier_ok,
                               "detail": tier_note})
        if not tier_ok:
            queued_reasons.append(tier_note)

        # G5b lone-source corroboration (Red-Team Round 2, Option C -
        # partner vote; the incharge's amendments: episodic captures
        # included, corroboration must be origin-disjoint). Round 1's
        # root cause was self-declared provenance: the gate checked a
        # claim's shape, never whether anyone independent backs it.
        ls_ok, ls_note = self._check_lone_source(record, existing)
        audit["gates"].append({"gate": "G5b-corroboration",
                               "pass": ls_ok, "detail": ls_note})
        if not ls_ok:
            queued_reasons.append(ls_note)

        # G5c source trust (Red-Team Round 3, Option A): the band
        # below G5b's threshold is governed by the claimant's track
        # record instead. Inert unless a registry is wired.
        st_ok, st_note = self._check_source_trust(record, existing)
        audit["gates"].append({"gate": "G5c-source-trust",
                               "pass": st_ok, "detail": st_note})
        if not st_ok:
            queued_reasons.append(st_note)

        # G6 claim calibration
        cal_ok, cal_note = self._check_calibration(record)
        audit["gates"].append({"gate": "G6-calibration", "pass": cal_ok,
                               "detail": cal_note})
        if not cal_ok:
            queued_reasons.append(cal_note)

        # G7 salience scoring (scoring, never a gate)
        salience, components = self._score_salience(record)
        record.salience = salience
        audit["salience_components"] = components
        audit["gates"].append({"gate": "G7-salience", "pass": True,
                               "detail": f"scored {salience:.3f}"})

        record.write_audit = audit
        if queued_reasons:
            self.review_queue.add(record, queued_reasons)
            outcome = self._finish(record, audit, "queued", queued_reasons)
        else:
            outcome = self._finish(record, audit, "admitted", ["all gates passed"])
        return outcome

    # -- gates -----------------------------------------------------------

    def _check_pregates(
        self, r: MemoryRecord
    ) -> list[tuple[str, bool, str]]:
        """2.1 regex pre-storage gates (HD-1). Returns
        [(gate_name, passed, detail)] for P1/P2/P3. Cheap by design
        (three regex scans; <50ms target)."""
        blob = f"{r.text}\n{r.content}"

        # P1 actionability
        p1_hits = []
        m = _P21_ACTION_VERBS.search(blob)
        if m:
            p1_hits.append(f"action verb {m.group(0)!r}")
        m = _P21_WHEN_THEN.search(blob)
        if m:
            p1_hits.append("when/if...then conditional")
        if _P21_INSTEAD_OF.search(blob):
            p1_hits.append("'instead of' comparison")
        m = _P21_ERRORFIX.search(blob)
        if m:
            p1_hits.append(f"error-fix pattern {m.group(0)!r}")
        p1_ok = bool(p1_hits)
        p1_detail = ("; ".join(p1_hits) if p1_ok
                     else "no action verb, when/if-then, 'instead of', "
                          "or error-fix pattern")

        # P2 specificity: >=2 concrete-detail signals, spans merged so
        # one token (e.g. "v2.3") counts once, and unique span texts so
        # a signal repeated in text+content still counts once.
        spans: list[tuple[int, int]] = []
        for pat in _P21_SPECIFICITY_PATTERNS:
            spans.extend(m.span() for m in pat.finditer(blob))
        spans.sort()
        merged: list[list[int]] = []
        for s, e in spans:
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        unique_signals = {blob[s:e].lower() for s, e in merged}
        n_signals = len(unique_signals)
        p2_ok = n_signals >= _P21_MIN_SIGNALS
        p2_detail = (f"{n_signals} concrete-detail signal(s)"
                     if p2_ok else
                     f"only {n_signals} concrete-detail signal(s), "
                     f"need >={_P21_MIN_SIGNALS} (numbers, versions, "
                     f"codes, refs)")

        # P3 relevance: negative filter on casual-opinion openers.
        opener = _P21_OPENER.match(blob.strip())
        p3_ok = opener is None
        p3_detail = ("no casual-opinion opener" if p3_ok
                     else f"casual-opinion opener {opener.group(0)!r}")

        return [
            ("P1-actionability", p1_ok, p1_detail),
            ("P2-specificity", p2_ok, p2_detail),
            ("P3-relevance", p3_ok, p3_detail),
        ]

    def _check_schema(self, r: MemoryRecord) -> list[str]:
        problems = []
        if not r.id:
            problems.append("missing id")
        if not (r.text or r.content):
            problems.append("missing text/content")
        if r.type not in VALID_TYPES:
            problems.append(f"invalid type {r.type!r}")
        if r.epistemic_tier not in VALID_EPISTEMIC_TIERS:
            problems.append(f"invalid epistemic_tier {r.epistemic_tier!r}")
        if r.tier not in VALID_TIERS:
            problems.append(f"invalid tier {r.tier!r}")
        if r.ttl_class not in VALID_TTL:
            problems.append(f"invalid ttl_class {r.ttl_class!r}")
        c = r.provenance.confidence
        if not (0.0 <= c <= 1.0):
            problems.append(f"provenance.confidence {c} outside [0,1]")
        if not (0.0 <= r.salience <= 1.0):
            problems.append(f"salience {r.salience} outside [0,1]")
        return problems

    def _scan_secrets(self, r: MemoryRecord) -> list[str]:
        blob = f"{r.text}\n{r.content}"
        hits = [f"secret/PII pattern matched ({p.pattern[:24]}?)"
                for p in _SECRET_PATTERNS if p.search(blob)]
        # Structural checks (Red-Team Round 1): labels lie, shapes
        # and decodings do not.
        for m in _CARD_CANDIDATE.finditer(blob):
            digits = re.sub(r"\D", "", m.group(0))
            if 13 <= len(digits) <= 19 and _luhn_ok(digits):
                hits.append("secret/PII pattern matched "
                            "(card-number Luhn check)")
                break
        import base64
        for m in _B64_CANDIDATE.finditer(blob):
            token = m.group(0)
            try:
                raw = base64.b64decode(token + "=" * (-len(token) % 4),
                                       validate=False)
                decoded = raw.decode("latin-1").lower()
            except Exception:
                continue
            if any(w in decoded for w in _B64_SECRET_WORDS):
                hits.append("secret/PII pattern matched "
                            "(base64-encoded secret)")
                break
        return hits

    def _check_authorization(self, r: MemoryRecord) -> tuple[bool, str]:
        """Retention basis: explicit user storage, consent scope, or
        system-internal episodic capture. Anything else -> review."""
        if r.explicit:
            return True, "explicit user-stored (consented)"
        if r.consent_scope:
            return True, f"consent_scope={r.consent_scope!r}"
        if r.gathered_how.startswith("episodic/") or r.type == "episodic":
            return True, "system-internal episodic capture"
        return False, ("no retention basis: not explicit, no consent_scope, "
                       "not episodic - needs review")

    def _dedup_key(self, r: MemoryRecord) -> tuple[str, str, str, bool]:
        body = (r.content or r.text).strip().lower()
        body = re.sub(r"\s+", " ", body)[:200]
        return (r.owner, r.type, body, r.explicit)

    def _find_duplicate(
        self, r: MemoryRecord, existing: dict[str, MemoryRecord]
    ) -> str | None:
        key = self._dedup_key(r)
        for eid, rec in existing.items():
            if eid != r.id and self._dedup_key(rec) == key:
                return eid
        return None

    @staticmethod
    def _supersession_closable(r: MemoryRecord,
                               loser: MemoryRecord) -> bool:
        """May r's supersedes claim close `loser` immediately?

        Red-Team Round 1 (class A4): before this check, ANY admitted
        record could archive ANY other record by naming it in
        provenance.supersedes - a foreign owner could delete the
        founder's standing memories by declaration. Closable now:
        - same owner (a lane corrects its own records), or
        - the loser is low-standing (inferred/unknown tier, or
          confidence <= 0.5): tentative records stay correctable
          cross-owner by design (the V4 contamination drill depends
          on it).
        Anything else is HELD for review, loser untouched.
        """
        if loser.owner == r.owner:
            return True
        if loser.epistemic_tier in ("inferred", "unknown"):
            return True
        if loser.provenance.confidence <= 0.5:
            return True
        return False

    def _check_contradictions(
        self, r: MemoryRecord, existing: dict[str, MemoryRecord]
    ) -> dict:
        """Declared contradictions only (same rule as mm.resolver.monitor).

        - supersedes names an existing record -> close-on-replacement
          (deterministic, admitted; loser archived with replacement flag),
          subject to _supersession_closable: a cross-owner supersession
          of a high-standing record is HELD for review instead.
        - contradicts names an existing record WITHOUT superseding ->
          ambiguous -> review queue (needs adjudication, never auto-resolved).
        - dangling refs -> noted, never blocking.
        """
        superseded, held, review_ids, dangling = [], [], [], []
        for tid in r.provenance.supersedes:
            if tid in existing and tid != r.id:
                if self._supersession_closable(r, existing[tid]):
                    superseded.append(tid)
                else:
                    held.append(tid)
            elif tid != r.id:
                dangling.append(tid)
        for tid in r.provenance.contradicts:
            if tid == r.id or tid in r.provenance.supersedes:
                continue
            if tid in existing:
                review_ids.append(tid)
            else:
                dangling.append(tid)
        detail = (
            f"supersedes={superseded} held={held} "
            f"contradicts-open={review_ids} "
            f"dangling={sorted(set(dangling))}"
        )
        return {
            "pass": not review_ids and not held,
            "superseded": superseded,
            "held": held,
            "review": bool(review_ids),
            "detail": ("close-on-replacement; " if superseded else "")
                      + ("held supersession -> review; " if held else "")
                      + ("ambiguous contradictions -> review; " if review_ids else "")
                      + detail,
        }

    def _check_epistemic_tier(
        self, r: MemoryRecord, existing: dict[str, MemoryRecord]
    ) -> tuple[bool, str]:
        """Inferred claims need corroboration: another record with the same
        dedup-adjacent claim at derived-or-better tier, or explicit=True."""
        if r.epistemic_tier in ("observed", "derived"):
            return True, f"{r.epistemic_tier} needs no corroboration"
        if r.epistemic_tier == "inferred":
            body = (r.content or r.text).strip().lower()[:80]
            for eid, rec in existing.items():
                if eid == r.id:
                    continue
                other = (rec.content or rec.text).strip().lower()[:80]
                if other == body and rec.epistemic_tier in ("observed", "derived"):
                    return True, f"corroborated by {eid}"
            if r.explicit:
                return True, "inferred but user-stated (explicit)"
            return False, "inferred claim without corroboration -> review"
        return False, f"unknown epistemic tier -> review"

    @staticmethod
    def _source_root(source: str) -> str:
        """Origin lineage root: the channel family a source string
        names ('external/kb-import' -> 'external'). Two records from
        the same root share a lineage however their full strings
        differ."""
        return (source or "").split("/")[0].strip().lower()

    def _benchmark_registration(self, r: MemoryRecord):
        """Benchmark Wave 2 (B5): if a source-trust registry is
        wired AND this record's identity carries a benchmark
        registration, return it. A registered benchmark source is
        a DECLARED ingest path (named dataset, named harness -
        see mm/source_trust.py), not a lone unknown origin, so
        G5b/G5c satisfy their corroboration requirement by
        registration. Registration waives corroboration ONLY:
        P1-P3, G0-G7 quality rules apply in full, and the pass
        note names the dataset + harness in the audit trail.
        No registry wired (the production default) -> None."""
        reg = self.trust_registry
        if reg is None:
            return None
        return reg.benchmark_registration_for(r.owner, r.source)

    @staticmethod
    def _registration_note(regn) -> str:
        return (f"benchmark-registered source (dataset "
                f"{regn.dataset!r} via harness {regn.harness!r})"
                f" - corroboration satisfied by registration "
                f"(Benchmark Wave 2, B5); all quality gates "
                f"still apply")

    def _check_lone_source(
        self, r: MemoryRecord, existing: dict[str, MemoryRecord]
    ) -> tuple[bool, str]:
        """G5b (Red-Team Round 2, Option C): a high-confidence claim
        may not land on one origin's say-so.

        Applies when the record claims tier observed/derived at
        confidence >= LONE_SOURCE_CONFIDENCE. It passes only if an
        existing, non-superseded record makes the SAME claim (the
        gate's claim-adjacency rule: normalised body prefix, as in
        G5) from a DISJOINT origin - different owner AND different
        source root, so a paraphrase cluster re-declared under a
        second owner string from the same lineage counts once, not
        as corroboration (origin-graph discounting, corpus 3360).

        Declared explicit does NOT exempt: 'explicit' is itself a
        declared field, and Round 1's poisons declared it too.
        Episodic captures are NOT exempt (the incharge's amendment:
        the MINJA plant arrived through the episodic path). The
        immune threat class IS exempt - a first-party system record,
        not a claim about the world. Everything else that fails
        queues for review: fail-closed, recoverable, never a silent
        admit and never a silent drop.

        Red-Team Round 6 follow-up (the incharge's ruling
        D-A + D-D): when a source-trust registry is wired and
        the CLAIMANT's registry tier is flagged (a G0 poison
        event on its history), one corroborator no longer
        suffices - the claim needs TWO corroborators, each
        non-flagged, pairwise disjoint in owner AND source
        root. A sticky flag raises the corroboration bar, and
        flagged identities cannot corroborate one another.
        Benchmark registration above is unchanged. With no
        registry wired there is no flag state and the
        single-corroborator rule governs, as before.

        Ruling A amendment (incharge, ChatGPT, 2026-10-21, on
        the Gemini audit of the Round-6 follow-up): the two
        interpretation residuals the follow-up record left open
        are closed. Ruling C's same-owner correction bypass no
        longer fires for a FLAGGED claimant - its supersession
        needs the same two clean, independent corroborators
        before it takes effect - and a flagged identity never
        counts as a corroborator for any claimant, flagged or
        not. Both closures are registry-wired only; unwired,
        legacy behaviour is byte-for-byte what it was.
        """
        if r.epistemic_tier not in ("observed", "derived"):
            return True, (f"tier {r.epistemic_tier} - corroboration "
                          f"handled by G5, G5b targets observed/derived")
        if r.provenance.confidence < LONE_SOURCE_CONFIDENCE:
            return True, (f"confidence {r.provenance.confidence:.2f} "
                          f"below {LONE_SOURCE_CONFIDENCE:.2f} - no "
                          f"corroboration required")
        if r.owner == "immune" and r.source.startswith("immune/"):
            return True, "immune threat class - exempt (system record)"
        # Benchmark Wave 2 (B5): a benchmark-registered source is
        # a declared corpus ingest path, not a lone unknown
        # origin - corroboration is satisfied by registration
        # (see _benchmark_registration). The note is stamped in
        # the audit trail for every such admission.
        regn = self._benchmark_registration(r)
        if regn is not None:
            return True, self._registration_note(regn)
        # Flag state (Ruling A amendment, below): computed BEFORE
        # the same-owner bypass, because the bypass is exactly
        # what the amendment conditions on it. Flag state exists
        # only when a registry is wired - the same opt-in shape
        # as G5c; unwired, there is no flag state and every rule
        # below reduces to its legacy form.
        reg = self.trust_registry
        claimant_flagged = (
            reg is not None
            and reg.tier_for(r.owner, r.source) == TIER_FLAGGED)
        # Incharge ruling (Red-Team Round 3, ChatGPT, Option C): a
        # correction superseding the corrector's OWN record lands
        # immediately - the supersession act is its own context.
        # Conditions per the ruling: the correction must explicitly
        # identify the record(s) it supersedes (declared supersedes
        # naming existing records) and meet the existing confidence
        # threshold (this check only runs at >= LONE_SOURCE_
        # CONFIDENCE, so that holds by construction). EVERY named
        # existing target must be the corrector's own - a mixed
        # target set gets no bypass (fail-closed reading, flagged
        # to the incharge in the round record). Cross-owner
        # corrections still need disjoint corroboration below.
        #
        # RULING A AMENDMENT (incharge, ChatGPT, 2026-10-21, on
        # the Gemini independent audit of the Round-6 follow-up -
        # redteam-round6-gemini-audit-ruling.txt, question (m) and
        # F-11): the audit showed this bypass, read together with
        # the D-A + D-D scoping, left two holes. (1) A FLAGGED
        # claimant could supersede its own records here with ZERO
        # corroborators - an uncorroborated >= 0.80 mutation from
        # a known-poisoned source, sidestepping the two-key rule
        # entirely. (2) A flagged identity could serve as the sole
        # corroborator for a NON-flagged claimant below, because
        # D-D was consulted only inside the flagged-claimant rule.
        # The amendment closes both, no broader: when the claimant
        # is flagged, this bypass does NOT fire - the filing falls
        # through to the flagged-claimant rule below and needs the
        # same TWO clean, independent corroborators before the
        # supersession takes effect (the store persists a closing
        # only on admission, so a queued correction closes
        # nothing; the claimant's flagged state is retained, and
        # clearing it remains rehabilitation's job, not this
        # gate's). And in the non-flagged branch below, a flagged
        # identity never counts as a corroborator at all.
        targets = [existing[tid] for tid in r.provenance.supersedes
                   if tid in existing and tid != r.id]
        if targets and all(t.owner == r.owner for t in targets) \
                and not claimant_flagged:
            return True, (f"same-owner correction superseding own "
                          f"record(s) {[t.id for t in targets]} - "
                          f"immediate per incharge ruling C "
                          f"(Red-Team Round 3)")
        candidates = self._lone_source_corroborators(r, existing)
        if not claimant_flagged:
            # Ruling A, hole (2): with a registry wired, a flagged
            # identity can never count as a clean corroborator -
            # for ANY claimant, not only a flagged one (the audit's
            # GU3 / F-11). Flagged candidates are skipped, never
            # fatal: one clean disjoint corroborator still admits.
            if reg is not None:
                eligible = [
                    (eid, rec) for eid, rec in candidates
                    if reg.tier_for(rec.owner, rec.source)
                    != TIER_FLAGGED]
            else:
                eligible = candidates
            if eligible:
                eid, rec = eligible[0]
                return True, (f"corroborated by {eid} from a "
                              f"disjoint origin (owner "
                              f"{rec.owner!r}, source root "
                              f"{self._source_root(rec.source)!r})")
            if candidates:
                return False, (
                    f"high-confidence claim (tier "
                    f"{r.epistemic_tier}, confidence "
                    f"{r.provenance.confidence:.2f}) corroborated "
                    f"only by flagged source(s) "
                    f"{[eid for eid, _ in candidates]} - a flagged "
                    f"identity can never count as a clean "
                    f"corroborator -> review (Ruling A amendment, "
                    f"incharge 2026-10-21, on the Gemini audit)")
            return False, (f"lone-source high-confidence claim "
                           f"(tier {r.epistemic_tier}, confidence "
                           f"{r.provenance.confidence:.2f}) without "
                           f"a disjoint-origin corroborator -> "
                           f"review (Red-Team Round 2, Option C)")
        # Red-Team Round 6 follow-up (the incharge's ruling
        # D-A + D-D, ChatGPT - re-taken through a verified
        # channel after Round 6's own consultation failed its
        # integrity check; see the round-6 record's parent
        # addendum): a FLAGGED claimant (a G0 poison event on
        # its registry history) may not land a high-confidence
        # claim on one corroborator like a clean source. It
        # needs TWO corroborators, each NON-FLAGGED (D-D: a
        # flagged identity cannot launder another), pairwise
        # disjoint in owner AND source root (D-A: the second
        # key must be a genuinely independent origin, not a
        # sibling of the first). Each candidate is already
        # disjoint from the claimant by the candidate filter.
        # Flag state exists only when a registry is wired -
        # the same opt-in shape as G5c; unwired, the legacy
        # single-corroborator rule above governs everyone.
        eligible = [(eid, rec) for eid, rec in candidates
                    if reg.tier_for(rec.owner, rec.source)
                    != TIER_FLAGGED]
        for i in range(len(eligible)):
            for j in range(i + 1, len(eligible)):
                a_id, a = eligible[i]
                b_id, b = eligible[j]
                a_owner, a_root = trust_identity_of(a)
                b_owner, b_root = trust_identity_of(b)
                if a_owner != b_owner and a_root != b_root:
                    return True, (
                        f"flagged claimant corroborated by "
                        f"{a_id} and {b_id} - two non-flagged, "
                        f"pairwise-disjoint corroborators "
                        f"(incharge ruling D-A + D-D, Red-Team "
                        f"Round 6 follow-up)")
        return False, (
            f"flagged source (poison event on its track "
            f"record) filing a high-confidence claim (tier "
            f"{r.epistemic_tier}, confidence "
            f"{r.provenance.confidence:.2f}) with "
            f"{len(eligible)} eligible non-flagged disjoint "
            f"corroborator(s) - a flagged claimant needs two, "
            f"pairwise disjoint in owner and root -> review "
            f"(incharge ruling D-A + D-D, Red-Team Round 6 "
            f"follow-up)")

    def _lone_source_corroborators(
        self, r: MemoryRecord, existing: dict[str, MemoryRecord]
    ) -> list[tuple[str, MemoryRecord]]:
        """G5b's candidate corroborator set: existing,
        non-superseded records making the SAME claim (the
        gate's claim-adjacency rule: normalised body prefix,
        as in G5) at tier observed/derived from a DISJOINT
        origin - different owner AND different source root
        than the claimant's, so a paraphrase cluster from one
        lineage counts once, not as corroboration. Iteration
        follows the store's order, as the pre-follow-up scan
        did (the single-corroborator path takes the first)."""
        body = (r.content or r.text).strip().lower()[:80]
        out: list[tuple[str, MemoryRecord]] = []
        for eid, rec in existing.items():
            if eid == r.id or rec.superseded_with_replacement:
                continue
            if rec.epistemic_tier not in ("observed", "derived"):
                continue
            other = (rec.content or rec.text).strip().lower()[:80]
            if other != body:
                continue
            if rec.owner == r.owner:
                continue
            if self._source_root(rec.source) == self._source_root(
                    r.source):
                continue
            out.append((eid, rec))
        return out

    def _check_source_trust(
        self, r: MemoryRecord, existing: dict[str, MemoryRecord]
    ) -> tuple[bool, str]:
        """G5c (Red-Team Round 3, Option A): the sub-threshold band
        is governed by the claimant's track record.

        G5b bites only at confidence >= LONE_SOURCE_CONFIDENCE;
        Round 2's record named the band below it as the residual
        hole (poison simply declares 0.79). When a source-trust
        registry is wired, a band record (tier observed/derived,
        confidence < LONE_SOURCE_CONFIDENCE) is judged by its
        origin's registry tier:

        - proven: passes on its track record;
        - flagged (a G0 poison event on its history): queues, no
          corroboration rescue - the claim can still land through
          the proven origin that corroborates it, under that
          origin's own name;
        - unproven: passes only with (a) a same-claim corroborator
          from a disjoint origin whose registry tier is PROVEN
          (Sybil clusters of fresh identities cannot manufacture
          this - their corroboration is worth nothing here), or
          (b) a store anchor: the record supersedes an existing
          record of its OWN (the incharge's ruling-C logic in the
          band: it cannot correct what never landed, so an anchor
          proves this identity already passed a gate or a review).

        Declared explicit does NOT exempt (declared fields lie -
        the Round 1/2 lesson G5b already applies). The immune
        threat class IS exempt, as in G5b. Unwired registry ->
        pass with a note: legacy behaviour, deployments opt in.

        Red-Team Round 4 additions: (GB) a PROVEN source whose
        promotion probation is pending queues ONCE - the first
        band filing after promotion is human-seen; the flag is
        consumed when it fires. (Shadow) with trust_shadow=True
        the decision below is computed and recorded on the
        registry (note_shadow) but NEVER enforced - the incharge
        held enforcement pending real-traffic queue rates.
        """
        reg = self.trust_registry
        if reg is None:
            return True, "source-trust registry not wired - legacy"
        if r.epistemic_tier not in ("observed", "derived"):
            return True, (f"tier {r.epistemic_tier} - trust band "
                          f"covers observed/derived; G5 governs "
                          f"the rest")
        if r.owner == "immune" and r.source.startswith("immune/"):
            return True, "immune threat class - exempt (system record)"
        if r.provenance.confidence >= LONE_SOURCE_CONFIDENCE:
            return True, (f"confidence "
                          f"{r.provenance.confidence:.2f} at/above "
                          f"the G5b threshold - corroboration rule "
                          f"governs, trust band does not apply")
        tier = reg.tier_for(r.owner, r.source)
        regn = reg.benchmark_registration_for(r.owner, r.source)
        if regn is not None:
            # Benchmark Wave 2 (B5): registration satisfies the
            # band's corroboration requirement by declaration
            # (see _benchmark_registration); the shadow epilogue
            # below still records the decision, stamped with the
            # dataset + harness names.
            decision = (True, self._registration_note(regn))
        elif tier == TIER_PROVEN:
            if reg.probation_pending(r.owner, r.source):
                if self.trust_shadow:
                    reg.note_shadow(r, would_queue=True)
                    return True, ("SHADOW: promotion probation - "
                                  "would queue this first band "
                                  "filing after promotion; verdict "
                                  "unchanged (Round 4 shadow mode)")
                reg.consume_probation(r.owner, r.source)
                return False, ("proven source on promotion "
                               "probation - the first band filing "
                               "after promotion queues for review "
                               "(Red-Team Round 4, guardrail GB)")
            decision = (True, (f"proven source (track record "
                               f"{reg.stats_for(r.owner, r.source)})"
                               f" - passes on its standing"))
        elif tier == TIER_FLAGGED:
            decision = (False, (f"flagged source (poison event on "
                                f"its track record) - band claims "
                                f"queue regardless of corroboration "
                                f"(Red-Team Round 3, Option A)"))
        else:
            decision = self._band_unproven_decision(r, existing,
                                                    reg)
        if self.trust_shadow:
            reg.note_shadow(r, would_queue=not decision[0])
            if not decision[0]:
                return True, ("SHADOW: would queue - "
                              + decision[1]
                              + "; verdict unchanged (Round 4 "
                                "shadow mode)")
            return decision
        return decision

    def _band_unproven_decision(
        self, r: MemoryRecord, existing: dict[str, MemoryRecord],
        reg: SourceTrustRegistry
    ) -> tuple[bool, str]:
        """G5c's unproven branch: anchor first (cheap, structural),
        then proven corroboration. Extracted in Round 4 so the
        shadow/probation epilogue wraps one decision value."""
        anchors = [tid for tid in r.provenance.supersedes
                   if tid in existing and tid != r.id
                   and existing[tid].owner == r.owner]
        if anchors:
            return True, (f"unproven source with store anchor - "
                          f"supersedes own record(s) {anchors} "
                          f"already held in the store")
        body = (r.content or r.text).strip().lower()[:80]
        for eid, rec in existing.items():
            if eid == r.id or rec.superseded_with_replacement:
                continue
            if rec.epistemic_tier not in ("observed", "derived"):
                continue
            other = (rec.content or rec.text).strip().lower()[:80]
            if other != body:
                continue
            if rec.owner == r.owner:
                continue
            if self._source_root(rec.source) == self._source_root(
                    r.source):
                continue
            if reg.tier_for(rec.owner, rec.source) != TIER_PROVEN:
                continue
            return True, (f"unproven source corroborated by {eid} "
                          f"from a PROVEN disjoint origin (owner "
                          f"{rec.owner!r})")
        return False, (f"unproven source (track record "
                       f"{reg.stats_for(r.owner, r.source)}) filing "
                       f"in the sub-threshold band (confidence "
                       f"{r.provenance.confidence:.2f}) without a "
                       f"proven corroborator or store anchor -> "
                       f"review (Red-Team Round 3, Option A)")

    def _check_calibration(self, r: MemoryRecord) -> tuple[bool, str]:
        cap = TIER_CONFIDENCE_CAPS[r.epistemic_tier]
        c = r.provenance.confidence
        if c > cap:
            return False, (f"confidence {c:.2f} exceeds {r.epistemic_tier} "
                           f"cap {cap:.2f} -> review")
        return True, f"confidence {c:.2f} within {r.epistemic_tier} cap"

    def _score_salience(self, r: MemoryRecord) -> tuple[float, dict]:
        """Write-time importance (S3). Computed once, stored, applied as a
        bounded retrieval multiplier (1.0?1.5x) downstream - never
        recomputed per query."""
        body = f"{r.text} {r.content}".lower()
        markers = [m for m in _LANGUAGE_MARKERS if m in body]
        components = {
            "type_weight": TYPE_WEIGHTS[r.type],
            "markers": markers,
            "marker_bonus": min(len(markers) * MARKER_BONUS, 0.30),
            "explicit_boost": EXPLICIT_BOOST if r.explicit else 0.0,
        }
        score = (components["type_weight"] + components["marker_bonus"]
                 + components["explicit_boost"])
        return round(max(0.0, min(1.0, score)), 4), components

    # -- bookkeeping -----------------------------------------------------

    def _reject(self, r: MemoryRecord, audit: dict,
                problems: list[str]) -> GateOutcome:
        r.write_audit = audit
        entry = {"id": r.id, "verdict": "rejected", "reasons": problems,
                 "at": audit["at"]}
        self.log.append(entry)
        return GateOutcome(verdict="rejected", reasons=problems, record=r)

    def _finish(self, r: MemoryRecord, audit: dict, verdict: str,
                reasons: list[str]) -> GateOutcome:
        if verdict == "admitted":
            # SEAL: admitted records are immutable. Corrections arrive as
            # new records with provenance.supersedes - never in-place edits.
            # This is the perfect-verbatim-recall guarantee (founder bar).
            audit["sealed_at"] = audit["at"]
            audit["immutable"] = True
        entry = {"id": r.id, "verdict": verdict, "reasons": reasons,
                 "at": audit["at"]}
        self.log.append(entry)
        return GateOutcome(verdict=verdict, reasons=reasons, record=r)
