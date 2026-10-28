#!/usr/bin/env python3
"""AI Memory phone bridge — Stage 1, local build.

Serves the PWA shell and answers its chat calls on 127.0.0.1 ONLY.
In production this process sits behind the founder-approved HTTPS
host; the phone never talks to the memory core directly.

Pairing: every /chat call must present the per-device pairing token
in the X-Pairing-Token header. The bridge stores no token — only
SHA-256 hashes, read from a JSON file OUTSIDE the repository
(env PHONE_PAIRING_FILE, default ~/.config/ai-memory/phone-pairing.json;
see PAIRING.md for the structure). No match -> 401, fail closed.

Mind: authenticated messages are forwarded to
`omniroute chat --stream --stdin --model gpt-6-luna` with the same
persona/guardrail prompt pattern as tools/telegram_instant.py.
MODEL_CMD (env) overrides the whole model command so tests can
substitute a fake; the prompt is always passed on stdin.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PAIRING_ENV = "PHONE_PAIRING_FILE"
DEFAULT_PAIRING_PATH = Path.home() / ".config" / "ai-memory" / "phone-pairing.json"
MODEL_ENV = "MODEL_CMD"
DEFAULT_MODEL_CMD = ["omniroute", "chat", "--stream", "--stdin",
                     "--model", "gpt-6-luna"]
MAX_BODY_BYTES = 16_384
MAX_MESSAGE_CHARS = 4_000
REPLY_CAP = 1_200
MODEL_TIMEOUT = 120.0

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/service-worker.js": ("service-worker.js", "text/javascript; charset=utf-8"),
    "/icon-192.png": ("icon-192.png", "image/png"),
    "/icon-512.png": ("icon-512.png", "image/png"),
}

# OmniRoute loader-noise markers: the evals/qa_client.py set, plus the
# leading bracketed-header heuristic from tools/telegram_instant.py.
_NOISE_MARKERS = ("Loaded env from", "STORAGE_ENCRYPTION_KEY",
                  ".env lives inside", "Usage:", "omniroute chat")
_HEADER_HINTS = ("omniroute", ".env", "loaded environment",
                 "loading environment")


def strip_model_output(raw: str) -> str:
    kept: list[str] = []
    for line in (raw or "").splitlines():
        if any(m in line for m in _NOISE_MARKERS):
            continue
        low = line.strip().lower()
        if not kept and (not low or (low.startswith("[")
                                     and any(h in low
                                             for h in _HEADER_HINTS))):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def cap_reply(text: str, cap: int = REPLY_CAP) -> str:
    text = (text or "").strip()
    if len(text) <= cap:
        return text
    return text[:cap - 3].rstrip() + "..."


# -- pairing ---------------------------------------------------------

def pairing_path() -> Path:
    raw = os.environ.get(PAIRING_ENV, "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_PAIRING_PATH


def load_allowed_hashes() -> set[str]:
    """SHA-256 digests of paired device tokens. Empty set on any
    problem — an unreadable or malformed pairing file pairs nobody."""
    try:
        data = json.loads(pairing_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    found: set[str] = set()

    def take(node):
        if isinstance(node, dict):
            value = node.get("token_sha256")
            if isinstance(value, str) and len(value.strip()) == 64:
                found.add(value.strip().lower())

    if isinstance(data, dict):
        take(data)
        devices = data.get("devices")
        if isinstance(devices, list):
            for entry in devices:
                take(entry)
    return found


def is_authorised(token: str | None) -> bool:
    if not token:
        return False
    allowed = load_allowed_hashes()
    if not allowed:
        return False
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return any(hmac.compare_digest(digest, known) for known in allowed)


# -- prompt + model ----------------------------------------------------

def read_corpus_tail() -> int | None:
    """Latest `### N` header from the corpus named by MEMORY_CORPUS_PATH.
    None when unset/unreadable — never invented."""
    raw = os.environ.get("MEMORY_CORPUS_PATH", "").strip()
    if not raw:
        return None
    tail: int | None = None
    try:
        with open(Path(raw).expanduser(), encoding="utf-8") as f:
            for line in f:
                if line.startswith("### "):
                    num = line[4:].strip().split()[0] if line[4:].strip() else ""
                    if num.isdigit():
                        tail = int(num)
    except OSError:
        return None
    return tail


def _today_ist() -> str:
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Calcutta"))
    except Exception:
        now = datetime.now()
    return now.strftime("%A %d %B %Y")


def build_prompt(text: str) -> str:
    tail = read_corpus_tail()
    if tail is not None:
        holdings = (f"Your stored corpus currently holds {tail} "
                    f"numbered ideas (the latest is #{tail}).")
    else:
        holdings = ("You could not read your corpus just now; do "
                    "not invent any count or total.")
    return (
        "You are the AI memory itself, speaking in the first person "
        "to nitesh, your founder, through your app on his phone. "
        "Answer his message directly, warmly and briefly, in plain "
        "language.\n"
        f"Today is {_today_ist()}. {holdings}\n"
        "Hard rules: never claim that you spent money, published, "
        "posted, sent anything anywhere, or logged in to anything; "
        "never ask him for any password, code or credential; if you "
        "do not know something, say so plainly rather than inventing "
        "it. Keep the reply under 1000 characters, plain text, no "
        "tables.\n"
        f'His message: "{text}"\n'
        "Your reply:")


def model_command() -> list[str]:
    override = os.environ.get(MODEL_ENV, "").strip()
    if override:
        return shlex.split(override)
    return list(DEFAULT_MODEL_CMD)


def model_reply(message: str) -> str:
    prompt = build_prompt(message)
    try:
        proc = subprocess.run(
            model_command(), input=prompt, capture_output=True,
            text=True, timeout=MODEL_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"model route failed ({type(exc).__name__})") from None
    if proc.returncode != 0:
        raise RuntimeError(f"model route exit {proc.returncode}")
    text = strip_model_output(proc.stdout or "")
    if not text:
        raise RuntimeError("model route returned an empty reply")
    return cap_reply(text)


# -- HTTP handler ------------------------------------------------------

class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "AIMemoryBridge/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter, single-line logs
        sys.stderr.write("bridge: " + (fmt % args) + "\n")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send_bytes(status,
                         json.dumps(payload).encode("utf-8"),
                         "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send_json(200, {"ok": True,
                                  "service": "ai-memory-phone-bridge"})
            return
        entry = STATIC_FILES.get(path)
        if entry is None:
            self._send_json(404, {"error": "not_found"})
            return
        filename, content_type = entry
        try:
            body = (APP_DIR / filename).read_bytes()
        except OSError:
            self._send_json(404, {"error": "not_found"})
            return
        self._send_bytes(200, body, content_type)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/chat":
            self._send_json(404, {"error": "not_found"})
            return
        if not is_authorised(self.headers.get("X-Pairing-Token")):
            self._send_json(401, {"error": "unauthorised"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "body_too_large_or_missing"})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return
        message = payload.get("message") if isinstance(payload, dict) else None
        if not isinstance(message, str) or not message.strip():
            self._send_json(400, {"error": "message_required"})
            return
        message = message.strip()[:MAX_MESSAGE_CHARS]
        try:
            reply = model_reply(message)
        except RuntimeError as exc:
            self._send_json(502, {"error": "model_unavailable",
                                  "detail": str(exc)})
            return
        self._send_json(200, {"reply": reply})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Memory phone bridge (Stage 1)")
    parser.add_argument("--host", default=os.environ.get("PHONE_BRIDGE_HOST",
                                                         DEFAULT_HOST))
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PHONE_BRIDGE_PORT",
                                                   str(DEFAULT_PORT))))
    args = parser.parse_args(argv)
    if args.host != "127.0.0.1":
        print("refusing to bind anything but 127.0.0.1", file=sys.stderr)
        return 2
    server = ThreadingHTTPServer((args.host, args.port), BridgeHandler)
    print(f"ai-memory phone bridge on http://{args.host}:{args.port} "
          f"(pairing file: {pairing_path()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
