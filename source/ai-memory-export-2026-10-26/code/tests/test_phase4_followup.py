"""Phase-4 follow-up tests: HD-1 (2.1 regex pre-storage gates) and HD-2
(isotonic source-parameter enforcement).

HD-1 (head decision 2026-10-20): three cheap regex gates run BEFORE G1;
any gate fails -> rejected, never stored. Frozen spec 2.1 stands; the
G1-G7 set runs after them.

HD-2 (head decision 2026-10-20): IsotonicCalibrator.fit() takes a source
parameter and raises on anything but 'real-decisions'. No synthetic data
in calibration.

Run:  python3 tests/test_phase4_followup.py   (from the repo root)
"""

import json
import sys
import time
from datetime import datetime

sys.path.insert(0, ".")

from mm.reflect import MemoryRecord, Provenance
from mm.write_gate import WriteGate
from mm import confidence as C
from evals.isotonic_fit import IsotonicCalibrator

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" - {detail}" if detail and not cond else ""))


def rec(**kw):
    base = dict(id="r1", text="t", timestamp=datetime(2026, 10, 20),
                type="fact", epistemic_tier="observed", explicit=True,
                owner="nitesh")
    base.update(kw)
    return MemoryRecord(**base)


def pregates(text):
    g = WriteGate()
    r = rec(text=text, content=text)
    return {name: (ok, detail)
            for name, ok, detail in g._check_pregates(r)}


# --- P1 actionability -------------------------------------------------------
check("P1 verb passes", pregates(
    "Deploy the fix to prod at 14:00 after the v2.3 review.")["P1-actionability"][0])
check("P1 when-then passes", pregates(
    "When the queue depth exceeds 100 at 09:00, then page the on-call.")["P1-actionability"][0])
check("P1 instead-of passes", pregates(
    "Use sqlite instead of postgres for the v1 store; 2 shards planned.")["P1-actionability"][0])
check("P1 error-fix passes", pregates(
    "The crash in worker 7 is a regression from commit a1b2c3.")["P1-actionability"][0])
ok, detail = pregates("The sky is blue and quite pretty today.")["P1-actionability"]
check("P1 vague fails", not ok, detail)

# --- P2 specificity ----------------------------------------------------------
check("P2 two signals pass", pregates(
    "Deploy the fix to prod at 14:00 after the v2.3 review.")["P2-specificity"][0])
ok, detail = pregates(
    "Deploy the fix to prod after the review.")["P2-specificity"]
check("P2 zero signals fail", not ok, detail)
ok, detail = pregates(
    "Deploy the fix to prod at 14:00.")["P2-specificity"]
check("P2 one signal fails", not ok, detail)
# text==content duplication must not inflate the count: one unique signal
# repeated in both fields is still one signal.
ok, detail = pregates("Fix the bug in v2.3.")["P2-specificity"]
check("P2 unique counting (no text+content double count)", not ok, detail)

# --- P3 relevance -------------------------------------------------------------
for opener in ("I think we should maybe refactor",
               "Maybe the deploy will work",
               "lol this config is broken, fix at 14:00 v2"):
    ok, detail = pregates(opener)["P3-relevance"]
    check(f"P3 opener fails: {opener[:24]!r}", not ok, detail)
check("P3 normal passes", pregates(
    "Deploy the fix to prod at 14:00 after the v2.3 review.")["P3-relevance"][0])

# --- rejection audit: which gate + why ----------------------------------------
g = WriteGate()
r = rec(id="rej1", text="The sky is blue and quite pretty today.")
out = g.admit(r, {})
check("P-gate rejection verdict", out.verdict == "rejected", str(out.reasons))
gates = {e["gate"]: e for e in r.write_audit["gates"]}
check("audit names P1", "P1-actionability" in gates)
check("audit names P2", "P2-specificity" in gates)
check("audit names P3", "P3-relevance" in gates)
check("audit P1 failed", gates["P1-actionability"]["pass"] is False)
check("reasons name the gate",
      any("P1-actionability" in x or "P2-specificity" in x for x in out.reasons),
      str(out.reasons))

