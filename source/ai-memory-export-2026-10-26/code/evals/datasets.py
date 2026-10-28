"""datasets — dataset registry, download/cache, and loaders for the eval harness.

v0.3 (2026-10-14): LongMemEval-S (cleaned) loader is real; the other four
datasets are registered with loaders that validate schema once present.
Download uses plain HTTPS from huggingface.co (no `datasets` dependency —
the VM is disk-tight). The S-split is PINNED; LongMemEval-V2 is a different
protocol and must never be substituted (see EVAL_PLAN.md).
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

PINNED_LONGMEMEVAL_S = "xiaowu0162/longmemeval-cleaned"
PINNED_S_FILE = "longmemeval_s_cleaned.json"


@dataclass
class DatasetSpec:
    """One eval dataset: where it lives, its license, and its harness role."""
    name: str                       # HF repo id or short id
    file: str                       # pinned data file
    url: str                        # direct download URL
    license: str
    license_note: str = ""
    role: str = ""
    loader: str = ""                # loader function name in this module


def _hf_file(repo: str, path: str) -> str:
    return f"https://huggingface.co/datasets/{repo}/resolve/main/{path}"


DATASETS: dict[str, DatasetSpec] = {
    "longmemeval-s": DatasetSpec(
        name=PINNED_LONGMEMEVAL_S,
        file=PINNED_S_FILE,
        url=_hf_file(PINNED_LONGMEMEVAL_S, PINNED_S_FILE),
        license="MIT",
        role="Core QA pillar: 500 questions, 5 abilities "
             "(single-session-user/assistant/preference, multi-session, "
             "knowledge-update, temporal-reasoning). Gold = answer_session_ids.",
        loader="load_longmemeval_s",
    ),
    "locomo-mc10": DatasetSpec(
        name="Percena/locomo-mc10",
        file="",
        url="",
        license="CC-BY-NC-4.0",
        license_note="RESEARCH ONLY — never commercial. Swap out for any "
                     "commercial demo.",
        role="Second QA pillar (multiple-choice variant).",
        loader="load_locomo_mc10",
    ),
    "resilience": DatasetSpec(
        name="sumitaidev/agent-memory-resilience-benchmark",
        file="",
        url="",
        license="Apache-2.0",
        role="Adversarial: memory poisoning / negative transfer; scores "
             "resolver + constraints.",
        loader="load_resilience",
    ),
    "procedural": DatasetSpec(
        name="shiweid1/Procedure_Memory_System_Benchmark",
        file="",
        url="",
        license="MIT",
        role="Procedural memory: skills/workflows; scores the sop module.",
        loader="load_procedural",
    ),
    "privacy": DatasetSpec(
        name="wwj95/privacy-aware-memory-benchmark",
        file="",
        url="",
        license="CC-BY-4.0",
        role="Forgetting/privacy: what should NOT be remembered; scores "
             "the forgetting policy.",
        loader="load_privacy",
    ),
}


def ensure(spec: DatasetSpec, *, timeout: int = 300) -> str:
    """Download the dataset file into evals/data/ if absent. Returns path."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, spec.file)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    if not spec.url:
        raise FileNotFoundError(
            f"dataset {spec.name!r} has no pinned file yet — "
            f"pin the file name/URL in datasets.py before running."
        )
    req = urllib.request.Request(spec.url, headers={"User-Agent": "mm-eval-harness/0.3"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(path, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    return path


# ---------------------------------------------------------------------------
# LongMemEval-S (cleaned) loader
# ---------------------------------------------------------------------------

@dataclass
class LMEvalSItem:
    """One LongMemEval-S question with its haystack and gold answer sessions."""
    question_id: str
    question_type: str
    question: str
    question_date: str          # e.g. "2023/05/30 (Tue) 23:40"
    answer: str
    session_ids: list[str]     # haystack_session_ids
    session_texts: list[str]   # concatenated user+assistant turns per session
    session_dates: list[str]   # haystack_dates, parallel to session_ids
    gold_session_ids: list[str]  # answer_session_ids (subset of session_ids)


def _session_to_text(session: list[dict]) -> str:
    parts = []
    for turn in session:
        role = turn.get("role", "?")
        content = (turn.get("content") or "").strip()
        if content:
            parts.append(f"[{role}] {content}")
    return "\n".join(parts)


def load_longmemeval_s(limit: int | None = None) -> list[LMEvalSItem]:
    """Load the pinned LongMemEval-S cleaned split. Downloads on first use."""
    spec = DATASETS["longmemeval-s"]
    path = ensure(spec)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    items: list[LMEvalSItem] = []
    for entry in raw:
        if len(entry["haystack_sessions"]) != len(entry["haystack_session_ids"]):
            raise ValueError(
                f"schema drift in {spec.name}: session/id arrays out of sync "
                f"for {entry['question_id']}"
            )
        items.append(LMEvalSItem(
            question_id=entry["question_id"],
            question_type=entry["question_type"],
            question=entry["question"],
            question_date=entry["question_date"],
            answer=entry["answer"],
            session_ids=list(entry["haystack_session_ids"]),
            session_texts=[_session_to_text(s) for s in entry["haystack_sessions"]],
            session_dates=list(entry["haystack_dates"]),
            gold_session_ids=list(entry["answer_session_ids"]),
        ))
        if limit is not None and len(items) >= limit:
            break
    return items


def _not_pinned(which: str):  # placeholder loaders for unpinned datasets
    def _loader(limit: int | None = None):
        raise NotImplementedError(
            f"{which}: no file pinned yet. Pin the HF file name in "
            f"datasets.py (registry entry {which!r}) and the schema will "
            f"be validated on load."
        )
    return _loader


load_locomo_mc10 = _not_pinned("locomo-mc10")
load_resilience = _not_pinned("resilience")
load_procedural = _not_pinned("procedural")
load_privacy = _not_pinned("privacy")


def list_datasets() -> list[dict]:
    """Registry summary for `run_evals.py list`."""
    out = []
    for key, spec in DATASETS.items():
        path = os.path.join(DATA_DIR, spec.file) if spec.file else None
        out.append({
            "key": key,
            "repo": spec.name,
            "license": spec.license,
            "license_note": spec.license_note,
            "role": spec.role,
            "cached": bool(path and os.path.exists(path)),
            "path": path,
        })
    return out
