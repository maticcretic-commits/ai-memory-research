"""Telegram channel tests: the standalone sender for the comms
layer (founder order 2026-10-25). The channel delivers ONLY what
MemoryAgent.propose_outreach() has already decided; the policy
gate itself is tested in tests/test_comms_layer.py.

Covered here:
- token comes ONLY from TELEGRAM_BOT_TOKEN; missing token fails
  closed (no send, no drain, outbox untouched);
- pairing: the first /start locks the allowlist to that chat_id,
  persists to disk, and every later chat is refused (a second
  /start included); refused chats' text is never recorded;
- outbound sends to a non-paired chat are refused;
- drain sends exactly the send-decided outbox entries (message +
  why-line), moves them through the agent's drain bookkeeping,
  and leaves quiet-hours-held entries held;
- a partial send failure drains only what was truly delivered;
- founder dismissal words route to note_outreach_response().

Everything runs against a mocked HTTP layer: no network, no real
token (the token used here is a literal test string injected via
the environment, exactly the production access path).

Run:  python3 tests/test_telegram_channel.py   (from the repo root)
"""

import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from mm.agent import MemoryAgent
from mm.storage import SQLiteStore
from mm.telegram_channel import (TelegramChannel, TelegramChannelError,
                                 MissingTokenError, TOKEN_ENV_VAR)

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


def ts(y, mo, d, h, mi):
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime(y, mo, d, h, mi, tzinfo=ist).timestamp()


def fresh_agent():
    store = SQLiteStore(tempfile.mktemp(suffix=".db"))
    cal = os.path.join(tempfile.mkdtemp(), "calibration.json")
    return MemoryAgent(store, calibration_path=cal)


NOON = ts(2026, 10, 20, 12, 0)        # in the proactive window
NIGHT = ts(2026, 10, 20, 23, 0)       # quiet hours
HI = dict(severity=0.9, confidence=0.9, novelty=0.9)   # score 0.729
FOUNDER = 111
STRANGER = 999


class FakeHTTP:
    """Mocked Bot API transport: (url, payload, timeout) -> dict."""

    def __init__(self, updates=None):
        self.calls = []
        self.updates = updates or []
        self.send_count = 0
        self.fail_send_at = None       # 1-based send attempt to fail

    def __call__(self, url, payload, timeout):
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, payload))
        if method == "getUpdates":
            return {"ok": True, "result": list(self.updates)}
        if method == "sendMessage":
            self.send_count += 1
            if self.fail_send_at == self.send_count:
                return {"ok": False, "description": "injected failure"}
            return {"ok": True, "result": {"message_id": self.send_count}}
        return {"ok": True, "result": True}

    def payloads(self, method):
        return [p for m, p in self.calls if m == method]


def upd(uid, chat_id, text):
    return {"update_id": uid,
            "message": {"chat": {"id": chat_id}, "text": text}}


def fresh_channel(fake, pair=False, agent=None):
    path = tempfile.mktemp(suffix=".json")
    ch = TelegramChannel(path, http_post=fake)
    if pair:
        ch.process_updates(agent or fresh_agent(),
                           [upd(1, FOUNDER, "/start")], at=NOON)
    return ch


os.environ[TOKEN_ENV_VAR] = "unit-test-token-not-real"

# -- missing token fails closed ----------------------------------------------

agent = fresh_agent()
fake = FakeHTTP()
ch = fresh_channel(fake, pair=True, agent=agent)
e = agent.propose_outreach("briefing", "Queued briefing", why="scheduled",
                           at=NOON, **HI)
assert e["decision"] == "send"
saved = os.environ.pop(TOKEN_ENV_VAR)
try:
    try:
        ch.api_call("getMe")
        raised = None
    except MissingTokenError as exc:
        raised = exc
    check("tg-missing-token-api-fails-closed", raised is not None)
    try:
        ch.drain(agent, at=NOON)
        raised = None
    except MissingTokenError as exc:
        raised = exc
    check("tg-missing-token-drain-fails-closed", raised is not None
          and len(agent.outbox) == 1 and fake.send_count == 0,
          f"outbox={len(agent.outbox)} sends={fake.send_count}")
finally:
    os.environ[TOKEN_ENV_VAR] = saved

# -- pairing: first /start locks, persists, everyone else refused ------------

fake = FakeHTTP()
ch = fresh_channel(fake)
check("tg-starts-unpaired", not ch.is_paired and ch.paired_chat_id is None)
recs = ch.process_updates(fresh_agent(), [upd(1, FOUNDER, "/start")], at=NOON)
check("tg-first-start-pairs", ch.paired_chat_id == FOUNDER
      and recs[0]["kind"] == "paired", f"recs={recs}")
ch2 = TelegramChannel(ch.pairing_path, http_post=fake)
check("tg-pairing-persists-to-disk", ch2.paired_chat_id == FOUNDER)
recs = ch.process_updates(fresh_agent(), [upd(2, STRANGER, "/start")], at=NOON)
check("tg-second-start-refused", ch.paired_chat_id == FOUNDER
      and recs[0]["kind"] == "refused", f"recs={recs}")
