"""Cross-shard resolution tests (Phase-4 follow-up spec, implemented
2026-10-21). Spec: hidden_files/implementation/
cross-shard-resolution-spec.md - the L0-L3 ladder in mm/shards.py.

Covers: L1 open + idempotence, L0 staying local, L2 corroboration,
L3a supersession (one side -> supersession, both -> moot, founder
precedence R1), L3b founder decide/reopen (verbatim, final), L3c
quorum (24h window, presence votes, tie, threshold, high-stakes
exclusion, R5 veto, resolution record through the gate), L3d
timeout (escalates, never resolves), restart survival from the
audit trail, and the audit write-failure fallback (in-memory +
error log, never silently dropped).

Run:  python3 tests/test_cross_shard.py   (from the repo root)
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.reflect import MemoryRecord, Provenance
from mm.storage import SQLiteStore
from mm.shards import Shard, Core
from mm.write_gate import GateOutcome

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


T0 = datetime(2026, 10, 21, 0, 0, 0)
H = timedelta(hours=1)
D = timedelta(days=1)


def rec(**kw):
    base = dict(
        id="r1",
        text="Kappa was frozen at 0.25 for Phase 2 per the 10:24 "
             "calibration run; verify seed 42 before closing",
        content="Kappa was frozen at 0.25 for Phase 2 per the "
                "10:24 calibration run; verify seed 42 before closing",
        timestamp=datetime(2026, 10, 20), type="fact",
        epistemic_tier="observed", explicit=True, owner="council",
        gathered_how="bench", salience=0.8,
        provenance=Provenance(confidence=0.6))
    base.update(kw)
    return MemoryRecord(**base)


def claim(rid, word, contradicts=None, owner="council"):
    body = (f"The launch date is {word} per the 10:24 calibration "
            f"run; verify against seed 42 before closing the ticket")
    return rec(id=rid, text=body, content=body, owner=owner,
               provenance=Provenance(
                   confidence=0.6, contradicts=contradicts or []))


def fresh_store():
    path = tempfile.mktemp(suffix=".db")
    return SQLiteStore(path), path


def mesh(lanes):
    stores, shards, paths = {}, {}, []
    for lane in lanes:
        stores[lane], p = fresh_store()
        paths.append(p)
        shards[lane] = Shard(lane, stores[lane])
    dstore, dpath = fresh_store()
    paths.append(dpath)
    core = Core(dispute_store=dstore)
    for lane in lanes:
        core.add_shard(shards[lane])
    return core, stores, shards, dstore, paths


def cleanup(stores, dstore, paths):
    for s in list(stores.values()) + [dstore]:
        try:
            s.close()
        except Exception:
            pass
    for p in paths:
        if os.path.exists(p):
            os.remove(p)


# ---------------------------------------------------------------------------
# A: L1 open + idempotence; L0 (intra-shard) stays local; citation status
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build"])
stores["research"].write(claim("cs-a", "March", contradicts=["cs-b"]))
stores["build"].write(claim("cs-b", "April"))
# an intra-shard declared contradiction: L0, the local flow's business
stores["research"].write(claim("loc-1", "May", contradicts=["loc-2"]))
stores["research"].write(claim("loc-2", "June"))

opened = core.open_disputes(now=T0)
check("l1-dispute-opened", len(opened) == 1
      and opened[0].dispute_id == "dsp-cs-a-cs-b",
      f"opened={[d.dispute_id for d in opened]}")
d = opened[0]
check("l1-dispute-fields", d.a_lane == "research" and d.b_lane == "build"
      and d.resolution == "open" and d.resolution_via == "none"
      and d.escalation == "none" and d.detected_at == T0.isoformat(),
      f"{d}")
check("l0-local-pair-not-a-dispute", len(core.disputes) == 1
      and core.citation_status("loc-1") is None,
      f"disputes={list(core.disputes)}")
audits = [r for r in dstore.all_records().values()
          if r.id.startswith("dsp-cs-a-cs-b-audit-")]
check("l1-audit-trail-written", len(audits) >= 1 and not core.error_log,
      f"audits={len(audits)} errors={core.error_log}")
n_trans = len(d.transitions)
again = core.open_disputes(now=T0 + H)
check("l1-idempotent-redetect", len(core.disputes) == 1
      and len(d.transitions) == n_trans
      and d.last_seen_at == (T0 + H).isoformat(),
      f"transitions {n_trans} -> {len(d.transitions)}")
cs = core.citation_status("cs-a")
check("citation-status-open", cs is not None
      and cs["dispute_id"] == "dsp-cs-a-cs-b"
      and cs["resolution"] == "open",
      f"{cs}")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# B: L2 corroboration + L3c quorum resolves (with the 24h window)
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build", "ops"])
stores["research"].write(claim("cs-a", "March", contradicts=["cs-b"]))
stores["build"].write(claim("cs-b", "April"))
stores["ops"].write(claim("cs-a-copy", "March"))  # exact dup of a, 3rd shard
core.open_disputes(stakes="low", now=T0)
d = core.disputes["dsp-cs-a-cs-b"]
check("l2-corroboration-gathered",
      {"shard": "ops", "side": "a", "record_id": "cs-a-copy"}
      in d.corroboration,
      f"corroboration={d.corroboration}")
core.evaluate_dispute(d.dispute_id, now=T0 + H)
check("quorum-window-24h", d.resolution == "open"
      and d.quorum_snapshot is None,
      f"resolution={d.resolution} snapshot={d.quorum_snapshot}")
core.evaluate_dispute(d.dispute_id, now=T0 + 25 * H)
check("quorum-resolves", d.resolution == "resolved"
      and d.resolution_via == "quorum" and d.resolved_at is not None,
      f"{d.resolution}/{d.resolution_via}")
check("quorum-snapshot-recorded",
      d.quorum_snapshot is not None
      and d.quorum_snapshot["counts"] == {"a": 2, "b": 1, "abstain": 0}
      and d.quorum_snapshot["votes"] == {"research": "a", "build": "b",
                                          "ops": "a"}
      and d.quorum_snapshot["veto"] is None,
      f"snapshot={d.quorum_snapshot and d.quorum_snapshot['counts']}")
check("quorum-resolution-record-admitted",
      "dsp-cs-a-cs-b-resolution" in dstore.all_records(),
      f"core-lane ids={sorted(dstore.all_records())[:6]}...")
check("quorum-no-errors", not core.error_log, f"{core.error_log}")

# I: restart survival - a fresh Core over the same audit trail restores state
core2 = Core(dispute_store=dstore)
for lane in ("research", "build", "ops"):
    core2.add_shard(shards[lane])
restored = core2.disputes.get("dsp-cs-a-cs-b")
check("restart-restores-resolution", restored is not None
      and restored.resolution == "resolved"
      and restored.resolution_via == "quorum",
      f"{restored}")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# C: quorum tie and below-threshold both stay open (4 shards)
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(
    ["research", "build", "ops", "qa"])
stores["research"].write(claim("t-a", "March", contradicts=["t-b"]))
stores["build"].write(claim("t-b", "April"))
stores["research"].write(claim("u-a", "May", contradicts=["u-b"]))
stores["build"].write(claim("u-b", "June"))
stores["ops"].write(claim("u-a-copy", "May"))
stores["qa"].write(claim("qa-note", "July"))
core.open_disputes(now=T0)
dt_ = core.disputes["dsp-t-a-t-b"]
du = core.disputes["dsp-u-a-u-b"]
core.evaluate_dispute(dt_.dispute_id, now=T0 + 25 * H)
check("quorum-tie-no-resolution", dt_.resolution == "open"
      and dt_.quorum_snapshot["counts"] == {"a": 1, "b": 1, "abstain": 2},
      f"counts={dt_.quorum_snapshot and dt_.quorum_snapshot['counts']}")
core.evaluate_dispute(du.dispute_id, now=T0 + 25 * H)
check("quorum-below-threshold", du.resolution == "open"
      and du.quorum_snapshot["counts"] == {"a": 2, "b": 1, "abstain": 1},
      f"counts={du.quorum_snapshot and du.quorum_snapshot['counts']} "
      f"(leader 2 < floor(4/2)+1 = 3)")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# D: high stakes - quorum never applies, not even attempted
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build", "ops"])
stores["research"].write(claim("h-a", "March", contradicts=["h-b"]))
stores["build"].write(claim("h-b", "April"))
stores["ops"].write(claim("h-a-copy", "March"))
core.open_disputes(stakes="high", now=T0)
d = core.disputes["dsp-h-a-h-b"]
core.evaluate_dispute(d.dispute_id, now=T0 + 25 * H)
check("high-stakes-no-quorum", d.resolution == "open"
      and d.quorum_snapshot is None,
      f"resolution={d.resolution} snapshot={d.quorum_snapshot}")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# E: R5 veto - a declared contradiction naming the leading side blocks quorum
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build", "ops"])
stores["research"].write(claim("v-a", "March", contradicts=["v-b"]))
stores["build"].write(claim("v-b", "April"))
stores["ops"].write(claim("v-a-copy", "March"))
# a third record declares a contradiction naming the a-side carrier
stores["build"].write(claim("v-veto", "August", contradicts=["v-a-copy"]))
core.open_disputes(now=T0)
d = core.disputes["dsp-v-a-v-b"]
core.evaluate_dispute(d.dispute_id, now=T0 + 25 * H)
check("veto-blocks-quorum", d.resolution == "open"
      and d.quorum_snapshot is not None
      and d.quorum_snapshot["veto"] is not None
      and d.quorum_snapshot["veto"]["record_id"] == "v-veto",
      f"veto={d.quorum_snapshot and d.quorum_snapshot['veto']}")
check("veto-transition-recorded",
      any(t["authority"] == "quorum veto (L3c/R5)"
          for t in d.transitions),
      f"authorities={[t['authority'] for t in d.transitions]}")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# F: L3a supersession - one side, both sides (moot), founder precedence (R1)
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build"])
stores["research"].write(claim("s-a", "March", contradicts=["s-b"],
                               owner="research"))
stores["build"].write(claim("s-b", "April", owner="build"))
core.open_disputes(now=T0)
d = core.disputes["dsp-s-a-s-b"]
sup = rec(id="s-a-v2",
          text="Correction: the launch date is May per the 10:24 "
               "calibration run; verify seed 42 instead of the "
               "March note before closing",
          content="Correction: the launch date is May per the "
                  "10:24 calibration run; verify seed 42 instead "
                  "of the March note before closing",
          provenance=Provenance(confidence=0.6, supersedes=["s-a"]))
shards["research"].write(sup)
core.evaluate_dispute(d.dispute_id, now=T0 + H)
check("supersession-resolves", d.resolution == "resolved"
      and d.resolution_via == "supersession",
      f"{d.resolution}/{d.resolution_via}")
check("superseded-record-closed-locally",
      stores["research"].get("s-a").tier == "archive",
      f"tier={stores['research'].get('s-a').tier}")

stores["research"].write(claim("m-a", "July", contradicts=["m-b"],
                               owner="research"))
stores["build"].write(claim("m-b", "August", owner="build"))
core.open_disputes(now=T0)
dm = core.disputes["dsp-m-a-m-b"]
for lane, old, new in (("research", "m-a", "m-a-v2"),
                       ("build", "m-b", "m-b-v2")):
    body = (f"Correction {new}: the earlier note is withdrawn per "
            f"the 10:24 calibration run; verify seed 42 instead")
    shards[lane].write(rec(
        id=new, text=body, content=body,
        provenance=Provenance(confidence=0.6, supersedes=[old])))
core.evaluate_dispute(dm.dispute_id, now=T0 + H)
check("both-sides-superseded-moot", dm.resolution == "resolved"
      and dm.resolution_via == "moot",
      f"{dm.resolution}/{dm.resolution_via}")

# R1: a founder ruling already stands; a later supersession is an
# ordinary record and does NOT reopen or change the dispute.
stores["research"].write(claim("f-a", "September",
                               contradicts=["f-b"], owner="research"))
stores["build"].write(claim("f-b", "October", owner="build"))
core.open_disputes(now=T0)
df = core.disputes["dsp-f-a-f-b"]
core.founder_decide(df.dispute_id, "Side a stands.", now=T0 + H)
body = ("Correction f-a-v2: the March note is withdrawn per the "
        "10:24 calibration run; verify seed 42 instead")
shards["research"].write(rec(
    id="f-a-v2", text=body, content=body,
    provenance=Provenance(confidence=0.6, supersedes=["f-a"])))
core.evaluate_dispute(df.dispute_id, now=T0 + 2 * H)
check("founder-ruling-survives-later-supersession",
      df.resolution == "resolved" and df.resolution_via == "founder",
      f"{df.resolution}/{df.resolution_via}")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# G: L3b founder decide / reopen - verbatim, final, explicit
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build"])
stores["research"].write(claim("g-a", "March", contradicts=["g-b"]))
stores["build"].write(claim("g-b", "April"))
core.open_disputes(now=T0)
d = core.disputes["dsp-g-a-g-b"]
RULING = "RULING-XYZ: side b stands; the April date is authoritative."
core.founder_decide(d.dispute_id, RULING, now=T0 + H)
check("founder-decides", d.resolution == "resolved"
      and d.resolution_via == "founder",
      f"{d.resolution}/{d.resolution_via}")
last = d.transitions[-1]
check("founder-ruling-verbatim", last["rationale"] == RULING
      and last["decider"] == "nitesh"
      and last["authority"] == "founder decision (L3b)",
      f"{last}")
raised = False
try:
    core.founder_decide(d.dispute_id, "second ruling", now=T0 + 2 * H)
except ValueError:
    raised = True
check("founder-decide-on-resolved-raises", raised, "no ValueError")
core.founder_reopen(d.dispute_id, "New evidence in the 11:02 run.",
                    now=T0 + 3 * H)
check("founder-reopens", d.resolution == "open"
      and d.resolution_via == "none" and d.resolved_at is None,
      f"{d.resolution}/{d.resolution_via}")
core.founder_decide(d.dispute_id, RULING, now=T0 + 4 * H)
core.evaluate_dispute(d.dispute_id, now=T0 + 8 * D)
check("resolved-dispute-never-times-out", d.resolution == "resolved"
      and d.escalation == "none",
      f"{d.resolution} esc={d.escalation}")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# H: L3d timeout - 2-shard mesh (quorum unreachable), escalates, never resolves
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build"])
stores["research"].write(claim("h1-a", "March", contradicts=["h1-b"]))
stores["build"].write(claim("h1-b", "April"))
core.open_disputes(now=T0)
d = core.disputes["dsp-h1-a-h1-b"]
core.evaluate_dispute(d.dispute_id, now=T0 + 25 * H)
check("two-shard-quorum-unreachable", d.resolution == "open"
      and d.escalation == "none",
      f"counts={d.quorum_snapshot and d.quorum_snapshot['counts']} "
      f"(threshold floor(2/2)+1 = 2, votes split 1-1)")
core.evaluate_dispute(d.dispute_id, now=T0 + 8 * D)
check("timeout-escalates-never-resolves", d.resolution == "open"
      and d.escalation == "timeout",
      f"{d.resolution} esc={d.escalation}")
check("timeout-in-founder-queue",
      [q.dispute_id for q in core.founder_queue()] == [d.dispute_id],
      f"queue={[q.dispute_id for q in core.founder_queue()]}")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# J: audit write failure - dispute survives in memory + error log
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build"])
stores["research"].write(claim("j-a", "March", contradicts=["j-b"]))
stores["build"].write(claim("j-b", "April"))
dstore.write = lambda record, token=None: GateOutcome(
    verdict="rejected", reasons=["test-injected refusal"],
    record=record)
core.open_disputes(now=T0)
d = core.disputes.get("dsp-j-a-j-b")
check("audit-failure-dispute-survives", d is not None
      and d.resolution == "open",
      f"{d}")
check("audit-failure-logged-not-silent", len(core.error_log) >= 1
      and all(e["dispute_id"] == "dsp-j-a-j-b"
              for e in core.error_log),
      f"error_log={core.error_log}")
cleanup(stores, dstore, paths)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
