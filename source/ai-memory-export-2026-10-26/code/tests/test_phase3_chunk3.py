"""Phase-3 chunk-3 tests: SQLite storage + the seal, janitor wiring,
consolidation probe invariants, gate-(b) metric helpers, trace re-fit.

Run:  python3 tests/test_phase3_chunk3.py   (from the repo root)
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, ".")

from mm.reflect import MemoryRecord, Provenance
from mm.storage import (
    SQLiteStore, SealedRecordError, record_from_dict, record_to_dict,
    METADATA_WHITELIST,
)
from mm.janitor import Janitor, ACTIVE_TO_COOLED_S
from mm.consolidation import ConsolidationDaemon
from evals.consolidation_probe import fixture_store, score_probes
from evals.gate_b_rerun import murphy, interaction
from evals.trace_refit import fit_logistic, evaluate, OLD_COEFS
from evals.isotonic_fit import IsotonicCalibrator

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


def rec(**kw):
    base = dict(id="r1", text="Kappa was frozen at 0.25 for Phase 2.",
                content="Kappa was frozen at 0.25 for Phase 2.",
                timestamp=datetime(2026, 10, 16), type="decision",
                epistemic_tier="observed", explicit=True, owner="council",
                consent_scope="project",
                provenance=Provenance(confidence=0.95))
    base.update(kw)
    r = MemoryRecord(**base)
    if not r.created_at:
        r.created_at = 1792000000.0
    return r


def tmp_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return SQLiteStore(path), path


def corr(rid, text):
    # G5b (Red-Team Round 2): a lone claim at confidence >= 0.80 queues
    # without a disjoint-origin corroborator. These fixtures seed the
    # wiki mirror's copy of a claim (different owner AND source root,
    # confidence below the threshold so it lands on its own) so the
    # sections below exercise the store paths they were written for.
    return rec(id=rid, owner="wiki-mirror", source="wiki/run",
               text=text, content=text,
               provenance=Provenance(confidence=0.6))


KAPPA = "Kappa was frozen at 0.25 for Phase 2."
REWRITE = ("Rewrite the r1 record body under the same id at 14:02; "
           "the store must refuse the duplicate id write.")
CORRECTED = ("Kappa corrected to 0.30 after review; update the controller "
             "config v0.5 and re-run gate-b at 14:02.")


# ---------------------------------------------------------------------------
# Storage: gate-mediated writes + round-trip
# ---------------------------------------------------------------------------

store, path = tmp_store()
store.write(corr("corr-kappa", KAPPA))
store.write(corr("corr-rewrite", REWRITE))
store.write(corr("corr-corrected", CORRECTED))
out = store.write(rec())
check("store admits clean record", out.verdict == "admitted", out.verdict)
got = store.get("r1")
check("round-trip content", got is not None and got.text.startswith("Kappa"))
check("round-trip provenance",
      got.provenance.confidence == 0.95 and got.epistemic_tier == "observed")
check("sealed audit persisted", got.write_audit.get("immutable") is True)
check("dict serialization round-trip",
      record_from_dict(record_to_dict(got)).text == got.text)

# Seal: content mutation refused, metadata allowed, re-insert refused.
try:
    store.update_metadata("r1", text="tampered text")
    check("seal refuses content update", False)
except SealedRecordError:
    check("seal refuses content update", True)
try:
    store.update_metadata("r1", salience=0.1)
    check("seal refuses salience update", False)
except SealedRecordError:
    check("seal refuses salience update", True)
store.update_metadata("r1", tier="cooled", access_count=3)
check("metadata whitelist applies",
      store.get("r1").tier == "cooled" and store.get("r1").access_count == 3)
check("whitelist is lifecycle-only",
      # Benchmark Wave 2 (B2 spec, voted 2026-10-20): invalid_at
      # joined the whitelist - the spec's one sanctioned post-seal
      # write (supersession stamps when the loser stopped being
      # in force; lifecycle-class like tier, never content).
      # Design consult (2026-10-21, ChatGPT ruling T3): dispute_refs
      # joined on the same lifecycle-class basis - the mesh's
      # dispute tag cache (records THAT the record is currently
      # contested, never what it says); the pin is amended, not
      # loosened: no unruled field may join this set.
      METADATA_WHITELIST == {"tier", "last_accessed", "access_count",
                             "decay_score", "superseded_with_replacement",
                             "invalid_at", "dispute_refs"})
try:
    store.write(rec(text="Rewrite the r1 record body under the same id at 14:02; "
                    "the store must refuse the duplicate id write.",
                    content="Rewrite the r1 record body under the same id at 14:02; "
                    "the store must refuse the duplicate id write."))
    check("duplicate id write is not admitted", False)
except SealedRecordError:
    check("re-insert of existing id raises (sealed)", True)

# Correction = new record with supersedes; loser closed via whitelist.
out2 = store.write(rec(
    id="r2", text="Kappa corrected to 0.30 after review; update the controller "
    "config v0.5 and re-run gate-b at 14:02.",
    content="Kappa corrected to 0.30 after review; update the controller "
    "config v0.5 and re-run gate-b at 14:02.",
    provenance=Provenance(confidence=0.9, supersedes=["r1"])))
check("correction admitted as new record", out2.verdict == "admitted")
loser = store.get("r1")
check("superseded loser archived by gate side effect",
      loser.tier == "archive" and loser.superseded_with_replacement is True)
check("original text preserved verbatim",
      loser.text.startswith("Kappa was frozen at 0.25"))

# Secrets rejected and never persisted anywhere (incl. gate log).
sec = rec(id="sec1", text="Rotate the api_key: hunter2hunter2 value in vault.yaml "
          "v3; deploy the replacement at 14:00 and verify the login flow.",
          content="Rotate the api_key: hunter2hunter2 value in vault.yaml "
          "v3; deploy the replacement at 14:00 and verify the login flow.")
out3 = store.write(sec)
check("secret write rejected", out3.verdict == "rejected")
check("secret not in records", "sec1" not in store)
check("secret string nowhere in gate log",
      all("hunter2" not in " ".join(e["reasons"]) for e in store.gate_log()))

# Uncorroborated inferred -> persisted review queue, not records.
inf = rec(id="inf1", text="The user probably likes tea in the morning; serve it "
          "at 07:30 before the 09:00 standup.",
          content="The user probably likes tea in the morning; serve it "
          "at 07:30 before the 09:00 standup.",
          type="preference", epistemic_tier="inferred", explicit=False,
          consent_scope="", gathered_how="chat-inference",
          provenance=Provenance(confidence=0.6))
out4 = store.write(inf)
check("uncorroborated inferred queued", out4.verdict == "queued")
check("queued record not landed", "inf1" not in store)
pend = store.pending_review()
check("review queue persisted", len(pend) == 1
      and pend[0]["record"].id == "inf1")
check("review resolves", store.resolve_review("inf1", "drop") is True
      and store.pending_review() == [])
# 8 writes + 1 extra row: the re-insert attempt logs BOTH the gate's
# verdict and the seal's refusal - the full accounting, nothing hidden.
# (The 3 corroborator seedings above are writes too, and they are
# counted: the log's completeness is the assertion, not the number 6.)
check("gate log has all outcomes", len(store.gate_log()) == 9,
      str(len(store.gate_log())))
check("sealed refusal logged truthfully",
      any(e["verdict"] == "rejected-sealed" for e in store.gate_log()))

# Exact duplicate through the store: rejected, original access refreshed.
before = store.get("r2").access_count
dup = rec(id="r3", text="Kappa corrected to 0.30 after review; update the controller "
          "config v0.5 and re-run gate-b at 14:02.",
          content="Kappa corrected to 0.30 after review; update the controller "
          "config v0.5 and re-run gate-b at 14:02.",
          provenance=Provenance(confidence=0.9))
out5 = store.write(dup)
check("exact duplicate rejected via store", out5.verdict == "rejected")
check("duplicate refreshed original access count",
      store.get("r2").access_count == before + 1)

# ---------------------------------------------------------------------------
# Janitor wiring against the real store
# ---------------------------------------------------------------------------

store2, path2 = tmp_store()
now = 1792000000.0 + 20 * 86400  # 20 days after creation
old = rec(id="old1", created_at=1792000000.0, last_accessed=1792000000.0)
store2.write(corr("corr-kappa2", KAPPA))
store2.write(old)
store2.log_access("old1", 1792000000.0 + 86400)
jan = store2.load_janitor()
check("access events persisted and reload", len(jan.access_log) == 1)
dry = store2.run_janitor(jan, now, dry_run=True)
check("janitor dry-run leaves store untouched",
      store2.get("old1").tier == "active" and len(dry.ops) > 0)
live = store2.run_janitor(jan, now, dry_run=False)
check("janitor live run migrates idle active -> cooled",
      store2.get("old1").tier == "cooled",
      f"ops={[o.op for o in live.ops]}")
hl = store2.load_janitor().estimate_half_life_for(store2.all_records())
check("half-life honest on thin data",
      all(v["status"] == "insufficient-data" for v in hl.values()),
      str(hl))
store.close()
store2.close()
os.unlink(path)
os.unlink(path2)

# ---------------------------------------------------------------------------
# Consolidation probe invariants (the harness's own fixture)
# ---------------------------------------------------------------------------

daemon = ConsolidationDaemon()
check("daemon default off", daemon.enabled is False)
try:
    daemon.run(fixture_store())
    check("disabled daemon raises", False)
except RuntimeError:
    check("disabled daemon raises", True)
daemon.enable()
fx = fixture_store()
tiers_before = {rid: r.epistemic_tier for rid, r in fx.items()}
pre = score_probes(fx)
diff = daemon.run(fx, probe=["kappa lambda controller"], dry_run=False)
post = score_probes(fx)
tiers_after = {rid: r.epistemic_tier for rid, r in fx.items()}
check("probe: duplicate merged", ("k1", "k1-dup") in diff.merged
      and "k1-dup" not in fx)
check("probe: superseded closed", "k0-stale" in diff.closed
      and fx["k0-stale"].tier == "archive")
check("probe: no tier promotion",
      daemon.assert_no_tier_promotion(tiers_before, tiers_after) == [])
mean = lambda rows, k: sum(r[k] for r in rows) / len(rows)
check("probe: precision does not regress",
      mean(post, "precision_at_3") >= mean(pre, "precision_at_3"),
      f"{mean(pre, 'precision_at_3')} -> {mean(post, 'precision_at_3')}")
check("probe: recall does not regress",
      mean(post, "recall_at_3") >= mean(pre, "recall_at_3"))

# ---------------------------------------------------------------------------
# Gate-(b) metric helpers
# ---------------------------------------------------------------------------

check("interaction arithmetic",
      interaction({"k1l1": 0.4, "k1l0": 0.3, "k0l1": 0.2, "k0l0": 0.25})
      == 0.4 - 0.3 - 0.2 + 0.25)
m = murphy([0.9, 0.8, 0.2, 0.1], [True, True, False, False])
check("murphy identity (rel - res + unc = brier, within binning slack)",
      abs(m["reliability"] - m["resolution"] + m["uncertainty"]
          - m["brier"]) < 0.01, str(m))
m2 = murphy([0.99] * 10, [True] * 5 + [False] * 5)
check("murphy finds overconfidence in reliability",
      m2["reliability"] > 0.2, str(m2))

# ---------------------------------------------------------------------------
# Trace re-fit machinery + isotonic on chunk-3-style pairs
# ---------------------------------------------------------------------------

rows = ([{"feats": [0.3, 0.9, 2.0, 3.0, 1.0], "correct": True}] * 40
        + [{"feats": [0.02, 0.2, 0.5, 12.0, 1.0], "correct": False}] * 40)
beta = fit_logistic(rows)
ev_new = evaluate(rows, beta)
ev_old = evaluate(rows, OLD_COEFS)
check("irls fit separates synthetic traces",
      ev_new["brier"] < ev_old["brier"], f"{ev_old} vs {ev_new}")
check("irls coefficients finite",
      all(abs(b) < 1e4 for b in beta))

pairs = ([(0.9, True, 0.85)] * 15 + [(0.9, False, 0.85)] * 15
         + [(0.4, False, 0.85)] * 20
         + [(0.8, True, 0.0)] * 40 + [(0.3, False, 0.0)] * 10)
cal = IsotonicCalibrator().fit(pairs, source="real-decisions")
check("isotonic fits chunk-3-style pairs", cal.status == "fitted")
check("isotonic high band corrects overconfidence",
      cal.calibrate(0.9, 0.85) < 0.9)
check("isotonic report declares borrowing",
      cal.report()["low"]["borrowed"] is True)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
