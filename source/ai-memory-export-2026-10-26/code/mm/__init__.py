"""mm — memory milestone v0.1 scaffold.

Memory → DECISION: a memory layer that ranks candidate options and recommends
actions with calibrated confidence, backed by an audit trail.

v0.1 STATUS: interfaces only. Every submodule exposes clean signatures and
detailed docstrings; bodies raise NotImplementedError. See ARCHITECTURE.md for
the design and RESEARCH.md for the learn-and-build traceability log.
"""

from mm import reflect, sop, constraints, resolver, temporal, tiers, confidence, decision

__version__ = "0.2.0"
__all__ = [
    "reflect",
    "sop",
    "constraints",
    "resolver",
    "temporal",
    "tiers",
    "confidence",
    "decision",
]
