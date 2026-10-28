"""qa_client — answer + judge clients for the LongMemEval-S QA protocol.

Wiring prep built 2026-10-15 (v0.3+). Both the answer model and the LLM
judge run through OmniRoute's local router::

    echo "$PROMPT" | omniroute chat --stream --stdin --model <model-id>

No provider keys are needed to build this client; the answer/judge MODEL
is chosen the day the free-provider keys land (Google AI Studio, Groq,
Cerebras, Mistral, OpenRouter).

Research-bar rules (per EVAL_PLAN.md — his bar, non-negotiable):
  1. Pin ONE judge model at the first wired run: write it into
     JUDGE_MODEL_PIN below with the date. Never mix judges across runs.
  2. Always report the deterministic fallback scores (exact + contains)
     ALONGSIDE any LLM-judge score — never instead of them.
  3. An LLM call that fails is a failed call (returns None / raises),
     never a silent zero.

Router lesson (workspace AGENTS.md): `omniroute chat` in non-streaming
mode drops long responses — always --stream, and strip the env-loader
header lines from captured output.
"""

from __future__ import annotations

import re
import subprocess

# --- pinned at the first wired run (date + model id); until then None ---
# Pinned 2026-10-20 (benchmark wave): first wired QA run used
# gpt-6-luna as both answer and judge model via OmniRoute. One judge
# per comparison series - do not mix.
JUDGE_MODEL_PIN: str | None = "gpt-6-luna"
DEFAULT_ANSWER_MODEL: str | None = "gpt-6-luna"

# Lines the omniroute CLI prints to stdout that are not model output.
_NOISE_MARKERS = ("Loaded env from", "STORAGE_ENCRYPTION_KEY",
                  ".env lives inside", "Usage:", "omniroute chat")

# Keep prompts inside the router's working context; sessions beyond this
# are trimmed oldest-first (documented, deterministic).
# 2026-10-20 (benchmark wave): per-session cap raised 900 -> 3000. At
# 900 chars the answer-bearing turn of a typical LongMemEval session
# (avg ~9.6k chars) was usually truncated away, so QA scores measured
# truncation, not memory. The 30k total cap still governs.
_MAX_SESSION_CHARS = 3000
_MAX_PROMPT_CHARS = 30_000


def _strip_router_noise(text: str) -> str:
    kept = [ln for ln in text.splitlines()
            if not any(m in ln for m in _NOISE_MARKERS)]
    return "\n".join(kept).strip()


def _norm(s) -> str:
    # 2026-10-20 (benchmark wave): LongMemEval gold answers can be
    # non-strings (counts). Coerce - v2 QA crashed on an int gold.
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def build_answer_prompt(question: str, sessions: list[str],
                        dates: list[str] | None = None) -> str:
    """Deterministic prompt: question + numbered haystack sessions.

    Budget rule: the header (instructions + question) is ALWAYS kept.
    Sessions fill the remaining char budget newest-first (oldest are
    dropped first), then display in chronological order.

    2026-10-20 fix (benchmark wave): the previous implementation
    left-trimmed the assembled string to _MAX_PROMPT_CHARS, which
    deleted the instructions and the question itself on every
    LongMemEval-S item (haystacks run ~500k chars vs a 30k cap). The
    answer model responded to the sessions as if continuing the
    conversation; all full-haystack QA numbers from that build are
    invalid artifacts and are superseded by post-fix runs.
    """
    dates = dates or [""] * len(sessions)
    header = ["Answer the question using ONLY the conversation sessions below.",
              "Reply with the answer alone — no explanation, no preamble.", "",
              f"Question: {question.strip()}", ""]
    budget = _MAX_PROMPT_CHARS - len("\n".join(header))
    blocks = []
    for i, (sess, date) in enumerate(zip(sessions, dates), 1):
        sess = sess[:_MAX_SESSION_CHARS]
        label = f"Session {i}" + (f" ({date})" if date else "")
        blocks.append(f"{label}:\n{sess}\n")
    kept: list[str] = []
    used = 0
    for block in reversed(blocks):  # newest first; oldest dropped first
        if kept and used + len(block) > budget:
            continue
        kept.append(block)
        used += len(block)
    kept.reverse()
    return "\n".join(header + kept)


def answer(question: str, sessions: list[str], model: str,
           dates: list[str] | None = None,
           timeout_s: int = 180) -> str:
    """Ask the answer model via OmniRoute. Raises RuntimeError on failure."""
    prompt = build_answer_prompt(question, sessions, dates)
    try:
        proc = subprocess.run(
            ["omniroute", "chat", "--stream", "--stdin", "--model", model],
            input=prompt, capture_output=True, text=True,
            timeout=timeout_s)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"answer model timed out after {timeout_s}s") from e
    out = _strip_router_noise(proc.stdout)
    if proc.returncode != 0 or not out:
        err = _strip_router_noise(proc.stderr)[-500:]
        raise RuntimeError(
            f"omniroute chat failed (rc={proc.returncode}): {err or 'no output'}")
    return out


def judge_exact(gold: str, pred: str) -> dict:
    """Deterministic fallback judge: normalized exact + contains."""
    g, p = _norm(gold), _norm(pred)
    return {"exact": bool(g) and g == p,
            "contains": bool(g) and bool(p) and (g in p or p in g)}


_JUDGE_PROMPT = ("You are grading a memory-QA answer.\n"
                 "Question: {q}\nGold answer: {gold}\nPredicted answer: {pred}\n"
                 "Is the predicted answer correct (same meaning, paraphrase "
                 "allowed)? Reply with exactly YES or NO.")


def judge_llm(question: str, gold: str, pred: str, model: str,
              timeout_s: int = 120) -> bool | None:
    """LLM judge via OmniRoute. Returns None on any failure (never a guess)."""
    prompt = _JUDGE_PROMPT.format(q=str(question).strip(),
                                  gold=str(gold).strip(),
                                  pred=str(pred).strip())
    try:
        proc = subprocess.run(
            ["omniroute", "chat", "--stream", "--stdin", "--model", model],
            input=prompt, capture_output=True, text=True,
            timeout=timeout_s)
        out = _strip_router_noise(proc.stdout)
        if proc.returncode != 0 or not out:
            return None
        first = _norm(out).split(" ")[0]
        if first == "yes":
            return True
        if first == "no":
            return False
        return None
    except (subprocess.TimeoutExpired, OSError):
        return None
