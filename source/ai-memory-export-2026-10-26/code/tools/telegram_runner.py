"""Telegram long-poll runner for the MemoryAgent (small on purpose).

Wires mm/telegram_channel.py to a live agent: long-polls the bot
for founder messages (pairing, inputs, dismissals), releases any
quiet-hours-held outreach when the proactive window opens, and
drains send-decided outbox entries to the paired chat.

The bot token comes ONLY from the TELEGRAM_BOT_TOKEN environment
variable (injected by the secure connector / service environment).
The runner fails closed at startup when it is missing. It holds no
credentials of its own and writes none anywhere.

Run:
    TELEGRAM_BOT_TOKEN=... python3 tools/telegram_runner.py \
        [--db data/memory.db] [--poll-timeout 25]

Pairing file: <db directory>/telegram-pairing.json (chat_id only).
First run: start the runner, then send /start to the bot from the
founder's Telegram - that chat is paired and the allowlist locks.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.agent import MemoryAgent
from mm.storage import SQLiteStore
from mm.telegram_channel import TelegramChannel, MissingTokenError


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/memory.db",
                    help="SQLite memory store (default data/memory.db)")
    ap.add_argument("--poll-timeout", type=int, default=25,
                    help="getUpdates long-poll seconds (default 25)")
    args = ap.parse_args()

    if not os.environ.get("TELEGRAM_BOT_TOKEN", "").strip():
        print("TELEGRAM_BOT_TOKEN is not set; refusing to start "
              "(fail closed).", file=sys.stderr)
        return 2

    store = SQLiteStore(args.db)
    agent = MemoryAgent(store)
    pairing = os.path.join(os.path.dirname(os.path.abspath(args.db)),
                           "telegram-pairing.json")
    channel = TelegramChannel(pairing)
    print(f"telegram runner up; paired={channel.is_paired} "
          f"db={args.db}", flush=True)

    while True:
        try:
            channel.poll_once(agent, timeout_s=args.poll_timeout)
            agent.release_held()
            if channel.is_paired and agent.outbox:
                sent = channel.drain(agent)
                if sent:
                    print(f"drained {len(sent)} outreach item(s)",
                          flush=True)
        except MissingTokenError:
            raise
        except Exception as exc:  # keep polling through API hiccups
            print(f"poll error: {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
