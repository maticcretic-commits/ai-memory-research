"""Ruling A amendment tests (2026-10-25).

Ruling A (incharge, ChatGPT, 2026-10-21, disposing the Gemini
independent audit of the Round-6 follow-up -
redteam-round6-gemini-audit-ruling.txt, question (m) and
finding F-11): when a claimant/source is in flagged state, a
same-owner supersession of that claimant requires TWO clean,
independent corroborations before it takes effect; the
flagged state is retained until then; and a flagged identity
can never count as a clean corroborator.

The audit named the two bypass paths this amendment closes:

1. Same-owner supersession submitted against a flagged
   claimant with NO corroborations: ruling C's bypass let a
   flagged source overwrite its own records at >= 0.80
   immediately - an uncorroborated mutation from a known-
   poisoned source, sidestepping the D-A + D-D two-key rule.
2. A flagged identity presented as a corroborator: D-D was
   consulted only inside the flagged-claimant rule, so a
   flagged source could act as the SOLE corroborator for a
   clean claimant (GU3), or pad out a flagged claimant's own
   supersession attempt.

Plus the legitimate path: the same supersession backed by
two genuinely clean, independent (pairwise-disjoint,
non-flagged) corroborators succeeds, and a flagged identity
in the pool is skipped, never fatal.

Fixtures mirror tests/test_redteam_round6_followup.py
(store-level with the gate wired to a fresh registry in
shadow mode). The flag clears only through rehabilitation -
a successful corroborated supersession does NOT clear it,
and these tests pin that too.
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.reflect import MemoryRecord, Provenance
from mm.source_trust import SourceTrustRegistry, TIER_FLAGGED
from mm.storage import SQLiteStore
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
CORRECTED = CLAIM + " Corrected at 10:30 per ticket B-10."
SECRET = ("Fix the token rotation: the legacy token "
          "ghp_R7Z2K9X4M8Q1W5E3R6T0Y7U2I9O4P6A1S3 was retired "
          "at 10:00 per ticket R-7; update the runbook RB-8.")


def gf_store(shadow=True):
    path = tempfile.mktemp(suffix=".db")
    assert "memory.db" not in path  # sandbox guard
    store = SQLiteStore(path)
    reg = SourceTrustRegistry()
    store.gate = WriteGate(trust_registry=reg,
                           trust_shadow=shadow)
    return store, path, reg


def cleanup(store, path):
    try:
        store.close()
    except Exception:
        pass
    try:
        os.remove(path)
    except OSError:
        pass


def flag(store, owner, source, rid):
    out = store.write(rec(id=rid, owner=owner, source=source,
                          text=SECRET, content=SECRET))
    assert out.verdict == "rejected", (rid, out.verdict)


def corroborate(store, rid, owner, source, suffix):
    t = CLAIM + suffix
    out = store.write(rec(id=rid, owner=owner, source=source,
                          provenance=Provenance(confidence=0.60),
                          text=t, content=t))
    assert out.verdict == "admitted", (rid, out.verdict,
                                       out.reasons)


def own_record(store, rid, owner, source):
    out = store.write(rec(id=rid, owner=owner, source=source,
                          provenance=Provenance(confidence=0.60),
                          text=CLAIM, content=CLAIM))
    assert out.verdict == "admitted", (rid, out.verdict,
                                       out.reasons)


def correction(store, rid, owner, source, target_id):
    r = rec(id=rid, owner=owner, source=source,
            provenance=Provenance(confidence=0.90,
                                  supersedes=[target_id]),
            text=CORRECTED, content=CORRECTED)
    return store.write(r), r


def claim(store, rid, owner, source, conf=0.90):
    r = rec(id=rid, owner=owner, source=source,
            provenance=Provenance(confidence=conf),
            text=CLAIM, content=CLAIM)
    return store.write(r), r


def g5b_detail(record):
    for g in record.write_audit["gates"]:
        if g["gate"] == "G5b-corroboration":
            return g["detail"]
    return ""


# --- Path 1a: flagged claimant, same-owner supersession, no --------------
# --- corroborators -> queued, target untouched, flag retained ------------

store, path, reg = gf_store()
own_record(store, "s1-own", "mallory", "insider/leak")
flag(store, "mallory", "insider/leak", "s1-poison")
out, r = correction(store, "s1-corr", "mallory", "insider/leak",
                    "s1-own")
check("p1-flagged-supersession-no-corroborators-queued",
      out.verdict == "queued", f"verdict={out.verdict}")
check("p1-bypass-note-absent",
      "immediate per incharge ruling C" not in g5b_detail(r),
      g5b_detail(r))
target = store.get("s1-own")
check("p1-target-not-closed",
      target is not None and not target.superseded_with_replacement
      and target.tier != "archive",
      f"target={target}")
check("p1-correction-not-stored",
      store.get("s1-corr") is None)
check("p1-flag-retained",
      reg.tier_for("mallory", "insider/leak") == TIER_FLAGGED)
cleanup(store, path)

# --- Path 1b: the legitimate path - two genuinely clean, -----------------
# --- independent corroborators -> the supersession takes effect ----------

store, path, reg = gf_store()
own_record(store, "s2-own", "mallory", "insider/leak")
corroborate(store, "s2-c1", "desk", "wire/desk",
            " Confirmed at 11:15.")
corroborate(store, "s2-c2", "lab", "lab/results",
            " Confirmed at 12:45.")
flag(store, "mallory", "insider/leak", "s2-poison")
out, r = correction(store, "s2-corr", "mallory", "insider/leak",
                    "s2-own")
check("p1-legit-two-clean-corroborators-admitted",
      out.verdict == "admitted", f"verdict={out.verdict} "
      f"reasons={out.reasons}")
check("p1-legit-note-names-both-corroborators",
      "s2-c1" in g5b_detail(r) and "s2-c2" in g5b_detail(r),
      g5b_detail(r))
target = store.get("s2-own")
check("p1-legit-target-closed-on-admission",
      target is not None and target.superseded_with_replacement,
      f"target={target}")
# The supersession taking effect does NOT clear the flag -
# clearing is rehabilitation's job, not this gate's.
check("p1-legit-flag-still-retained",
      reg.tier_for("mallory", "insider/leak") == TIER_FLAGGED)
cleanup(store, path)

# --- Path 1c/2b: one clean + one FLAGGED corroborator offered for ---------
# --- the flagged claimant's own supersession -> still only one key --------

store, path, reg = gf_store()
own_record(store, "s3-own", "mallory", "insider/leak")
corroborate(store, "s3-c1", "desk", "wire/desk",
            " Confirmed at 11:15.")
corroborate(store, "s3-c2", "tainted", "feeds/x",
            " Confirmed at 12:45.")
flag(store, "tainted", "feeds/x", "s3-p2")
flag(store, "mallory", "insider/leak", "s3-poison")
out, r = correction(store, "s3-corr", "mallory", "insider/leak",
                    "s3-own")
check("p1-one-clean-one-flagged-corroborator-queued",
      out.verdict == "queued", f"verdict={out.verdict}")
target = store.get("s3-own")
check("p1-mixed-pool-target-not-closed",
      target is not None and not target.superseded_with_replacement)
cleanup(store, path)

# --- Path 1 scope: a NON-flagged claimant's same-owner correction ---------
# --- still lands immediately (the amendment is no broader than ruled) -----

store, path, reg = gf_store()
own_record(store, "s4-own", "council", "bench")
out, r = correction(store, "s4-corr", "council", "bench", "s4-own")
check("p1-clean-claimant-bypass-unchanged",
      out.verdict == "admitted"
      and "immediate per incharge ruling C" in g5b_detail(r),
      f"verdict={out.verdict} detail={g5b_detail(r)}")
cleanup(store, path)

# --- Path 2a: flagged identity as SOLE corroborator for a clean -----------
# --- claimant (the audit's GU3) -> the corroboration does not count -------

store, path, reg = gf_store()
corroborate(store, "s5-c1", "tainted", "feeds/x",
            " Confirmed at 11:15.")
flag(store, "tainted", "feeds/x", "s5-poison")
out, r = claim(store, "s5-claim", "council", "bench")
check("p2-flagged-sole-corroborator-queued",
      out.verdict == "queued", f"verdict={out.verdict}")
check("p2-queue-note-names-ruling-a",
      "Ruling A" in g5b_detail(r), g5b_detail(r))
cleanup(store, path)

# --- Path 2b: flagged corroborator is skipped, not fatal - a clean --------
# --- corroborator behind it still admits the clean claimant ---------------

store, path, reg = gf_store()
corroborate(store, "s6-c1", "tainted", "feeds/x",
            " Confirmed at 11:15.")
flag(store, "tainted", "feeds/x", "s6-poison")
corroborate(store, "s6-c2", "desk", "wire/desk",
            " Confirmed at 12:45.")
out, r = claim(store, "s6-claim", "council", "bench")
check("p2-flagged-skipped-clean-corroborator-admits",
      out.verdict == "admitted"
      and "corroborated by s6-c2" in g5b_detail(r),
      f"verdict={out.verdict} detail={g5b_detail(r)}")
cleanup(store, path)

# --- Path 2c: the flagged identity corroborating its OWN claim under a ----
# --- second identity it controls still cannot launder it ------------------
# (A flagged claimant filing through a sibling identity whose only
# corroborator is the original flagged identity: the claimant here
# is the sibling - itself unflagged - but its sole corroborator is
# flagged, so the claim queues under path 2.)

store, path, reg = gf_store()
corroborate(store, "s7-c1", "mallory", "insider/leak",
            " Confirmed at 11:15.")
flag(store, "mallory", "insider/leak", "s7-poison")
out, r = claim(store, "s7-claim", "mallory-alt", "mirror/feed")
check("p2-flagged-cannot-launder-sibling-claim",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

# --- Wiring scope: no registry -> no flag state -> legacy paths -----------

path = tempfile.mktemp(suffix=".db")
assert "memory.db" not in path  # sandbox guard
store = SQLiteStore(path)  # default gate: no registry wired
own_record(store, "s8-own", "mallory", "insider/leak")
out, r = correction(store, "s8-corr", "mallory", "insider/leak",
                    "s8-own")
check("unwired-registry-legacy-bypass-admits",
      out.verdict == "admitted", f"verdict={out.verdict}")
cleanup(store, path)

# --- Gate-level: the legitimate path without the store --------------------

reg = SourceTrustRegistry()
reg.note_poison(rec(id="p", owner="mallory", source="insider/leak"))
g = WriteGate(trust_registry=reg)
own = rec(id="s9-own", owner="mallory", source="insider/leak",
          provenance=Provenance(confidence=0.60),
          text=CLAIM, content=CLAIM)
c1 = rec(id="s9-c1", owner="desk", source="wire/desk",
         provenance=Provenance(confidence=0.60),
         text=CLAIM + " Confirmed at 11:15.",
         content=CLAIM + " Confirmed at 11:15.")
c2 = rec(id="s9-c2", owner="lab", source="lab/results",
         provenance=Provenance(confidence=0.60),
         text=CLAIM + " Confirmed at 12:45.",
         content=CLAIM + " Confirmed at 12:45.")
corr = rec(id="s9-corr", owner="mallory", source="insider/leak",
           provenance=Provenance(confidence=0.90,
                                 supersedes=["s9-own"]),
           text=CORRECTED, content=CORRECTED)
out = g.admit(corr, {"s9-own": own, "s9-c1": c1, "s9-c2": c2})
check("gate-level-legit-correction-admitted",
      out.verdict == "admitted", f"verdict={out.verdict} "
      f"reasons={out.reasons}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
