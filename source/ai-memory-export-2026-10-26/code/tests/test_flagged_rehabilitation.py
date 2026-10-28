"""Flagged-source rehabilitation regression tests (2026-10-21).

Pins the incharge's ruling (ChatGPT, design consultation):
adopt A + C - automatic clean-streak rehabilitation at
K = 5 held-accruing admissions, plus manual rehabilitation
as a recorded exception - measured by
evals/redteam_round1.py --rehab (preregistration:
flagged-rehabilitation-preregistration.md):

- The streak counts only admissions that ACCRUE held (the
  GA cap starves a solo reviewer at 2); disputes and poison
  reset it; completion covers the poison history without
  erasing it, grants no score, arms GB probation, and is
  logged.
- One journey per identity: a poison event after a
  completed rehabilitation (streak or manual) makes the
  flag permanent; neither path lifts it again.
- Gate consequences flow from tier_of alone (mm/write_gate
  .py unchanged): the GU4 tax recovers for a rehabilitated
  source, a rehabilitated identity corroborates a flagged
  claimant immediately (the ruling's corroboration point),
  a still-flagged corroborator still does not count (D-D),
  and rehabilitation's GB probation queues the first band
  filing in enforcement posture without shadow consuming it.

Fixtures are store-level with the gate wired to a fresh
registry (shadow posture unless a check says enforcement),
mirroring the harness; registry pins call the registry API
directly, as in the Round-3 suite.
"""

import json
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
CLAIM_B = ("The Cedar deploy window is 22:00 IST per ticket C-31; "
           "run the release then and verify the smoke test.")
SECRET = ("Fix the token rotation: the legacy token "
             "ghp_R7Z2K9X4M8Q1W5E3R6T0Y7U2I9O4P6A1S3 was retired "
             "at 10:00 per ticket R-7; update the runbook RB-8.")
TRUTHS = [
    "The staging database DS-2 runs Postgres 15.4; restart it "
    "at 06:00 before the load test per ticket S-11.",
    "The Ledger component owns the billing export per ticket "
    "B-09; check runbook RB-2 v1.8 at 09:30.",
    "Deploy window for project Cedar is 22:00 IST per ticket "
    "C-31; run the release then and verify the smoke test.",
    "The winter audit checklist WA-3 v1.0 requires two "
    "reviewers; schedule the audit review at 15:00.",
    "Hotfix HF-7 for the glorp scheduler sets thread_pool=64 "
    "in glorp.yaml v1.3; verify after the restart.",
]


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


def corroborate(store, rid, owner, source, suffix, claim=CLAIM):
    t = claim + suffix
    out = store.write(rec(id=rid, owner=owner, source=source,
                          provenance=Provenance(confidence=0.60),
                          text=t, content=t))
    assert out.verdict == "admitted", (rid, out.verdict,
                                       out.reasons)


def earn(store, reg, owner, source, tag, n=5):
    """The C3 reviewer path: true claims at conf 0.85 queue,
    a rotating panel of five reviewers admits each."""
    built = 0
    for i in range(n):
        r = rec(id=f"{tag}-t{i}", owner=owner, source=source,
                provenance=Provenance(confidence=0.85),
                text=TRUTHS[i], content=TRUTHS[i])
        out = store.write(r)
        if out.verdict == "queued" and store.resolve_review(
                r.id, "admit"):
            built += 1
            reg.note_admitted(r, via="review",
                              reviewer=f"rev-{i % 5 + 1}")
    return built


# ------------------------------------------------------------------
# Registry-level pins
# ------------------------------------------------------------------

# 1-2: the streak completes at exactly K=5 held-accruing
# admissions, covering (not erasing) the poison history.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
for _ in range(4):
    reg.note_admitted(r)
st = reg.stats_for("lane", "ops/feed")
check("streak-incomplete-at-four",
      reg.tier_for("lane", "ops/feed") == "flagged"
      and st.clean_streak == 4,
      f"tier={reg.tier_for('lane', 'ops/feed')} streak="
      f"{st.clean_streak}")
reg.note_admitted(r)
st = reg.stats_for("lane", "ops/feed")
check("streak-completes-at-five",
      reg.tier_for("lane", "ops/feed") != "flagged"
      and st.rehabilitations == 1 and st.poison_covered == 1
      and st.poison == 1,
      f"tier={reg.tier_for('lane', 'ops/feed')} st={st}")

# 3: a solo reviewer stalls at the GA cap - held, streak and
# tier all stop at 2.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
for _ in range(5):
    reg.note_admitted(r, via="review", reviewer="rev-solo")
