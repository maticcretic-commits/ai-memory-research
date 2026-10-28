"""Master prompt prototype (Jeff Su J4).

Builds one prompt from a frozen template with every slot filled. The
conventions hash must match the frozen prototype conventions document
(prototype-conventions-v1, via conventions.freeze); a mismatch is
rejected, and no unfilled placeholder may remain. The prompt is text
only: it instructs, it never sends. Stdlib only. Synthetic data only.
"""

from __future__ import annotations

import conventions
from fixtures import CONVENTIONS_V1

_TEMPLATE = (
    "Role: {role}\n"
    "Task: {task}\n"
    "Conventions: {conventions_sha256} (prototype-conventions-v1)\n"
    "Style guide: {style_guide_version}\n"
    "Rules: follow the frozen conventions; draft only; never send."
)


class MasterPromptError(Exception):
    """Raised for a missing slot or a conventions-hash mismatch."""


def build(
    role: str,
    task: str,
    conventions_sha256: str,
    style_guide_version: str,
) -> dict:
    """Build the master prompt, or reject it."""
    if not role or not task or not conventions_sha256 or not style_guide_version:
        raise MasterPromptError("missing slot")
    expected = conventions.freeze(CONVENTIONS_V1)["sha256"]
    if conventions_sha256 != expected:
        raise MasterPromptError("conventions hash mismatch")
    text = _TEMPLATE.format(
        role=role,
        task=task,
        conventions_sha256=conventions_sha256,
        style_guide_version=style_guide_version,
    )
    if "{" in text or "}" in text:
        raise MasterPromptError("unfilled placeholder remains")
    return {
        "text": text,
        "conventions_sha256": conventions_sha256,
        "style_guide_version": style_guide_version,
    }
