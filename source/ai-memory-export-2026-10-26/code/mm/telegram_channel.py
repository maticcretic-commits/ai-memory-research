"""Telegram channel for the MemoryAgent (comms layer, standalone
build, founder order 2026-10-25: "the AI memory can talk to me /
Do it now").

Until now the comms layer was policy only: MemoryAgent.propose_
outreach() decides send / defer / suppress, send-decided items wait
in the outbox, and drain_outbox() is bookkeeping with no sending
code behind it. This module is the missing sender for ONE channel:
a Telegram bot the founder registered himself (bot registration is
his hard gate) whose token arrives through a secure connector.

Security rules (fail-closed everywhere):
- The bot token is read ONLY from the environment variable
  TELEGRAM_BOT_TOKEN, at call time. It is never read from a file,
  never accepted as a stored literal, never logged, and never put
  into an exception message. If the variable is absent the channel
  refuses to operate - no fallback of any kind.
- Pairing allowlist: the first /start message pairs its chat_id,
  persisted to a local pairing file (a chat_id is an identifier,
  not a secret). From then on the allowlist is that chat_id ONLY:
  inbound messages from any other chat are refused, and outbound
  sends to any other chat are refused.
- The channel delivers only what the agent has already decided:
  drain() sends outbox entries (decision == "send") and leaves
  quiet-hours-held entries in held_outreach untouched. The gate
  stays in mm/agent.py; this module never decides to speak.
- Inbound founder messages are recorded; dismissal words ("stop",
  "not now", ...) are routed to agent.note_outreach_response() so
  the D-K2 back-off learns from them, exactly as on other channels.

HTTP is urllib only (no new dependencies). The HTTP layer is
injectable (http_post callable) so tests run with no network and
no real token.
"""

import json
import os
import time
import urllib.error
import urllib.request

API_BASE = "https://api.telegram.org"
TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"

# Words the founder can reply with to dismiss the most recent
# outreach (D-K2). Matched case-insensitively on the whole message
# after stripping punctuation/space, so "Stop." and "not now"
# both count; a longer message that merely contains the word does
# not (a real conversation is never mistaken for a dismissal).
DISMISSAL_PHRASES = frozenset({
    "stop", "not now", "dismiss", "dismissed", "later", "no",
    "not interested", "go away", "quiet",
})


class TelegramChannelError(RuntimeError):
    """Any channel failure. Messages never contain the token."""


class MissingTokenError(TelegramChannelError):
    """TELEGRAM_BOT_TOKEN is not set: fail closed, no fallback."""


def _require_token(env_var: str = TOKEN_ENV_VAR) -> str:
    """Read the bot token from the environment, right now.

    Deliberately the ONLY token source in this module. Raises
    MissingTokenError when the variable is unset or empty."""
    token = os.environ.get(env_var, "").strip()
    if not token:
        raise MissingTokenError(
            f"{env_var} is not set; the Telegram channel fails "
            "closed without it (no file or literal fallback)")
    return token


def _urllib_post(url: str, payload: dict, timeout: float) -> dict:
    """Default HTTP layer: POST JSON, return the decoded body.

    The URL carries the token, so it is never echoed into errors:
    transport failures are re-raised as a bare TelegramChannelError.
    """
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise TelegramChannelError(
            f"Telegram API request failed ({type(exc).__name__})"
        ) from None


def format_outreach(entry: dict) -> str:
    """Render an outbox entry for delivery: the message itself,
    then its why-line (D-K2: no silent outreach - the founder can
    always see why the memory spoke first)."""
    text = entry.get("message", "")
    why = entry.get("why")
    if why:
        text = f"{text}\n\nWhy: {why}"
    return text