recs = ch.process_updates(fresh_agent(),
                          [upd(3, STRANGER, "let me in")], at=NOON)
check("tg-stranger-message-refused-unrecorded",
      recs[0]["kind"] == "refused" and "text" not in recs[0]
      and all(r.get("text") != "let me in" for r in ch.inbound_log),
      f"recs={recs}")
recs = ch.process_updates(fresh_agent(),
                          [upd(4, FOUNDER, "hello memory")], at=NOON)
check("tg-founder-message-recorded", recs[0]["kind"] == "message"
      and recs[0]["text"] == "hello memory", f"recs={recs}")

# -- outbound allowlist --------------------------------------------------------

try:
    ch.send_message(STRANGER, "hi")
    refused = False
except TelegramChannelError:
    refused = True
check("tg-send-to-stranger-refused", refused and fake.send_count == 0)
sent = ch.send_message(FOUNDER, "hello founder")
check("tg-send-to-founder-ok", sent.get("message_id") == 1
      and fake.payloads("sendMessage")[0]["chat_id"] == FOUNDER)

# -- drain: only send-decided, held stays held ---------------------------------

agent = fresh_agent()
fake = FakeHTTP()
ch = fresh_channel(fake, pair=True, agent=agent)
e_send = agent.propose_outreach("briefing", "Midday briefing",
                                why="scheduled digest", at=NOON, **HI)
e_held = agent.propose_outreach("briefing", "Late-night briefing",
                                why="scheduled digest", at=NIGHT, **HI)
assert e_send["decision"] == "send" and e_held["decision"] == "defer"
drained = ch.drain(agent, at=NOON)
payloads = fake.payloads("sendMessage")
check("tg-drain-sends-only-send-decided", drained == [e_send]
      and len(payloads) == 1 and payloads[0]["chat_id"] == FOUNDER
      and "Midday briefing" in payloads[0]["text"]
      and "Why: scheduled digest" in payloads[0]["text"],
      f"drained={drained} payloads={payloads}")
check("tg-drain-bookkeeping-and-held-untouched",
      agent.outbox == [] and agent.drained_outreach == [e_send]
      and e_send.get("delivered_via") == "telegram"
      and agent.held_outreach == [e_held],
      f"outbox={agent.outbox} held={agent.held_outreach}")
check("tg-drain-empty-is-noop", ch.drain(agent, at=NOON) == []
      and fake.send_count == 1)

# -- drain: unpaired fails closed, partial failure drains only delivered ------

agent = fresh_agent()
fake = FakeHTTP()
ch_unpaired = fresh_channel(fake)
e = agent.propose_outreach("briefing", "Queued", why="scheduled",
                           at=NOON, **HI)
try:
    ch_unpaired.drain(agent, at=NOON)
    raised = False
except TelegramChannelError:
    raised = True
check("tg-drain-unpaired-fails-closed", raised
      and len(agent.outbox) == 1 and fake.send_count == 0)

agent = fresh_agent()
fake = FakeHTTP()
fake.fail_send_at = 2
ch = fresh_channel(fake, pair=True, agent=agent)
a = agent.propose_outreach("briefing", "First", why="one", at=NOON, **HI)
b = agent.propose_outreach("briefing", "Second", why="two", at=NOON, **HI)
drained = ch.drain(agent, at=NOON)
check("tg-partial-drain-only-delivered", drained == [a]
      and agent.drained_outreach == [a] and agent.outbox == [b],
      f"drained={drained} outbox={agent.outbox}")

# -- inbound dismissals train the gate ------------------------------------------

agent = fresh_agent()
fake = FakeHTTP()
ch = fresh_channel(fake, pair=True, agent=agent)
e = agent.propose_outreach("briefing", "Morning briefing",
                           why="scheduled digest", at=NOON, **HI)
ch.drain(agent, at=NOON)
recs = ch.process_updates(agent, [upd(9, FOUNDER, "not now")], at=NOON)
check("tg-dismissal-routed", recs[0]["kind"] == "dismissal"
      and recs[0]["routed"] is True
      and recs[0]["outreach_id"] == e["id"]
      and e.get("response") == "dismissed", f"recs={recs}")
agent2 = fresh_agent()
recs = ch.process_updates(agent2, [upd(10, FOUNDER, "stop")], at=NOON)
check("tg-dismissal-no-target-not-faked", recs[0]["kind"] == "dismissal"
      and recs[0]["routed"] is False, f"recs={recs}")

# -- getUpdates offset advances ---------------------------------------------------

fake = FakeHTTP(updates=[upd(41, FOUNDER, "/start")])
ch = TelegramChannel(tempfile.mktemp(suffix=".json"), http_post=fake)
ch.poll_once(fresh_agent(), at=NOON)
ch.get_updates()
offs = [p.get("offset") for p in fake.payloads("getUpdates")]
check("tg-offset-advances", offs[-1] == 42, f"offsets={offs}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
