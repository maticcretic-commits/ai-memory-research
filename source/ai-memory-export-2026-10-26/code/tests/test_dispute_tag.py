"""Cross-shard dispute tag (v0.6 dispute_refs, DT-A) tests
(2026-10-21; design consult, ChatGPT ruling T1-T5; preregistration:
implementation/design-consults-preregistration.md; design:
implementation/dispute-tag-design.md).

dispute_refs on a record == ids of CURRENTLY OPEN cross-shard
disputes naming it (DT-A current-state pointer). Written ONLY by
the mesh (Core) through the storage lifecycle whitelist; the
dispute record + audit trail stays authoritative and the cache
is reconciled from it on restore. A failed tag write retries
once, lands in the mesh error log, and never blocks a transition.

Run:  python3 tests/test_dispute_tag.py   (from the repo root)
"""

import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.reflect import MemoryRecord, Provenance
from mm.storage import (SQLiteStore, SealedRecordError,
                        record_from_dict, record_to_dict)
from mm.shards import Shard, Core

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


T0 = datetime(2026, 10, 21, 0, 0, 0)
H = timedelta(hours=1)


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


def claim(rid, word, contradicts=None, supersedes=None, owner="council"):
    body = (f"The launch date is {word} per the 10:24 calibration "
            f"run; verify against seed 42 before closing the ticket")
    return rec(id=rid, text=body, content=body, owner=owner,
               provenance=Provenance(
                   confidence=0.6, contradicts=contradicts or [],
                   supersedes=supersedes or []))


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
# DT-1/DT-2: field, storage round-trip, dict round-trip, whitelist, migration
# ---------------------------------------------------------------------------

store, path = fresh_store()
check("dt1-field-default", rec(id="x").dispute_refs == [])
out = store.write(rec(id="dt-a", dispute_refs=["dsp-m-n"]))
check("dt1-insert-roundtrip", out.verdict == "admitted"
      and store.get("dt-a").dispute_refs == ["dsp-m-n"],
      f"verdict={out.verdict}")
d = record_to_dict(store.get("dt-a"))
check("dt1-dict-roundtrip", d["dispute_refs"] == ["dsp-m-n"]
      and record_from_dict(d).dispute_refs == ["dsp-m-n"])
store.update_metadata("dt-a", dispute_refs=["dsp-p-q", "dsp-r-s"])
check("dt2-whitelist-accepts", store.get("dt-a").dispute_refs
      == ["dsp-p-q", "dsp-r-s"])
try:
    store.update_metadata("dt-a", text="forged content")
    seal = False
except SealedRecordError:
    seal = True
check("dt2-seal-still-holds", seal)
store.close()
os.remove(path)

# Old-schema DB (records table WITHOUT dispute_refs) migrates on open.
schema = open(os.path.join(os.path.dirname(__file__), "..",
                           "mm", "storage.py")).read()
schema = schema.split('_SCHEMA = """')[1].split('"""')[0].replace(
    ",\n    dispute_refs TEXT NOT NULL DEFAULT '[]'", "")
old_path = tempfile.mktemp(suffix=".db")
conn = sqlite3.connect(old_path)
conn.executescript(schema)
conn.commit()
conn.close()
store = SQLiteStore(old_path)
cols = [r[1] for r in store._conn.execute("PRAGMA table_info(records)")]
out = store.write(rec(id="dt-old"))
check("dt1b-migration", "dispute_refs" in cols
      and out.verdict == "admitted"
      and store.get("dt-old").dispute_refs == [],
      f"cols has dispute_refs: {'dispute_refs' in cols}")
store.close()
os.remove(old_path)

# ---------------------------------------------------------------------------
# DT-3: dispute open tags BOTH records, readable shard-locally
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build", "ops"])
stores["research"].write(claim("cs-a", "March",
                               contradicts=["cs-b", "cs-c"]))
stores["build"].write(claim("cs-b", "April"))
stores["ops"].write(claim("cs-c", "May"))
opened = core.open_disputes(now=T0)
check("dt3-two-disputes-opened", len(opened) == 2,
      f"opened={[d.dispute_id for d in opened]}")
check("dt3-tag-on-b", stores["build"].get("cs-b").dispute_refs
      == ["dsp-cs-a-cs-b"])
check("dt3-tag-on-c", stores["ops"].get("cs-c").dispute_refs
      == ["dsp-cs-a-cs-c"])
check("dt3-tag-carries-both-on-a",
      stores["research"].get("cs-a").dispute_refs
      == ["dsp-cs-a-cs-b", "dsp-cs-a-cs-c"],
      f"refs={stores['research'].get('cs-a').dispute_refs}")

# DT-7: citation_status behaviour unchanged (authoritative, complete).
cs = core.citation_status("cs-a")
check("dt7-citation-status-intact", cs is not None
      and cs["dispute_id"] == "dsp-cs-a-cs-b"
      and cs["resolution"] == "open")