class TelegramChannel:
    """One paired Telegram chat <-> one MemoryAgent.

    pairing_path: where the pairing record lives (JSON, next to the
    agent's store by the caller's convention). http_post: optional
    callable (url, payload, timeout) -> dict, for tests.
    """

    def __init__(self, pairing_path: str, *,
                 http_post=None, timeout: float = 35.0,
                 env_var: str = TOKEN_ENV_VAR) -> None:
        self.pairing_path = pairing_path
        self._http_post = http_post or _urllib_post
        self.timeout = timeout
        self.env_var = env_var
        self.inbound_log: list[dict] = []
        self.refused_log: list[dict] = []
        self._next_offset: int | None = None
        self._pairing: dict | None = self._load_pairing()

    # -- pairing -----------------------------------------------------

    def _load_pairing(self) -> dict | None:
        try:
            with open(self.pairing_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("chat_id"), int):
                return data
        except (OSError, ValueError, AttributeError):
            pass
        return None

    def _save_pairing(self) -> None:
        tmp = self.pairing_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._pairing, f, indent=1, sort_keys=True)
        os.replace(tmp, self.pairing_path)

    @property
    def paired_chat_id(self) -> int | None:
        return self._pairing["chat_id"] if self._pairing else None

    @property
    def is_paired(self) -> bool:
        return self._pairing is not None

    def _pair(self, chat_id: int, at: float) -> bool:
        """Lock the allowlist to the first /start's chat. Returns
        False (and changes nothing) when already paired elsewhere."""
        if self._pairing is not None:
            return self._pairing["chat_id"] == chat_id
        self._pairing = {"chat_id": chat_id, "paired_at": at,
                         "channel": "telegram"}
        self._save_pairing()
        return True

    # -- Bot API -----------------------------------------------------

    def api_call(self, method: str, payload: dict | None = None) -> object:
        """One Bot API call. The token goes in the URL path exactly
        as Telegram requires; it is read fresh from the environment
        for every call and never stored on the instance."""
        token = _require_token(self.env_var)
        url = f"{API_BASE}/bot{token}/{method}"
        resp = self._http_post(url, payload or {}, self.timeout)
        if not isinstance(resp, dict) or not resp.get("ok"):
            desc = ""
            if isinstance(resp, dict):
                desc = str(resp.get("description", ""))[:200]
            raise TelegramChannelError(
                f"Telegram API {method} not ok"
                + (f": {desc}" if desc else ""))
        return resp.get("result")

    def get_updates(self, *, timeout_s: int = 0) -> list[dict]:
        """Fetch pending updates (long-poll when timeout_s > 0).
        Does not process them; see process_updates()."""
        payload: dict = {"timeout": timeout_s}
        if self._next_offset is not None:
            payload["offset"] = self._next_offset
        result = self.api_call("getUpdates", payload)
        return result if isinstance(result, list) else []

    def send_message(self, chat_id: int, text: str) -> dict:
        """Send one message. Refused unless chat_id is the paired
        chat (allowlist enforced outbound as well as inbound)."""
        if self.paired_chat_id is None:
            raise TelegramChannelError(
                "not paired: no founder chat to send to yet")
        if chat_id != self.paired_chat_id:
            raise TelegramChannelError(
                "refused: chat_id is not the paired founder chat")
        if not text:
            raise TelegramChannelError("refused: empty message")
        result = self.api_call(
            "sendMessage", {"chat_id": chat_id, "text": text})
        return result if isinstance(result, dict) else {}

    # -- outbound: drain the agent's outbox --------------------------

    def drain(self, agent, at: float | None = None) -> list[dict]:
        """Deliver the agent's send-decided outbox entries.

        Only entries physically in agent.outbox are touched - by
        construction those are exactly the decision == "send" ones;
        quiet-hours-held entries live in agent.held_outreach and
        stay held. Each entry is sent first and stamped via the
        agent's own drain bookkeeping: when every send succeeds we
        defer to agent.drain_outbox(); on a partial failure only
        the entries actually delivered are moved, so nothing is
        ever delivered twice or marked sent when it was not.
        Returns the entries delivered by this call.
        """
        at = time.time() if at is None else at
        _require_token(self.env_var)          # fail closed, pre-send
        if self.paired_chat_id is None:
            raise TelegramChannelError(
                "not paired: outbox left untouched")
        pending = [e for e in agent.outbox if e["decision"] == "send"]
        if not pending:
            return []
        sent: list[dict] = []
        for entry in pending:
            try:
                self.send_message(self.paired_chat_id,
                                  format_outreach(entry))
            except TelegramChannelError:
                break            # stop: later entries stay queued
            sent.append(entry)
        if not sent:
            return []
        if len(sent) == len(pending) and len(agent.outbox) == len(pending):
            agent.drain_outbox(at=at)         # agent's own bookkeeping
        else:
            # Partial drain: move only what was truly delivered,
            # mirroring drain_outbox()'s stamping.
            for e in sent:
                e["drained_at"] = at
                e["drained_ist"] = agent._ist(at).isoformat()
                agent.outbox.remove(e)
                agent.drained_outreach.append(e)
        for e in sent:
            e["delivered_via"] = "telegram"
        return sent

    # -- inbound: pairing, recording, dismissals ---------------------

    @staticmethod
    def _is_dismissal(text: str) -> bool:
        norm = " ".join(text.strip().lower().strip(".!").split())
        return norm in DISMISSAL_PHRASES

    @staticmethod
    def _last_outreach_id(agent) -> str | None:
        """The outreach a dismissal most plausibly answers: the
        most recently drained one, else the newest logged."""
        if agent.drained_outreach:
            return agent.drained_outreach[-1]["id"]
        if agent.outreach_log:
            return agent.outreach_log[-1]["id"]
        return None

    def process_updates(self, agent, updates: list[dict],
                        at: float | None = None) -> list[dict]:
        """Process fetched updates. Returns the records made (also
        appended to inbound_log / refused_log).

        - A /start from an unpaired channel pairs that chat.
        - Anything from a chat other than the paired one is refused
          (its text is not even recorded).
        - Founder text is recorded as an agent input; a dismissal
          phrase is routed to agent.note_outreach_response().
        """
        at = time.time() if at is None else at
        records: list[dict] = []
        for upd in updates:
            uid = upd.get("update_id")
            if isinstance(uid, int):
                self._next_offset = max(self._next_offset or 0, uid + 1)
            msg = upd.get("message") or upd.get("edited_message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            text = msg.get("text") or ""
            if not isinstance(chat_id, int):
                continue
            if text.strip().startswith("/start"):
                if self._pair(chat_id, at):
                    rec = {"kind": "paired", "chat_id": chat_id,
                           "update_id": uid, "at": at, "accepted": True}
                    self.inbound_log.append(rec)
                    records.append(rec)
                else:
                    rec = {"kind": "refused", "reason": "already paired "
                           "to another chat", "chat_id": chat_id,
                           "update_id": uid, "at": at, "accepted": False}
                    self.refused_log.append(rec)
                    records.append(rec)
                continue
            if chat_id != self.paired_chat_id:
                rec = {"kind": "refused", "reason": "chat not on the "
                       "allowlist", "chat_id": chat_id,
                       "update_id": uid, "at": at, "accepted": False}
                self.refused_log.append(rec)
                records.append(rec)
                continue
            rec = {"kind": "message", "chat_id": chat_id,
                   "update_id": uid, "at": at, "accepted": True,
                   "text": text}
            if self._is_dismissal(text):
                rec["kind"] = "dismissal"
                target = self._last_outreach_id(agent)
                rec["outreach_id"] = target
                rec["routed"] = bool(target) and agent.note_outreach_response(
                    target, "dismissed", at=at)
            self.inbound_log.append(rec)
            records.append(rec)
        return records

    def poll_once(self, agent, *, timeout_s: int = 0,
                  at: float | None = None) -> list[dict]:
        """One fetch + process round (the runner's loop body)."""
        return self.process_updates(agent, self.get_updates(
            timeout_s=timeout_s), at=at)
