"""shards - octopus arms: edge memory nodes (instinct 4).

~2/3 of the octopus's neurons are in its arms: local processing,
central goals. Each partner lane / domain gets a local memory shard
(its own SQLiteStore) that reads, writes (through its own gate), and
decides LOCALLY on goal signals from the center. The center (mind) does
not micromanage shard contents.

The center's job: goal signals down, summarized deltas up, and
inter-arm conflict resolution ONLY (the conflict monitor's M over
cross-shard declared contradictions). This is the partner-lane
architecture the council already runs socially; the agent makes it
mechanical.

Named risks (from the study): state divergence, race conditions,
memory-thrashing between arms. Mitigations: shards own their records
exclusively (single-owner interpretation, design doc 2.1 item 4);
cross-shard claims arrive as NEW records with provenance naming the
source shard - never as edits. A shard's write gate still fails closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from mm.reflect import MemoryRecord, Provenance
from mm.storage import SQLiteStore
from mm.resolver import monitor


def exact_content_key(record: MemoryRecord) -> str:
    """Deterministic cross-shard exact-duplicate key: normalized content +
    type. Finding 2 (ChatGPT review): local shard gates cannot see across
    shards, so the Core checks this key globally. Exact-only - never fuzzy,
    per the frozen exact-dedup decision."""
    body = (record.content or record.text).strip().lower()
    body = re.sub(r"\s+", " ", body)
    return hashlib.sha256(f"{record.type}\x00{body}".encode("utf-8")).hexdigest()


@dataclass
class GoalSignal:
    """A goal pushed down from the center to one lane."""
    lane: str
    instruction: str
    at: str = ""


@dataclass
class ShardDelta:
    """The summary a shard pushes up: counts + notable events."""
    lane: str
    records: int
    admitted: int = 0
    rejected: int = 0
    queued: int = 0
    at: str = ""


def _now() -> str:
    return datetime.utcnow().isoformat()


class Shard:
    """One lane's local memory. Exclusive record ownership; its own
    gate; local decisions on goal signals from the center."""

    def __init__(self, lane: str, store: SQLiteStore) -> None:
        self.lane = lane
        self.store = store
        self._core: "Core | None" = None  # set by Core.add_shard

    def write(self, record: MemoryRecord):
        """Local write, through the shard's own gate. Fail-closed.

        Red-Team Round 1 (classes A9/A9b): ownership is EXCLUSIVE -
        the holding lane IS the owner, whatever the record claims
        (provenance may name an origin; the owner field may not
        impersonate another lane). And when the shard belongs to a
        Core, an exact-content duplicate already held by another
        shard is refused BEFORE the local gate runs - the local gate
        cannot see across shards, so without this the same poison
        lands in every lane (post-hoc detection is not prevention).
        """
        record.owner = self.lane
        if self._core is not None:
            dup_lane = self._core.exact_duplicate_elsewhere(
                record, self.lane)
            if dup_lane is not None:
                raise ValueError(
                    f"cross-shard exact duplicate already held by "
                    f"shard {dup_lane!r}; refused at write time "
                    f"(Red-Team Round 1 guard)")
        return self.store.write(record)

    def search(self, query: str, limit: int = 10):
        return self.store.search(query, limit=limit)

    def delta(self) -> ShardDelta:
        log = self.store.gate_log()
        return ShardDelta(
            lane=self.lane,
            records=len(self.store),
            admitted=sum(1 for e in log if e["verdict"] == "admitted"),
            rejected=sum(1 for e in log if e["verdict"] == "rejected"),
            queued=sum(1 for e in log if e["verdict"] == "queued"),
            at=_now(),
        )

    def accept_goal(self, goal: GoalSignal) -> None:
        """Goal signals are recorded as shard-local memory (advisory,
        through the gate - the gate can still queue it)."""
        rec = MemoryRecord(
            id=f"goal-{self.lane}-{hash(goal.instruction) & 0xffffff:06x}",
            text=f"Goal signal for lane {self.lane}: {goal.instruction}",
            content=goal.instruction,
            timestamp=datetime.utcnow(),
            source="center/goal-signal",
            type="preference",
            epistemic_tier="observed",
            explicit=True,
            owner=self.lane,
            gathered_how="center-goal-signal",
            salience=0.9,
        )
        try:
            self.store.write(rec)
        except Exception:
            pass  # goals are advisory; a queued/refused goal never blocks


# ---------------------------------------------------------------------------
# Cross-shard dispute resolution (Phase-4 follow-up spec:
# hidden_files/implementation/cross-shard-resolution-spec.md).
#
# First principle (spec, verbatim): "The system never silently picks a
# winner. Every resolution names its authority, its evidence, and its
# decider, in an append-only audit trail."
#
# The ladder: L1 dispute opened on detection; L2 corroboration
# gathering (evidence, never resolution); L3 resolution in strict
# authority order - (a) same-author supersession, (b) founder
# decision, (c) quorum (low/medium stakes only, after a 24h founder
# right-of-first-refusal, vetoable), (d) timeout, which escalates
# and NEVER resolves. L0 (intra-shard) stays on the existing local
# gate flow, unchanged.
# ---------------------------------------------------------------------------

QUORUM_WINDOW = timedelta(hours=24)   # founder right-of-first-refusal
TIMEOUT_WINDOW = timedelta(days=7)    # escalate at >= 7d, never resolve


@dataclass
class Dispute:
    """One cross-shard dispute and its append-only audit trail.

    resolution and escalation are SEPARATE fields (spec R3): a
    dispute can be open AND timeout-escalated at once; timeout
    never resolves. Transitions are appended, never edited; the
    dispute is sealed on resolution in the audit trail (a founder
    reopen appends a transition - it does not rewrite history)."""
    dispute_id: str
    a_id: str
    a_lane: str
    b_id: str
    b_lane: str
    severity: float = 0.0     # monitor M for the pair, 0..1
    stakes: str = "medium"    # low|medium|high, set at open time
    detected_at: str = ""     # UTC ISO-8601; the single clock
    resolution: str = "open"        # open | resolved (R3)
    resolution_via: str = "none"    # none | supersession | moot |
                                    # founder | quorum (R3)
    escalation: str = "none"        # none | timeout (R3)
    corroboration: list = field(default_factory=list)
    quorum_snapshot: dict | None = None
    transitions: list = field(default_factory=list)
    resolved_at: str | None = None
    last_seen_at: str = ""


class Core:
    """The coordinating mind over the shards. Resolves cross-shard
    conflicts ONLY; never micromanages shard contents."""

    def __init__(self, dispute_store: SQLiteStore | None = None) -> None:
        self.shards: dict[str, Shard] = {}
        self.deltas: list[ShardDelta] = []
        # Cross-shard resolution state (spec above). Disputes live
        # in memory (detection is the source of truth for which
        # pairs exist); the core-lane dispute store, when attached,
        # is the append-only audit trail and the restart source
        # for resolution state.
        self.disputes: dict[str, Dispute] = {}
        self.error_log: list[dict] = []
        self.dispute_store = dispute_store
        if dispute_store is not None:
            self._restore_disputes()

    def add_shard(self, shard: Shard) -> None:
        self.shards[shard.lane] = shard
        shard._core = self  # wires the write-time duplicate guard
        # Dispute-tag reconcile: the constructor restores dispute
        # state before any shard exists, so a shard joining a
        # mesh that already holds disputes gets its records'
        # cached refs repaired against that state here.
        if self.disputes:
            self._reconcile_dispute_refs()

    def broadcast_goal(self, instruction: str,
                       lanes: list[str] | None = None) -> None:
        for lane, shard in self.shards.items():
            if lanes is None or lane in lanes:
                shard.accept_goal(GoalSignal(lane=lane,
                                             instruction=instruction,
                                             at=_now()))

    def collect_deltas(self) -> list[ShardDelta]:
        self.deltas = [s.delta() for s in self.shards.values()]
        return list(self.deltas)

    def cross_shard_conflicts(self, stakes: str = "medium") -> list[dict]:
        """Declared contradictions spanning shards: a record in shard A
        whose provenance names a record in shard B. Uses resolver.monitor
        over the union, then filters pairs whose two sides live in
        different shards. Pairs are (a_id, b_id, severity) tuples.

        Finding 13 (ChatGPT review): the monitor MEASURES - it never
        resolves. Resolution happens in the agent's mind via
        decision.select with the conflict score, fail-closed on
        impasse. A disputed record never becomes a high-confidence
        fact by monitoring alone."""
        union: list[MemoryRecord] = []
        owners: dict[str, str] = {}
        for lane, shard in self.shards.items():
            for rid, rec in shard.store.all_records().items():
                union.append(rec)
                owners.setdefault(rid, lane)
        report = monitor(union, stakes=stakes)
        out: list[dict] = []
        for a_id, b_id, severity in (report.pairs or []):
            lanes = {owners.get(str(a_id), "?"), owners.get(str(b_id), "?")}
            if len(lanes) > 1:
                out.append({"a": a_id, "b": b_id,
                            "lanes": sorted(lanes), "severity": severity})
        return out

    def exact_duplicate_elsewhere(self, record: MemoryRecord,
                                  own_lane: str) -> str | None:
        """Deterministic cross-shard exact-duplicate check (finding 2).

        Returns the lane holding an exact-content duplicate of `record`
        outside `own_lane`, or None. Exact-only (sha256 of normalized
        content + type) - never fuzzy, per the frozen exact-dedup
        decision. Callers should run this BEFORE a shard write when the
        record must be globally unique; the shard's own gate still runs
        fail-closed locally."""
        key = exact_content_key(record)
        for lane, shard in self.shards.items():
            if lane == own_lane:
                continue
            for rec in shard.store.all_records().values():
                if exact_content_key(rec) == key:
                    return lane
        return None

    # -- cross-shard dispute resolution (spec L1-L3) -------------------

    def attach_dispute_store(self, store: SQLiteStore) -> None:
        """Attach the core-lane store that carries the dispute
        audit trail; restores resolution state from it."""
        self.dispute_store = store
        self._restore_disputes()

    def _restore_disputes(self) -> None:
        """Restart survival (spec): rebuild dispute state from the
        core-lane audit trail. Each audit record carries the full
        dispute state after its transition; the state with the
        most transitions wins. Detection (open_disputes) remains
        the source of truth for which pairs exist."""
        if self.dispute_store is None:
            return
        fields = {f.name for f in Dispute.__dataclass_fields__.values()}
        best: dict[str, dict] = {}
        for rec in self.dispute_store.all_records().values():
            if rec.source != "core/dispute":
                continue
            try:
                payload = json.loads(rec.content or "{}")
            except ValueError:
                continue
            if payload.get("kind") != "dispute-state":
                continue
            st = payload.get("dispute") or {}
            did = st.get("dispute_id")
            if not did:
                continue
            cur = best.get(did)
            if (cur is None or len(st.get("transitions", []))
                    >= len(cur.get("transitions", []))):
                best[did] = st
        for did, st in best.items():
            self.disputes[did] = Dispute(
                **{k: v for k, v in st.items() if k in fields})
        self._reconcile_dispute_refs()

    def _owners(self) -> dict[str, str]:
        owners: dict[str, str] = {}
        for lane, shard in self.shards.items():
            for rid in shard.store.all_records():
                owners.setdefault(rid, lane)
        return owners

    @staticmethod
    def _dispute_id(a_id: str, b_id: str) -> str:
        lo, hi = sorted([str(a_id), str(b_id)])
        return f"dsp-{lo}-{hi}"

    def _record(self, lane: str, record_id: str) -> MemoryRecord | None:
        shard = self.shards.get(lane)
        return shard.store.get(record_id) if shard else None

    def _transition(self, d: Dispute, to: str, authority: str,
                    decider: str, rationale: str, now: datetime) -> None:
        """Append one transition and mirror it to the audit trail.
        Transitions are appended, never edited."""
        d.transitions.append({
            "at": now.isoformat(), "from": d.resolution, "to": to,
            "authority": authority, "decider": decider,
            "rationale": rationale})
        self._audit(d, now)
        self._sync_dispute_refs(d)

    def _audit(self, d: Dispute, now: datetime) -> None:
        """Write the dispute's audit record to the core lane.

        Spec write-failure rule: if the gate refuses, retry ONCE
        with the P-gate-passing rationale template; if still
        refused, the dispute stays in the in-memory open set AND
        the mesh error log - never silently dropped."""
        if self.dispute_store is None:
            return
        # audit_seq leads the payload on purpose: the gate's G3
        # dedup key covers the first 200 chars of content, and a
        # dispute's state dict starts identically across its
        # transitions - without the sequence number every audit
        # after the first would be refused as an exact duplicate
        # of it (found by test_cross_shard, 2026-10-21).
        payload = json.dumps(
            {"audit_seq": len(d.transitions), "kind": "dispute-state",
             "dispute": asdict(d)},
            sort_keys=True)
        natural = (
            f"Dispute {d.dispute_id} update: record {d.a_id} in "
            f"lane {d.a_lane} contradicts record {d.b_id} in lane "
            f"{d.b_lane}; resolution {d.resolution} via "
            f"{d.resolution_via}, escalation {d.escalation}, "
            f"{len(d.transitions)} transition(s) recorded.")
        template = (
            f"Update dispute {d.dispute_id} in the core lane: "
            f"record {d.a_id} in lane {d.a_lane} contradicts "
            f"record {d.b_id} in lane {d.b_lane}; when the mesh "
            f"runs the cross-shard ladder, then it records "
            f"severity {d.severity:.2f}, stakes {d.stakes}, "
            f"detected at {d.detected_at}, resolution "
            f"{d.resolution} via {d.resolution_via}, escalation "
            f"{d.escalation} (cross-shard resolution spec, "
            f"2026-10-20, ladder L1-L3, quorum window 24 hours, "
            f"timeout 7 days).")
        outcome = None
        for text in (natural, template):
            rec = MemoryRecord(
                id=f"{d.dispute_id}-audit-{len(d.transitions)}",
                text=text, content=payload, timestamp=now,
                source="core/dispute", type="fact",
                epistemic_tier="observed", explicit=True,
                owner="core", gathered_how="cross-shard-resolution",
                salience=0.9,
                provenance=Provenance(confidence=0.5))
            try:
                outcome = self.dispute_store.write(rec)
            except Exception as exc:  # seal/id collisions included
                outcome = None
                self.error_log.append({
                    "dispute_id": d.dispute_id, "at": now.isoformat(),
                    "error": f"audit write raised: {exc}"})
            if outcome is not None and outcome.verdict == "admitted":
                return
        self.error_log.append({
            "dispute_id": d.dispute_id, "at": now.isoformat(),
            "error": "dispute audit record not admitted after one "
                     "template retry; dispute kept in the in-memory "
                     "open set (spec: never silently dropped)",
            "verdict": outcome.verdict if outcome else None,
            "reasons": outcome.reasons if outcome else []})

    # -- dispute record tags (v0.6 dispute_refs; design consult
    # 2026-10-21, ChatGPT ruling T1-T3, staleness rule DT-A) -------
    #
    # The dispute record + audit trail above is AUTHORITATIVE.
    # dispute_refs on the disputed records is a CACHE of one
    # projection of it - which disputes naming the record are
    # CURRENTLY OPEN - so a shard-local reader can see the flag
    # without the mesh. Only the mesh writes it, only through the
    # storage lifecycle whitelist (update_metadata). A failed tag
    # write follows the audit rule: retry once, then the error
    # log; it never blocks or falsifies a transition.

    def _tag_write(self, store, record_id: str, refs: list,
                   dispute_id: str) -> None:
        """Best-effort dispute_refs write (retry once, then the
        mesh error log - never silently dropped, never fatal)."""
        last: Exception | None = None
        for _ in range(2):
            try:
                store.update_metadata(record_id,
                                      dispute_refs=list(refs))
                return
            except Exception as exc:  # unknown record included
                last = exc
        self.error_log.append({
            "dispute_id": dispute_id,
            "at": datetime.utcnow().isoformat(),
            "record_id": record_id,
            "error": "dispute_refs tag write failed after one "
                     f"retry: {last}; the dispute record stays "
                     "authoritative and restore-reconcile will "
                     "repair the cache"})

    def _sync_dispute_refs(self, d: Dispute) -> None:
        """Bring both disputed records' stored refs in line with
        d's CURRENT resolution (DT-A: the id is present iff the
        dispute is open). Writes only on divergence; called from
        _transition, so every lifecycle moment - open, resolve,
        reopen, timeout - is covered by the one hook."""
        for lane, rid in ((d.a_lane, d.a_id), (d.b_lane, d.b_id)):
            shard = self.shards.get(lane)
            if shard is None:
                continue
            rec = shard.store.get(rid)
            if rec is None:
                continue
            current = list(rec.dispute_refs or [])
            if d.resolution == "open":
                if d.dispute_id in current:
                    continue
                desired = sorted(current + [d.dispute_id])
            else:
                if d.dispute_id not in current:
                    continue
                desired = [x for x in current
                           if x != d.dispute_id]
            self._tag_write(shard.store, rid, desired, d.dispute_id)

    def _reconcile_dispute_refs(self) -> None:
        """Repair stored refs from the audit-derived dispute
        state: refs == ids of OPEN disputes naming the record,
        for every record in every shard the mesh holds. Forged,
        stale, and stripped refs are rewritten to expectation.
        Runs at restore (after _restore_disputes rebuilds state)
        and when a shard joins a mesh that already holds restored
        disputes (the constructor restores before any shard is
        added)."""
        if not self.disputes or not self.shards:
            return
        expected: dict[str, list[str]] = {}
        for d in self.disputes.values():
            if d.resolution != "open":
                continue
            for rid in (d.a_id, d.b_id):
                expected.setdefault(rid, []).append(d.dispute_id)
        for shard in self.shards.values():
            all_records = getattr(shard.store, "all_records", None)
            if all_records is None:
                continue
            for rid, rec in all_records().items():
                want = sorted(expected.get(rid, []))
                if list(rec.dispute_refs or []) != want:
                    self._tag_write(
                        shard.store, rid, want,
                        want[0] if want else "reconcile")

    def open_disputes(self, stakes: str = "medium",
                      now: datetime | None = None) -> list[Dispute]:
        """L1 - DISPUTE OPENED. Run the (pure) detector; open one
        dispute per cross-shard pair in the core lane and gather
        L2 corroboration. Idempotent: one dispute per unordered
        record pair (dispute_id "dsp-<min>-<max>"); re-detection
        bumps last_seen_at only, never a second dispute. L0
        (intra-shard) pairs are excluded by the detector itself
        and stay on the local gate flow. Returns open disputes."""
        now = now or datetime.utcnow()
        owners = self._owners()
        for pair in self.cross_shard_conflicts(stakes=stakes):
            a_id, b_id = str(pair["a"]), str(pair["b"])
            did = self._dispute_id(a_id, b_id)
            d = self.disputes.get(did)
            if d is None:
                d = Dispute(
                    dispute_id=did, a_id=a_id,
                    a_lane=owners.get(a_id, "?"),
                    b_id=b_id, b_lane=owners.get(b_id, "?"),
                    severity=float(pair.get("severity", 0.0)),
                    stakes=stakes, detected_at=now.isoformat(),
                    last_seen_at=now.isoformat())
                self.disputes[did] = d
                self._transition(
                    d, "open", "detection (L1)", "mesh",
                    "cross-shard declared contradiction detected "
                    "by the monitor over the union of shards", now)
                self.gather_corroboration(did, now=now)
            else:
                d.last_seen_at = now.isoformat()
        return [d for d in self.disputes.values()
                if d.resolution == "open"]

    def gather_corroboration(self, dispute_id: str,
                             now: datetime | None = None) -> Dispute:
        """L2 - CORROBORATION GATHERING. Every OTHER shard is
        queried for exact-content duplicates of a and of b. The
        results are recorded on the dispute as evidence; this step
        changes nothing about resolvability by itself."""
        now = now or datetime.utcnow()
        d = self.disputes[dispute_id]
        a_rec = self._record(d.a_lane, d.a_id)
        b_rec = self._record(d.b_lane, d.b_id)
        a_key = exact_content_key(a_rec) if a_rec else None
        b_key = exact_content_key(b_rec) if b_rec else None
        entries: list[dict] = []
        for lane, shard in self.shards.items():
            if lane in (d.a_lane, d.b_lane):
                continue
            for rec in shard.store.all_records().values():
                key = exact_content_key(rec)
                if a_key is not None and key == a_key:
                    entries.append({"shard": lane, "side": "a",
                                    "record_id": rec.id})
                elif b_key is not None and key == b_key:
                    entries.append({"shard": lane, "side": "b",
                                    "record_id": rec.id})
        d.corroboration = entries
        self._transition(
            d, d.resolution, "corroboration (L2)", "mesh",
            f"{len(entries)} exact-duplicate corroboration "
            f"entrie(s) gathered from third shards", now)
        return d

    def _superseding_record(self, lane: str,
                            record_id: str) -> str | None:
        """A record in the author's OWN shard whose provenance
        supersedes the disputed record - the L3a signal. (The
        gate admits it in the author's shard; cross-owner
        supersessions cannot moot a side by construction here.)"""
        shard = self.shards.get(lane)
        if shard is None:
            return None
        for rec in shard.store.all_records().values():
            if record_id in rec.provenance.supersedes:
                return rec.id
        return None

    def evaluate_dispute(self, dispute_id: str,
                         now: datetime | None = None) -> Dispute:
        """L3 - RESOLUTION, in strict authority order. The first
        applicable authority resolves; lower authorities are never
        consulted once a higher one has spoken:
          (a) same-author supersession - moots a side;
          (b) founder decision - manual (founder_decide); an
              existing founder ruling means the dispute is already
              resolved, and a later supersession does NOT reopen
              it (R1);
          (c) quorum - low/medium stakes only, after 24h;
          (d) timeout - at 7d the dispute escalates to the
              founder queue; it NEVER auto-resolves."""
        now = now or datetime.utcnow()
        d = self.disputes[dispute_id]
        if d.resolution == "resolved":
            return d
        detected = datetime.fromisoformat(d.detected_at)
        # (a) same-author supersession (symmetric, R2).
        sup_a = self._superseding_record(d.a_lane, d.a_id)
        sup_b = self._superseding_record(d.b_lane, d.b_id)
        if sup_a or sup_b:
            if sup_a and sup_b:
                via = "moot"
                why = (f"both sides superseded by their own "
                       f"authors ({sup_a} supersedes {d.a_id}; "
                       f"{sup_b} supersedes {d.b_id}) - nothing "
                       f"left to dispute")
            else:
                via = "supersession"
                side = "a" if sup_a else "b"
                why = (f"author of side {side} superseded their "
                       f"own record via {sup_a or sup_b} - that "
                       f"side is retracted, which moots the "
                       f"dispute rather than deciding it")
            d.resolution, d.resolution_via = "resolved", via
            d.resolved_at = now.isoformat()
            self._transition(d, "resolved", "supersession (L3a)",
                             "record author", why, now)
            return d
        # (c) quorum - never on high stakes, never inside the 24h
        # founder right-of-first-refusal window.
        if (d.stakes in ("low", "medium")
                and now - detected >= QUORUM_WINDOW):
            self._attempt_quorum(d, now)
            if d.resolution == "resolved":
                return d
        # (d) timeout - escalate only; silence is not consent.
        if (now - detected >= TIMEOUT_WINDOW
                and d.escalation != "timeout"):
            d.escalation = "timeout"
            self._transition(
                d, "open", "timeout (L3d)", "mesh",
                "no authority resolved within 7 days of detection; "
                "escalated to the founder queue - the dispute "
                "stays open and flagged, never auto-resolved", now)
        return d

    def _attempt_quorum(self, d: Dispute, now: datetime) -> None:
        """L3c - deterministic quorum over a recorded snapshot
        (R4/R5). One shard, one vote, assigned by presence:
        vote-a iff the shard holds a or an exact duplicate of a
        and holds neither b nor a duplicate of b; holding both or
        neither is an ABSTAIN, recorded, never assumed. Threshold
        floor(N/2)+1 of ALL shards in the mesh. A declared
        contradiction naming a record that carries the leading
        side VETOES quorum regardless of count."""
        lanes = sorted(self.shards)
        n = len(lanes)
        a_rec = self._record(d.a_lane, d.a_id)
        b_rec = self._record(d.b_lane, d.b_id)
        a_key = exact_content_key(a_rec) if a_rec else None
        b_key = exact_content_key(b_rec) if b_rec else None
        examined: dict[str, dict] = {}
        votes: dict[str, str] = {}
        holders: dict[str, set] = {"a": set(), "b": set()}
        for lane in lanes:
            recs = self.shards[lane].store.all_records()
            examined[lane] = {rid: exact_content_key(r)
                              for rid, r in recs.items()}
            holds_a = {rid for rid, r in recs.items()
                       if rid == d.a_id
                       or exact_content_key(r) == a_key}
            holds_b = {rid for rid, r in recs.items()
                       if rid == d.b_id
                       or exact_content_key(r) == b_key}
            holders["a"] |= holds_a
            holders["b"] |= holds_b
            if holds_a and not holds_b:
                votes[lane] = "a"
            elif holds_b and not holds_a:
                votes[lane] = "b"
            else:
                votes[lane] = "abstain"
        counts = {side: sum(1 for v in votes.values() if v == side)
                  for side in ("a", "b", "abstain")}
        detected = datetime.fromisoformat(d.detected_at)
        snapshot = {
            "eligible_shards": lanes,
            "examined": examined,
            "votes": votes,
            "counts": counts,
            "evaluated_at": now.isoformat(),
            "window": {
                "detected_at": d.detected_at,
                "quorum_eligible_from":
                    (detected + QUORUM_WINDOW).isoformat()},
            "veto": None,
        }
        d.quorum_snapshot = snapshot
        # Invariant (spec): the snapshot is written into the
        # dispute record BEFORE any resolution record exists.
        self._transition(
            d, "open", "quorum snapshot (L3c)", "mesh",
            f"snapshot recorded before any resolution record: "
            f"votes {counts} over {n} shards", now)
        leader = None
        if counts["a"] > counts["b"]:
            leader = "a"
        elif counts["b"] > counts["a"]:
            leader = "b"
        threshold = n // 2 + 1
        if leader is None or counts[leader] < threshold:
            self._transition(
                d, "open", "quorum (L3c)", "mesh",
                f"no quorum: votes {counts}, threshold {threshold} "
                f"of {n} (a tie means no quorum) - dispute stays "
                f"open", now)
            return
        # Veto (R5), evaluated over the SAME snapshot. The two
        # disputed records are excluded from the scan: their
        # mutual declaration IS this dispute, already counted.
        side_ids = holders[leader]
        veto = None
        for lane in lanes:
            for rid, rec in self.shards[lane].store.all_records(
            ).items():
                if rid in (d.a_id, d.b_id):
                    continue
                named = set(rec.provenance.contradicts) & side_ids
                if named:
                    veto = {"shard": lane, "record_id": rid,
                            "names": sorted(named)}
                    break
            if veto:
                break
        snapshot["veto"] = veto
        if veto:
            self._transition(
                d, "open", "quorum veto (L3c/R5)", "mesh",
                f"veto: record {veto['record_id']} in shard "
                f"{veto['shard']} declares a contradiction naming "
                f"{veto['names']} (record(s) carrying leading side "
                f"{leader}) - quorum blocked regardless of count; "
                f"dispute goes to founder/timeout", now)
            return
        # The quorum resolution is itself a record and must pass
        # the core-lane write gate like any record. If the gate
        # refuses it, the dispute stays open - never a resolution
        # nobody can audit.
        if not self._write_quorum_resolution(d, snapshot, leader,
                                             counts, threshold, now):
            self._transition(
                d, "open", "quorum (L3c)", "mesh",
                "quorum met but the resolution record was not "
                "admitted by the core-lane gate - dispute stays "
                "open", now)
            return
        d.resolution, d.resolution_via = "resolved", "quorum"
        d.resolved_at = now.isoformat()
        self._transition(
            d, "resolved", "quorum (L3c)", "mesh",
            f"quorum resolved for side {leader}: votes {counts}, "
            f"threshold {threshold} of {n}, veto search negative, "
            f"snapshot recorded", now)

    def _write_quorum_resolution(self, d: Dispute, snapshot: dict,
                                 leader: str, counts: dict,
                                 threshold: int,
                                 now: datetime) -> bool:
        """The quorum resolution record (spec L3c): cites both
        disputed record ids, the snapshot, vote counts, veto
        search result, and window timestamps; admitted through
        the core-lane write gate (P1-P3 included) or not at all."""
        if self.dispute_store is None:
            self.error_log.append({
                "dispute_id": d.dispute_id, "at": now.isoformat(),
                "error": "quorum resolution cannot be recorded: "
                         "no core-lane dispute store attached - "
                         "dispute stays open (fail-closed)"})
            return False
        payload = json.dumps({
            "kind": "quorum-resolution", "dispute_id": d.dispute_id,
            "a_id": d.a_id, "b_id": d.b_id, "leader": leader,
            "counts": counts, "threshold": threshold,
            "snapshot": snapshot, "decided_at": now.isoformat()},
            sort_keys=True)
        text = (
            f"Quorum resolution for dispute {d.dispute_id}: "
            f"update the citation status of records {d.a_id} and "
            f"{d.b_id} to resolved via quorum for side {leader} "
            f"when the 24 hour window after detection at "
            f"{d.detected_at} elapsed, then the recorded snapshot "
            f"showed {counts[leader]} of "
            f"{len(snapshot['eligible_shards'])} shards voting "
            f"for side {leader} (threshold {threshold}, veto "
            f"search negative, evaluated {now.isoformat()}, "
            f"cross-shard resolution spec L3c, 2026-10-20).")
        rec = MemoryRecord(
            id=f"{d.dispute_id}-resolution", text=text,
            content=payload, timestamp=now, source="core/dispute",
            type="decision", epistemic_tier="observed",
            explicit=True, owner="core",
            gathered_how="cross-shard-quorum", salience=0.9,
            provenance=Provenance(confidence=0.5))
        try:
            outcome = self.dispute_store.write(rec)
        except Exception as exc:
            self.error_log.append({
                "dispute_id": d.dispute_id, "at": now.isoformat(),
                "error": f"quorum resolution write raised: {exc}"})
            return False
        if outcome.verdict != "admitted":
            self.error_log.append({
                "dispute_id": d.dispute_id, "at": now.isoformat(),
                "error": "quorum resolution record not admitted "
                         "by the core-lane gate",
                "verdict": outcome.verdict,
                "reasons": outcome.reasons})
            return False
        return True

    def founder_decide(self, dispute_id: str, ruling: str,
                       now: datetime | None = None) -> Dispute:
        """L3b - FOUNDER DECISION. nitesh decides; his vote is
        final on any conflict (standing rule, 15 Oct 2026), at any
        stakes. The ruling is recorded VERBATIM with timestamp.
        This is the only authority that OVERRIDES: ruling on an
        already-resolved dispute goes through founder_reopen
        first (fail-closed, explicit - never a silent rewrite)."""
        now = now or datetime.utcnow()
        d = self.disputes[dispute_id]
        if d.resolution == "resolved":
            raise ValueError(
                f"dispute {dispute_id} already resolved via "
                f"{d.resolution_via}; the founder reopens it first "
                f"(founder_reopen), then rules")
        d.resolution, d.resolution_via = "resolved", "founder"
        d.resolved_at = now.isoformat()
        self._transition(d, "resolved", "founder decision (L3b)",
                         "nitesh", ruling, now)
        return d

    def founder_reopen(self, dispute_id: str, rationale: str,
                       now: datetime | None = None) -> Dispute:
        """L3b - the founder may REOPEN a resolved dispute (e.g.
        disagreeing with a quorum resolution): appends a
        transition, unseals the dispute, resolution back to open.
        History is never rewritten."""
        now = now or datetime.utcnow()
        d = self.disputes[dispute_id]
        if d.resolution != "resolved":
            raise ValueError(
                f"dispute {dispute_id} is not resolved; nothing "
                f"to reopen")
        d.resolution, d.resolution_via = "open", "none"
        d.resolved_at = None
        self._transition(d, "open", "founder reopen (L3b)",
                         "nitesh", rationale, now)
        return d

    def evaluate_all(self, stakes: str = "medium",
                     now: datetime | None = None) -> list[Dispute]:
        """One full ladder pass: detect/open (L1+L2), then
        evaluate every open dispute (L3). Returns all disputes."""
        self.open_disputes(stakes=stakes, now=now)
        for d in list(self.disputes.values()):
            if d.resolution == "open":
                self.evaluate_dispute(d.dispute_id, now=now)
        return list(self.disputes.values())

    def dispute_list(self) -> list[Dispute]:
        """The briefing surface (spec): all disputes, open first,
        so the founder's hourly briefing can carry the open
        count. A dispute open past 7 days appears in every
        briefing until resolved (see founder_queue)."""
        return sorted(self.disputes.values(),
                      key=lambda d: (d.resolution == "resolved",
                                     d.detected_at))

    def founder_queue(self) -> list[Dispute]:
        """Open disputes awaiting the founder, timeout-escalated
        first. Nothing here executes anything: hard gates queue
        for nitesh, they never auto-run."""
        open_ = [d for d in self.disputes.values()
                 if d.resolution == "open"]
        return sorted(open_, key=lambda d: (
            d.escalation != "timeout", d.detected_at))

    def citation_status(self, record_id: str) -> dict | None:
        """Point-in-time dispute status for one record, for answer
        provenance (spec): an answer citing a disputed record
        carries the dispute_id and the dispute's CURRENT
        resolution/escalation status - never a silent citation of
        a contested fact. The association lives in the dispute
        record, which stays authoritative; since the design
        consult (2026-10-21, ruling T1-T3) the records also
        carry a cached dispute_refs tag (v0.6, DT-A) for
        shard-local readers - this method remains the complete,
        current answer (ids, vias, escalation), the tag only
        open-ness."""
        for d in self.disputes.values():
            if record_id in (d.a_id, d.b_id):
                return {"dispute_id": d.dispute_id,
                        "resolution": d.resolution,
                        "resolution_via": d.resolution_via,
                        "escalation": d.escalation}
        return None
