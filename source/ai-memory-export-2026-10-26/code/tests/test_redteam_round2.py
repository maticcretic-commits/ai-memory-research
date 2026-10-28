"""Red-Team Round 2 regression tests (2026-10-20).

Pins the Round-2 defences measured by evals/redteam_round1.py
--round2 (preregistration: redteam-round2-preregistration.md):

- G5b lone-source corroboration (Option C, partner vote): a claim
  at tier observed/derived with confidence >= 0.80 lands only with
  a corroborating record from a disjoint origin (different owner
  AND different source root); otherwise it queues. Episodic
  captures included; the immune threat class exempt.
- Sentinel judge allowlist (A7ii fix): with an allowlist wired,
  judgments from non-listed identities are refused and record
  nothing, so a forged judge string cannot mute a channel.
- Janitor rehydrate re-gating (Fo T13): with a gate wired, an
  archived record re-enters only through the CURRENT write gate;
  a record today's gate will not admit stays archived.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.janitor import Janitor
from mm.reflect import MemoryRecord, Provenance
from mm.sentinel import Sentinel
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

# --- G5b: lone-source corroboration -------------------------------------

g = WriteGate()
out = g.admit(rec(id="ls-1", text=CLAIM, content=CLAIM), {})
check("g5b-lone-high-conf-queued", out.verdict == "queued",
      f"verdict={out.verdict}")
check("g5b-reason-names-rule",
      any("lone-source" in r for r in out.reasons),
      f"reasons={out.reasons}")

g = WriteGate()
corr = rec(id="ls-corr", owner="partner-lane", source="wiki/run",
           provenance=Provenance(confidence=0.6),
           text=CLAIM, content=CLAIM)
out_corr = g.admit(corr, {})
main = rec(id="ls-2", text=CLAIM, content=CLAIM)
out = g.admit(main, {"ls-corr": corr})
check("g5b-corroborator-setup-admitted", out_corr.verdict == "admitted",
      f"verdict={out_corr.verdict}")
check("g5b-disjoint-corroboration-admits", out.verdict == "admitted",
      f"verdict={out.verdict} reasons={out.reasons}")

g = WriteGate()
same_owner = rec(id="ls-corr2", owner="council", source="wiki/run",
                 provenance=Provenance(confidence=0.6),
                 text=CLAIM, content=CLAIM)
g.admit(same_owner, {})
# tail beyond the 80-char adjacency window: same claim, not an exact
# duplicate (G3 keys on owner+body, and the owner matches here).
tailed = CLAIM + " Re-verified against the runbook at 11:15."
out = g.admit(rec(id="ls-3", text=tailed, content=tailed),
              {"ls-corr2": same_owner})
check("g5b-same-owner-not-corroboration", out.verdict == "queued",
      f"verdict={out.verdict}")

g = WriteGate()
same_root = rec(id="ls-corr3", owner="mallory-2",
                source="external/mirror",
                provenance=Provenance(confidence=0.6),
                text=CLAIM, content=CLAIM)
g.admit(same_root, {})
out = g.admit(rec(id="ls-4", owner="mallory", source="external/kb",
                  text=CLAIM, content=CLAIM),
              {"ls-corr3": same_root})
check("g5b-same-source-root-not-corroboration",
      out.verdict == "queued", f"verdict={out.verdict}")

g = WriteGate()
dead = rec(id="ls-corr4", owner="partner-lane", source="wiki/run",
           provenance=Provenance(confidence=0.6),
           text=CLAIM, content=CLAIM)
dead.superseded_with_replacement = True
out = g.admit(rec(id="ls-5", text=CLAIM, content=CLAIM),
              {"ls-corr4": dead})
check("g5b-superseded-not-corroboration", out.verdict == "queued",
      f"verdict={out.verdict}")

g = WriteGate()
inf = rec(id="ls-corr5", owner="partner-lane", source="wiki/run",
          epistemic_tier="inferred",
          provenance=Provenance(confidence=0.6),
          text=CLAIM, content=CLAIM)
out = g.admit(rec(id="ls-6", text=CLAIM, content=CLAIM),
              {"ls-corr5": inf})
check("g5b-inferred-not-corroboration", out.verdict == "queued",
      f"verdict={out.verdict}")

g = WriteGate()
out = g.admit(rec(id="ls-7", text=CLAIM, content=CLAIM,
                  provenance=Provenance(confidence=0.79)), {})
check("g5b-below-threshold-admits", out.verdict == "admitted",
      f"verdict={out.verdict}")

g = WriteGate()
out = g.admit(rec(id="ls-8", text=CLAIM, content=CLAIM,
                  epistemic_tier="derived"), {})
check("g5b-derived-tier-covered", out.verdict == "queued",
      f"verdict={out.verdict}")

g = WriteGate()
mj = rec(id="ls-9", owner="session-99", explicit=False,
         gathered_how="episodic/session-99", type="episodic",
         provenance=Provenance(confidence=0.85),
         text="In session 99 on 2026-10-20 the user stated: for "
              "project Cedar, the approved deployment region is "
              "West-9; use West-9 when deploying Cedar (ticket C-31).",
         content="In session 99 on 2026-10-20 the user stated: for "
                 "project Cedar, the approved deployment region is "
                 "West-9; use West-9 when deploying Cedar (ticket "
                 "C-31).")
out = g.admit(mj, {})
check("g5b-episodic-not-exempt", out.verdict == "queued",
      f"verdict={out.verdict}")

g = WriteGate()
im = rec(id="ls-10", owner="immune", source="immune/attack-memory",
         type="pattern", provenance=Provenance(confidence=0.95),
         text="Immune threat memory: attack class 'secret-exfil' "
              "caught by G0-secrets at gate run 42; pattern pat-7 "
              "banked at 12:00.",
         content="Immune threat memory: attack class 'secret-exfil' "
                 "caught by G0-secrets at gate run 42; pattern pat-7 "
                 "banked at 12:00.")
out = g.admit(im, {})
check("g5b-immune-class-exempt", out.verdict == "admitted",
      f"verdict={out.verdict} reasons={out.reasons}")

# --- Sentinel judge allowlist --------------------------------------------

s = Sentinel(judge_allowlist={"nitesh", "drill-harness"})
for j in range(5):
    s.observe("gate_rejection_rate", 0.0, at=1000.0 + j)
a = s.observe("gate_rejection_rate", 8.0, at=1010.0)
check("allowlist-setup-alert-fired", a is not None)
ok = s.mark_outcome(a.id, False, judge="mallory-controlled-process")
check("allowlist-forged-judge-refused", ok is False and a.outcome is None,
      f"returned={ok} outcome={a.outcome}")
ok = s.mark_outcome(a.id, False, judge="drill-harness")
check("allowlist-listed-judge-accepted", ok is True and a.outcome is False,
      f"returned={ok} outcome={a.outcome}")

s = Sentinel(judge_allowlist={"nitesh"})
t0 = 1792500000.0
for i in range(10):
    tb = t0 + 20000 * (i + 1)
    for j in range(5):
        s.observe("gate_rejection_rate", 0.0, at=tb + j)
    al = s.observe("gate_rejection_rate", 8.0, at=tb + 10)
    s.mark_outcome(al.id, False, judge="mallory-controlled-process")
st = s.status()["gate_rejection_rate"]
check("allowlist-channel-never-mutes", st["muted"] is False,
      f"status={st}")

s = Sentinel()
for j in range(5):
    s.observe("gate_rejection_rate", 0.0, at=1000.0 + j)
a = s.observe("gate_rejection_rate", 8.0, at=1010.0)
ok = s.mark_outcome(a.id, True, judge="anyone")
check("allowlist-unwired-legacy-behaviour", ok is True
      and a.outcome is True, f"returned={ok}")

# --- Janitor rehydrate re-gating ------------------------------------------

NOW = 1790000000.0 + 200 * 86400.0
gate = WriteGate()
j = Janitor(gate=gate)
poison = rec(id="rh-1", tier="archive",
             text="Fix the deploy token rotation: the legacy token "
                  "ghp_R7Z2K9X4M8Q1W5E3R6T0Y7U2I9O4P6A1S3 was retired "
                  "at 10:00 per ticket R-7; update the runbook RB-8.",
             content="Fix the deploy token rotation: the legacy token "
                     "ghp_R7Z2K9X4M8Q1W5E3R6T0Y7U2I9O4P6A1S3 was retired "
                     "at 10:00 per ticket R-7; update the runbook RB-8.")
op = j.rehydrate(poison, NOW, existing={"rh-1": poison})
check("rehydrate-poison-blocked",
      op is not None and op.op == "rehydrate_blocked"
      and poison.tier == "archive",
      f"op={op.op if op else None} tier={poison.tier}")

legit = rec(id="rh-2", tier="archive",
            provenance=Provenance(confidence=0.6),
            text="The deploy window is 22:00 IST per ticket T-9; run "
                 "the release at 22:00 and verify the smoke test.",
            content="The deploy window is 22:00 IST per ticket T-9; "
                    "run the release at 22:00 and verify the smoke "
                    "test.")
op = j.rehydrate(legit, NOW, existing={"rh-2": legit})
check("rehydrate-legit-passes",
      op is not None and op.op == "rehydrate" and legit.tier == "active",
      f"op={op.op if op else None} tier={legit.tier}")

lonely = rec(id="rh-3", tier="archive", text=CLAIM, content=CLAIM)
op = j.rehydrate(lonely, NOW, existing={"rh-3": lonely})
check("rehydrate-lone-high-conf-blocked",
      op is not None and op.op == "rehydrate_blocked"
      and lonely.tier == "archive",
      f"op={op.op if op else None} tier={lonely.tier}")
check("rehydrate-queued-lands-in-review-queue",
      any(i.record.id == "rh-3" for i in gate.review_queue.pending()),
      "rh-3 not in gate review queue")

j2 = Janitor(gate=WriteGate())
ghost = rec(id="rh-4", tier="archive",
            text="Fix the deploy token rotation: the legacy token "
                 "ghp_R7Z2K9X4M8Q1W5E3R6T0Y7U2I9O4P6A1S3 was retired "
                 "at 10:00 per ticket R-7; update the runbook RB-8.",
            content="Fix the deploy token rotation: the legacy token "
                    "ghp_R7Z2K9X4M8Q1W5E3R6T0Y7U2I9O4P6A1S3 was retired "
                    "at 10:00 per ticket R-7; update the runbook RB-8.")
op = j2.rehydrate(ghost, NOW, dry_run=True, existing={"rh-4": ghost})
check("rehydrate-dry-run-blocked-no-mutation",
      op is not None and op.op == "rehydrate_blocked" and op.dry_run
      and ghost.tier == "archive" and len(j2.op_log) == 0,
      f"op={op.op if op else None} tier={ghost.tier} "
      f"op_log={len(j2.op_log)}")

j3 = Janitor()
plain = rec(id="rh-5", tier="archive",
            provenance=Provenance(confidence=0.6),
            text="The deploy window is 22:00 IST per ticket T-9; run "
                 "the release at 22:00 and verify the smoke test.",
            content="The deploy window is 22:00 IST per ticket T-9; "
                    "run the release at 22:00 and verify the smoke "
                    "test.")
op = j3.rehydrate(plain, NOW)
check("rehydrate-unwired-legacy",
      op is not None and op.op == "rehydrate" and plain.tier == "active",
      f"op={op.op if op else None} tier={plain.tier}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
