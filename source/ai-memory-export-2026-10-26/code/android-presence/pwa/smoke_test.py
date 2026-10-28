#!/usr/bin/env python3
"""Smoke tests for the Stage 1 AI Memory PWA (local build).

Checks:
  1. manifest.webmanifest parses as JSON and carries the required fields;
  2. icon-192.png is a 192x192 PNG;
  3. icon-512.png is a 512x512 PNG;
  4. the bridge rejects an unauthenticated /chat call with 401;
  5. the bridge accepts a fake pairing token + fake model command and
     returns the fake reply (loader noise stripped).

Localhost only. The bridge subprocess is always terminated, pass or fail.
Run:  python3 smoke_test.py
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAKE_TOKEN = "fake-pairing-token-for-smoke-tests"
FAKE_REPLY = "Fake reply from the memory."

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def post_chat(port: int, token: str | None, message: str):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/chat",
        data=json.dumps({"message": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    if token is not None:
        req.add_header("X-Pairing-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, {"raw": body}


def wait_for_health(port: int, proc: subprocess.Popen, seconds: float = 15.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            time.sleep(0.15)
    return False


def main() -> int:
    # 1. Manifest
    try:
        manifest = json.loads((HERE / "manifest.webmanifest").read_text("utf-8"))
        fields_ok = (
            manifest.get("name") == "AI Memory"
            and manifest.get("short_name") == "Memory"
            and manifest.get("display") == "standalone"
            and manifest.get("theme_color") == "#07332f"
            and {icon.get("sizes") for icon in manifest.get("icons", [])}
                >= {"192x192", "512x512"}
        )
        check("manifest-json-valid-and-fields", fields_ok)
    except (OSError, ValueError) as exc:
        check("manifest-json-valid-and-fields", False, str(exc))

    # 2-3. Icons
    try:
        from PIL import Image
        for size in (192, 512):
            with Image.open(HERE / f"icon-{size}.png") as img:
                check(f"icon-{size}-size", img.size == (size, size)
                      and img.format == "PNG", f"got {img.size} {img.format}")
    except Exception as exc:  # PIL missing or unreadable icon
        check("icon-192-size", False, str(exc))
        check("icon-512-size", False, str(exc))

    # 4-5. Bridge auth + fake model
    tmp = Path(tempfile.mkdtemp(prefix="pwa-smoke-"))
    pairing = tmp / "phone-pairing.json"
    pairing.write_text(json.dumps({
        "device_name": "smoke-test-device",
        "token_sha256": hashlib.sha256(FAKE_TOKEN.encode()).hexdigest(),
    }), encoding="utf-8")
    fake_model = tmp / "fake_model.py"
    fake_model.write_text(
        "import sys\n"
        "sys.stdin.read()\n"
        "print('Loaded env from /fake/.env')\n"
        f"print({FAKE_REPLY!r})\n",
        encoding="utf-8")

    port = free_port()
    env = dict(os.environ)
    env["PHONE_PAIRING_FILE"] = str(pairing)
    env["MODEL_CMD"] = f"{sys.executable} {fake_model}"
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "bridge.py"), "--port", str(port)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True)
    try:
        up = wait_for_health(port, proc)
        check("bridge-starts-on-localhost", up)
        if up:
            status, _ = post_chat(port, None, "Hello")
            check("bridge-unauthenticated-401", status == 401,
                  f"got {status}")
            status, body = post_chat(port, FAKE_TOKEN, "Hello, memory.")
            check("bridge-fake-token-fake-model-reply",
                  status == 200 and body.get("reply") == FAKE_REPLY,
                  f"got {status} {body}")
        else:
            check("bridge-unauthenticated-401", False, "bridge did not start")
            check("bridge-fake-token-fake-model-reply", False,
                  "bridge did not start")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    check("bridge-process-stopped", proc.poll() is not None)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", FAIL)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
