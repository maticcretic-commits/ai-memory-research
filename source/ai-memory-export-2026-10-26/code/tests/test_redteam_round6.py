"""Red-Team Round 6 regression tests (2026-10-21).

Pins the Round-6 defences measured by evals/redteam_round1.py
--round6 (preregistration: redteam-round6-preregistration.md):

- Authorize-then-rank (mm/storage.py search_for): the
  authorized search filters the snapshot through the
  ReadAuthorizer FIRST and ranks within the authorized subset
  alone. Round 4's rank-then-filter leaked through returned
  counts (existence oracle) and displacement of a reader's own
  planted records (rank / vocabulary oracle), and could serve
  an authorized reader an empty page while their own records
  matched below the window. The pinned property: outputs are
  a pure function of the authorized subset - identical whether
  or not restricted records exist.
- Breaker group aggregation (mm/circuit_breaker.py): alerts
  also fire per SOURCE ROOT and per OWNER over >= 2 member
  identities (Sybil dilution), with level + members on the
  alert and every member in suppressed_identities(). The
  shared-infrastructure-root tax (FU2c) is pinned as known
  behaviour, not silently tuned away.
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.access_control import ReaderContext
from mm.circuit_breaker import RetrievalShareBreaker
from mm.identity import IdentityAuthority
from mm.janitor import AccessEvent
from mm.reflect import MemoryRecord, Provenance
from mm.storage import SQLiteStore

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
                salience=0.8, provenance=Provenance(confidence=0.6))
    base.update(kw)
    r = MemoryRecord(**base)
    if not r.content:
        r.content = r.text
    if not r.created_at:
        r.created_at = 1790000000.0
    return r


def tmp_store(**kw):
    path = os.path.join(tempfile.mkdtemp(), "store.db")
    return SQLiteStore(path, **kw), path


CONF = Provenance(confidence=0.6)
RIVAL = ReaderContext(reader_id="rival-reader", owner="rival")


def _text(words, code):
    return (f"Memo {code}: the {words} review was updated; "
            f"check the ledger {code} at 09:00.")


def _oracle_store(with_restricted):
    store, path = tmp_store()
    for i in range(12):
        t = _text("harbor logistics", f"V-{i + 1}")
        store.write(rec(id=f"vis-{i + 1}", owner="rival",
                        source="rival/notes", provenance=CONF,
                        text=t, content=t))
    if with_restricted:
        for i in range(24):
            t = _text("harbor logistics quixotic", f"C-{i + 1}")
            store.write(rec(id=f"rst-{i + 1}", owner="council",
                            source="council/decisions",
                            type="decision",
                            consent_scope="council-only",
                            provenance=CONF, text=t, content=t))
    return store, path


# ---------------------------------------------------------------------------
# Authorize-then-rank: divergence immunity + utility
# ---------------------------------------------------------------------------

sa, pa = _oracle_store(False)
sb, pb = _oracle_store(True)
probes = [("harbor logistics", 10), ("harbor logistics", 2),
          ("quixotic", 10), ("harbor quixotic", 2)]
for q, lim in probes:
    a = [r.id for r in sa.search_for(RIVAL, q, limit=lim)]
    b = [r.id for r in sb.search_for(RIVAL, q, limit=lim)]
    check(f"search_for output independent of restricted set "
          f"({q!r}, limit={lim})", a == b, f"A={a} B={b}")
b_all = sb.search_for(RIVAL, "harbor logistics", limit=50)
check("restricted records never returned",
      all(r.owner == "rival" for r in b_all),
      f"{[r.id for r in b_all if r.owner != 'rival']}")
check("authorized page is full despite 24 higher-ranked "
      "restricted records", len(b_all) == 12,
      f"returned {len(b_all)}")
top10 = sb.search_for(RIVAL, "harbor logistics", limit=10)
check("recall@10 is the subset maximum (10 of 12 relevant)",
      len(top10) == 10
      and all(r.id.startswith("vis-") for r in top10))
sa.close()
sb.close()
os.unlink(pa)
os.unlink(pb)

# Bound readers still denied without a token (Round-5 path
# through the new search_for).
auth = IdentityAuthority()
store, path = tmp_store(identity_authority=auth)
tok = auth.register_reader("bound-reader")
t = _text("harbor logistics", "B-1")
store.write(rec(id="own-1", owner="field", source="field/reports",
                provenance=CONF, text=t, content=t))
bound = ReaderContext(reader_id="bound-reader", owner="field")
check("registered reader without token gets nothing",
      store.search_for(bound, "harbor logistics") == [])
got = store.search_for(bound, "harbor logistics", token=tok)
check("registered reader with token reads own lane",
      [r.id for r in got] == ["own-1"], f"{[r.id for r in got]}")
store.close()
os.unlink(path)

# ---------------------------------------------------------------------------
# Breaker group aggregation (Sybil dilution)
# ---------------------------------------------------------------------------

T0 = 1790000000.0


def _events(spec, actor="agent"):
    """spec: list of (record_id, n_events, n_distinct_queries)."""
    out = []
    t = T0
    for rid, n, nq in spec:
        for i in range(n):
            out.append(AccessEvent(
                record_id=rid, at=t, actor=actor,
                query=f"q-{rid}-{i % nq}"))
            t += 1.0
    return out


def _records(spec):
    """spec: list of (record_id, owner, source)."""
    return {rid: rec(id=rid, owner=o, source=s, provenance=CONF)
            for rid, o, s in spec}


brk = RetrievalShareBreaker()

# Root dilution: 5 owners, one root, 12 events each of 100.
recs = _records([(f"s{i}", f"sib{i}", "spamnet/feed")
                 for i in range(1, 6)]
                + [("lg", "council", "council/decisions")])
evs = _events([(f"s{i}", 12, 6) for i in range(1, 6)]
              + [("lg", 40, 6)])
alerts = brk.evaluate(evs, recs)
root_alerts = [a for a in alerts if a.level == "root"]
check("root dilution trips a root-level alert",
      len(root_alerts) == 1 and len(alerts) == 1,
      f"{alerts}")
if root_alerts:
    a = root_alerts[0]
    check("root alert names all 5 members",
          a.members == [(f"sib{i}", "spamnet") for i in range(1, 6)],
          f"{a.members}")
    check("root alert share is the combined share",
          abs(a.share - 0.6) < 1e-9, f"{a.share}")
check("suppressed set includes every diluted member",
      brk.suppressed_identities(evs, recs)
      == {(f"sib{i}", "spamnet") for i in range(1, 6)})

# Owner dilution: 1 owner, 5 roots, 12 events each of 100.
recs = _records([(f"m{i}", "mallory", f"r{i}/feed")
                 for i in range(1, 6)]
                + [("lg", "council", "council/decisions")])
evs = _events([(f"m{i}", 12, 6) for i in range(1, 6)]
              + [("lg", 40, 6)])
alerts = brk.evaluate(evs, recs)
owner_alerts = [a for a in alerts if a.level == "owner"]
check("owner dilution trips an owner-level alert",
      len(owner_alerts) == 1 and len(alerts) == 1, f"{alerts}")
if owner_alerts:
    check("owner alert members are the 5 root identities",
          owner_alerts[0].members
          == [("mallory", f"r{i}") for i in range(1, 6)],
          f"{owner_alerts[0].members}")

# Independent identities: nothing trips at any level.
recs = _records([(f"i{i}", f"o{i}", f"r{i}/x") for i in range(1, 6)]
                + [("lg", "council", "council/decisions")])
evs = _events([(f"i{i}", 12, 6) for i in range(1, 6)]
              + [("lg", 40, 6)])
check("independent identities trip nothing",
      brk.evaluate(evs, recs) == [])

# Benign owner across 3 roots, combined 0.36: nothing trips.
# (Background split across two identities, neither dominant.)
recs = _records([("b1", "solo", "a/x"), ("b2", "solo", "b/x"),
                 ("b3", "solo", "c/x"),
                 ("lg", "council", "council/decisions"),
                 ("lg2", "ops", "ops/notes")])
evs = _events([("b1", 12, 6), ("b2", 12, 6), ("b3", 12, 6),
               ("lg", 32, 6), ("lg2", 32, 6)])
check("benign owner at 0.36 combined trips nothing",
      brk.evaluate(evs, recs) == [])

# SHARED-ROOT TAX (pinned known behaviour, FU2c): two unrelated
# owners under one infrastructure root aggregate and trip.
recs = _records([("a1", "alice", "external/alice"),
                 ("b1", "bob", "external/bob"),
                 ("lg", "council", "council/decisions")])
evs = _events([("a1", 30, 6), ("b1", 30, 6), ("lg", 40, 6)])
tax = [a for a in brk.evaluate(evs, recs) if a.level == "root"]
check("shared-root tax: unrelated owners under one root DO "
      "trip a root alert (known aggregation tax)",
      len(tax) == 1 and abs(tax[0].share - 0.6) < 1e-9,
      f"{tax}")

# Identity alerts keep their Round-5 shape.
recs = _records([("p", "mallory", "spam/seo"),
                 ("lg", "council", "council/decisions")])
evs = _events([("p", 30, 7), ("lg", 10, 6)])
alerts = brk.evaluate(evs, recs)
check("single dominant identity: one identity-level alert",
      len(alerts) == 1 and alerts[0].level == "identity"
      and alerts[0].identity == ("mallory", "spam")
      and alerts[0].members == [("mallory", "spam")],
      f"{alerts}")
rep = brk.share_report(evs, recs)
check("share_report carries per_group root/owner views",
      "spamnet" not in rep["per_group"]
      and "root|spam" in rep["per_group"]
      and "owner|mallory" in rep["per_group"],
      f"{sorted(rep['per_group'])}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
