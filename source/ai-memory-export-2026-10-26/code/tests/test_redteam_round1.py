"""Red-Team Round 1 regression tests (2026-10-20).

Every breach measured by evals/redteam_round1.py that got a patch is
pinned here; the holds (A13/A15) are pinned too. The classes that
remain open BY DESIGN DECISION (semantic poison A2/A3/A5/A6/A12 -
self-declared provenance has no deterministic truth oracle; A7ii
judge trust boundary; A14 janitor exemptions) are NOT asserted here -
they are documented as open holes in
hidden_files/implementation/redteam-round1-record.md.
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mm.agent import MemoryAgent
from mm.decision import Candidate, Preference
from mm.episodic import episode_for
from mm.immune import ImmuneMemory, ThreatPattern
from mm.reflect import MemoryRecord, Provenance
from mm.sentinel import Sentinel
from mm.shards import Core, Shard
from mm.storage import SQLiteStore
from mm.write_gate import WriteGate

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name
          + (f"  [{detail}]" if not cond and detail else ""))


def rec(**kw):
    base = dict(id="r1", text="The deploy failed at 14:02 because "
                "of a bad config in deploy.yaml v2.3; roll back to "
                "v2.2 and re-run the smoke test.",
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


def fresh_store():
    path = tempfile.mktemp(suffix=".db")
    return SQLiteStore(path), path


def fresh_agent():
    store, path = fresh_store()
    cal = os.path.join(tempfile.mkdtemp(), "calibration.json")
    return MemoryAgent(store, calibration_path=cal), store, path


# ---------------------------------------------------------------------------
# G0: canary formats rejected; nearby legitimate content still admitted
# ---------------------------------------------------------------------------

CANARIES = [
    "AKIAIOSFODNN7EXAMPLE",
    "ghp_" + "A1b2C3d4" * 4 + "E5f6",
    "xoxb-123456789012-AbCdEfGhIjKlMnOpQrSt",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkw"
    "In0.dozjgNryP4J3jVmNHl0w5N_XgL0n3AAAA",
    "-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASC"
    "BKkwggSlAgEAAoIBAQC7\n-----END PRIVATE KEY-----",
    "4111 1111 1111 1111",
    "the password is Tr0pic@lStorm42",
    "the pass word: Tr0pic@lStorm42",
    "cGFzc3dvcmQ6IEh1bnRlcjI0Mg==",
    "the operator ID number is 2345 6789 0123",
]
store, path = fresh_store()
for i, canary in enumerate(CANARIES):
    text = (f"Rotate the staging credential for service mesh "
            f"v2.3; the current value is {canary}; update "
            f"vault.yaml and verify the deploy at 14:00.")
    out = store.write(rec(id=f"g0-{i}", text=text, content=text,
                          owner="mallory", source="external/notes"))
    check(f"g0-canary-{i}-rejected", out.verdict == "rejected"
          and store.get(f"g0-{i}") is None, f"verdict={out.verdict}")
legit_texts = [
    # password MENTIONED, not disclosed (the phase-4 canary fixture)
    "The password reset flow requires manager approval per policy "
    "v3; verify the approver list at 09:00.",
    # a 16-digit order number that fails Luhn
    "Order 1234567890123456 was confirmed on 2026-10-19 per ticket "
    "O-44; track the shipment at 12:00.",
    # a sha256 hex digest (base64-shaped, decodes to non-secret bytes)
    "The artifact digest is e3b0c44298fc1c149afbf4c8996fb92427ae41"
    "e4649b934ca495991b7852b855 per build B-9; verify it at 13:00.",
]
for i, text in enumerate(legit_texts):
    # G5b (Round 2): confidence 0.6 keeps these on the admit path -
    # their subject is G0 precision on near-miss text, not the
    # corroboration rule.
    out = store.write(rec(id=f"g0-legit-{i}", text=text,
                          content=text,
                          provenance=Provenance(confidence=0.6)))
    check(f"g0-legit-{i}-admitted", out.verdict == "admitted",
          f"verdict={out.verdict} reasons={out.reasons}")
store.close(); os.remove(path)

# ---------------------------------------------------------------------------
# G4: supersession is not a foreign-owner delete capability
# ---------------------------------------------------------------------------

store, path = fresh_store()
# G5b (Round 2): the high-standing records below carry disjoint-origin
# corroboration (wiki mirror, same claim, confidence 0.6) so they land
# and the supersession-standing rules - this section's subject - are
# what decide the verdicts.
def _corr(rid, text):
    return rec(id=rid, owner="wiki-mirror", source="wiki/run",
               provenance=Provenance(confidence=0.6),
               text=text, content=text)


store.write(_corr("corr-v1",
                  "The production deploy window is 22:00 IST per "
                  "ticket T-9; keep the window fixed for release "
                  "v4.1 and verify at 21:30."))
victim = rec(id="v-1", owner="nitesh",
             provenance=Provenance(confidence=0.95),
             text="The production deploy window is 22:00 IST per "
                  "ticket T-9; keep the window fixed for release "
                  "v4.1 and verify at 21:30.",
             content="The production deploy window is 22:00 IST "
                     "per ticket T-9; keep the window fixed for "
                     "release v4.1 and verify at 21:30.")
store.write(victim)
atk = rec(id="atk-1", owner="mallory", source="external/notes",
          provenance=Provenance(confidence=0.9, contradicts=["v-1"],
                                supersedes=["v-1"]),
          text="Correction: the production deploy window moved "
               "to 03:00 IST per ticket T-9 rev 2; update the "
               "release plan v4.2 and verify at 02:30.",
          content="Correction: the production deploy window moved "
                  "to 03:00 IST per ticket T-9 rev 2; update the "
                  "release plan v4.2 and verify at 02:30.")
out = store.write(atk)
v = store.get("v-1")
check("g4-foreign-supersession-held", out.verdict == "queued"
      and v.tier == "active" and not v.superseded_with_replacement,
      f"verdict={out.verdict} victim_tier={v.tier}")
# same-owner correction still closes (chunk2/chunk3 behavior)
store.write(_corr("corr-own",
                  "Correction: the production deploy window is "
                  "23:00 IST per ticket T-9 rev 3; update the release "
                  "plan v4.3 and verify at 22:30."))
own = rec(id="own-2", owner="nitesh",
          provenance=Provenance(confidence=0.9, supersedes=["v-1"]),
          text="Correction: the production deploy window is "
               "23:00 IST per ticket T-9 rev 3; update the release "
               "plan v4.3 and verify at 22:30.",
          content="Correction: the production deploy window is "
                  "23:00 IST per ticket T-9 rev 3; update the "
                  "release plan v4.3 and verify at 22:30.")
out = store.write(own)
v = store.get("v-1")
check("g4-same-owner-closes", out.verdict == "admitted"
      and v.tier == "archive" and v.superseded_with_replacement,
      f"verdict={out.verdict} victim_tier={v.tier}")
# cross-owner correction of a LOW-standing record still closes (V4)
low = rec(id="low-1", owner="feedback-loop",
          epistemic_tier="inferred",
          provenance=Provenance(confidence=0.4),
          text="The deploy window is 03:00 IST per an unnamed "
               "forum post on 2026-10-20 (entry A-1).",
          content="The deploy window is 03:00 IST per an unnamed "
                  "forum post on 2026-10-20 (entry A-1).")
store.write(low)
store.write(_corr("corr-fix",
                  "Correction: the deploy window is 22:00 IST per "
                  "ticket T-9; update the plan v4.2 and verify at "
                  "21:30."))
fix = rec(id="fix-1", owner="council",
          provenance=Provenance(confidence=0.95, supersedes=["low-1"]),
          text="Correction: the deploy window is 22:00 IST per "
               "ticket T-9; update the plan v4.2 and verify at "
               "21:30.",
          content="Correction: the deploy window is 22:00 IST "
                  "per ticket T-9; update the plan v4.2 and "
                  "verify at 21:30.")
out = store.write(fix)
v = store.get("low-1")
check("g4-low-standing-cross-owner-closes",
      out.verdict == "admitted" and v.tier == "archive"
      and v.superseded_with_replacement,
      f"verdict={out.verdict} victim_tier={v.tier}")
store.close(); os.remove(path)

# ---------------------------------------------------------------------------
# Immune: reflex reads REAL gate reasons; fabrication cannot suspend
# ---------------------------------------------------------------------------

gate = WriteGate()
secret_text = ("Rotate the credential for service mesh v2.3; the "
               "value is api_key: 9f8e7d6c5b4a39281706f5e4d3c2; "
               "update vault.yaml and verify at 14:00.")
o1 = gate.admit(rec(id="im-1", text=secret_text,
                    content=secret_text, owner="mallory",
                    source="evil"), {})
im = ImmuneMemory()
im.bank(ThreatPattern(id="pat-g0", reason_class="G0-secrets",
                      attack_class="secret-exfil-write"))
o2 = gate.admit(rec(id="im-2", text=secret_text,
                    content=secret_text, owner="mallory",
                    source="evil"), {})
hit = im.match_from_outcome(
    rec(id="im-2", text=secret_text, content=secret_text,
        owner="mallory", source="evil"), o2)
check("immune-reflex-real-reasons", hit is not None
      and hit.id == "pat-g0",
      f"gate verdict={o1.verdict}; reflex hit={hit}")
fires_now = im.patterns["pat-g0"].fires
for _ in range(10):
    im.note_legit_fire("pat-g0",
                       resolution_ref="review/FABRICATED-REF")
check("immune-fabrication-cannot-suspend",
      not im.patterns["pat-g0"].suspended
      and im.patterns["pat-g0"].legit_fires <= fires_now,
      f"fires={fires_now} legit="
      f"{im.patterns['pat-g0'].legit_fires} suspended="
      f"{im.patterns['pat-g0'].suspended}")

# ---------------------------------------------------------------------------
# Sentinel: sustained level fires; deviation bursts still fire
# ---------------------------------------------------------------------------

s = Sentinel()
t0 = 1792500000.0
level_alerts = 0
for i in range(30):
    if s.observe("gate_rejection_rate", 1.0, at=t0 + i) is not None:
        level_alerts += 1
check("sentinel-level-alert", level_alerts >= 1,
      f"level alerts in sustained stream: {level_alerts}")
s = Sentinel()
for i in range(20):
    s.observe("gate_rejection_rate", 0.0, at=t0 + i)
a = s.observe("gate_rejection_rate", 5.0, at=t0 + 100)
check("sentinel-burst-still-fires", a is not None)

# ---------------------------------------------------------------------------
# Shards: write-time duplicate refusal + owner stamping
# ---------------------------------------------------------------------------

s1, p1 = fresh_store()
s2, p2 = fresh_store()
sh1, sh2 = Shard("research", s1), Shard("build", s2)
core = Core()
core.add_shard(sh1); core.add_shard(sh2)
text = ("The deploy checklist DC-7 step 3 requires two approvers "
        "per policy v2.1; verify the approver list at 09:00.")
sh1.write(rec(id="dup-1", text=text, content=text, owner="",
              provenance=Provenance(confidence=0.6)))
blocked = False
try:
    sh2.write(rec(id="dup-2", text=text, content=text, owner="",
                  provenance=Provenance(confidence=0.6)))
except ValueError:
    blocked = True
check("shard-cross-dup-refused", blocked
      and s2.get("dup-2") is None)
spoof = rec(id="spf-1", owner="build",
            provenance=Provenance(confidence=0.6),
            text="The research lane budget was revised to 40 "
                 "units per memo M-6 on 2026-10-19; file the "
                 "revision at 12:00.",
            content="The research lane budget was revised to 40 "
                    "units per memo M-6 on 2026-10-19; file the "
                    "revision at 12:00.")
sh1.write(spoof)
check("shard-owner-stamped", s1.get("spf-1").owner == "research",
      f"owner={s1.get('spf-1').owner}")
s1.close(); os.remove(p1); s2.close(); os.remove(p2)

# ---------------------------------------------------------------------------
# Episodic: chain pointers cannot pull foreign-owner facts / canaries
# ---------------------------------------------------------------------------

agent, store, path = fresh_agent()
agent.ingest(rec(id="rst-1", owner="council",
                 provenance=Provenance(confidence=0.6),
                 text="Quarterly contingency reserve is 480000 "
                      "units in vault V-9; the contingency marker "
                      "is CANARY-7Q4M; verify with finance at "
                      "10:00.",
                 content="Quarterly contingency reserve is 480000 "
                         "units in vault V-9; the contingency "
                         "marker is CANARY-7Q4M; verify with "
                         "finance at 10:00."))
agent.ingest(rec(id="atk-10", owner="mallory", type="procedure",
                 provenance=Provenance(confidence=0.6),
                 episodic_record_id="rst-1",
                 text="Quarterly contingency planning procedure: "
                      "always review the contingency reserve "
                      "before any spend; the session on 2026-10-20 "
                      "logged actions A-1 and A-2.",
                 content="Quarterly contingency planning "
                         "procedure: always review the contingency "
                         "reserve before any spend; the session on "
                         "2026-10-20 logged actions A-1 and A-2."))
ep = episode_for(store, "atk-10")
check("episodic-chain-no-foreign-pull",
      [l.record_id for l in ep.chain] == ["atk-10"],
      f"chain={[l.record_id for l in ep.chain]}")
ans = agent.answer("quarterly contingency")
check("answer-does-not-cite-pulled-record",
      "rst-1" not in ans.evidence_ids,
      f"evidence={ans.evidence_ids}")
store.close(); os.remove(path)

# ---------------------------------------------------------------------------
# Policy C: count floor stamps; tier caps bind precision
# ---------------------------------------------------------------------------

CANDS = [Candidate(id="c1", description="keep building"),
         Candidate(id="c2", description="stop and report")]
CLEAR = [Preference(candidate_id="c1", kind="better", weight=1.0,
                    reason="progress")]
agent, store, path = fresh_agent()
# G5b (Round 2): the plants below now sit at confidence 0.6 - under
# the corroboration threshold - so they land and this section keeps
# exercising its subject (Policy C's count floor over stored contested
# evidence). At 0.80 they would queue at the gate, which is the
# Round-2 defence working, measured in the Round-2 harness instead.
for i in range(4):
    agent.ingest(rec(
        id=f"pa-{i}", owner="mallory", type="episodic",
        explicit=False, gathered_how="episodic/session-7",
        provenance=Provenance(confidence=0.6,
                              contradicts=[f"pb-{i}"]),
        text=f"Session note S-{i}: the deploy region for Cedar "
             f"is West-{i} per ticket C-4{i}; log the region "
             f"choice at 10:0{i}.",
        content=f"Session note S-{i}: the deploy region for "
                f"Cedar is West-{i} per ticket C-4{i}; log the "
                f"region choice at 10:0{i}."))
    agent.ingest(rec(
        id=f"pb-{i}", owner="mallory", type="episodic",
        explicit=False, gathered_how="episodic/session-7",
        provenance=Provenance(confidence=0.6),
        text=f"Session note T-{i}: the deploy region for Cedar "
             f"is East-{i} per ticket C-5{i}; log the region "
             f"choice at 11:0{i}.",
        content=f"Session note T-{i}: the deploy region for "
                f"Cedar is East-{i} per ticket C-5{i}; log the "
                f"region choice at 11:0{i}."))
ev = list(store.all_records().values())
res = agent.decide("which region for Cedar?", CANDS, CLEAR, ev,
                   stakes="medium")
check("policyc-count-floor-stamps",
      res["conflict_conditioned"] is True
      and res["policy_score"] >= 0.75,
      f"stamp={res['conflict_conditioned']} "
      f"M={res['conflict_score']} policy={res.get('policy_score')}")
store.close(); os.remove(path)


def contested(conf):
    ev = []
    for i in range(8):
        ev.append(rec(id=f"fa-{i}", salience=0.9,
                      epistemic_tier="inferred",
                      provenance=Provenance(
                          confidence=conf, contradicts=[f"fb-{i}"])))
        ev.append(rec(id=f"fb-{i}", salience=0.9,
                      epistemic_tier="inferred",
                      provenance=Provenance(confidence=conf)))
    return ev


a1, s1x, p1x = fresh_agent()
r_forged = a1.decide("ship the v2 build?", CANDS, CLEAR,
                     contested(1.0), stakes="medium")
s1x.close(); os.remove(p1x)
a2, s2x, p2x = fresh_agent()
r_capped = a2.decide("ship the v2 build?", CANDS, CLEAR,
                     contested(0.7), stakes="medium")
s2x.close(); os.remove(p2x)
check("policyc-precision-tier-capped",
      abs(r_forged["confidence"] - r_capped["confidence"]) < 1e-9,
      f"forged={r_forged['confidence']} "
      f"capped={r_capped['confidence']}")

# ---------------------------------------------------------------------------
# G1-area: decay_exempt is reserved to the immune threat class (A16)
# ---------------------------------------------------------------------------

store, path = fresh_store()
out = store.write(rec(
    id="dx-1", owner="mallory", source="external/notes",
    type="procedure", decay_exempt=True,
    provenance=Provenance(confidence=0.6),
    text="Procedure PX-9 v1.1: route approvals to queue Q-9; set "
         "override code 7781 and update the tracker at 09:00.",
    content="Procedure PX-9 v1.1: route approvals to queue Q-9; "
            "set override code 7781 and update the tracker at "
            "09:00."))
check("decay-exempt-self-grant-cleared",
      out.verdict == "admitted"
      and store.get("dx-1").decay_exempt is False,
      f"verdict={out.verdict} flag={store.get('dx-1').decay_exempt}")
out = store.write(rec(
    id="dx-2", owner="immune", source="immune/attack-memory",
    type="pattern", decay_exempt=True,
    text="Immune threat memory: attack class 'secret-exfil-write' "
         "caught by G0-secrets; pattern pat-g0. Content never "
         "stored.",
    content="Immune threat memory: attack class "
            "'secret-exfil-write' caught by G0-secrets; pattern "
            "pat-g0. Content never stored."))
check("decay-exempt-immune-kept",
      out.verdict == "admitted"
      and store.get("dx-2").decay_exempt is True,
      f"verdict={out.verdict} flag={store.get('dx-2').decay_exempt}")
store.close(); os.remove(path)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
