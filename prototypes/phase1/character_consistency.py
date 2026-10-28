"""Character-consistency spec prototype (Sirio Berati, hard problem).

Compares a depiction against a character sheet on two signals only:
the reference id must match, and the description must overlap the
sheet description by at least half its tokens. A mismatch on either
signal is inconsistent, and a missing reference fails closed.

This is a check, not a solution: character consistency is not solved
by this function, which has no generation step and is unverified on
real depictions. Stdlib only. Synthetic sheets only.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"\w+")
MIN_OVERLAP = 0.5
_NOTE = (
    "character consistency is not solved by this check; it only compares "
    "a reference id and description overlap, and is unverified on real depictions."
)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def check_consistency(sheet: dict, depiction: dict) -> dict:
    """Return {consistent, overlap, reasons, note}. Never generates."""
    reasons: list[str] = []
    if depiction.get("reference_id") != sheet.get("reference_id"):
        reasons.append("reference_mismatch")
    sheet_tokens = _tokens(sheet.get("description", ""))
    depiction_tokens = _tokens(depiction.get("description", ""))
    overlap = (
        len(sheet_tokens & depiction_tokens) / len(sheet_tokens)
        if sheet_tokens
        else 0.0
    )
    if overlap < MIN_OVERLAP:
        reasons.append("low_description_overlap")
    return {
        "consistent": not reasons,
        "overlap": overlap,
        "reasons": reasons,
        "note": _NOTE,
    }
