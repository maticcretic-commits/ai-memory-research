"""access_control - read-side authorization (Red-Team Round 4).

Round 1's A10 closed the episodic chain and the answer-citation
path, and its record declared the residue plainly: "Store reads
return full content to any caller (single-tenant design,
declared)." A read model with no concept of WHO is asking
cannot distinguish the founder's own mouth from an attacker's
probe - every caller is trusted because there is no caller.

This module is the first increment of a read model:

- A ReaderContext names the principal asking: a reader_id
  (audit identity), the owner lane it acts as, the consent
  scopes it holds clearances for, and a system flag for
  first-party in-process components.
- A ReadAuthorizer decides per record, fail-closed. Rules, in
  order (inspectable, no hidden state):
    1. system readers read everything - the gate, the janitor
       and consolidation are in-process trusted components;
       that boundary is DECLARED here, not smuggled: this
       increment authorizes reader-facing paths, it does not
       pretend code inside the process can distrust itself.
    2. a reader reads its own lane's records (owner match);
    3. a record with a non-empty consent_scope is readable
       only by readers holding that scope as a clearance
       (rule 2 already covers the owning lane; this governs
       everyone else, episodic records included);
    4. episodic-type records are shared event context - the
       Round-1 chain doctrine treats episodes as common
       ground - readable by any identified reader;
    5. everything else is denied.
- Denial is indistinguishable from absence: the store's
  authorized get returns None for a forbidden id exactly as
  for a missing one, so the read API is not an existence
  oracle for other lanes' record ids.

Honest limits (stated, not hidden): a ReaderContext is still
a DECLARED identity - like the write side's owner strings
(Round 3), it prices anonymous access at zero and gives every
read an audit actor, but binding a context to a principal
non-malleably is the same strong-form problem as Fo's
provenance binding (corpus 3358), still unbuilt. In-process
callers that use the raw store API bypass this layer by
design; deployments must route reader-facing surfaces
(agent mouth, search APIs) through the authorized paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mm.reflect import MemoryRecord


@dataclass(frozen=True)
class ReaderContext:
    """Who is asking. reader_id is the audit actor written to
    the access log; owner is the lane the reader acts as;
    clearances are the consent scopes it may read; system
    marks a first-party in-process component."""

    reader_id: str
    owner: str = ""
    clearances: frozenset = field(default_factory=frozenset)
    system: bool = False


#: The in-process trusted reader (gate/janitor/consolidation and
#: the agent acting as itself, first-party). Named, not implicit.
SYSTEM_READER = ReaderContext(reader_id="system", system=True)


class ReadAuthorizer:
    """Per-record read decisions. Pure function of (reader,
    record) - no state, no I/O, fully inspectable."""

    def can_read(self, reader: ReaderContext,
                 record: MemoryRecord) -> tuple[bool, str]:
        if reader.system:
            return True, "system reader (in-process trusted)"
        owner = (record.owner or "").strip()
        if owner and owner == (reader.owner or "").strip():
            return True, "own lane's record"
        scope = (record.consent_scope or "").strip()
        if scope:
            if scope in reader.clearances:
                return True, f"consent-scope clearance {scope!r}"
            return False, (f"consent_scope {scope!r} requires a "
                           f"clearance the reader does not hold")
        if not owner:
            return True, "unowned record (no lane claims it)"
        if record.type == "episodic":
            return True, "episodic record - shared event context"
        return False, (f"cross-owner record of lane {owner!r}; "
                       f"reader acts as {(reader.owner or '')!r} "
                       f"with no clearance")

    def filter_records(self, reader: ReaderContext,
                       records: dict[str, MemoryRecord]
                       ) -> dict[str, MemoryRecord]:
        """The subset of `records` this reader may read."""
        return {rid: rec for rid, rec in records.items()
                if self.can_read(reader, rec)[0]}


__all__ = ["ReaderContext", "ReadAuthorizer", "SYSTEM_READER"]
