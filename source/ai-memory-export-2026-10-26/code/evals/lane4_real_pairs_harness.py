"""lane4_real_pairs_harness - operator harness for REAL decision pairs.

Lane 4 (Muse bench work), 2026-10-25. Spec:
implementation/lane4-real-pairs-spec-2026-10-25.md.

WHAT THIS IS
The pair-logging PATH already exists in mm/agent.py (gate-(a)
remediation R-C, 2026-10-21): decide() registers a pending decision,
note_decision_outcome() lands a real (confidence, outcome, M) pair
only under a named independent resolution source, resolved_pairs()
is the evaluation view, and calibration_status() counts toward the
PAIR_EVALUATION_UNLOCK of 30. What did NOT exist is an operator
surface: a ready-to-run command that a human (or a scheduled job
driven by one) can use to make a production decision, see what is
pending, resolve a decision when its outcome is independently
known, and read the count toward n>=30 - without writing ad-hoc
Python against MemoryAgent internals. This harness is that surface.
It adds NO new logging semantics: every command delegates to the
existing agent methods and their refusals.

COMMANDS
  decide            run one production decision; registers it as
                    PENDING (no pair exists until it is resolved)
  pending           list decisions awaiting an observed outcome
  resolve           resolve one pending decision with its
                    independently resolved outcome -> lands ONE pair
  correct           append a correction event to a resolved pair
  status            pair counts, pending count, distance to the
                    n>=30 evaluation unlock (unlock = EVALUATION
                    only; nothing is ever fitted automatically)
  export            write resolved_pairs() + status to a JSON file
  verify-synthetic  end-to-end self-check in a TEMP directory with
                    ONE clearly labelled synthetic pair; touches no
                    production file; proves the path, counts as
                    NOTHING toward n>=30

USAGE
  python3 evals/lane4_real_pairs_harness.py status
  python3 evals/lane4_real_pairs_harness.py decide \
      --question "ship the v2 build on Friday per plan P-7?" \
      --candidate ship="ship Friday" --candidate hold="hold a week" \
      --prefer ship --stakes medium
  python3 evals/lane4_real_pairs_harness.py pending
  python3 evals/lane4_real_pairs_harness.py resolve \
      --key decision-key-00001 --correct \
      --source observed-outcome --by nitesh
  python3 evals/lane4_real_pairs_harness.py export --out pairs.json

Defaults: --db data/memory.db (the production store),
--calibration <db dir>/calibration.json (the MemoryAgent default).
Every command prints one JSON object on stdout. Exit codes:
0 ok, 2 refused (the underlying agent refused; nothing was
recorded), 1 usage / runtime error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from mm.agent import (  # noqa: E402
    MemoryAgent, PAIR_EVALUATION_UNLOCK, REFUSED_RESOLUTION_SOURCES)
from mm.decision import Candidate, Preference  # noqa: E402
from mm.storage import SQLiteStore  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(REPO_ROOT, "data", "memory.db")

SYNTHETIC_LABEL = ("SYNTHETIC - verification only, NOT a production "
                   "real pair; counts as 0 toward n>=30")


def make_agent(db: str, calibration: str | None) -> MemoryAgent:
    store = SQLiteStore(db)
    if calibration:
        return MemoryAgent(store, calibration_path=calibration)
    return MemoryAgent(store)


def status_dict(agent: MemoryAgent) -> dict:
    st = dict(agent.calibration_status())
    st["unlock_threshold"] = PAIR_EVALUATION_UNLOCK
    st["pairs_remaining_to_unlock"] = max(
        0, PAIR_EVALUATION_UNLOCK - st["pairs_with_provenance"])
    st["counting_rule"] = (
        "only pairs_with_provenance count toward the unlock: pairs "
        "landed via resolve (the pending-decision path) with a named "
        "independent resolution source. Legacy unkeyed pairs count "
        "in log_pairs_total only.")
    return st


def emit(obj: dict, code: int = 0) -> int:
    print(json.dumps(obj, indent=2, sort_keys=True))
    return code


def refuse_reason(agent: MemoryAgent, key: str, source) -> str:
    if not agent.pair_recording_enabled:
        return "pair recording is disabled (consent control is off)"
    if (source is None
            or str(source).strip().lower()
            in REFUSED_RESOLUTION_SOURCES):
        return ("resolution source refused: acceptance / self-"
                "assessment / assumed / silence never ground a pair")
    if key not in {p["decision_key"] for p in agent.pending_decisions()}:
        return "unknown or already-resolved decision_key"
    return "refused by agent (no reason isolated)"


def cmd_decide(args) -> int:
    cands = []
    for spec in args.candidate:
        cid, _, desc = spec.partition("=")
        cands.append(Candidate(id=cid.strip(),
                               description=desc.strip() or cid.strip()))
    prefs = [Preference(candidate_id=p, kind="better", weight=1.0,
                        source_module="lane4-harness")
             for p in (args.prefer or [])]
    agent = make_agent(args.db, args.calibration)
    result = agent.decide(args.question, cands, prefs,
                          stakes=args.stakes)
    return emit({
        "decision_key": result["decision_key"],
        "presentation": agent.present(result),
        "audit": {
            "selected_id": result["selected_id"],
            "impasse": result["impasse"],
            "confidence_raw_audit_only": result["confidence"],
            "conflict_score_m": result["conflict_score"],
            "policy_score": result["policy_score"],
        },
        "state": "PENDING - no pair exists until resolve is called "
                 "with an independently resolved outcome",
        "status": status_dict(agent),
    })


def cmd_pending(args) -> int:
    agent = make_agent(args.db, args.calibration)
    pend = agent.pending_decisions()
    return emit({"pending_count": len(pend), "pending": pend,
                 "status": status_dict(agent)})


def cmd_resolve(args) -> int:
    agent = make_agent(args.db, args.calibration)
    ok = agent.note_decision_outcome(
        args.key, bool(args.correct),
        resolution_source=args.source, resolved_by=args.by)
    if not ok:
        return emit({"resolved": False, "decision_key": args.key,
                     "reason": refuse_reason(agent, args.key,
                                             args.source),
                     "status": status_dict(agent)}, code=2)
    return emit({"resolved": True, "decision_key": args.key,
                 "provenance": agent.pair_provenance(args.key),
                 "status": status_dict(agent)})


def cmd_correct(args) -> int:
    agent = make_agent(args.db, args.calibration)
    ok = agent.note_decision_correction(
        args.key, bool(args.correct),
        resolution_source=args.source, resolved_by=args.by,
        note=args.note or "")
    if not ok:
        return emit({"corrected": False, "decision_key": args.key,
                     "reason": ("refused: key must name an already-"
                                "resolved pair and the source must "
                                "not be a refused source"),
                     "status": status_dict(agent)}, code=2)
    return emit({"corrected": True, "decision_key": args.key,
                 "corrections": agent.decision_corrections(args.key),
                 "status": status_dict(agent)})


def cmd_status(args) -> int:
    agent = make_agent(args.db, args.calibration)
    return emit({"db": args.db,
                 "calibration_path": agent.calibration_path,
                 "status": status_dict(agent)})


def cmd_export(args) -> int:
    agent = make_agent(args.db, args.calibration)
    payload = {"exported_from": "lane4_real_pairs_harness",
               "status": status_dict(agent),
               "resolved_pairs": agent.resolved_pairs()}
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, indent=2, sort_keys=True))
    return emit({"written": args.out,
                 "pairs_exported": len(payload["resolved_pairs"]),
                 "status": payload["status"]})


# -- synthetic end-to-end verification (temp dir only) --------------------

def verify_synthetic() -> dict:
    """ONE synthetic pair through the whole path, in a temp dir.

    Proves: decide registers pending and lands NO pair; a refused
    source (acceptance) lands nothing and leaves the decision
    pending; an independent source lands exactly one pair with
    provenance; the pair and its provenance survive a restart;
    question text appears in neither persisted pair file; a
    correction flips the evaluation view without rewriting the
    calibration log. The production store is never opened."""
    steps = []

    def step(name, cond, detail=""):
        steps.append({"step": name, "pass": bool(cond),
                      "detail": detail})
        return bool(cond)

    tdir = tempfile.mkdtemp(prefix="lane4-synthetic-")
    db = os.path.join(tdir, "memory.db")
    cal = os.path.join(tdir, "calibration.json")
    question = ("[SYNTHETIC] lane4 verification question - "
                "ship build Z on 2026-10-25?")
    cands = [Candidate(id="c1", description="ship it"),
             Candidate(id="c2", description="hold it")]
    prefs = [Preference(candidate_id="c1", kind="better", weight=1.0,
                        source_module="lane4-verify")]
    agent = MemoryAgent(SQLiteStore(db), calibration_path=cal)
    st0 = status_dict(agent)
    step("starts-at-zero", st0["pairs_with_provenance"] == 0
         and st0["log_pairs_total"] == 0
         and st0["pairs_remaining_to_unlock"] == 30,
         f"status={st0}")
    r = agent.decide(question, cands, prefs)
    key = r["decision_key"]
    step("decide-registers-pending-no-pair",
         len(agent.pending_decisions()) == 1
         and agent.calibration.pairs == [],
         f"key={key}")
    refused = agent.note_decision_outcome(
        key, True, resolution_source="acceptance",
        resolved_by="lane4-verify-synthetic")
    step("acceptance-source-refused-stays-pending",
         refused is False and len(agent.pending_decisions()) == 1
         and agent.calibration.pairs == [])
    ok = agent.note_decision_outcome(
        key, True, resolution_source="synthetic-observed-outcome",
        resolved_by="lane4-verify-synthetic")
    st1 = status_dict(agent)
    step("independent-source-lands-one-pair",
         ok is True and st1["pairs_with_provenance"] == 1
         and st1["log_pairs_total"] == 1
         and st1["pending_decisions"] == 0
         and st1["evaluation_unlocked"] is False
         and st1["pairs_remaining_to_unlock"] == 29,
         f"status={st1}")
    # restart durability + provenance + evaluation view
    agent2 = MemoryAgent(SQLiteStore(db), calibration_path=cal)
    rp = agent2.resolved_pairs()
    step("pair-survives-restart-with-provenance",
         len(rp) == 1 and rp[0]["decision_key"] == key
         and rp[0]["outcome"] is True
         and rp[0]["resolution_source"]
         == "synthetic-observed-outcome"
         and rp[0]["confidence"] == r["confidence"]
         and rp[0]["m"] == r["conflict_score"],
         f"resolved_pairs={rp}")
    # privacy: pair files hold numbers + resolution metadata only
    with open(cal, encoding="utf-8") as f:
        cal_text = f.read()
    with open(cal + ".pending.json", encoding="utf-8") as f:
        sidecar_text = f.read()
    step("no-question-text-in-pair-files",
         question not in cal_text and question not in sidecar_text)
    # correction: evaluation view flips, substrate untouched
    before = list(agent2.calibration.pairs)
    cok = agent2.note_decision_correction(
        key, False, resolution_source="synthetic-corrected-record",
        resolved_by="lane4-verify-synthetic",
        note="synthetic correction drill")
    rp2 = agent2.resolved_pairs()
    step("correction-flips-view-log-untouched",
         cok is True and rp2[0]["outcome"] is False
         and rp2[0]["original_outcome"] is True
         and rp2[0]["corrected"] is True
         and agent2.calibration.pairs == before,
         f"resolved_pairs={rp2}")
    return {"label": SYNTHETIC_LABEL, "temp_dir": tdir,
            "decision_key": key,
            "all_pass": all(s["pass"] for s in steps),
            "steps": steps,
            "final_status": status_dict(agent2),
            "production_pairs_after_verify": 0,
            "note": ("verification ran entirely under temp_dir; "
                     "the production db was never opened and this "
                     "synthetic pair counts as 0 real pairs")}


def cmd_verify_synthetic(args) -> int:
    ev = verify_synthetic()
    return emit(ev, code=0 if ev["all_pass"] else 1)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Operator harness for REAL decision pairs "
                    "(lane 4, 2026-10-25). See module docstring.")
    p.add_argument("--db", default=DEFAULT_DB,
                   help="SQLite store path (default: data/memory.db)")
    p.add_argument("--calibration", default=None,
                   help="calibration JSON path (default: "
                        "<db dir>/calibration.json)")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decide", help="run one production decision")
    d.add_argument("--question", required=True)
    d.add_argument("--candidate", action="append", required=True,
                   help="id=description (repeatable)")
    d.add_argument("--prefer", action="append",
                   help="candidate id given a better-vote, "
                        "weight 1.0 (repeatable)")
    d.add_argument("--stakes", default="medium",
                   choices=["low", "medium", "high"])
    d.set_defaults(fn=cmd_decide)

    sub.add_parser("pending", help="list unresolved decisions") \
        .set_defaults(fn=cmd_pending)

    rs = sub.add_parser("resolve", help="resolve a pending decision")
    rs.add_argument("--key", required=True)
    g = rs.add_mutually_exclusive_group(required=True)
    g.add_argument("--correct", action="store_true",
                   help="the decision's selection was CORRECT")
    g.add_argument("--incorrect", action="store_false",
                   dest="correct",
                   help="the decision's selection was WRONG")
    rs.add_argument("--source", required=True,
                    help="independent channel that established the "
                         "outcome (never acceptance/self/assumed)")
    rs.add_argument("--by", default=None,
                    help="who/what resolved it")
    rs.set_defaults(fn=cmd_resolve)

    co = sub.add_parser("correct", help="correct a resolved pair")
    co.add_argument("--key", required=True)
    g2 = co.add_mutually_exclusive_group(required=True)
    g2.add_argument("--correct", action="store_true")
    g2.add_argument("--incorrect", action="store_false", dest="correct")
    co.add_argument("--source", required=True)
    co.add_argument("--by", default=None)
    co.add_argument("--note", default="")
    co.set_defaults(fn=cmd_correct)

    sub.add_parser("status", help="counts toward n>=30") \
        .set_defaults(fn=cmd_status)

    ex = sub.add_parser("export", help="export resolved pairs JSON")
    ex.add_argument("--out", required=True)
    ex.set_defaults(fn=cmd_export)

    sub.add_parser("verify-synthetic",
                   help="temp-dir end-to-end check, 1 synthetic pair") \
        .set_defaults(fn=cmd_verify_synthetic)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
