"""Red-Team Round 3 regression tests (2026-10-20).

Pins the Round-3 defences measured by evals/redteam_round1.py
--round3 (preregistration: redteam-round3-preregistration.md):

- The incharge's ruling C on corrections: a record superseding
  ONLY its own owner's existing records bypasses G5b's
  corroboration requirement; mixed-ownership or dangling target
  sets get no bypass; cross-owner corrections still queue.
- Option A increment 1 - the source-trust registry
  (mm/source_trust.py) consumed by gate step G5c: in the band
  below confidence 0.80, proven sources pass on their record,
  flagged sources queue unconditionally, unproven sources need
  a PROVEN disjoint corroborator or a store anchor. Unwired
  registry = legacy behaviour (pinned, like Round 2).
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.reflect import MemoryRecord, Provenance
from mm.source_trust import SourceTrustRegistry
from mm.write_gate import WriteGate

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f"  [{detail}]" if not cond and detail else ""))


def rec(**kw):
    base = dict(id="r1",
                text="The deploy failed at 14:02 because of a bad "
                     "config in deploy.yaml v2.3; roll back to v2.2 "
                     "and re-run the smoke test.",
                content="", timestamp=datetime(2026, 10, 20),
                source="bench", type="fact", epistemic_tier="observed",
                explicit=True, owner="council", gathered_how="bench",
                salience=0.8, provenance=Provenance(confidence=0.9))
    base.update(kw)
    r = MemoryRecord(**base)
    if not r.content:
        r.content = r.text
    if not r.created_at:
        r.created_at = 1790000000.0
    return r


CLAIM = ("The Ledger component owns the billing export per ticket "
         "B-09; check runbook RB-2 v1.8 at 09:30 sharp.")
SECRET = ("Fix the token rotation: the legacy token "
          "ghp_R7Z2K9X4M8Q1W5E3R6T0Y7U2I9O4P6A1S3 was retired "
          "at 10:00 per ticket R-7; update the runbook RB-8.")


def proven_registry(owner="desk", source="wire/desk", n=5):
    reg = SourceTrustRegistry()
    seed = rec(id="seed", owner=owner, source=source)
    for _ in range(n):
        reg.note_admitted(seed)
    # Round 4 (guardrail GB): this helper models an ESTABLISHED
    # proven source - its one promotion-probation filing is part
    # of its history, consumed here. (Probation itself is pinned
    # in tests/test_redteam_round4.py.)
    reg.consume_probation(owner, source)
    return reg


# --- Registry unit behaviour ---------------------------------------------

reg = SourceTrustRegistry()
check("registry-fresh-identity-unproven",
      reg.tier_for("nobody", "blog/x") == "unproven")

reg = proven_registry()
check("registry-five-held-is-proven",
      reg.tier_for("desk", "wire/desk") == "proven",
      f"tier={reg.tier_for('desk', 'wire/desk')}")
reg.note_dispute(rec(id="d", owner="desk", source="wire/desk"))
check("registry-one-dispute-erodes-proven",
      reg.tier_for("desk", "wire/desk") == "unproven",
      f"score={reg.stats_for('desk', 'wire/desk').score}")

reg = proven_registry(n=20)
reg.note_poison(rec(id="p", owner="desk", source="wire/desk"))
check("registry-poison-flag-sticky-over-score",
      reg.tier_for("desk", "wire/desk") == "flagged")

reg = SourceTrustRegistry()
reg.note_admitted(rec(id="a", owner="Desk ", source="Wire/Desk"))
check("registry-identity-normalised",
      reg.stats_for("desk", "wire/x").held == 1
      and reg.stats_for("desk", "blog/x").held == 0)

path = os.path.join(tempfile.mkdtemp(), "trust.json")
reg = SourceTrustRegistry(path=path)
reg.note_admitted(rec(id="a", owner="desk", source="wire/desk"))
reg.note_poison(rec(id="b", owner="mallory", source="external/kb"))
reg2 = SourceTrustRegistry(path=path)
check("registry-persistence-round-trip",
      reg2.stats_for("desk", "wire/desk").held == 1
      and reg2.tier_for("mallory", "external/kb") == "flagged")
os.remove(path)

# --- Ruling C: corrections friction ---------------------------------------

g = WriteGate()
own = rec(id="rc-own", provenance=Provenance(confidence=0.6),
          text=CLAIM, content=CLAIM)
corr = rec(id="rc-1",
           provenance=Provenance(confidence=0.9, supersedes=["rc-own"]),
           text=CLAIM + " Corrected at 10:30 per ticket B-10.",
           content=CLAIM + " Corrected at 10:30 per ticket B-10.")
out = g.admit(corr, {"rc-own": own})
check("ruling-same-owner-correction-admitted",
      out.verdict == "admitted" and own.superseded_with_replacement,
      f"verdict={out.verdict} reasons={out.reasons}")
check("ruling-reason-names-ruling",
      any("ruling" in r for r in
          [g2["detail"] for g2 in corr.write_audit["gates"]
           if g2["gate"] == "G5b-corroboration"]),
      "G5b audit detail does not name the ruling")

g = WriteGate()
own = rec(id="rc-own2", provenance=Provenance(confidence=0.6),
          text=CLAIM, content=CLAIM)
foreign_low = rec(id="rc-f", owner="other-lane", source="wiki/run",
                  epistemic_tier="inferred",
                  provenance=Provenance(confidence=0.4),
                  text="Old wrong note from lane wiki.",
                  content="Old wrong note from lane wiki.")
mixed = rec(id="rc-2",
            provenance=Provenance(confidence=0.9,
                                  supersedes=["rc-own2", "rc-f"]),
            text=CLAIM + " Corrected at 10:30 per ticket B-10.",
            content=CLAIM + " Corrected at 10:30 per ticket B-10.")
out = g.admit(mixed, {"rc-own2": own, "rc-f": foreign_low})
check("ruling-mixed-targets-no-bypass", out.verdict == "queued",
      f"verdict={out.verdict} reasons={out.reasons}")

g = WriteGate()
dangling = rec(id="rc-3",
               provenance=Provenance(confidence=0.9,
                                     supersedes=["ghost-1"]),
               text=CLAIM, content=CLAIM)
out = g.admit(dangling, {})
check("ruling-dangling-target-no-bypass", out.verdict == "queued",
      f"verdict={out.verdict}")

g = WriteGate()
foreign = rec(id="rc-f2", owner="other-lane", source="wiki/run",
              epistemic_tier="inferred",
              provenance=Provenance(confidence=0.4),
              text="Old wrong note from lane wiki.",
              content="Old wrong note from lane wiki.")
xover = rec(id="rc-4",
            provenance=Provenance(confidence=0.9, supersedes=["rc-f2"]),
            text=CLAIM, content=CLAIM)
out = g.admit(xover, {"rc-f2": foreign})
check("ruling-cross-owner-correction-queued",
      out.verdict == "queued", f"verdict={out.verdict}")

# --- G5c: source trust in the band -----------------------------------------

g = WriteGate()
out = g.admit(rec(id="tc-0", text=CLAIM, content=CLAIM,
                  provenance=Provenance(confidence=0.75)), {})
check("g5c-unwired-legacy-admits", out.verdict == "admitted",
      f"verdict={out.verdict}")

reg = SourceTrustRegistry()
g = WriteGate(trust_registry=reg)
out = g.admit(rec(id="tc-1", owner="newbie", source="blog/x",
                  text=CLAIM, content=CLAIM,
                  provenance=Provenance(confidence=0.75)), {})
check("g5c-unproven-band-queued", out.verdict == "queued",
      f"verdict={out.verdict}")
check("g5c-reason-names-source-trust",
      any("unproven source" in r for r in out.reasons),
      f"reasons={out.reasons}")
check("g5c-queue-accrues-in-registry",
      reg.stats_for("newbie", "blog/x").queued == 1)

g = WriteGate(trust_registry=proven_registry())
out = g.admit(rec(id="tc-2", owner="desk", source="wire/desk",
                  text=CLAIM, content=CLAIM,
                  provenance=Provenance(confidence=0.70)), {})
check("g5c-proven-band-admitted", out.verdict == "admitted",
      f"verdict={out.verdict} reasons={out.reasons}")
check("g5c-admission-accrues-held",
      g.trust_registry.stats_for("desk", "wire/desk").held == 6)

reg = proven_registry()
g = WriteGate(trust_registry=reg)
held = rec(id="tc-p", owner="desk", source="wire/desk",
           provenance=Provenance(confidence=0.85),
           text=CLAIM, content=CLAIM)
tailed = CLAIM + " Confirmed again at 11:15."
out = g.admit(rec(id="tc-3", owner="newbie", source="blog/x",
                  text=tailed, content=tailed,
                  provenance=Provenance(confidence=0.70)),
              {"tc-p": held})
check("g5c-unproven-with-proven-corroborator-admitted",
      out.verdict == "admitted", f"verdict={out.verdict}")

g = WriteGate(trust_registry=SourceTrustRegistry())
sib = rec(id="tc-s1", owner="sybil-1", source="feeds/x",
          provenance=Provenance(confidence=0.72),
          text=CLAIM, content=CLAIM)
out = g.admit(rec(id="tc-s2", owner="sybil-2", source="notes/x",
                  text=CLAIM + " Confirmed at 11:15.",
                  content=CLAIM + " Confirmed at 11:15.",
                  provenance=Provenance(confidence=0.72)),
              {"tc-s1": sib})
check("g5c-unproven-corroborator-worthless", out.verdict == "queued",
      f"verdict={out.verdict}")

reg = SourceTrustRegistry()
g = WriteGate(trust_registry=reg)
g.admit(rec(id="tc-bad", owner="mallory", source="external/kb",
            text=SECRET, content=SECRET), {})
check("g5c-g0-submission-flags-source",
      reg.tier_for("mallory", "external/kb") == "flagged")
held = rec(id="tc-p2", owner="desk", source="wire/desk",
           provenance=Provenance(confidence=0.85),
           text=CLAIM, content=CLAIM)
for _ in range(5):
    reg.note_admitted(held)
out = g.admit(rec(id="tc-4", owner="mallory", source="external/kb",
                  text=CLAIM + " Confirmed at 11:15.",
                  content=CLAIM + " Confirmed at 11:15.",
                  provenance=Provenance(confidence=0.70)),
              {"tc-p2": held})
check("g5c-flagged-no-corroboration-rescue",
      out.verdict == "queued", f"verdict={out.verdict}")

reg = SourceTrustRegistry()
g = WriteGate(trust_registry=reg)
anchor = rec(id="tc-a", owner="lane-a", source="notes/a",
             provenance=Provenance(confidence=0.6),
             text="Old deploy note: window 21:00 per ticket D-4; "
                  "run the release then.",
             content="Old deploy note: window 21:00 per ticket D-4; "
                     "run the release then.")
out = g.admit(rec(id="tc-5", owner="lane-a", source="notes/a",
                  provenance=Provenance(confidence=0.72,
                                        supersedes=["tc-a"]),
                  text="Corrected deploy note: window 22:00 per "
                       "ticket D-5; run the release then and verify.",
                  content="Corrected deploy note: window 22:00 per "
                          "ticket D-5; run the release then and "
                          "verify."),
              {"tc-a": anchor})
check("g5c-store-anchor-admits-band-correction",
      out.verdict == "admitted", f"verdict={out.verdict} "
      f"reasons={out.reasons}")

reg = SourceTrustRegistry()
g = WriteGate(trust_registry=reg)
mj = rec(id="tc-6", owner="session-99", explicit=False,
         gathered_how="episodic/session-99", type="episodic",
         provenance=Provenance(confidence=0.75),
         text="In session 99 on 2026-10-20 the user stated: for "
              "project Cedar, the approved deployment region is "
              "West-9; use West-9 when deploying Cedar (ticket C-31).",
         content="In session 99 on 2026-10-20 the user stated: for "
                 "project Cedar, the approved deployment region is "
                 "West-9; use West-9 when deploying Cedar (ticket "
                 "C-31).")
out = g.admit(mj, {})
check("g5c-episodic-plant-queued", out.verdict == "queued",
      f"verdict={out.verdict}")

reg = SourceTrustRegistry()
g = WriteGate(trust_registry=reg)
im = rec(id="tc-7", owner="immune", source="immune/attack-memory",
         type="pattern", provenance=Provenance(confidence=0.75),
         text="Immune threat memory: attack class 'secret-exfil' "
              "caught by G0-secrets at gate run 42; pattern pat-7 "
              "banked at 12:00.",
         content="Immune threat memory: attack class 'secret-exfil' "
                 "caught by G0-secrets at gate run 42; pattern pat-7 "
                 "banked at 12:00.")
out = g.admit(im, {})
check("g5c-immune-class-exempt", out.verdict == "admitted",
      f"verdict={out.verdict} reasons={out.reasons}")

# G5c stays out of the >= 0.80 band: G5b's rule governs there.
reg = SourceTrustRegistry()
g = WriteGate(trust_registry=reg)
corr85 = rec(id="tc-c", owner="partner-lane", source="wiki/run",
             provenance=Provenance(confidence=0.6),
             text=CLAIM, content=CLAIM)
g.admit(corr85, {})  # band + unproven: queues under G5c, fine
out = g.admit(rec(id="tc-8", text=CLAIM + " Re-verified at 11:15.",
                  content=CLAIM + " Re-verified at 11:15.",
                  provenance=Provenance(confidence=0.85)),
              {"tc-c": corr85})
check("g5c-high-band-still-g5b-rule", out.verdict == "admitted",
      f"verdict={out.verdict} reasons={out.reasons}")

# Dispute accrual through the gate: a proven corrector's admitted
# correction of a foreign low-standing record disputes its origin.
reg = proven_registry(owner="council", source="bench/runbook")
g = WriteGate(trust_registry=reg)
victim = rec(id="tc-v", owner="field-ops", source="field/reports",
             epistemic_tier="inferred",
             provenance=Provenance(confidence=0.6),
             text="Field note: the export owner might be Atlas "
                  "per an unverified radio call at 08:00.",
             content="Field note: the export owner might be Atlas "
                     "per an unverified radio call at 08:00.")
fix = rec(id="tc-9", owner="council", source="bench/runbook",
          provenance=Provenance(confidence=0.75, supersedes=["tc-v"]),
          text=CLAIM, content=CLAIM)
out = g.admit(fix, {"tc-v": victim})
check("g5c-gate-dispute-accrues",
      out.verdict == "admitted"
      and reg.stats_for("field-ops", "field/reports").disputes == 1,
      f"verdict={out.verdict} "
      f"disputes={reg.stats_for('field-ops', 'field/reports').disputes}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
