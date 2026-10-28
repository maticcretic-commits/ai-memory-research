# AI Memory Research — Round 4 brief (to send, lane framing added per partner)

Context, in brief. We are researching how AI memory works, how it
can talk back, and how memory can drive decisions rather than just
supply context. The system on file is called Memory Milestone (mm):
memory → DECISION, with an internal record of 829 tests green,
LongMemEval-S R@1 0.712 / MRR 0.797, and six red-team rounds to zero
critical attack success in the final round. Its own record also lists
open gaps: a calibration gate still FAIL (underconfident agent path),
zero real production decision pairs so far, and proactive speech built
only as gated proposals, with no sending channel. Those internal figures
have not been independently verified in public sources; treat them as
claims, not facts.

Rounds 1–3 established: SQLite as the authoritative record with
hybrid retrieval and metadata filtering first, versioned supersession
with history preserved and no silent overwrites, talk-back as its own
layer (surface, remind, warn, ask, explain, silence), confidence per
claim and per action with high confidence granting no permission, a
shared one-page scorecard per experiment with raw counts and
denominators and no merged readiness score, and a pre-commitment
discipline (stop/pivot/scale rules and a cost rule fixed before
results). Round 3 left one central conflict unresolved and one lane
missing.

The conflict: Grok's safety-first order (synthetic ledger, then
red-team forgetting, then the controlled talk-back gate, then
reproduction plus participants, and only then the real-pair pilot,
with earlier real pairs called a process violation) versus DeepSeek's
build-first order (write-time provenance plus secret blocking, then
read-time re-scoring, then the 14-pair pilot, deferring the
consolidation gate and red-team suite until a live system exists).
The missing lane: Gemini's label-reliability study — whether
consenting participants can supply reliable contemporaneous decision
labels — on which the participant and pilot designs depend.

Round 4 resolves, not adds. Each lane below takes one open item and
must end with a decision rule, not another design.

LANE TASKS (use only the lane framing for your chat):

- ChatGPT (talk-back / UX lane): propose the severity taxonomy for
  missed interventions and the minimum evidence requirements for a
  critical missed intervention, across all five experiments. Give
  the taxonomy levels, what evidence each level requires, and how
  the scorecard reports a missed intervention whose severity is
  disputed.

- Gemini (deep research lane): design the label-reliability study
  that Round 3 missed. Can consenting participants supply reliable
  contemporaneous decision labels, and how would we know? Give the
  exact setup, sample size, agreement metric, and pass/fail rule,
  and say what happens to the participant and pilot designs if
  labels prove unreliable.

- Grok (challenger QA lane): adjudicate the Grok-versus-DeepSeek
  order conflict with an explicit cost-of-being-wrong criterion.
  What is costlier to get wrong — unproven forgetting on real data,
  or unproven value on synthetic data — and under what measurable
  condition should the order flip? Challenge your own Round 3 order
  as hard as DeepSeek's.

- DeepSeek (build lane): answer your own power question. What pair
  count, if any, can distinguish "memory drove the decision" from
  "memory was merely present"? Give the minimum pilot size worth
  its elapsed time, what the 14-pair pilot can and cannot show,
  and the kill criterion for read-time re-scoring if it reproduces
  the underconfident path on every pair.

- Perplexity (verified research lane): propose the first predeclared
  value V per decision class — the maximum acceptable expenditure
  per additional successful decision over retrieval-only — and say
  who declares it, how, and what happens if stakeholders will not
  predeclare. Cite any public evidence you can verify for the
  values, and say plainly where no public evidence exists. Do not
  invent a dollar figure as an empirical finding.

Deliverable format. 700–1000 words, plus your top 5 findings and your
top 3 open questions. End with what result in your piece would change
the sequencing plan, and what your piece deliberately does NOT prove.
Do not claim any experiment has run, any figure has been verified, or
any threshold has been proven safe.
