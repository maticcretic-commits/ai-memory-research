"""Conventions checker prototype (Jeff Su J3).

Mirrors the mm pattern of a frozen, hashed rulebook loaded in every run,
without touching mm code. Stdlib only. No network, no sending.

A conventions document is frozen by hashing its canonical JSON. check()
reports violations; it never rewrites the document or the output.
"""

from __future__ import annotations

import hashlib
import json


def freeze(conventions: dict) -> dict:
    """Return the frozen hash for a conventions document."""
    canonical = json.dumps(conventions, sort_keys=True, separators=(",", ":"))
    return {
        "name": conventions.get("name"),
        "version": conventions.get("version"),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def verify_frozen(conventions: dict, expected_sha256: str) -> bool:
    """True only if the document still hashes to the frozen value."""
    return freeze(conventions)["sha256"] == expected_sha256


def check(conventions: dict, title: str, body: str) -> dict:
    """Check a synthetic output against the frozen conventions.

    Returns {"passed": bool, "violations": [rule ids]}. Fail-closed:
    an empty title or body fails rather than passing silently.
    """
    violations: list[str] = []
    allowed_verbs = conventions.get("allowed_verbs", [])
    secret_words = [w.lower() for w in conventions.get("secret_words", [])]

    if not title or not body:
        violations.append("empty_input")
        return {"passed": False, "violations": violations}

    first_word = title.split()[0] if title.split() else ""
    if first_word not in allowed_verbs:
        violations.append("title_verb")
    if len(title) > 80:
        violations.append("title_length")
    if not any(line.startswith("- ") for line in body.splitlines()):
        violations.append("context_bullets")
    lowered = body.lower()
    if any(word in lowered for word in secret_words):
        violations.append("no_secrets")

    return {"passed": not violations, "violations": violations}
