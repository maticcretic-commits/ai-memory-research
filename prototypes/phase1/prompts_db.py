"""Prompts database prototype (Jeff Su J2).

Versioned prompt library. Records are sealed: a correction arrives as a
new version with a supersedes link; the old version stays retrievable and
is flagged superseded. Exact duplicates are not new versions. Secret
content and missing fields are rejected, never silently admitted.
Stdlib only. Synthetic data only. No network, no sending.
"""

from __future__ import annotations

import copy

REQUIRED_FIELDS = ("id", "type", "use_case", "output_format", "app", "text")
SECRET_WORDS = ("api_key", "password", "token", "secret")


class PromptsDb:
    def __init__(self) -> None:
        self._versions: dict[str, list[dict]] = {}

    def add(self, entry: dict) -> dict:
        if any(field not in entry or not entry[field] for field in REQUIRED_FIELDS):
            return {"outcome": "rejected", "reason": "missing_required_field"}
        text = f"{entry.get('text', '')} {entry.get('example', '')}".lower()
        if any(word in text for word in SECRET_WORDS):
            return {"outcome": "rejected", "reason": "secret_content"}
        versions = self._versions.get(entry["id"], [])
        if versions:
            latest = versions[-1]
            if latest["text"] == entry["text"] and latest["use_case"] == entry["use_case"]:
                return {"outcome": "duplicate", "reason": "exact_duplicate"}
            return {"outcome": "rejected", "reason": "use_supersede_for_changes"}
        record = copy.deepcopy(entry)
        record["version"] = 1
        record["superseded"] = False
        record["supersedes"] = None
        self._versions[entry["id"]] = [record]
        return {"outcome": "admitted", "version": 1}

    def supersede(self, entry_id: str, updated: dict) -> dict:
        versions = self._versions.get(entry_id)
        if not versions:
            return {"outcome": "rejected", "reason": "unknown_id"}
        if any(field not in updated or not updated[field] for field in REQUIRED_FIELDS):
            return {"outcome": "rejected", "reason": "missing_required_field"}
        text = f"{updated.get('text', '')} {updated.get('example', '')}".lower()
        if any(word in text for word in SECRET_WORDS):
            return {"outcome": "rejected", "reason": "secret_content"}
        versions[-1]["superseded"] = True
        record = copy.deepcopy(updated)
        record["version"] = len(versions) + 1
        record["superseded"] = False
        record["supersedes"] = versions[-1]["version"]
        versions.append(record)
        return {"outcome": "admitted", "version": record["version"]}

    def all_versions(self, entry_id: str) -> list[dict]:
        return [copy.deepcopy(v) for v in self._versions.get(entry_id, [])]

    def search(self, use_case: str | None = None, app: str | None = None) -> list[dict]:
        results = []
        for versions in self._versions.values():
            latest = versions[-1]
            if latest["superseded"]:
                continue
            if use_case is not None and latest["use_case"] != use_case:
                continue
            if app is not None and latest["app"] != app:
                continue
            results.append(copy.deepcopy(latest))
        return results
