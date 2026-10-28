"""constraints — negative-constraint store: learn what NOT to do.

v0.1 STUB: interface only. Not implemented.

Past failure trajectories become negative constraints injected at decision
time, steering the agent away from known-bad tool sequences and option
patterns. Constraints are learned offline, applied online, and every
injection is audit-logged.

Pattern update (v0.2): two learning rules now defined. (1) Rescorla-Wagner
outcome feedback (mnemoverse, W4): report a memory "helped"/"misled";
prediction-error updates re-rank it — the only outcome-conditioned memory
ranking found. MIT covers their MCP server only; the ranking engine is
proprietary: steal the *rule*, never the code. (2) Dopamine-signed surprise
(neuro track): every executed action records predicted_outcome; on observed
outcome, δ = outcome − prediction. Negative δ CREATES or strengthens a
negative constraint with strength ∝ |δ| (first-class avoidance learning);
positive δ boosts salience of the records involved. Constraints decay as the
environment changes — a constraint from a since-fixed bug must die.
Specificity-vs-decay: ANSWERED-with-mechanism; implementation pending.

Pattern inspiration: OpenViking reflection-guided guardrails (AGPL-3.0 —
read-only, reimplement); Memori tool-execution telemetry; neuro dopamine
RPE, signed (Schultz 1997).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NegativeConstraint:
    """An inhibitory memory: a pattern known to fail."""

    id: str
    description: str
    failed_pattern: str              # abstracted pattern, not a literal trace
    severity: float = 0.5            # 0..1
    learned_at: datetime = field(default_factory=datetime.utcnow)
    source_trajectory_id: str = ""
    still_valid: bool = True


def get_constraints(task_signature: str) -> list[NegativeConstraint]:
    """Return negative constraints relevant to the current task.

    Called at decision time; the confidence scorer uses these to prune or
    down-rank options matching known-bad patterns.

    TODO (research): matching granularity — how is `task_signature`
    computed so constraints generalize without over-firing?
    See ARCHITECTURE.md §3.
    """
    raise NotImplementedError(
        "v0.1 stub — implement once constraint matching granularity is "
        "defined (ARCHITECTURE.md §3, open questions)."
    )


def learn_constraint(failure_trajectory: list[dict]) -> NegativeConstraint:
    """Generalize a failure trajectory into a reusable negative constraint.

    Offline job. Must abstract the *pattern* of failure (not memorize the
    literal trace) and record provenance for audit.

    TODO (research): abstraction level for the failure pattern (exact tool
    sequence vs generalized pattern); task_signature granularity so
    constraints generalize without over-firing. See ARCHITECTURE.md §3.
    """
    raise NotImplementedError(
        "v0.2 stub — signed-δ mechanism defined; implement once the "
        "abstraction level and matching granularity are set "
        "(ARCHITECTURE.md §3, open questions)."
    )


def audit_log() -> list[dict]:
    """Return the log of every constraint injection at decision time.

    TODO (research): log schema — what must an audit entry contain for a
    human to overrule a pruned option? See ARCHITECTURE.md §3 and §7.
    """
    raise NotImplementedError("v0.1 stub — implement with the audit schema.")
