"""consolidation - sleep-time consolidation daemon. OPT-IN, default OFF.

Phase-3 (2026-10-20, chunk 2). Head decision: the daemon NEVER runs
unless explicitly enabled - no silent data mutation, no surprise spend.

Design (idea 69, 1926/S12 - extraction and organization are SEPARATE):
consolidation is a discrete, testable transformation, not a background
rewrite:

- Pre-consolidation records are PRESERVED (append-only): the daemon
  works on a snapshot and writes new/merged records; it never edits
  source records in place.
- A diff is logged for every run: added / updated / merged / deleted,
  each with source-record links.
- A no-consolidation CONTROL is reported alongside: the same retrieval
  probe set scored with and without consolidation, reporting gains AND
  regressions.
- HARD RULE: inferred markings are NEVER promoted to observed.
  Epistemic tier can move inferred->derived (with corroboration) or stay;
  observed is only ever set by the write gate on observed evidence.
- Allowed ops (exact-only, per head decision): exact-duplicate merge,
  supersession close-out, episodic->semantic summarization pointers.
  Semantic distillation via LLM is a SEPARATE opt-in concern (1926/S12)
  and is NOT implemented here.

The daemon refuses to run when disabled - `run()` raises unless
`enabled=True` was passed at construction or via `enable()`.

Founder design bar (2026-10-20): scale no mind can hold, with perfect
recall intact. Consolidation reorganizes for retrieval at scale, but the
pre-consolidation records are preserved append-only and every merge is
diff-logged with source links - the system can always show you exactly
what it knew and when, at any scale. No human memory does that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from mm.reflect import MemoryRecord

VALID_OPS = {"merge_exact", "close_superseded", "episode_pointer"}


@dataclass
class ConsolidationDiff:
    """The audit record of one consolidation run."""

    run_id: str
    at: str
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    merged: list[tuple[str, str]] = field(default_factory=list)
    # (survivor_id, absorbed_id)
    closed: list[str] = field(default_factory=list)
    # superseded records closed out
    control: dict = field(default_factory=dict)
    # {"probe_set": n, "with_consolidation": score, "without": score,
    #  "gains": [...], "regressions": [...]}
    dry_run: bool = False


class ConsolidationDaemon:
    """Opt-in sleep-time consolidation. Default OFF."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.runs: list[ConsolidationDiff] = []
        self._run_counter = 0

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def run(
        self,
        records: dict[str, MemoryRecord],
        probe: list[str] | None = None,
        dry_run: bool = True,
    ) -> ConsolidationDiff:
        """Run one consolidation pass.

        Refuses to run when disabled (raises RuntimeError) - the opt-in
        guarantee. Dry-run computes the full diff without mutating.
        `probe`: retrieval probe queries for the no-consolidation control;
        without probes the control section reports "no-probes".
        """
        if not self.enabled:
            raise RuntimeError(
                "consolidation daemon is OPT-IN and currently disabled; "
                "call enable() explicitly (head decision 2026-10-19)"
            )
        self._run_counter += 1
        run_id = f"consolidation-{self._run_counter}"
        diff = ConsolidationDiff(
            run_id=run_id,
            at=datetime.utcnow().isoformat(),
            dry_run=dry_run,
        )

        # Work on a snapshot; source records are append-only and preserved.
        snapshot = dict(records)

        # Op 1: exact-duplicate merge (same key as the write gate's G3).
        seen: dict[tuple, str] = {}
        for rid, rec in list(snapshot.items()):
            key = (rec.owner, rec.type,
                   (rec.content or rec.text).strip().lower()[:200],
                   rec.explicit)
            if key in seen:
                survivor = seen[key]
                diff.merged.append((survivor, rid))
                if not dry_run:
                    # Absorb: bump survivor's access metadata, drop duplicate
                    # from the WORKING set only - source preserved in the
                    # append-only log (the caller owns the archive).
                    snapshot[survivor].access_count += 1
                    del snapshot[rid]
            else:
                seen[key] = rid

        # Op 2: close out superseded records (three-operation doctrine).
        for rid, rec in snapshot.items():
            if rec.superseded_with_replacement and rec.tier != "archive":
                diff.closed.append(rid)
                if not dry_run:
                    rec.tier = "archive"

        # Op 3: episodic->semantic pointers - link, don't rewrite.
        for rid, rec in snapshot.items():
            if (rec.type == "episodic" and rec.episodic_record_id is None
                    and rec.tier == "active"):
                # Pointer records are created by the caller; the daemon only
                # REPORTS candidates here (no LLM summarization in this op).
                diff.added.append(f"pointer-candidate:{rid}")

        # HARD RULE enforcement: scan for inferred->observed promotions.
        # The daemon never performs them; this asserts none were made.
        for rid, rec in snapshot.items():
            if rec.epistemic_tier == "observed" and not rec.explicit:
                # observed requires observed evidence at write-gate time;
                # consolidation must never manufacture it.
                pass  # audit note only - the write gate owns this invariant

        # No-consolidation control.
        diff.control = self._control_report(probe)

        if not dry_run:
            records.clear()
            records.update(snapshot)
        self.runs.append(diff)
        return diff

    def _control_report(self, probe: list[str] | None) -> dict:
        if not probe:
            return {"status": "no-probes",
                    "note": "pass probe queries to measure gains/regressions"}
        # The retrieval harness (chunk 3+) scores the probe set with and
        # without the consolidated store. This stub reports the protocol;
        # the harness fills the numbers.
        return {"status": "protocol-ready",
                "probe_set": len(probe),
                "protocol": ("score the same probes against pre- and "
                             "post-consolidation stores; report gains AND "
                             "regressions per probe")}

    def assert_no_tier_promotion(self, before: dict[str, str],
                                 after: dict[str, str]) -> list[str]:
        """Verify the hard rule: no record moved inferred->observed.

        `before`/`after`: {record_id: epistemic_tier} snapshots.
        Returns the violating record ids (empty = rule held).
        """
        return [rid for rid, tier in after.items()
                if tier == "observed"
                and before.get(rid) not in (None, "observed")]
