"""Instant-reply runner tests (founder order 2026-10-26: instant
reply is top priority). The runner answers the founder's Telegram
messages through mm.telegram_channel (token only from the
TELEGRAM_BOT_TOKEN environment variable - under systemd it is
loaded from the founder's locked EnvironmentFile) and generates
replies through the OmniRoute model route.

Covered here:
- startup fails closed when the helper cannot reach Telegram with
  a working vault credential (no poll, no send, no model call);
- only the paired chat is answered; a stranger is refused and his
  text is recorded nowhere (not in the queue, not in any state);
- a founder message gets exactly one reply, the persisted offset
  advances, and a redelivered update is not answered twice;
- on model failure the founder gets the holding reply at once and
  his message is queued; a later retry delivers the real answer;
- dismissal phrases route to note_outreach_response() and get no
  model reply, as in the channel tests;
- the bot's own messages are ignored (no reply loops);
- replies are capped at 1200 characters;
- quiet hours do not block replies to founder-initiated messages;
- a first /start pairs the chat and locks the allowlist.

Everything runs against fakes: no network, no helper subprocess,
no model call, no credential of any kind.

Run:  python3 tests/test_telegram_instant.py   (from the repo root)
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from mm.agent import MemoryAgent
from mm.storage import SQLiteStore
from mm.telegram_channel import TelegramChannel, TOKEN_ENV_VAR
from tools.telegram_instant import (EnvChannelClient, HelperError,
                                    HOLDING_REPLY, InstantReplier,
                                    ModelError, REPLY_CAP,
                                    strip_model_output)

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


def ts(y, mo, d, h, mi):
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime(y, mo, d, h, mi, tzinfo=ist).timestamp()


NOON = ts(2026, 10, 20, 12, 0)
NIGHT = ts(2026, 10, 20, 23, 30)      # inside quiet hours
FOUNDER = 111
STRANGER = 999
BOT_ID = 555000


class FakeHelper:
    """Connector-helper stand-in: same contract, no network."""

    def __init__(self, fail_me=False):
        self.fail_me = fail_me
        self.sends = []               # [(chat_id, text)]
        self.updates_calls = 0

    def get_me(self):
        if self.fail_me:
            raise HelperError("helper failed: no credential")
        return {"id": BOT_ID, "username": "test_memory_bot",
                "is_bot": True}

    def get_updates(self, offset, timeout_s=0):
        self.updates_calls += 1
        return []

    def send(self, chat_id, text):
        self.sends.append((chat_id, text))
        return {"message_id": len(self.sends)}


class FakeModel:
    def __init__(self, mode="ok", text="I am well, and listening."):
        self.mode = mode
        self.text = text
        self.prompts = []

    def reply(self, prompt):
        self.prompts.append(prompt)
        if self.mode == "fail":
            raise ModelError("injected route failure")
        if self.mode == "long":
            return "x" * 2000
        return self.text


def upd(uid, chat_id, text, from_id=None):
    return {"update_id": uid,
            "message": {"chat": {"id": chat_id}, "text": text,
                        "from": {"id": from_id if from_id is not None
                                 else chat_id}}}


def fresh_replier(helper=None, model=None, agent=None, paired=True,
                  now=None):
    d = tempfile.mkdtemp()
    paths = {"pairing": os.path.join(d, "telegram-pairing.json"),
             "offset": os.path.join(d, "telegram-offset.json"),
             "queue": os.path.join(d, "telegram-retry-queue.json"),
             "corpus": os.path.join(d, "BEST-IDEAS.md")}
    if paired:
        with open(paths["pairing"], "w", encoding="utf-8") as f:
            json.dump({"chat_id": FOUNDER, "paired_at": NOON,
                       "channel": "telegram"}, f)
    with open(paths["corpus"], "w", encoding="utf-8") as f:
        f.write("### 4001\nolder\n### 4014\nnewest\n")
    r = InstantReplier(helper=helper or FakeHelper(),
                       model=model or FakeModel(),
                       pairing_path=paths["pairing"],
                       offset_path=paths["offset"],
                       queue_path=paths["queue"],
                       corpus_path=paths["corpus"],
                       agent=agent, now=now or (lambda: NOON))
    r.startup_check()
    return r, paths


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# -- startup fails closed without a working credential ------------------------

helper = FakeHelper(fail_me=True)
model = FakeModel()
d = tempfile.mkdtemp()
r = InstantReplier(helper=helper, model=model,
                   pairing_path=os.path.join(d, "p.json"),
                   offset_path=os.path.join(d, "o.json"),
                   queue_path=os.path.join(d, "q.json"),
                   corpus_path=None)
try:
    r.startup_check()
    raised = None
except HelperError as exc:
    raised = exc
check("instant-startup-fails-closed-no-credential", raised is not None
      and helper.sends == [] and model.prompts == []
      and helper.updates_calls == 0)

# -- allowlist: stranger refused, text recorded nowhere ------------------------

helper, model = FakeHelper(), FakeModel()
r, paths = fresh_replier(helper, model)
act = r.process_update(upd(10, STRANGER, "let me in"))
queue_text = read(paths["queue"]) if os.path.exists(paths["queue"]) else ""
check("instant-stranger-refused-unrecorded",
      act["kind"] == "refused" and "text" not in act
      and helper.sends == [] and model.prompts == []
      and "let me in" not in queue_text
      and "let me in" not in read(paths["offset"]),
      f"act={act}")

# -- founder message: one reply, offset persists, prompt carries corpus tail ---

helper, model = FakeHelper(), FakeModel()
r, paths = fresh_replier(helper, model)
act = r.process_update(upd(20, FOUNDER, "hello memory"))
state = json.loads(read(paths["offset"]))
check("instant-founder-gets-one-reply",
      act["kind"] == "reply"
      and helper.sends == [(FOUNDER, "I am well, and listening.")]
      and state["next_offset"] == 21
      and "4014" in model.prompts[0],
      f"act={act} sends={helper.sends} state={state}")
act = r.process_update(upd(20, FOUNDER, "hello memory"))
check("instant-redelivery-not-answered-twice",
      act["kind"] == "duplicate" and len(helper.sends) == 1,
      f"act={act}")
r_restart = InstantReplier(helper=helper, model=model,
                           pairing_path=paths["pairing"],
                           offset_path=paths["offset"],
                           queue_path=paths["queue"],
                           corpus_path=paths["corpus"],
                           now=lambda: NOON)
check("instant-offset-survives-restart", r_restart.next_offset == 21
      and r_restart.paired_chat_id == FOUNDER)

# -- model failure: holding reply at once, queued, retry delivers --------------

helper = FakeHelper()
model = FakeModel(mode="fail")
r, paths = fresh_replier(helper, model)
act = r.process_update(upd(30, FOUNDER, "what do you know?"))
queue = json.loads(read(paths["queue"]))
check("instant-model-failure-holding-and-queue",
      act["kind"] == "holding"
      and helper.sends == [(FOUNDER, HOLDING_REPLY)]
      and len(queue) == 1 and queue[0]["text"] == "what do you know?",
      f"act={act} sends={helper.sends} queue={queue}")
model.mode = "ok"
model.text = "I hold 4,014 numbered ideas."
actions = r.retry_pending()
check("instant-retry-delivers-real-answer",
      actions and actions[0]["kind"] == "retry-replied"
      and helper.sends[-1] == (FOUNDER, "I hold 4,014 numbered ideas.")
      and json.loads(read(paths["queue"])) == [],
      f"actions={actions} sends={helper.sends}")

# -- dismissal routes to the agent, no model reply ------------------------------

store = SQLiteStore(tempfile.mktemp(suffix=".db"))
cal = os.path.join(tempfile.mkdtemp(), "calibration.json")
agent = MemoryAgent(store, calibration_path=cal)
e = agent.propose_outreach("briefing", "Morning briefing",
                           why="scheduled digest", at=NOON,
                           severity=0.9, confidence=0.9, novelty=0.9)
assert e["decision"] == "send"
helper, model = FakeHelper(), FakeModel()
r, paths = fresh_replier(helper, model, agent=agent)
act = r.process_update(upd(40, FOUNDER, "not now"))
check("instant-dismissal-routed-no-reply",
      act["kind"] == "dismissal" and act["routed"] is True
      and e.get("response") == "dismissed"
      and helper.sends == [] and model.prompts == [],
      f"act={act}")

# -- own messages ignored, reply cap, quiet hours do not block -------------------

helper, model = FakeHelper(), FakeModel()
r, paths = fresh_replier(helper, model)
act = r.process_update(upd(50, FOUNDER, "echo?", from_id=BOT_ID))
check("instant-own-message-ignored", act["kind"] == "ignored-own"
      and helper.sends == [] and model.prompts == [], f"act={act}")

helper = FakeHelper()
model = FakeModel(mode="long")
r, paths = fresh_replier(helper, model)
r.process_update(upd(60, FOUNDER, "tell me everything"))
check("instant-reply-length-capped",
      len(helper.sends) == 1 and len(helper.sends[0][1]) <= REPLY_CAP,
      f"len={len(helper.sends[0][1]) if helper.sends else None}")

helper, model = FakeHelper(), FakeModel()
r, paths = fresh_replier(helper, model, now=lambda: NIGHT)
act = r.process_update(upd(70, FOUNDER, "are you awake?"))
check("instant-quiet-hours-do-not-block-founder",
      act["kind"] == "reply" and len(helper.sends) == 1, f"act={act}")

# -- first /start pairs and locks -------------------------------------------------

helper, model = FakeHelper(), FakeModel()
r, paths = fresh_replier(helper, model, paired=False)
act = r.process_update(upd(80, 777, "/start"))
pairing = json.loads(read(paths["pairing"]))
act2 = r.process_update(upd(81, STRANGER, "/start"))
check("instant-first-start-pairs-and-locks",
      act["kind"] == "paired" and pairing["chat_id"] == 777
      and len(helper.sends) == 1 and helper.sends[0][0] == 777
      and act2["kind"] == "refused",
      f"act={act} act2={act2} pairing={pairing}")

# -- env-backed transport: fails closed with no token, works with one ---------


class FakeTransport:
    """(url, payload, timeout) -> dict, as TelegramChannel expects."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, payload, timeout):
        method = url.rsplit("/", 1)[-1]
        self.calls.append(method)
        if method == "getMe":
            return {"ok": True, "result": {"id": BOT_ID,
                                           "username": "test_bot"}}
        if method == "getUpdates":
            return {"ok": True, "result": []}
        if method == "sendMessage":
            return {"ok": True, "result": {"message_id": 1}}
        return {"ok": True, "result": True}


