"""sop — procedure matcher: constrain options with procedural knowledge.

v0.1 STUB: interface only. Not implemented.

Matches the current intent to executable playbooks (SOPs) distilled from past
successful trajectories. An option that no known procedure can execute is
down-ranked by the confidence scorer. Distillation itself (`extract_sop`) is
an offline job: sessions → reusable procedures.

Pattern update (v0.2, neuro track): basal-ganglia fast path — match_sop
runs as a CHEAP similarity gate BEFORE the expensive reflect/confidence
pipeline; below a confidence floor, fall back to full deliberation (humans
revert to prefrontal control when habits fail). Cerebellar micro-tuning:
attach execution telemetry to every SOP; repeated small deviations in the
same direction NUDGE parameters, while large failures feed mm.constraints
instead of discarding the procedure.

Pattern inspiration: OpenViking skill-extraction (AGPL-3.0 — read-only,
reimplement); memU session→skill distillation + dumb-storage/smart-agent
split; alibaizhanov/mengram (W4) experience-driven procedural memory;
neuro basal ganglia action selection + cerebellar error-driven tuning.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Procedure:
    """A distilled executable playbook."""

    name: str
    steps: list[str]
    preconditions: list[str] = field(default_factory=list)
    success_rate: float = 0.0      # observed, 0..1
    uses: int = 0                  # times executed
    version: int = 1


def match_sop(intent: str, procedures: list[Procedure]) -> list[Procedure]:
    """Rank procedures by fit to the current intent.

    Returns procedures ranked by relevance to `intent`; the caller uses the
    ranking to constrain which candidate options are executable.

    TODO (research): matching signal — embedding similarity on intent text?
    precondition satisfaction check? Both? See ARCHITECTURE.md §2.
    """
    raise NotImplementedError(
        "v0.1 stub — implement once the SOP matching signal is defined "
        "(ARCHITECTURE.md §2, open questions)."
    )


def extract_sop(trajectory: list[dict]) -> Procedure:
    """Distill a successful execution trajectory into a reusable Procedure.

    Offline job. Input is a recorded trajectory (tool calls, observations,
    outcome); output is a generalized, parameterized playbook.

    TODO (research): minimal SOP schema? success threshold for promotion?
    versioning when the environment changes? See ARCHITECTURE.md §2.
    """
    raise NotImplementedError(
        "v0.1 stub — implement once the SOP schema and promotion policy "
        "are defined (ARCHITECTURE.md §2, open questions)."
    )
