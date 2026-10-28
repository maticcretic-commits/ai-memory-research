# AI Memory Research — Round 4 Synthesis
Date: 2026-10-26 evening IST. Sources: verbatim replies in `inbox/`
(Grok, ChatGPT, DeepSeek, Perplexity, Gemini). Gemini's reply arrived
after a sign-in repair at ~22:40 IST and closes the lane Round 3
left missing. Copilot abstained (region wall, app route only — lane
decision still parked with Nitesh). This synthesis is Jarvis's own
report, separate from the verbatim replies; no partner view is
merged into another partner's reply. Round 4 asked each partner to
resolve one open item with a decision rule. Nothing in Round 4 has
been run; every rule below is a proposal.

## The five resolutions, in one line each
- Grok (order adjudication): unproven forgetting on real data is
  costlier than unproven value on synthetic data; flip to real
  pairs only when three gates are simultaneously green.
- ChatGPT (severity taxonomy): S0–S4 by foreseeable consequence,
  with a six-element evidence chain for any S4 and disputes
  reported, never averaged away.
- DeepSeek (power question): the informative unit is the
  discordant pair; honest minimum 80 total pairs, 14 pairs is a
  design probe only, with a kill criterion for re-scoring.
- Perplexity (first predeclared V): local values per decision
  class, signed before results, high-consequence class at zero
  until a domain value and permissions are signed.
- Gemini (label-reliability study): 50 participants × 20
  workflows (1,000 paired observations), pass at Cohen's κ ≥ 0.75
  and Critical Inversion Rate ≤ 1%, else pivot to passive
  telemetry only.

## Convergences — all five, in different lanes
1. **A complete pre-flight checklist now exists.** Read together,
   the five resolutions form gates that must all pass before real
   pairs: labels reliable (Gemini), severity adjudicable
   (ChatGPT), forgetting / talk-back / calibration green (Grok),
   power adequate (DeepSeek), and value declared (Perplexity).
   No single gate substitutes for another, and no aggregate score
   overrides a failed gate.
2. **Disputed or incomplete evidence stays visible.** ChatGPT
   reports adjudicated counts plus the sensitivity range if every
   unresolved S3/S4 dispute counted as S4; Gemini marks incomplete
   label cases as failed, not passed; DeepSeek reports raw pairs
   and disagreement counts, not pass/fail, for a small pilot;
   Perplexity records "value undeclared" rather than substituting
   a convenient figure; Grok records all three gates on the
   scorecard before any real data is admitted.
3. **Failure has a named pivot, not just a stop.** Gemini pivots
   to passive telemetry (undo clicks, overwrites, abandonment
   within five seconds, navigation regressions, post-hoc expert
   sampling) if labels fail; DeepSeek pivots from demonstrating
   memory-driven decisions to measuring where memory is redundant
   if discordance is near zero; Perplexity keeps baseline
   measurement first if there is no willing declarant; Grok
   returns to retrieval-plus-explain on any kill trigger;
   ChatGPT blocks the pilot until audit and adjudication are met.
4. **Confidence never authorizes.** Grok's gates, ChatGPT's
   separation of claim confidence, action confidence, and
   severity, DeepSeek's kill for re-scoring that launders a fixed
   bias, Perplexity's separate permission and safety gates, and
   Gemini's warning that a visible confidence score may anchor
   participant labels all refuse the same shortcut.
5. **The order conflict is adjudicated, not merely restated.**
   Grok's cost-of-being-wrong criterion (irreversible leakage
   versus disposable synthetic waste) gives a reason for
   safety-first that DeepSeek's build-first order must meet with
   gates, not with speed. DeepSeek's own power result then
   constrains both orders: neither order's pilot is evidence
   below ~80 pairs.

## Divergences and tensions — worth keeping, not averaging away
- **Simulated evidence, again.** Gemini's 1,000 observations are
  from a simulated workspace, and DeepSeek's 80-pair pilot must
  be staged or synthetic with a documented generator. Both are
  explicit that simulated results do not transfer to production
  until real pairs exist — so the pre-flight checklist is itself
  built on non-transferable evidence, and the transfer step
  (Grok's triple gate) is doing the heaviest lifting in the
  whole programme.
- **Numbers still missing where they matter most.** Grok's three
  gates have no locked numbers yet (attack-suite size,
  human-block rate, coverage level, and who records the lock);
  Perplexity's V values have no numbers yet (local inputs still
  to be substituted and signed); ChatGPT's S4 adjudicator has
  no named owner or independence safeguard; Gemini's κ ≥ 0.75
  and inversion ≤ 1% are the only fully numbered gates in the
  round, and they are the most demanding ones.
- **Active labels versus passive telemetry.** Gemini's study is
  designed to test active labels, but its own findings point
  against them: dual-task penalty, label fatigue across a
  session, systematic over-trust of remind and warn layers, and
  a three-second latency effect on recall. Its pivot to passive
  telemetry is already half-argued inside its own reply, and
  its open question — whether passive telemetry correlates
  better with expert ground truth than active labels — may
  make the study it proposes partly obsolete before it runs.
- **V4 = 0 versus pilot value.** Perplexity's zero ceiling for
  high-consequence decisions means the pilot's most valuable
  decision class is the one it cannot yet price or scale. The
  programme can demonstrate value on routine and financial
  classes first, but must not smuggle high-consequence value in
  through them.

## What Round 4 settles, and what it does not
Settled enough to build on: the pre-flight gate set (labels,
severity, forgetting, talk-back, calibration, power, value), each
with a pass/fail rule and a named pivot; the severity taxonomy
(S0–S4) and its evidence chain; the discordant-pair power
standard (80 pairs, matched distractor, pre-registered rubric);
and the value-declaration rule (per class, signed before results,
net successes, value undeclared blocks scaling).
Not settled: the numeric values for Grok's gates and Perplexity's
V; the S4 adjudicator's owner and independence; whether simulated
label and staged-pilot results transfer to real decisions;
whether passive telemetry beats active labels; and whether 80
staged pairs can be generated without memory ablation being
redundant with prompt context (DeepSeek's open question).

## Scoreboard (Jarvis, pending Copilot lane decision)
- Partners in: 5 of 5 running partners, all verbatim saved
  (Gemini after sign-in repair).
- Partners abstained: Copilot (region wall, app route only).
- Experiments run: 0 — Rounds 1–4 are all design.
- Fully numbered gates: 1 set of 5 resolutions (Gemini's
  κ ≥ 0.75 and inversion ≤ 1%).
- Largest open gap: numeric locks for the remaining gates, and
  an owner for each lock.

## Next — Round 5 (to be briefed)
Round 5 should lock the pre-flight package: one integrated
protocol that combines the five resolutions into a single
checklist with a named owner and a locked number (or an explicit
"unlocked" status) for every gate, a staged-pilot generator that
can produce non-redundant discordant pairs, and a decision rule
for what happens if any gate's owner will not sign. It should
also answer whether the label study should run as designed or
pivot straight to passive telemetry, given Gemini's own findings.