st = reg.stats_for("lane", "ops/feed")
check("solo-reviewer-cap-stalls-streak",
      st.held == 2 and st.clean_streak == 2
      and st.review_capped == 3
      and reg.tier_for("lane", "ops/feed") == "flagged",
      f"st={st}")

# 4: a dispute resets the streak; completion then costs the
# full five again.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
for _ in range(4):
    reg.note_admitted(r)
reg.note_dispute(r)
st = reg.stats_for("lane", "ops/feed")
ok = st.clean_streak == 0 and st.disputes == 1
for _ in range(4):
    reg.note_admitted(r)
ok = ok and reg.tier_for("lane", "ops/feed") == "flagged"
reg.note_admitted(r)
check("dispute-resets-streak",
      ok and reg.tier_for("lane", "ops/feed") != "flagged",
      f"st={reg.stats_for('lane', 'ops/feed')}")

# 5: a repeat poison BEFORE any rehabilitation resets the
# streak but does not consume the journey or turn permanent.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
for _ in range(4):
    reg.note_admitted(r)
reg.note_poison(r)
st = reg.stats_for("lane", "ops/feed")
ok = st.clean_streak == 0 and not st.permanent \
    and st.poison == 2
for _ in range(5):
    reg.note_admitted(r)
check("pre-rehab-repeat-poison-not-permanent",
      ok and reg.tier_for("lane", "ops/feed") != "flagged"
      and reg.stats_for("lane", "ops/feed").rehabilitations == 1,
      f"st={reg.stats_for('lane', 'ops/feed')}")

# 6: rehabilitation grants no score - a dispute-heavy
# identity completes to UNPROVEN, not proven.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_admitted(r)
for _ in range(3):
    reg.note_dispute(r)
reg.note_poison(r)
for _ in range(5):
    reg.note_admitted(r)
st = reg.stats_for("lane", "ops/feed")
check("rehab-grants-no-score",
      st.rehabilitations == 1
      and reg.tier_for("lane", "ops/feed") == "unproven",
      f"tier={reg.tier_for('lane', 'ops/feed')} st={st}")

# 7: manual rehabilitation succeeds, is logged with decider
# and rationale, and keeps the poison history visible.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
ok = reg.rehabilitate("lane", "ops/feed",
                      decided_by="founder (nitesh)",
                      rationale="one G0 slip; record clean")
entries = reg.rehabilitation_log()
e = entries[-1] if entries else {}
st = reg.stats_for("lane", "ops/feed")
check("manual-rehab-success-and-log",
      ok and len(entries) == 1 and e.get("mode") == "manual"
      and e.get("decided_by") == "founder (nitesh)"
      and bool(e.get("rationale")) and st.poison == 1
      and st.rehabilitations == 1
      and reg.tier_for("lane", "ops/feed") != "flagged",
      f"ok={ok} entries={entries} st={st}")

# 8-9: the manual path refuses anonymity (ValueError).
reg = SourceTrustRegistry()
reg.note_poison(rec(id="x", owner="lane", source="ops/feed"))
try:
    reg.rehabilitate("lane", "ops/feed", decided_by=" ",
                     rationale="recorded")
    raised = False
except ValueError:
    raised = True
check("manual-rehab-requires-decider", raised)
try:
    reg.rehabilitate("lane", "ops/feed",
                     decided_by="founder", rationale="")
    raised = False
except ValueError:
    raised = True
check("manual-rehab-requires-rationale", raised)

# 10: nothing to lift -> False (unflagged and unknown).
reg = SourceTrustRegistry()
reg.note_admitted(rec(id="x", owner="lane", source="ops/feed"))
check("manual-rehab-unflagged-false",
      reg.rehabilitate("lane", "ops/feed",
                       decided_by="founder",
                       rationale="not flagged") is False
      and reg.rehabilitate("ghost", "none/x",
                           decided_by="founder",
                           rationale="unknown") is False)

# 11: permanence after a streak rehabilitation + poison.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
for _ in range(5):
    reg.note_admitted(r)
reg.note_poison(r)
st = reg.stats_for("lane", "ops/feed")
ok = st.permanent \
    and reg.tier_for("lane", "ops/feed") == "flagged"
lifted = reg.rehabilitate("lane", "ops/feed",
                          decided_by="founder",
                          rationale="second chance")
for _ in range(5):
    reg.note_admitted(r)
st = reg.stats_for("lane", "ops/feed")
check("permanent-after-streak-rehab-poison",
      ok and lifted is False and st.rehabilitations == 1
      and reg.tier_for("lane", "ops/feed") == "flagged",
      f"st={st} lifted={lifted}")

# 12: permanence after a MANUAL rehabilitation + poison.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
reg.rehabilitate("lane", "ops/feed", decided_by="founder",
                 rationale="exception granted")
