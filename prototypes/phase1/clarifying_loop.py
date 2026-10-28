"""Clarifying-question loop prototype (Nate Herk N8, 95% loop).

Proceed only at confidence 0.95 or above with no missing fields. A
missing field asks exactly one question for the first missing field.
Low confidence asks for confirmation before proceeding. After three
questions with the task still unresolved, the loop escalates to a
human and never proceeds on its own. Stdlib only. Synthetic data only.
"""

from __future__ import annotations

PROCEED_CONFIDENCE = 0.95
MAX_QUESTIONS = 3


class ClarifyingLoop:
    def __init__(self, task: str, confidence: float, missing_fields: list[str]) -> None:
        self.task = task
        self.confidence = confidence
        self._missing = list(missing_fields)
        self.fields: dict[str, str] = {}
        self.questions_asked = 0

    def decide(self) -> dict:
        if self._missing and self.questions_asked >= MAX_QUESTIONS:
            return {"decision": "escalate", "reason": "question_limit_reached"}
        if self._missing:
            field = self._missing[0]
            return {
                "decision": "ask",
                "question": f"What is the {field} for this synthetic task?",
                "field": field,
            }
        if self.questions_asked >= MAX_QUESTIONS and self.confidence < PROCEED_CONFIDENCE:
            return {"decision": "escalate", "reason": "question_limit_reached"}
        if self.confidence >= PROCEED_CONFIDENCE:
            return {"decision": "proceed"}
        return {
            "decision": "ask",
            "question": "Please confirm the synthetic task details before proceeding.",
            "field": None,
        }

    def answer(self, value: str, confidence: float | None = None) -> dict:
        """Record one answer, then re-evaluate. One answer, one question."""
        self.questions_asked += 1
        if self._missing:
            field = self._missing.pop(0)
            self.fields[field] = value
        if confidence is not None:
            self.confidence = confidence
        return self.decide()