check("dt7-citation-none-for-clean", core.citation_status("nope") is None)

# DT-4b: founder resolve clears the tag; reopen restores it.
core.founder_decide("dsp-cs-a-cs-b", "the March date stands per "
                                   "ruling F-9", now=T0 + H)
check("dt4-founder-resolve-clears",
      stores["build"].get("cs-b").dispute_refs == []
      and stores["research"].get("cs-a").dispute_refs
      == ["dsp-cs-a-cs-c"],
      "only the resolved dispute's id leaves the shared record")
core.founder_reopen("dsp-cs-a-cs-b", "new evidence arrived",
                    now=T0 + 2 * H)
check("dt4-reopen-restores",
      stores["build"].get("cs-b").dispute_refs == ["dsp-cs-a-cs-b"])
core.founder_decide("dsp-cs-a-cs-b", "the March date stands per "
                                   "ruling F-9", now=T0 + 3 * H)

# ---------------------------------------------------------------------------
# DT-5: forged + stripped refs repaired by restore-reconcile on restart
# ---------------------------------------------------------------------------

stores["research"].write(claim("cs-d", "June"))  # in no dispute
stores["research"].update_metadata("cs-d",
                                   dispute_refs=["dsp-forged-zz"])
stores["ops"].update_metadata("cs-c", dispute_refs=[])
forged_before = stores["research"].get("cs-d").dispute_refs
stripped_before = stores["ops"].get("cs-c").dispute_refs
check("dt5-divergence-planted", forged_before == ["dsp-forged-zz"]
      and stripped_before == [],
      "precondition: the cache now disagrees with the audit trail")

core2 = Core(dispute_store=dstore)
for lane in ("research", "build", "ops"):
    core2.add_shard(Shard(lane, stores[lane]))
check("dt5-forge-repaired",
      stores["research"].get("cs-d").dispute_refs == [],
      "cs-d sits in no dispute; the forged ref must be gone")
check("dt5-strip-repaired",
      stores["ops"].get("cs-c").dispute_refs == ["dsp-cs-a-cs-c"],
      "the open dispute's tag must be restored from the audit "
      "trail")
check("dt5-resolved-stays-clear",
      stores["build"].get("cs-b").dispute_refs == [],
      "a resolved dispute's records stay untagged after restart")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# DT-4a: supersession resolution clears both tags
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build"])
stores["research"].write(claim("cs-a", "March", contradicts=["cs-b"]))
stores["build"].write(claim("cs-b", "April"))
core.open_disputes(now=T0)
check("dt4a-tagged-before-resolution",
      stores["research"].get("cs-a").dispute_refs == ["dsp-cs-a-cs-b"]
      and stores["build"].get("cs-b").dispute_refs
      == ["dsp-cs-a-cs-b"])
stores["research"].write(claim("cs-a2", "May", supersedes=["cs-a"]))
d = core.evaluate_dispute("dsp-cs-a-cs-b", now=T0 + H)
check("dt4a-supersession-clears", d.resolution == "resolved"
      and d.resolution_via == "supersession"
      and stores["research"].get("cs-a").dispute_refs == []
      and stores["build"].get("cs-b").dispute_refs == [],
      f"via={d.resolution_via}")
cleanup(stores, dstore, paths)

# ---------------------------------------------------------------------------
# DT-6: sabotaged tag write - transitions proceed, failure is logged
# ---------------------------------------------------------------------------

core, stores, shards, dstore, paths = mesh(["research", "build"])
stores["research"].write(claim("cs-a", "March", contradicts=["cs-b"]))
stores["build"].write(claim("cs-b", "April"))


def _raise(self=None, *a, **kw):
    raise RuntimeError("sabotaged update_metadata")


orig_um = stores["build"].update_metadata
stores["build"].update_metadata = _raise
opened = core.open_disputes(now=T0)
check("dt6-dispute-opens-despite-sabotage", len(opened) == 1
      and opened[0].resolution == "open",
      f"opened={len(opened)}")
check("dt6-failure-logged", any("dispute_refs" in str(e.get("error", ""))
                                for e in core.error_log),
      f"error_log={core.error_log}")
check("dt6-other-side-still-tagged",
      stores["research"].get("cs-a").dispute_refs == ["dsp-cs-a-cs-b"],
      "a one-sided tag failure must not block the other side")
core.founder_decide("dsp-cs-a-cs-b", "the March date stands per "
                                   "ruling F-9", now=T0 + H)
d = core.disputes["dsp-cs-a-cs-b"]
check("dt6-resolution-proceeds", d.resolution == "resolved"
      and d.resolution_via == "founder")
stores["build"].update_metadata = orig_um
cleanup(stores, dstore, paths)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
