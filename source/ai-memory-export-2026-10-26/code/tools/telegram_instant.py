"""Always-on instant-reply runner for the AI memory's Telegram bot
(founder order 2026-10-26: "instant reply is top priority").

Where tools/telegram_runner.py drains the agent's proactive outbox,
this runner answers the founder's own messages, immediately. All
Telegram calls go through mm/telegram_channel.py, whose token rule
is unchanged: the token is read only from the TELEGRAM_BOT_TOKEN
environment variable, at call time, and the channel fails closed
without it. Under systemd the variable is supplied by an
EnvironmentFile pointing at the founder's locked credential store
(/home/hatch/.config/ai-memory/telegram.env, mode 600, outside this
repository). The token appears in no code, unit, or repo file; an
earlier connector-helper transport remains in this module as an
unused alternative and is not in the service's path.

Behaviour:
- Long-polls getUpdates through the helper, passing a persisted
  offset (data/telegram-offset.json) so restarts neither lose
  messages nor answer one twice (an answered-ids ledger is kept
  beside the offset for redelivered updates).
- Answers ONLY the paired chat (data/telegram-pairing.json, the
  allowlist locked by mm/telegram_channel.py's first-/start rule;
  a first /start here pairs by the same rule). Any other chat is
  refused and its text is recorded nowhere.
- Reply text is generated per message: a short file-based prompt
  (the memory speaking in first person, with today's date and the
  current corpus tail) is piped to
  `omniroute chat --stream --stdin --model gpt-6-luna`.
- If the model route fails, the founder still hears back at once:
  one short holding reply, and his message is queued
  (data/telegram-retry-queue.json) for a later retry. Silence and
  fabricated answers are both refused.
- Dismissal phrases route to agent.note_outreach_response(), as in
  mm/telegram_channel.py, and get no model reply.
- Quiet hours do NOT apply here: he initiated the conversation.

Fail-closed: at startup the runner probes the API with getMe. If
TELEGRAM_BOT_TOKEN is absent (channel MissingTokenError) or the
API rejects it, the runner exits non-zero and sends nothing.

Run:
    python3 tools/telegram_instant.py [--db data/memory.db]
        [--poll-timeout 25] [--once] [--check]
(Under systemd, TELEGRAM_BOT_TOKEN arrives via EnvironmentFile;
a bare shell run without the variable fails closed by design.)
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.telegram_channel import TelegramChannel, TelegramChannelError

DEFAULT_HELPER = os.path.expanduser(
    "~/workspace/custom-connectors/custom.telegram-bot/bin/telegram_bot.py")
DEFAULT_PAIRING = "data/telegram-pairing.json"
DEFAULT_OFFSET = "data/telegram-offset.json"
DEFAULT_QUEUE = "data/telegram-retry-queue.json"
DEFAULT_CORPUS = os.path.expanduser(
    "~/workspace/goals/ai-agent-memory-milestone-repo/hidden_files/"
    "research/video-corpus-100/BEST-IDEAS.md")
MODEL_NAME = "gpt-6-luna"
REPLY_CAP = 1200
MAX_RETRY_ATTEMPTS = 5
HOLDING_REPLY = ("I have your message; my mind is briefly "
                 "unreachable and I shall answer when it returns.")
WELCOME_REPLY = ("I am here, and this chat is paired to me alone. "
                 "Write to me any time and I shall answer.")


class HelperError(RuntimeError):
    """The connector helper could not complete a Telegram call."""


class ModelError(RuntimeError):
    """The model route produced no usable reply."""


# -- connector helper client ------------------------------------------

class HelperClient:
    """Subprocess client for the telegram-bot connector helper
    (alternative transport; NOT used by the systemd service, whose
    token arrives via EnvironmentFile - see EnvChannelClient).

    The helper prints the Telegram API response as JSON on stdout.
    Any non-zero exit, unparseable output, or ok:false response is
    a HelperError; error text is truncated and never contains a
    credential (the helper itself never sees the raw token)."""

    def __init__(self, helper_path: str = DEFAULT_HELPER, *,
                 runner=subprocess.run, timeout: float = 60.0) -> None:
        self.helper_path = helper_path
        self._runner = runner
        self.timeout = timeout

    def _call(self, args: list[str]) -> dict:
        try:
            proc = self._runner(
                [sys.executable, self.helper_path, *args],
                capture_output=True, text=True, timeout=self.timeout)
        except (OSError, subprocess.SubprocessError) as exc:
            raise HelperError(
                f"helper invocation failed ({type(exc).__name__})"
            ) from None
        if proc.returncode != 0:
            tail = (proc.stderr or "").strip().splitlines()
            detail = tail[-1][:160] if tail else f"exit {proc.returncode}"
            raise HelperError(f"helper failed: {detail}")
        try:
            resp = json.loads(proc.stdout)
        except ValueError:
            raise HelperError("helper returned unparseable output") \
                from None
        if not isinstance(resp, dict) or not resp.get("ok"):
            desc = ""
            if isinstance(resp, dict):
                desc = str(resp.get("description", ""))[:160]
            raise HelperError("Telegram API not ok"
                              + (f": {desc}" if desc else ""))
        return resp

    def get_me(self) -> dict:
        result = self._call(["get-me"]).get("result")
        return result if isinstance(result, dict) else {}

    def get_updates(self, offset: int | None,
                    timeout_s: int = 0) -> list[dict]:
        args = ["updates", "--timeout", str(timeout_s)]
        if offset is not None:
            args += ["--offset", str(offset)]
        result = self._call(args).get("result")
        return result if isinstance(result, list) else []

    def send(self, chat_id: int, text: str) -> dict:
        fd, path = tempfile.mkstemp(prefix="tg-reply-", suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            result = self._call(["send", "--chat-id", str(chat_id),
                                 "--text-file", path]).get("result")
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        return result if isinstance(result, dict) else {}


# -- env-backed channel client (the service's transport) -----------------

class EnvChannelClient:
    """Telegram transport over mm.telegram_channel.TelegramChannel.

    The channel reads TELEGRAM_BOT_TOKEN from the environment at
    call time (under systemd: the locked EnvironmentFile) and fails
    closed without it; its send path additionally enforces the
    pairing allowlist. Channel errors are re-raised as HelperError
    so the replier has one transport error type; channel error
    messages never contain the token."""

    def __init__(self, channel: TelegramChannel) -> None:
        self.channel = channel

    def get_me(self) -> dict:
        try:
            result = self.channel.api_call("getMe")
        except TelegramChannelError as exc:
            raise HelperError(str(exc)) from None
        return result if isinstance(result, dict) else {}

    def get_updates(self, offset: int | None,
                    timeout_s: int = 0) -> list[dict]:
        payload: dict = {"timeout": timeout_s}
        if offset is not None:
            payload["offset"] = offset
        try:
            result = self.channel.api_call("getUpdates", payload)
        except TelegramChannelError as exc:
            raise HelperError(str(exc)) from None
        return result if isinstance(result, list) else []

    def send(self, chat_id: int, text: str) -> dict:
        try:
            return self.channel.send_message(chat_id, text)
        except TelegramChannelError as exc:
            raise HelperError(str(exc)) from None


# -- model route --------------------------------------------------------

_HEADER_HINTS = ("omniroute", ".env", "loaded environment",
                 "loading environment")

# Lines the omniroute CLI prints that are not model output; the
# same marker set evals/qa_client.py has used since the benchmark
# wave. Any line containing one is dropped, wherever it appears.
_NOISE_MARKERS = ("Loaded env from", "STORAGE_ENCRYPTION_KEY",
                  ".env lives inside", "Usage:", "omniroute chat")


def strip_model_output(raw: str) -> str:
    """Drop OmniRoute's loader/noise lines from streamed output:
    any line carrying a known CLI noise marker (the qa_client set),
    plus leading bracketed loader notices. The model's own lines
    are returned untouched."""
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


class OmniRouteModel:
    """Reply generator: file-based prompt in, streamed reply out."""

    def __init__(self, model: str = MODEL_NAME, *,
                 runner=subprocess.run, timeout: float = 120.0) -> None:
        self.model = model
        self._runner = runner
        self.timeout = timeout

    def reply(self, prompt: str) -> str:
        fd, path = tempfile.mkstemp(prefix="tg-prompt-", suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
            with open(path, encoding="utf-8") as fin:
                try:
                    proc = self._runner(
                        ["omniroute", "chat", "--stream", "--stdin",
                         "--model", self.model],
                        stdin=fin, capture_output=True, text=True,
                        timeout=self.timeout)
                except (OSError, subprocess.SubprocessError) as exc:
                    raise ModelError(
                        f"model route failed ({type(exc).__name__})"
                    ) from None
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        if proc.returncode != 0:
            raise ModelError(f"model route exit {proc.returncode}")
        text = strip_model_output(proc.stdout or "")
        if not text:
            raise ModelError("model route returned an empty reply")
        return text


# -- prompt ---------------------------------------------------------------

def read_corpus_tail(path: str | None) -> int | None:
    """The corpus's current tail: the last `### N` header in the
    BEST-IDEAS file. None when unreadable - never invented."""
    if not path:
        return None
    tail: int | None = None
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("### "):
                    num = line[4:].strip().split()[0] if line[4:].strip() \
                        else ""
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


def build_prompt(text: str, *, tail: int | None,
                 today: str | None = None) -> str:
    today = today or _today_ist()
    if tail is not None:
        holdings = (f"Your stored corpus currently holds {tail} "
                    f"numbered ideas (the latest is #{tail}).")
    else:
        holdings = ("You could not read your corpus just now; do "
                    "not invent any count or total.")
    return (
        "You are the AI memory itself, speaking in the first person "
        "to nitesh, your founder, over Telegram. Answer his message "
        "directly, warmly and briefly, in plain language.\n"
        f"Today is {today}. {holdings}\n"
        "Hard rules: never claim that you spent money, published, "
        "posted, sent anything anywhere, or logged in to anything; "
        "never ask him for any password, code or credential; if you "
        "do not know something, say so plainly rather than inventing "
        "it. Keep the reply under 1000 characters, plain text, no "
        "tables.\n"
        f'His message: "{text}"\n'
        "Your reply:")


def cap_reply(text: str, cap: int = REPLY_CAP) -> str:
    text = (text or "").strip()
    if len(text) <= cap:
        return text
    return text[:cap - 3].rstrip() + "..."


# -- small JSON state files ------------------------------------------------

def _load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _save_json(path: str, data) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


# -- the replier -------------------------------------------------------------

class InstantReplier:
    """Poll -> allowlist -> answer, once per founder message.

    helper/model are injectable for tests. agent (optional) receives
    dismissal routing exactly as mm/telegram_channel.py does it.
    """

    def __init__(self, *, helper, model, pairing_path: str,
                 offset_path: str, queue_path: str,
                 corpus_path: str | None = DEFAULT_CORPUS,
                 agent=None, now=time.time) -> None:
        self.helper = helper
        self.model = model
        self.pairing_path = pairing_path
        self.offset_path = offset_path
        self.queue_path = queue_path
        self.corpus_path = corpus_path
        self.agent = agent
        self._now = now
        self.bot_id: int | None = None
        self.bot_username: str | None = None
        self.refused_log: list[dict] = []
        pairing = _load_json(pairing_path, {})
        self._paired_chat_id = pairing.get("chat_id") \
            if isinstance(pairing.get("chat_id"), int) else None
        state = _load_json(offset_path, {})
        self._next_offset = state.get("next_offset") \
            if isinstance(state.get("next_offset"), int) else None
        self._answered: dict[str, str] = state.get("answered", {}) \
            if isinstance(state.get("answered"), dict) else {}
        self._queue: list[dict] = _load_json(queue_path, [])

    # -- state -----------------------------------------------------

    @property
    def paired_chat_id(self) -> int | None:
        return self._paired_chat_id

    @property
    def next_offset(self) -> int | None:
        return self._next_offset

    @property
    def queue(self) -> list[dict]:
        return list(self._queue)

    def _save_offset(self) -> None:
        answered = dict(list(self._answered.items())[-500:])
        self._answered = answered
        _save_json(self.offset_path,
                   {"next_offset": self._next_offset,
                    "answered": answered,
                    "updated_at": self._now()})

    def _save_queue(self) -> None:
        _save_json(self.queue_path, self._queue)

    def _pair(self, chat_id: int) -> None:
        self._paired_chat_id = chat_id
        _save_json(self.pairing_path,
                   {"chat_id": chat_id, "paired_at": self._now(),
                    "channel": "telegram"})

    # -- startup -----------------------------------------------------

    def startup_check(self) -> dict:
        """Probe the API. Raises HelperError when the credential
        is missing or wrong: the runner fails closed before
        polling or sending anything."""
        me = self.helper.get_me()
        if isinstance(me.get("id"), int):
            self.bot_id = me["id"]
        self.bot_username = me.get("username")
        return me

    # -- update handling ----------------------------------------------

    def _advance(self, uid) -> None:
        if isinstance(uid, int):
            self._next_offset = max(self._next_offset or 0, uid + 1)
            self._save_offset()

    def _refuse(self, uid, chat_id, reason: str) -> dict:
        rec = {"kind": "refused", "reason": reason,
               "chat_id": chat_id, "update_id": uid}
        self.refused_log.append(rec)
        return rec

    def process_update(self, upd: dict) -> dict:
        """Handle one update; returns an action record. Founder
        text is used to build the reply prompt and is otherwise
        kept only in the retry queue (his own words, for his own
        pending answer); refused chats' text goes nowhere."""
        uid = upd.get("update_id")
        try:
            return self._process(upd, uid)
        finally:
            self._advance(uid)

    def _process(self, upd: dict, uid) -> dict:
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        sender = msg.get("from") or {}
        text = msg.get("text") or ""
        if not isinstance(chat_id, int) or not text.strip():
            return {"kind": "ignored", "update_id": uid}
        if self.bot_id is not None and sender.get("id") == self.bot_id:
            return {"kind": "ignored-own", "update_id": uid}
        if text.strip().startswith("/start"):
            if self._paired_chat_id is None:
                self._pair(chat_id)
                self.helper.send(chat_id, WELCOME_REPLY)
                self._answered[str(uid)] = "welcome"
                return {"kind": "paired", "chat_id": chat_id,
                        "update_id": uid}
            if chat_id == self._paired_chat_id:
                self.helper.send(chat_id, WELCOME_REPLY)
                self._answered[str(uid)] = "welcome"
                return {"kind": "welcome", "chat_id": chat_id,
                        "update_id": uid}
            return self._refuse(uid, chat_id, "already paired "
                                "to another chat")
        if chat_id != self._paired_chat_id:
            return self._refuse(uid, chat_id,
                                "chat not on the allowlist")
        if str(uid) in self._answered:
            return {"kind": "duplicate", "update_id": uid}
        if TelegramChannel._is_dismissal(text):
            routed = False
            target = None
            if self.agent is not None:
                target = TelegramChannel._last_outreach_id(self.agent)
                if target:
                    routed = bool(self.agent.note_outreach_response(
                        target, "dismissed", at=self._now()))
            self._answered[str(uid)] = "dismissal"
            return {"kind": "dismissal", "update_id": uid,
                    "routed": routed, "outreach_id": target}
        prompt = build_prompt(text, tail=read_corpus_tail(
            self.corpus_path))
        try:
            reply = cap_reply(self.model.reply(prompt))
        except ModelError:
            self._queue.append(
                {"update_id": uid, "chat_id": chat_id, "text": text,
                 "queued_at": self._now(), "attempts": 0})
            self._save_queue()
            self._answered[str(uid)] = "holding"
            try:
                self.helper.send(chat_id, HOLDING_REPLY)
            except HelperError:
                pass          # queued; the retry will speak
            return {"kind": "holding", "update_id": uid}
        self.helper.send(chat_id, reply)
        self._answered[str(uid)] = "reply"
        return {"kind": "reply", "update_id": uid}

    def retry_pending(self) -> list[dict]:
        """One retry pass over the model-failure queue."""
        actions: list[dict] = []
        remaining: list[dict] = []
        for item in self._queue:
            if item.get("attempts", 0) >= MAX_RETRY_ATTEMPTS:
                actions.append({"kind": "retry-dropped",
                                "update_id": item.get("update_id")})
                continue
            prompt = build_prompt(item.get("text", ""),
                                  tail=read_corpus_tail(
                                      self.corpus_path))
            try:
                reply = cap_reply(self.model.reply(prompt))
            except ModelError:
                item["attempts"] = item.get("attempts", 0) + 1
                remaining.append(item)
                actions.append({"kind": "retry-deferred",
                                "update_id": item.get("update_id")})
                continue
            if item.get("chat_id") == self._paired_chat_id:
                self.helper.send(item["chat_id"], reply)
            actions.append({"kind": "retry-replied",
                            "update_id": item.get("update_id")})
        self._queue = remaining
        self._save_queue()
        return actions

    def poll_once(self, timeout_s: int = 0) -> list[dict]:
        updates = self.helper.get_updates(self._next_offset, timeout_s)
        actions = [self.process_update(u) for u in updates]
        actions.extend(self.retry_pending())
        return actions