reg.note_poison(r)
st = reg.stats_for("lane", "ops/feed")
check("permanent-after-manual-rehab-poison",
      st.permanent
      and reg.tier_for("lane", "ops/feed") == "flagged"
      and reg.rehabilitate("lane", "ops/feed",
                           decided_by="founder",
                           rationale="again") is False,
      f"st={st}")

# 13: completion arms GB probation.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
for _ in range(5):
    reg.note_admitted(r)
check("probation-armed-on-completion",
      reg.stats_for("lane", "ops/feed").probation is True)

# 14: sidecar round-trip + a legacy sidecar (no rehab
# fields) loads with the flag still active.
tmpdir = tempfile.mkdtemp()
path = os.path.join(tmpdir, "trust.json")
reg = SourceTrustRegistry(path)
reg.note_poison(rec(id="x", owner="lane", source="ops/feed"))
reg.rehabilitate("lane", "ops/feed", decided_by="founder",
                 rationale="exception granted")
reg2 = SourceTrustRegistry(path)
legacy = os.path.join(tmpdir, "legacy.json")
with open(legacy, "w", encoding="utf-8") as f:
    json.dump({"lane\x1fops": {"held": 0, "disputes": 0,
                               "poison": 1, "queued": 0,
                               "rejected": 1}}, f)
reg3 = SourceTrustRegistry(legacy)
check("sidecar-roundtrip-and-legacy-load",
      len(reg2.rehabilitation_log()) == 1
      and reg2.tier_for("lane", "ops/feed") != "flagged"
      and reg3.tier_for("lane", "ops/feed") == "flagged",
      f"log={reg2.rehabilitation_log()} legacy="
      f"{reg3.tier_for('lane', 'ops/feed')}")

# 15: streak log entries carry the audit fields.
reg = SourceTrustRegistry()
r = rec(id="x", owner="lane", source="ops/feed")
reg.note_poison(r)
for _ in range(5):
    reg.note_admitted(r)
e = reg.rehabilitation_log()[-1]
check("streak-log-entry-fields",
      e.get("mode") == "streak" and e.get("owner") == "lane"
      and e.get("root") == "ops" and bool(e.get("at"))
      and e.get("poison") == 1 and e.get("held") == 5,
      f"entry={e}")

# ------------------------------------------------------------------
# Gate-level pins (consequences flow from tier alone)
# ------------------------------------------------------------------

# 16: GU4a recovered - rehabilitated source + one clean
# corroborator admits at 0.90.
store, path, reg = gf_store()
corroborate(store, "t16-c1", "desk", "wire/desk",
            " Confirmed at 11:15.")
flag(store, "honest-lane", "field/reports", "t16-poison")
built = earn(store, reg, "honest-lane", "field/reports",
             "t16")
out = store.write(rec(id="t16-claim", owner="honest-lane",
                      source="field/reports",
                      provenance=Provenance(confidence=0.90),
                      text=CLAIM, content=CLAIM))
check("gu4a-recovered-after-streak-rehab",
      built == 5 and out.verdict == "admitted",
      f"built={built} verdict={out.verdict}")
cleanup(store, path)

# 17: gate-earned admissions (the two-key path) advance the
# streak too - invariant: no new accrual path, both old ones
# count.
store, path, reg = gf_store()
flag(store, "honest-lane", "field/reports", "t17-poison")
corroborate(store, "t17-a1", "desk", "wire/desk",
            " Confirmed at 11:15.", claim=CLAIM)
corroborate(store, "t17-a2", "lab", "lab/results",
            " Confirmed at 12:45.", claim=CLAIM)
o1 = store.write(rec(id="t17-claim-a", owner="honest-lane",
                     source="field/reports",
                     provenance=Provenance(confidence=0.90),
                     text=CLAIM, content=CLAIM))
corroborate(store, "t17-b1", "desk", "wire/desk",
            " Confirmed at 11:15.", claim=CLAIM_B)
corroborate(store, "t17-b2", "lab", "lab/results",
            " Confirmed at 12:45.", claim=CLAIM_B)
o2 = store.write(rec(id="t17-claim-b", owner="honest-lane",
                     source="field/reports",
                     provenance=Provenance(confidence=0.90),
                     text=CLAIM_B, content=CLAIM_B))
st = reg.stats_for("honest-lane", "field/reports")
check("gate-earned-admissions-advance-streak",
      o1.verdict == "admitted" and o2.verdict == "admitted"
      and st.clean_streak == 2 and st.held == 2,
      f"o1={o1.verdict} o2={o2.verdict} st={st}")
cleanup(store, path)

