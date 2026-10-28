"""tiers — self-editing memory tiers: the agent maintains its own memory.

v0.1 STUB: interface only. Not implemented.

Two tiers: a small prompt-resident **core** (working memory — current goals,
standing answers, active constraints) and a large **archive** (episodic +
semantic stores). The agent edits core only through narrow, audited tools —
every edit logged, every edit reversible. Memory maintenance is itself a
decision the agent makes, not a background daemon rewriting state silently.

Pattern update (v0.2, neuro track): hippocampal two-stage design — fast
append-only episodic log (cheap writes, recency-weighted) + consolidated
semantic store (expensive writes, interference-resistant); background
consolidate() ("sleep") replays the log and distills patterns, PFC-tagged:
only salient, decision-referenced, or surprising records consolidate.
Reconsolidation protocol: recall makes ONLY the retrieved record labile
until task end (boundary conditions honored); edit resistance scales with
record age and confirmation count. Core stays tiny (≤2k tokens) with
PFC-like intake gating — an intake classifier routes episodic-log vs core
vs discard.

Pattern inspiration: letta core/archive + agent-operated tools (MemGPT
lineage); claude-mem hook capture; A-mem Zettelkasten rewriting (W3);
ReMe Auto Dream opcodes (W2); neuro hippocampal consolidation + sleep
replay (CLS), PFC gating, reconsolidation (Nader 2000).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from mm.reflect import MemoryRecord


@dataclass
class EditOp:
    """One audited mutation of core memory."""

    op: str                          # "append" | "replace" | "delete" | "promote" | "demote"
    target_id: str
    payload: str = ""
    actor: str = "agent"
    at: datetime = field(default_factory=datetime.utcnow)
    reversible: bool = True


@dataclass
class AuditEntry:
    op: EditOp
    before: str
    after: str


class MemoryTiers:
    """Self-editing two-tier memory with a full audit trail.

    v0.1 STUB: the class exists so the interface is reviewable; methods
    raise NotImplementedError.
    """

    def __init__(self, core_budget_tokens: int = 2000) -> None:
        self.core_budget_tokens = core_budget_tokens
        self._audit: list[AuditEntry] = []

    def read_core(self) -> list[MemoryRecord]:
        """Return the current core (working) memory."""
        raise NotImplementedError("v0.1 stub.")

    def edit_core(self, op: EditOp) -> AuditEntry:
        """Apply a narrow edit to core memory; log it; keep it reversible.

        TODO (research): which edit ops are safe to expose? What guardrails
        prevent self-lobotomy (e.g. deleting own goals)? See ARCHITECTURE.md §6.
        """
        raise NotImplementedError(
            "v0.1 stub — implement once the safe edit-op set and guardrails "
            "are defined (ARCHITECTURE.md §6, open questions)."
        )

    def archive_search(self, query: str) -> list[MemoryRecord]:
        """Search the archive tier (delegates to mm.temporal scoring)."""
        raise NotImplementedError("v0.1 stub.")

    def promote(self, record_id: str) -> AuditEntry:
        """Move an archive record into core (subject to budget)."""
        raise NotImplementedError("v0.1 stub.")

    def demote(self, record_id: str) -> AuditEntry:
        """Move a core record back to the archive."""
        raise NotImplementedError("v0.1 stub.")

    def audit_trail(self) -> list[AuditEntry]:
        """Full reversible history of core edits."""
        return list(self._audit)


# TODO (research): consolidation schedule — timer, log-size threshold, or
# decision-boundary events? Labile-window edge cases (concurrent tasks on one
# record)? See ARCHITECTURE.md §6. Core budget (≤2k) + PFC intake gating now
# defined; membership policy still open.