# -- entry point -----------------------------------------------------------

def _build_agent(db: str):
    """The live MemoryAgent, for dismissal routing. If the store
    cannot be opened the runner still answers; dismissals are then
    recorded as unrouted rather than crashing the loop."""
    try:
        from mm.agent import MemoryAgent
        from mm.storage import SQLiteStore
        return MemoryAgent(SQLiteStore(db))
    except Exception as exc:  # noqa: BLE001 - deliberate softening
        print(f"agent unavailable ({type(exc).__name__}); dismissal "
              "routing off", file=sys.stderr, flush=True)
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/memory.db",
                    help="SQLite memory store (default data/memory.db)")
    ap.add_argument("--pairing", default=DEFAULT_PAIRING)
    ap.add_argument("--offset", default=DEFAULT_OFFSET)
    ap.add_argument("--queue", default=DEFAULT_QUEUE)
    ap.add_argument("--corpus", default=DEFAULT_CORPUS)
    ap.add_argument("--poll-timeout", type=int, default=25,
                    help="getUpdates long-poll seconds (default 25)")
    ap.add_argument("--once", action="store_true",
                    help="one poll + retry pass, then exit")
    ap.add_argument("--check", action="store_true",
                    help="probe the helper credential and exit")
    args = ap.parse_args(argv)

    replier = InstantReplier(
        helper=EnvChannelClient(TelegramChannel(args.pairing)),
        model=OmniRouteModel(),
        pairing_path=args.pairing, offset_path=args.offset,
        queue_path=args.queue, corpus_path=args.corpus,
        agent=None if args.check else _build_agent(args.db))
    try:
        me = replier.startup_check()
    except HelperError as exc:
        print(f"refusing to start (fail closed): {exc}",
              file=sys.stderr)
        return 2
    print(f"telegram instant runner up; bot=@{me.get('username')} "
          f"paired={replier.paired_chat_id is not None}", flush=True)
    if args.check:
        return 0
    while True:
        try:
            replier.poll_once(timeout_s=args.poll_timeout)
        except HelperError as exc:
            print(f"poll error: {exc}", file=sys.stderr, flush=True)
            time.sleep(5)
        if args.once:
            return 0


if __name__ == "__main__":
    sys.exit(main())
