"""CORE workflow prototype (Jeff Su J1).

Capture, Organise, Review, Engage over synthetic items. Every stage
appends to an audit trail and preserves provenance. Review at
confidence below 0.6 sends the record to a human review queue, and
engage() refuses a record that is not approved. Engage produces a
draft only, never a send. Stdlib only. Synthetic data only.
"""

from __future__ import annotations

import copy

REVIEW_CONFIDENCE = 0.6

_CATEGORIES = {
    "finance": ("finance", "budget", "invoice", "sales", "revenue"),
    "support": ("help", "refund", "broken", "support"),
    "personal": ("lunch", "coffee", "birthday"),
}


class CoreError(Exception):
    """Raised when engage() is called on an unapproved record."""


class CorePipeline:
    def __init__(self) -> None:
        self._seq = 0

    def capture(self, text: str) -> dict:
        self._seq += 1
        return {
            "text": text,
            "provenance": {"source": "synthetic", "seq": self._seq},
            "audit": [{"stage": "capture"}],
            "status": "captured",
            "category": None,
            "confidence": None,
            "action": None,
        }

    def organise(self, record: dict) -> dict:
        result = copy.deepcopy(record)
        lowered = result["text"].lower()
        category = "general"
        for name, keywords in _CATEGORIES.items():
            if any(word in lowered for word in keywords):
                category = name
                break
        result["category"] = category
        result["audit"].append({"stage": "organise"})
        result["status"] = "organised"
        return result

    def review(self, record: dict, confidence: float) -> dict:
        result = copy.deepcopy(record)
        result["confidence"] = confidence
        result["audit"].append({"stage": "review"})
        result["status"] = "approved" if confidence >= REVIEW_CONFIDENCE else "in_review_queue"
        return result

    def engage(self, record: dict) -> dict:
        if record.get("status") != "approved":
            raise CoreError("record is not approved for engage")
        result = copy.deepcopy(record)
        result["audit"].append({"stage": "engage"})
        result["action"] = {
            "kind": "draft_only",
            "sent": False,
            "draft": f"Draft action for: {result['text']}",
        }
        result["status"] = "drafted"
        return result
