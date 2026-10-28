"""Inbox classifier prototype (Nate Herk N7, inbox shape).

Rule-based labelling of synthetic messages. Output is a label only, or
a draft for human review. There is no send path in this module: the
only actions are "label_only" and "draft_for_review". Uncertain input
— a tie between labels, or no keyword signal at all — goes to review
rather than being auto-labelled. Stdlib only. Synthetic data only.
"""

from __future__ import annotations

_KEYWORDS = {
    "support": ("help", "refund", "broken", "late", "support", "order", "arrived"),
    "lead": ("quote", "proposal", "pricing", "budget", "pilot", "timeline"),
    "newsletter": ("unsubscribe", "digest", "newsletter", "preferences", "roundup"),
    "personal": ("lunch", "coffee", "birthday", "friday"),
}


def _score(text: str) -> dict[str, int]:
    lowered = text.lower()
    return {
        label: sum(1 for word in words if word in lowered)
        for label, words in _KEYWORDS.items()
    }


def classify(subject: str, body: str) -> dict:
    """Return {"label": ..., "action": ..., "scores": {...}}.

    Fail-closed: ties and empty signal return label "review" with
    action "draft_for_review". No other action exists.
    """
    scores = _score(f"{subject} {body}")
    best = max(scores.values())
    leaders = [label for label, score in scores.items() if score == best]
    if best == 0 or len(leaders) != 1:
        return {"label": "review", "action": "draft_for_review", "scores": scores}
    return {"label": leaders[0], "action": "label_only", "scores": scores}
