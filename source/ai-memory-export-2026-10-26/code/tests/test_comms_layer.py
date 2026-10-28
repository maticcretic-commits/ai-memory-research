"""Comms-layer tests: anytime two-way communication policy engine
(research program addition, majority verdict 2026-10-20: C1=C,
C2/C3 pass 5-0).

The engine DECIDES; it never sends. A "send" decision lands in the
agent's outbox for Muse's existing live channels (this chat +
WhatsApp one-on-one). No new accounts, no sending code - the
standalone channel is spec-only behind nitesh's own bot registration
(hard gate). Spec: hidden_files/implementation/comms-layer-spec.md.

Rules under test (his standing parameters + lane rules):
- four trigger classes only; interrupt classes need a concrete
  reference (D-K1); every outreach carries a why-line (D-K2);
- relevance gate: score = severity x confidence x novelty >= 0.25;
- quiet hours 21:30-09:00 IST defer everything except emergency;
- daily interrupt budget 3 (D-K1), dropping to 1 after 3 dismissals;
- dismissal back-off: 1 dismissal deprioritizes a class for 7 days,
  2 inside 30 days pause it until re-enabled (D-K2).

Run:  python3 tests/test_comms_layer.py   (from the repo root)
"""

import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, ".")

from mm.agent import MemoryAgent
from mm.storage import SQLiteStore

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


def ts(y, mo, d, h, mi):
    """Epoch seconds for an IST wall-clock time (IST = UTC+5:30)."""
    from datetime import timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime(y, mo, d, h, mi, tzinfo=ist).timestamp()


def fresh_agent():
    store = SQLiteStore(tempfile.mktemp(suffix=".db"))
    cal = os.path.join(tempfile.mkdtemp(), "calibration.json")
    return MemoryAgent(store, calibration_path=cal)


NOON = ts(2026, 10, 20, 12, 0)        # in the proactive window
NIGHT = ts(2026, 10, 20, 23, 0)       # quiet hours
MORNING = ts(2026, 10, 21, 9, 30)     # next window
HI = dict(severity=0.9, confidence=0.9, novelty=0.9)   # score 0.729

agent = fresh_agent()

# -- the gate: triggers, why-line, reference, relevance ---------------------

e = agent.propose_outreach("hard_gate_vote", "Vote needed: publish?",
                           why="decision record d-7 hit the rights gate",
                           reference="d-7", at=NOON, **HI)
check("comms-send-in-window", e["decision"] == "send"
      and e["channels"] == ["claude-chat"] and agent.outbox[-1] is e,
      f"decision={e['decision']}")
e = agent.propose_outreach("opportunity", "Idea: fold the sweep",
                           why="", reference="idea-3319", at=NOON, **HI)
check("comms-no-why-suppressed", e["decision"] == "suppress"
      and "why-line" in e["reasons"][0], f"reasons={e['reasons']}")
e = agent.propose_outreach("opportunity", "Idea: fold the sweep",
                           why="corpus fold is queued", at=NOON, **HI)
check("comms-no-reference-suppressed", e["decision"] == "suppress"
      and "reference" in e["reasons"][0], f"reasons={e['reasons']}")
e = agent.propose_outreach("chatter", "just checking in",
                           why="felt like it", at=NOON, **HI)
check("comms-unknown-trigger-suppressed", e["decision"] == "suppress",
      f"decision={e['decision']}")
e = agent.propose_outreach("opportunity", "Weak maybe-item",
                           why="low value signal", reference="idea-x",
                           severity=0.2, confidence=0.2, novelty=0.2,
                           at=NOON)
check("comms-low-relevance-suppressed", e["decision"] == "suppress"
      and "below threshold" in e["reasons"][0],
      f"reasons={e['reasons']}")

# -- quiet hours: defer routine, emergency speaks ---------------------------

e = agent.propose_outreach("briefing", "Evening briefing",
                           why="hourly partner briefing", at=NIGHT, **HI)
check("comms-quiet-defers", e["decision"] == "defer"
      and agent.held_outreach[-1] is e, f"decision={e['decision']}")
