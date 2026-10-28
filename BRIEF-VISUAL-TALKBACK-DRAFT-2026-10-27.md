# DRAFT — AI memory: visual / simulation talk-back brief (NOT SENT)

Prepared 2026-10-27 ~15:20 IST at research stage. Awaiting Nitesh's word.
Do NOT launch without his explicit go. Recommended sequencing: hold until
the Round 7 synthesis is written (Lanes 3 and 4 still outstanding), then
run this as the next round. Running it now, while Round 7 is unfinished,
risks a third wrong-lane filing — two partners already answered Lane 1
when assigned other lanes in Round 7.

## System under study (do not re-argue)

"Memory Milestone (mm)", memory → DECISION, not just memory → context.
Its own record (25 Oct 2026): 829 tests green, LongMemEval-S R@1 0.712 /
MRR 0.797, six red-team rounds to zero critical attack success in the final
round. Honest gaps: calibration gate (a) still FAIL (underconfident agent
path), zero real production decision pairs, proactive speech as gated
proposals only, NO sending channel. Experiments run in this programme:
still 0. Fail-closed is the default: silence, delay, or a missing signature
never counts as approval. Never invent a named individual, an appointing
body, a numeric value, a gate status, or a measured result. A placeholder
marked TBD is honest; an invented name or number is fabrication.

## Study material supplied (verified live 2026-10-27, text fetch only)

Filed at `STUDY-VISUALISERS-2026-10-27.md`. No simulation was run, no
account was created, no licence or pricing was checked beyond what each
page itself states. Nothing has been integrated into the mm code.

1. Chemistry lab — NOBOOK Virtual Laboratory, https://chemistry-en.nobook.com/
   Catalogue of virtual chemistry experiments (e.g. preparing oxygen gas
   by heating potassium permanganate, activity order of metals). Question:
   a remembered procedure rendered as a runnable experiment rather than
   recalled as text — when should a memory system re-run/show a procedure
   instead of describing it, and what counts as a correct outcome?
2. Circuit visualisation — Tinkered, https://www.tinkered.ai/
   "Describe what you want to build. Tinkered designs the circuit, writes
   the firmware, validates the system, and simulates the complete device
   in 3D before you assemble it." Question: prompt, circuit, firmware,
   schematic and simulation kept as one connected record — when one part
   changes, which dependent records must change with it, and what is the
   audit trail? (Closest analogue in this study to mm's provenance +
   supersession problem.)
3. How things work — Animagraffs, https://animagraffs.com/
   "Animated infographics about everything" (car engines, jet engines,
   the human eye, ...). Question: a complex mechanism decomposed into
   labelled, moving parts — a short, visual, inspectable answer instead
   of a paragraph, each part labelled so the user can check it. Cost side:
   every visualiser is authored, not generated from a memory record — who
   authors the visual, and what happens when the underlying facts change?

## The brief to send (one verbatim message per partner, new chat)

Header rule, learned from Round 7: the FIRST LINE of the message must be
"YOUR LANE IS LANE N — [lane name]. Do not answer any other lane." Each
partner answers ONLY its assigned lane, in 700–1000 words, plus Top 5
findings and Top 3 open questions. State at the top whether the answer is
COMPLETE, COMPLETE-WITH-TBD-FIELDS, or INCOMPLETE, naming every TBD /
UNRESOLVED field. Save each reply verbatim before any synthesis. This is
design only: no sending channel exists in mm, no experiment is authorised
by this round, no publish, send, payment, sign-in, or Terms acceptance.

Common question for every lane: what would a visual/simulation talk-back
surface have to RECORD (inputs, run, outcome, provenance) to be auditable
under the Round 5–7 gates, and what must it NEVER show (unverified outcome,
unlabelled animation, a superseded fact presented as current) under
fail-closed? Silence must remain a counted, legitimate outcome: a visual
not shown is not a failure.

- LANE 1 — ChatGPT (talk-back): show vs tell vs silence. When does a
  visual/simulation earn an interruption, when is text enough, and when
  must the system stay silent? Extend the Round 2 silence metric to
  visual surfaces: define Correct Visual Silence Rate and the companion
  rates (unnecessary visual interruption, critical visual omission,
  stale-visual error). What must be logged for each shown / withheld
  visual so a later audit can replay the choice?
- LANE 2 — Gemini (deep research / calibration + consolidation): change
  over time. An animation or simulation is authored against facts that
  later change. Specify versioning for a visual record: what is frozen,
  what supersedes what, what the user sees when a visual is superseded,
  and how a visual built from a superseded fact is prevented from
  re-entering retrieval. Do not invent a threshold or a calibration
  value; name the calibration procedure that would set any number.
- LANE 3 — Grok (challenger QA): red-team the visual surface. Attack
  cases: a simulation whose outcome is plausible but unverified, an
  animation that omits a safety step, a visual that makes a low-trust
  memory look authoritative, a superseded visual reused out of context.
  Give kill criteria: what visual failure aborts the visual talk-back
  programme, and what failure only pauses one surface?
- LANE 4 — DeepSeek (build): the smallest auditable record. Specify the
  record schema a visual talk-back surface must write BEFORE any visual
  channel exists: inputs, run parameters, observed outcome, provenance
  (source memory IDs + supersession links), hash/freeze step, and the
  replay check. What is the minimum build order, and what must NOT be
  built before provenance logging exists?
- LANE 5 — Perplexity (verified research): verify, do not invent. For
  each of the three sites, establish from primary sources only: licence /
  reuse terms, pricing / account requirements, whether runs or designs
  are exportable or logged, and whether any claim on its page is
  unverified marketing. Mark every claim ESTABLISHED, UNVERIFIED, or
  UNJUDGEABLE ON THE SOURCES CHECKED, with the source for each.

Copilot: NOT assigned. Its lane decision remains parked (region wall,
no browser bridge) as in every round so far; do not pretend a reply came
from Copilot. If a scoreboard is needed, it is built from the five
verbatim replies, labelled as such.

## Standing round rules

Check sign-in first: if signed out, stop and do not sign in. Bot check /
region wall / CAPTCHA = sit out, reported plainly. Return the full reply
text plus the account and model shown and the chat URL. Individual work
only. Verify every claim, mark anything uncertain as uncertain, plain
language.

## Choice for Nitesh (delivery)

(A) Hold this draft until the Round 7 synthesis is written, then run it
as the next round. (B) Run it now as a standalone study round, in
parallel with the outstanding Round 7 re-runs. (C) Keep it as study
material only — no partner round. No partner is briefed until he picks.
