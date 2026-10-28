"""Brand rulebook prototype (Sirio Berati, brand rulebook draft).

A frozen, hashed brand rulebook: palette, voice, forbidden claims, and
the credit rule (credits in the description only, never in frames).
check() reports violations; it never rewrites an asset. Stdlib only.
Synthetic assets only. No network, no publishing.
"""

from __future__ import annotations

import hashlib
import json


def freeze(rulebook: dict) -> dict:
    """Return the frozen hash for a brand rulebook."""
    canonical = json.dumps(rulebook, sort_keys=True, separators=(",", ":"))
    return {
        "name": rulebook.get("name"),
        "version": rulebook.get("version"),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def verify_frozen(rulebook: dict, expected_sha256: str) -> bool:
    """True only if the rulebook still hashes to the frozen value."""
    return freeze(rulebook)["sha256"] == expected_sha256


def check(rulebook: dict, asset: dict) -> dict:
    """Check a synthetic asset against the frozen rulebook."""
    violations: list[str] = []
    if asset.get("credits_in_frame"):
        violations.append("credits_in_frame")
    text = asset.get("text", "").lower()
    if any(claim.lower() in text for claim in rulebook.get("forbidden_claims", [])):
        violations.append("forbidden_claim")
    palette = set(rulebook.get("palette", []))
    if any(colour not in palette for colour in asset.get("colours", [])):
        violations.append("off_palette")
    return {"passed": not violations, "violations": violations}
