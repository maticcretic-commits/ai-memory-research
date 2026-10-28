"""Storyboard spec prototype (Sirio Berati S1-S3, show layer).

Builds a text-only storyboard specification: scene descriptions, a
render plan, and a credits block. Every scene must name a source and a
licence; captions are capped; total duration is capped at 60 seconds.
Nothing here generates an image or a video, and credits live in the
credits block only, never inside a frame description. Stdlib only.
Synthetic descriptions only. No network, no media generation.
"""

from __future__ import annotations

import copy

MAX_CAPTION_CHARS = 120
MAX_SCENE_SECONDS = 15
MAX_TOTAL_SECONDS = 60


class StoryboardError(Exception):
    """Raised when a scene or the whole spec fails validation."""


def build(scenes: list[dict]) -> dict:
    """Validate scenes and return a text-only storyboard spec."""
    if not scenes:
        raise StoryboardError("no scenes")
    total = 0
    for scene in scenes:
        if not scene.get("title"):
            raise StoryboardError("scene missing title")
        if len(scene.get("caption", "")) > MAX_CAPTION_CHARS:
            raise StoryboardError("caption too long")
        duration = scene.get("duration_s", 0)
        if not 0 < duration <= MAX_SCENE_SECONDS:
            raise StoryboardError("scene duration out of range")
        if not scene.get("source"):
            raise StoryboardError("scene missing source")
        if not scene.get("licence"):
            raise StoryboardError("scene missing licence")
        total += duration
    if total > MAX_TOTAL_SECONDS:
        raise StoryboardError("total duration exceeds 60 seconds")
    return {
        "scene_count": len(scenes),
        "total_duration_s": total,
        "credits": [
            {"source": s["source"], "licence": s["licence"]} for s in scenes
        ],
        "render_plan": [
            {
                "kind": "text_description",
                "title": s["title"],
                "visual": s.get("visual", ""),
                "caption": s["caption"],
                "duration_s": s["duration_s"],
            }
            for s in scenes
        ],
        "scenes": copy.deepcopy(scenes),
    }
