"""Red-Team Round 6 follow-up regression tests (2026-10-21).

Pins the D-A + D-D broadening measured by
evals/redteam_round1.py --round6f (preregistration:
redteam-round6-followup-preregistration.md):

- The incharge's ruling (ChatGPT, re-taken through a verified
  channel after Round 6's consultation failed its integrity
  check): at confidence >= 0.80, a registry-FLAGGED claimant
  needs TWO corroborators, each non-flagged, pairwise disjoint
  in owner AND source root - not the single corroborator a
  clean source needs under G5b (Round 2, Option C).
- Scope pins, per the ruling's exact form: a non-flagged
  claimant's path is unchanged (one corroborator); the
  sub-0.80 band stays G5c's; with no registry wired there is
  no flag state and legacy G5b governs.
- AMENDED 2026-10-25 (Ruling A, incharge 2026-10-21, on the
  Gemini audit's question (m) / F-11): the two residuals this
  suite originally pinned as unchanged - ruling C's
  same-owner correction bypass FOR a flagged claimant, and a
  flagged identity serving as sole corroborator for a clean
  claimant (GU3) - are now CLOSED. The two affected pins
  below assert the amended behaviour; full coverage lives in
  tests/test_ruling_a_amendment.py.
- The preregistered utility tax is pinned, not tuned away:
  a legit flagged source with exactly one independent
  corroborator, or with a same-owner corroborator pair,
  now QUEUES (recoverable through review).

Fixtures are store-level with the gate wired to a fresh
registry in shadow mode (the Round-4 posture), mirroring the
harness; two pins are gate-level with hand-built store dicts,
as in the Round-3 suite.
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.reflect import MemoryRecord, Provenance
from mm.source_trust import SourceTrustRegistry
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


def claim(store, rid, owner, source, conf=0.90, tier="observed"):
    r = rec(id=rid, owner=owner, source=source, epistemic_tier=tier,
            provenance=Provenance(confidence=conf),
            text=CLAIM, content=CLAIM)
    return store.write(r), r


def g5b_detail(record):
    for g in record.write_audit["gates"]:
        if g["gate"] == "G5b-corroboration":
            return g["detail"]
    return ""


# --- G1: flagged claimant + one clean corroborator queues ----------------

store, path, reg = gf_store()
corroborate(store, "t1-c1", "desk", "wire/desk", " Confirmed at 11:15.")
flag(store, "mallory", "insider/leak", "t1-poison")
out, r = claim(store, "t1-claim", "mallory", "insider/leak")
check("g1-flagged-one-clean-corroborator-queued",
      out.verdict == "queued", f"verdict={out.verdict}")
check("g1-queue-note-names-ruling",
      "D-A + D-D" in g5b_detail(r), g5b_detail(r))
cleanup(store, path)

store, path, reg = gf_store()
corroborate(store, "t2-c1", "desk", "wire/desk", " Confirmed at 11:15.")
corroborate(store, "t2-c2", "mallory", "mirror/feed",
            " Confirmed at 11:20.")
flag(store, "mallory", "insider/leak", "t2-poison")
out, r = claim(store, "t2-claim", "mallory", "insider/leak")
check("g1-same-owner-extra-never-counts",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

store, path, reg = gf_store()
corroborate(store, "t3-c1", "desk", "wire/desk", " Confirmed at 11:15.")
corroborate(store, "t3-c2", "other-lane", "insider/wire-copy",
            " Confirmed at 11:25.")
flag(store, "mallory", "insider/leak", "t3-poison")
out, r = claim(store, "t3-claim", "mallory", "insider/leak")
check("g1-same-root-extra-never-counts",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

# --- G2: flagged corroborators cannot launder ----------------------------

store, path, reg = gf_store()
corroborate(store, "t4-c1", "sybil-a", "feeds/a", " Confirmed at 11:15.")
flag(store, "sybil-a", "feeds/a", "t4-p1")
corroborate(store, "t4-c2", "sybil-b", "notes/b", " Confirmed at 12:45.")
flag(store, "sybil-b", "notes/b", "t4-p2")
flag(store, "mallory", "insider/leak", "t4-p0")
out, r = claim(store, "t4-claim", "mallory", "insider/leak")
check("g2-two-flagged-corroborators-queue",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

store, path, reg = gf_store()
corroborate(store, "t5-c1", "sybil-a", "feeds/a", " Confirmed at 11:15.")
flag(store, "sybil-a", "feeds/a", "t5-p1")
corroborate(store, "t5-c2", "sybil-b", "notes/b", " Confirmed at 12:45.")
flag(store, "sybil-b", "notes/b", "t5-p2")
flag(store, "mallory", "insider/leak", "t5-p0")
out, r = claim(store, "t5-claim", "mallory", "insider/leak",
               conf=0.88, tier="derived")
check("g2-derived-tier-variant-queued",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

# --- G3: the pair must be pairwise disjoint -------------------------------

store, path, reg = gf_store()
corroborate(store, "t6-c1", "wire-service", "wire/east",
            " Confirmed at 11:15.")
corroborate(store, "t6-c2", "wire-service", "agency/west",
            " Confirmed at 12:45.")
flag(store, "mallory", "insider/leak", "t6-poison")
out, r = claim(store, "t6-claim", "mallory", "insider/leak")
check("g3-pair-sharing-owner-queued",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

store, path, reg = gf_store()
corroborate(store, "t7-c1", "desk-a", "external/alice",
            " Confirmed at 11:15.")
corroborate(store, "t7-c2", "desk-b", "external/bob",
            " Confirmed at 12:45.")
flag(store, "mallory", "insider/leak", "t7-poison")
out, r = claim(store, "t7-claim", "mallory", "insider/leak")
check("g3-pair-sharing-root-queued",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

# --- GU1: two clean disjoint corroborators admit ---------------------------

store, path, reg = gf_store()
corroborate(store, "t8-c1", "desk", "wire/desk", " Confirmed at 11:15.")
corroborate(store, "t8-c2", "lab", "lab/results",
            " Confirmed at 12:45.")
flag(store, "stringer", "tips/desk", "t8-poison")
out, r = claim(store, "t8-claim", "stringer", "tips/desk")
check("gu1-flagged-two-clean-disjoint-admitted",
      out.verdict == "admitted", f"verdict={out.verdict} "
      f"reasons={out.reasons}")
check("gu1-admit-note-names-both-and-ruling",
      "t8-c1" in g5b_detail(r) and "t8-c2" in g5b_detail(r)
      and "D-A + D-D" in g5b_detail(r), g5b_detail(r))
cleanup(store, path)

# Pair search is not "first two eligible": a same-root pair in
# front must not block a valid pair behind it.
store, path, reg = gf_store()
corroborate(store, "t9-c1", "desk", "wire/desk", " Confirmed at 11:15.")
corroborate(store, "t9-c2", "lab", "wire/lab-desk",
            " Confirmed at 11:20.")
corroborate(store, "t9-c3", "field-ops", "field/reports",
            " Confirmed at 12:45.")
flag(store, "stringer", "tips/desk", "t9-poison")
out, r = claim(store, "t9-claim", "stringer", "tips/desk")
check("gu1-pair-search-finds-valid-pair",
      out.verdict == "admitted" and "t9-c3" in g5b_detail(r),
      f"verdict={out.verdict} detail={g5b_detail(r)}")
cleanup(store, path)

# Mixed pool: flagged corroborators are skipped, the clean
# disjoint pair still admits.
store, path, reg = gf_store()
corroborate(store, "t10-c1", "tainted", "feeds/x",
            " Confirmed at 11:05.")
flag(store, "tainted", "feeds/x", "t10-p1")
corroborate(store, "t10-c2", "desk", "wire/desk",
            " Confirmed at 11:15.")
corroborate(store, "t10-c3", "lab", "lab/results",
            " Confirmed at 12:45.")
flag(store, "stringer", "tips/desk", "t10-p0")
out, r = claim(store, "t10-claim", "stringer", "tips/desk")
check("gu1-flagged-corroborators-skipped-not-fatal",
      out.verdict == "admitted", f"verdict={out.verdict}")
cleanup(store, path)

# One clean + two flagged is still only one eligible key.
store, path, reg = gf_store()
corroborate(store, "t11-c1", "desk", "wire/desk",
            " Confirmed at 11:15.")
corroborate(store, "t11-c2", "sybil-a", "feeds/a",
            " Confirmed at 11:20.")
flag(store, "sybil-a", "feeds/a", "t11-p2")
corroborate(store, "t11-c3", "sybil-b", "notes/b",
            " Confirmed at 12:45.")
flag(store, "sybil-b", "notes/b", "t11-p3")
flag(store, "stringer", "tips/desk", "t11-p0")
out, r = claim(store, "t11-claim", "stringer", "tips/desk")
check("g2-one-clean-two-flagged-still-queued",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

# --- Scope pins: the clean claimant's path is unchanged -------------------

store, path, reg = gf_store()
corroborate(store, "t12-c1", "desk", "wire/desk",
            " Confirmed at 11:15.")
out, r = claim(store, "t12-claim", "council", "bench")
check("gu2-clean-claimant-one-corroborator-admitted",
      out.verdict == "admitted" and "corroborated by t12-c1"
      in g5b_detail(r), f"verdict={out.verdict} "
      f"detail={g5b_detail(r)}")
cleanup(store, path)

store, path, reg = gf_store()
corroborate(store, "t13-c1", "tainted", "feeds/x",
            " Confirmed at 11:15.")
flag(store, "tainted", "feeds/x", "t13-poison")
out, r = claim(store, "t13-claim", "council", "bench")
# AMENDED (Ruling A, 2026-10-21): GU3 is closed - a flagged
# identity can never count as a clean corroborator, so the
# clean claimant backed only by the flagged source now queues.
check("gu3-amended-flagged-corroborator-no-longer-counts",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

# --- The preregistered utility tax, pinned --------------------------------

store, path, reg = gf_store()
corroborate(store, "t14-c1", "desk", "wire/desk",
            " Confirmed at 11:15.")
flag(store, "honest-lane", "field/reports", "t14-poison")
out, r = claim(store, "t14-claim", "honest-lane", "field/reports")
check("gu4a-tax-lone-corroborated-flagged-source-queues",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

store, path, reg = gf_store()
corroborate(store, "t15-c1", "newsroom", "newsroom/desk",
            " Confirmed at 11:15.")
corroborate(store, "t15-c2", "newsroom", "agency/wire",
            " Confirmed at 12:45.")
flag(store, "stringer", "tips/desk", "t15-poison")
out, r = claim(store, "t15-claim", "stringer", "tips/desk")
check("gu4b-tax-syndication-pair-queues",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

# --- Wiring / shadow / band scope ------------------------------------------

path = tempfile.mktemp(suffix=".db")
assert "memory.db" not in path  # sandbox guard
store = SQLiteStore(path)
t = CLAIM + " Confirmed at 11:15."
store.write(rec(id="t16-c1", owner="desk", source="wire/desk",
                provenance=Provenance(confidence=0.60),
                text=t, content=t))
out, r = claim(store, "t16-claim", "council", "bench")
check("gu5-unwired-registry-legacy-admits",
      out.verdict == "admitted", f"verdict={out.verdict}")
cleanup(store, path)

# Shadow mode does not soften G5b: the two-key rule enforces
# even while G5c only measures.
store, path, reg = gf_store(shadow=True)
corroborate(store, "t17-c1", "desk", "wire/desk",
            " Confirmed at 11:15.")
flag(store, "mallory", "insider/leak", "t17-poison")
out, r = claim(store, "t17-claim", "mallory", "insider/leak")
check("shadow-mode-does-not-soften-g5b",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

# The band below 0.80 is still G5c's: a flagged claimant at
# 0.75 queues under the band rule (non-shadow registry), not
# under the two-key rule.
store, path, reg = gf_store(shadow=False)
flag(store, "mallory", "insider/leak", "t18-poison")
out, r = claim(store, "t18-claim", "mallory", "insider/leak",
               conf=0.75)
band = [g["detail"] for g in r.write_audit["gates"]
        if g["gate"] == "G5c-source-trust"]
check("band-flagged-still-g5c-governed",
      out.verdict == "queued" and band
      and "flagged source" in band[0],
      f"verdict={out.verdict} band={band}")
cleanup(store, path)

# --- Gate-level pins --------------------------------------------------------

# A superseded corroborator never counts toward the two keys.
reg = SourceTrustRegistry()
reg.note_poison(rec(id="p", owner="mallory", source="insider/leak"))
g = WriteGate(trust_registry=reg)
live = rec(id="t19-c1", owner="desk", source="wire/desk",
           provenance=Provenance(confidence=0.60),
           text=CLAIM + " Confirmed at 11:15.",
           content=CLAIM + " Confirmed at 11:15.")
dead = rec(id="t19-c2", owner="lab", source="lab/results",
           provenance=Provenance(confidence=0.60),
           text=CLAIM + " Confirmed at 12:45.",
           content=CLAIM + " Confirmed at 12:45.")
dead.superseded_with_replacement = True
out = g.admit(rec(id="t19-claim", owner="mallory",
                  source="insider/leak", text=CLAIM, content=CLAIM),
              {"t19-c1": live, "t19-c2": dead})
check("superseded-corroborator-not-counted",
      out.verdict == "queued", f"verdict={out.verdict}")

# AMENDED (Ruling A, 2026-10-21): the bypass no longer fires
# for a flagged claimant. A correction superseding ONLY its
# own record, with no corroborators, now QUEUES - it needs
# two clean, independent corroborators before it takes
# effect (preregistration interpretation note i is closed).
reg = SourceTrustRegistry()
reg.note_poison(rec(id="p", owner="mallory", source="insider/leak"))
g = WriteGate(trust_registry=reg)
own = rec(id="t20-own", owner="mallory", source="insider/leak",
          provenance=Provenance(confidence=0.60),
          text=CLAIM, content=CLAIM)
corr = rec(id="t20-corr", owner="mallory", source="insider/leak",
           provenance=Provenance(confidence=0.90,
                                 supersedes=["t20-own"]),
           text=CLAIM + " Corrected at 10:30 per ticket B-10.",
           content=CLAIM + " Corrected at 10:30 per ticket B-10.")
out = g.admit(corr, {"t20-own": own})
check("ruling-a-flagged-correction-without-corroborators-queues",
      out.verdict == "queued", f"verdict={out.verdict} "
      f"reasons={out.reasons}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
