"""Lane-4 real-pairs harness tests (Muse bench work, 2026-10-25).

The pair-logging PATH (mm/agent.py R-C plumbing) is pinned by
tests/test_gate_a_remediation.py and tests/test_next_steps.py.
This suite pins the OPERATOR HARNESS built on top of it
(evals/lane4_real_pairs_harness.py): the CLI is the only surface
an operator needs, it delegates every refusal to the agent, and
its verify-synthetic self-check runs one clearly labelled
synthetic pair in a temp dir without touching production files.

All CLI runs here use temp --db/--calibration paths. Nothing in
this suite opens data/memory.db.

Run:  python3 tests/test_lane4_real_pairs_harness.py
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, ".")

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f" - {detail}" if detail and not cond else ""))


HARNESS = os.path.join("evals", "lane4_real_pairs_harness.py")
TD = tempfile.mkdtemp(prefix="lane4-test-")
DB = os.path.join(TD, "memory.db")
CAL = os.path.join(TD, "calibration.json")
PROD_CAL = os.path.join("data", "calibration.json")
prod_cal_existed_before = os.path.exists(PROD_CAL)


def run_cli(*argv, expect=0):
    r = subprocess.run(
        [sys.executable, HARNESS, "--db", DB, "--calibration", CAL,
         *argv], capture_output=True, text=True)
    if expect is not None:
        check(f"cli-exit-{argv[0]}-{expect}", r.returncode == expect,
              f"rc={r.returncode} stderr={r.stderr.strip()[:200]}")
    try:
        return r.returncode, json.loads(r.stdout)
    except Exception:
        check(f"cli-json-{argv[0]}", False,
              f"stdout={r.stdout[:200]} stderr={r.stderr[:200]}")
        return r.returncode, {}


# --- status on an empty store: zero pairs, full distance to 30 -------
rc, out = run_cli("status")
st = out.get("status", {})
check("h-status-zero", st.get("pairs_with_provenance") == 0
      and st.get("log_pairs_total") == 0
      and st.get("pending_decisions") == 0
      and st.get("evaluation_unlocked") is False
      and st.get("pairs_remaining_to_unlock") == 30
      and st.get("unlock_threshold") == 30, f"status={st}")

# --- decide via CLI: pending registered, NO pair yet -------------------
rc, out = run_cli(
    "decide", "--question", "harness test question q-1?",
    "--candidate", "ship=ship it", "--candidate", "hold=hold it",
    "--prefer", "ship")
key = out.get("decision_key", "")
check("h-decide-key", key.startswith("decision-key-"),
      f"out={out}")
check("h-decide-pending-not-pair",
      out.get("status", {}).get("pending_decisions") == 1
      and out.get("status", {}).get("pairs_with_provenance") == 0,
      f"status={out.get('status')}")
check("h-decide-presentation-banded",
      out.get("presentation", {}).get("confidence_suppressed") is True
      and out.get("presentation", {}).get("confidence") is None,
      f"presentation={out.get('presentation')}")

rc, out = run_cli("pending")
check("h-pending-lists-key",
      out.get("pending_count") == 1
      and out["pending"][0]["decision_key"] == key, f"out={out}")

# --- resolve under a REFUSED source: nothing lands, stays pending -----
rc, out = run_cli("resolve", "--key", key, "--correct",
                  "--source", "acceptance", "--by", "test",
                  expect=2)
check("h-resolve-acceptance-refused",
      out.get("resolved") is False
      and out.get("status", {}).get("pairs_with_provenance") == 0
      and out.get("status", {}).get("pending_decisions") == 1,
      f"out={out}")

# --- resolve under an independent source: exactly one pair ------------
rc, out = run_cli("resolve", "--key", key, "--correct",
                  "--source", "observed-outcome", "--by", "test-suite")
check("h-resolve-lands-pair",
      out.get("resolved") is True
      and out.get("provenance", {}).get("resolution_source")
      == "observed-outcome"
      and out.get("status", {}).get("pairs_with_provenance") == 1
      and out.get("status", {}).get("pairs_remaining_to_unlock") == 29,
      f"out={out}")

# --- double resolve refused --------------------------------------------
rc, out = run_cli("resolve", "--key", key, "--correct",
                  "--source", "observed-outcome", expect=2)
check("h-double-resolve-refused",
      out.get("resolved") is False
      and out.get("status", {}).get("pairs_with_provenance") == 1,
      f"out={out}")

# --- correction via CLI: view flips, count of pairs unchanged ---------
rc, out = run_cli("correct", "--key", key, "--incorrect",
                  "--source", "verified-record", "--by", "test-suite",
                  "--note", "harness correction drill")
check("h-correct-appends-event",
      out.get("corrected") is True
      and out.get("status", {}).get("corrections") == 1
      and out.get("status", {}).get("pairs_with_provenance") == 1,
      f"out={out}")

# --- export: the evaluation view, with provenance + correction --------
exp_path = os.path.join(TD, "export.json")
rc, out = run_cli("export", "--out", exp_path)
with open(exp_path, encoding="utf-8") as f:
    exp = json.load(f)
rp = exp.get("resolved_pairs", [])
check("h-export-one-pair-corrected-view",
      len(rp) == 1 and rp[0]["decision_key"] == key
      and rp[0]["outcome"] is False
      and rp[0]["original_outcome"] is True
      and rp[0]["corrected"] is True
      and rp[0]["resolution_source"] == "observed-outcome",
      f"resolved_pairs={rp}")

# --- verify-synthetic: temp-dir end-to-end, labelled, all steps pass --
rc, out = run_cli("verify-synthetic")
check("h-verify-synthetic-passes",
      out.get("all_pass") is True
      and "SYNTHETIC" in out.get("label", "")
      and out.get("production_pairs_after_verify") == 0
      and all(s["pass"] for s in out.get("steps", [])),
      f"steps={out.get('steps')}")

# --- the suite never created a production calibration file ------------
check("h-production-untouched",
      os.path.exists(PROD_CAL) == prod_cal_existed_before,
      f"prod cal existed before={prod_cal_existed_before}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