# --- P-stage runs before G1 ----------------------------------------------------
g2 = WriteGate()
bad = rec(id="", text="vague nothing here",
          type="bogus-type", epistemic_tier="observed")
out2 = g2.admit(bad, {})
names = [e["gate"] for e in bad.write_audit["gates"]]
check("P-failure short-circuits before G1",
      out2.verdict == "rejected" and "G1-schema" not in names
      and names[:3] == ["P1-actionability", "P2-specificity", "P3-relevance"],
      str(names))
check("P-failure rejects before schema is even checked",
      any("P1-actionability" in x for x in out2.reasons), str(out2.reasons))
# when the P-stage passes, G1 follows it in audit order
g2b = WriteGate()
good = rec(id="ok1", text="Deploy the fix to prod at 14:00 after the v2.3 review.",
           content="Deploy the fix to prod at 14:00 after the v2.3 review.")
g2b.admit(good, {})
names2 = [e["gate"] for e in good.write_audit["gates"]]
check("P-stage precedes G1 in audit order",
      names2.index("P3-relevance") < names2.index("G1-schema"), str(names2))

# --- P-gates are cheap (<50ms target; assert a safe bound) ----------------------
g3 = WriteGate()
long_text = ("Deploy the fix to prod at 14:00 after the v2.3 review; " * 200)
t0 = time.perf_counter()
for _ in range(100):
    g3._check_pregates(rec(text=long_text, content=long_text))
elapsed_ms = (time.perf_counter() - t0) * 1000 / 100
check("P-gates fast (target <50ms/record)", elapsed_ms < 50,
      f"{elapsed_ms:.2f} ms/record")
print(f"  (measured P-gate cost: {elapsed_ms:.2f} ms/record)")

# --- HD-2: source enforcement ----------------------------------------------------
pairs = [(0.9, True, 0.0)] * 40 + [(0.9, False, 0.8)] * 40
cal = IsotonicCalibrator().fit(pairs, source="real-decisions")
check("HD-2 real-decisions accepted", cal.status == "fitted")
for bad_src in ("synthetic", "bench", "harness-generated", "", None):
    try:
        IsotonicCalibrator().fit(pairs, source=bad_src)
        check(f"HD-2 refuses source={bad_src!r}", False, "no raise")
    except (ValueError, TypeError):
        check(f"HD-2 refuses source={bad_src!r}", True)
empty = IsotonicCalibrator().fit([], source="real-decisions")
check("HD-2 empty real pairs -> no-data (never invents)",
      empty.status == "no-data")

# --- HD-2 supporting: M threading through CalibrationLog --------------------------
log = C.CalibrationLog()
log.record(0.8, True, m=0.35)
log.record(0.4, False)          # m unknown -> None
log.record(0.9, True, m=0.0)
check("pairs unchanged (2-tuples)", log.pairs == [(0.8, True), (0.4, False), (0.9, True)],
      str(log.pairs))
check("m_values parallel", log.m_values == [0.35, None, 0.0], str(log.m_values))
check("triples only M-known", log.triples() == [(0.8, True, 0.35), (0.9, True, 0.0)],
      str(log.triples()))
rt = C.CalibrationLog.load_json(log.to_json())
check("to_json/load_json roundtrip", rt.pairs == log.pairs and rt.m_values == log.m_values)
old_payload = json.dumps({"min_samples": 5, "pairs": [[0.7, True]]})
rt_old = C.CalibrationLog.load_json(old_payload)
check("old payload loads with None M",
      rt_old.m_values == [None] and rt_old.triples() == [])
# the v0.4-phase-4 contract still holds: pairs stay 2-tuples
check("phase-4 pair contract intact", rt_old.pairs == [(0.7, True)])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