d = tempfile.mkdtemp()
pair_path = os.path.join(d, "telegram-pairing.json")
with open(pair_path, "w", encoding="utf-8") as f:
    json.dump({"chat_id": FOUNDER, "paired_at": NOON,
               "channel": "telegram"}, f)
transport = FakeTransport()
client = EnvChannelClient(TelegramChannel(pair_path,
                                          http_post=transport))
saved_env = os.environ.pop(TOKEN_ENV_VAR, None)
try:
    try:
        client.get_me()
        raised = None
    except HelperError as exc:
        raised = exc
    check("instant-env-transport-fails-closed-no-token",
          raised is not None and transport.calls == [],
          f"calls={transport.calls}")
    os.environ[TOKEN_ENV_VAR] = "unit-test-token-not-real"
    me = client.get_me()
    sent = client.send(FOUNDER, "hello founder")
    check("instant-env-transport-works-with-token",
          me.get("username") == "test_bot"
          and sent.get("message_id") == 1
          and transport.calls == ["getMe", "sendMessage"],
          f"me={me} calls={transport.calls}")
finally:
    if saved_env is None:
        os.environ.pop(TOKEN_ENV_VAR, None)
    else:
        os.environ[TOKEN_ENV_VAR] = saved_env

# -- model output noise stripping (qa_client marker set) -------------------------

noisy = ("Loaded env from /home/hatch/.omniroute/.env\n"
         "[omniroute] loading environment\n"
         "I am well, and listening.\n"
         "Usage: omniroute chat [options]")
clean = strip_model_output(noisy)
check("instant-model-output-noise-stripped",
      clean == "I am well, and listening.", f"clean={clean!r}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