# 18: a rehabilitated identity corroborates a flagged
# claimant immediately (ruling point 3 - its own GB
# probation has not cleared; no band filing made).
store, path, reg = gf_store()
corroborate(store, "t18-c1", "rehab-lane", "field/reports",
            " Confirmed at 11:15.")
flag(store, "rehab-lane", "field/reports", "t18-poison-r")
earn(store, reg, "rehab-lane", "field/reports", "t18")
corroborate(store, "t18-c2", "desk", "wire/desk",
            " Confirmed at 12:45.")
flag(store, "mallory", "insider/leak", "t18-poison")
out = store.write(rec(id="t18-claim", owner="mallory",
                      source="insider/leak",
                      provenance=Provenance(confidence=0.90),
                      text=CLAIM, content=CLAIM))
check("rehabilitated-corroborator-counts",
      reg.tier_for("rehab-lane", "field/reports") != "flagged"
      and out.verdict == "admitted",
      f"tier={reg.tier_for('rehab-lane', 'field/reports')} "
      f"verdict={out.verdict}")
cleanup(store, path)

# 19: a still-flagged corroborator does not count (D-D
# intact after the change).
store, path, reg = gf_store()
corroborate(store, "t19-c1", "tainted", "feeds/x",
            " Confirmed at 11:15.")
flag(store, "tainted", "feeds/x", "t19-poison-t")
corroborate(store, "t19-c2", "desk", "wire/desk",
            " Confirmed at 12:45.")
flag(store, "mallory", "insider/leak", "t19-poison")
out = store.write(rec(id="t19-claim", owner="mallory",
                      source="insider/leak",
                      provenance=Provenance(confidence=0.90),
                      text=CLAIM, content=CLAIM))
check("still-flagged-corroborator-excluded",
      out.verdict == "queued",
      f"verdict={out.verdict}")
cleanup(store, path)

# 20: enforcement posture - rehabilitation's GB probation
# queues the first band filing; the second admits.
store, path, reg = gf_store(shadow=False)
flag(store, "field-ops", "field/reports", "t20-poison")
earn(store, reg, "field-ops", "field/reports", "t20")
b1 = store.write(rec(id="t20-b1", owner="field-ops",
                     source="field/reports",
                     provenance=Provenance(confidence=0.75),
                     text="The night backup window moves to "
                          "01:30 per ticket L-08; verify the "
                          "vault log after the first run.",
                     content="The night backup window moves "
                             "to 01:30 per ticket L-08; verify "
                             "the vault log after the first "
                             "run."))
b2 = store.write(rec(id="t20-b2", owner="field-ops",
                     source="field/reports",
                     provenance=Provenance(confidence=0.75),
                     text="The staging freeze for release "
                          "R-12 starts Friday 18:00 per "
                          "ticket M-19; check the exception "
                          "list with the desk lead.",
                     content="The staging freeze for release "
                             "R-12 starts Friday 18:00 per "
                             "ticket M-19; check the exception "
                             "list with the desk lead."))
check("band-probation-after-rehab-enforcement",
      b1.verdict == "queued" and b2.verdict == "admitted",
      f"b1={b1.verdict} b2={b2.verdict}")
cleanup(store, path)

# 21: shadow posture records the probation would-queue but
# never consumes it.
store, path, reg = gf_store(shadow=True)
flag(store, "field-ops", "field/reports", "t21-poison")
earn(store, reg, "field-ops", "field/reports", "t21")
out = store.write(rec(id="t21-b1", owner="field-ops",
                      source="field/reports",
                      provenance=Provenance(confidence=0.75),
                      text="The night backup window moves to "
                           "01:30 per ticket L-08; verify the "
                           "vault log after the first run.",
                      content="The night backup window moves "
                              "to 01:30 per ticket L-08; "
                              "verify the vault log after the "
                              "first run."))
st = reg.stats_for("field-ops", "field/reports")
check("shadow-does-not-consume-rehab-probation",
      out.verdict == "admitted" and st.probation is True,
      f"verdict={out.verdict} probation={st.probation}")
cleanup(store, path)

# 22: control - a flagged, unrehabilitated source's band
# filing still queues in enforcement (G5c unchanged).
store, path, reg = gf_store(shadow=False)
flag(store, "field-ops", "field/reports", "t22-poison")
out = store.write(rec(id="t22-b1", owner="field-ops",
                      source="field/reports",
                      provenance=Provenance(confidence=0.75),
                      text="The night backup window moves to "
                           "01:30 per ticket L-08; verify the "
                           "vault log after the first run.",
                      content="The night backup window moves "
                              "to 01:30 per ticket L-08; "
                              "verify the vault log after the "
                              "first run."))
check("flagged-band-queues-enforcement-control",
      out.verdict == "queued", f"verdict={out.verdict}")
cleanup(store, path)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