e = agent.propose_outreach("sentinel_alert", "Poison burst on the gate",
                           why="sentinel precision dropped",
                           reference="sentinel-3", urgency="emergency",
                           at=NIGHT, **HI)
check("comms-emergency-bypasses-quiet", e["decision"] == "send"
      and "whatsapp-1to1" in e["channels"], f"decision={e['decision']}")
rel = agent.release_held(at=NIGHT)
check("comms-release-needs-window", rel == [], f"released={rel}")
rel = agent.release_held(at=MORNING)
check("comms-release-at-open", rel and agent.outbox[-1]["trigger"]
      == "briefing", f"released={rel}")

# -- daily budget: 3 interrupts, briefings exempt ----------------------------

agent2 = fresh_agent()
for i in range(3):
    e = agent2.propose_outreach("sentinel_alert", f"Alert {i}",
                                why="sentinel fired", reference=f"s-{i}",
                                at=NOON, **HI)
    assert e["decision"] == "send", e
e = agent2.propose_outreach("sentinel_alert", "Alert 4",
                            why="sentinel fired", reference="s-4",
                            at=NOON, **HI)
check("comms-budget-cap", e["decision"] == "suppress"
      and "budget" in e["reasons"][0], f"reasons={e['reasons']}")
e = agent2.propose_outreach("briefing", "Midday briefing",
                            why="scheduled", at=NOON, **HI)
check("comms-briefing-exempt-from-budget", e["decision"] == "send",
      f"decision={e['decision']}")

# -- dismissal back-off (D-K2) ------------------------------------------------

agent3 = fresh_agent()
e1 = agent3.propose_outreach("opportunity", "Opp 1", why="signal",
                             reference="o-1", at=NOON, **HI)
check("comms-backoff-setup", e1["decision"] == "send", e1["decision"])
check("comms-response-unknown-id",
      not agent3.note_outreach_response("out-9999", "dismissed", at=NOON),
      "unknown id accepted")
agent3.note_outreach_response(e1["id"], "dismissed", at=NOON)
e = agent3.propose_outreach("opportunity", "Borderline opp",
                            why="weak signal", reference="o-2",
                            severity=0.6, confidence=0.5, novelty=1.0,
                            at=NOON)
check("comms-one-dismissal-deprioritizes", e["decision"] == "suppress"
      and "below threshold" in e["reasons"][0],
      f"decision={e['decision']} reasons={e['reasons']}")
e2 = agent3.propose_outreach("opportunity", "Opp 2", why="signal",
                             reference="o-3", at=NOON, **HI)
agent3.note_outreach_response(e2["id"], "dismissed", at=NOON)
e = agent3.propose_outreach("opportunity", "Opp 3", why="signal",
                            reference="o-4", at=NOON, **HI)
check("comms-two-dismissals-pause", e["decision"] == "suppress"
      and "paused" in e["reasons"][0], f"reasons={e['reasons']}")
agent3.reenable_outreach_class("opportunity")
e = agent3.propose_outreach("opportunity", "Opp 4", why="signal",
                            reference="o-5", at=NOON, **HI)
check("comms-reenable-restores", e["decision"] == "send",
      f"decision={e['decision']}")

# -- 3 dismissals across classes drop the daily budget to 1 -------------------

agent4 = fresh_agent()
ids = []
for trig, ref in (("sentinel_alert", "s-1"), ("opportunity", "o-1"),
                  ("hard_gate_vote", "d-1")):
    e = agent4.propose_outreach(trig, "Item", why="signal",
                                reference=ref, at=NOON, **HI)
    ids.append(e["id"])
for oid in ids:
    agent4.note_outreach_response(oid, "dismissed", at=NOON)
day2 = ts(2026, 10, 21, 12, 0)
e = agent4.propose_outreach("sentinel_alert", "Next-day alert",
                            why="sentinel fired", reference="s-9",
                            at=day2, **HI)
first = e["decision"]
e = agent4.propose_outreach("hard_gate_vote", "Next-day vote",
                            why="gate hit", reference="d-9",
                            at=day2, **HI)
check("comms-budget-drops-to-1", first == "send"
      and e["decision"] == "suppress" and "budget" in e["reasons"][0],
      f"first={first} second={e['decision']} {e['reasons']}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
