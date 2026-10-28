"""Workspace adapter prototype (Jeff Su J6).

Adapters for synthetic workspace sources. They take no credentials,
make no network calls, and touch no real account: fetch() returns
copies of the synthetic items they were constructed with, and
to_draft() returns a draft only, never a send. Stdlib only. Synthetic
data only.
"""

from __future__ import annotations

import copy


class AdapterError(Exception):
    """Raised for an unknown adapter name."""


class SyntheticAdapter:
    def __init__(self, name: str, items: list[dict]) -> None:
        self.name = name
        self._items = copy.deepcopy(items)

    def fetch(self) -> list[dict]:
        """Return copies of the synthetic items. Stored items are untouched."""
        return copy.deepcopy(self._items)

    def to_draft(self, item: dict) -> dict:
        """Turn one synthetic item into a draft summary. Draft only."""
        return {
            "kind": "draft_only",
            "sent": False,
            "source": self.name,
            "draft_text": f"Draft summary of synthetic item {item.get('id')}: {item.get('text', '')}",
        }


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SyntheticAdapter] = {}

    def register(self, adapter: SyntheticAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> SyntheticAdapter:
        if name not in self._adapters:
            raise AdapterError(f"unknown adapter: {name}")
        return self._adapters[name]

    def list_adapters(self) -> list[str]:
        return list(self._adapters)
