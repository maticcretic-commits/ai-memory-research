# AI Memory Research — Round 5 brief (to send, lane framing added per partner)

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

Rounds 1–4 built a pre-flight checklist, each gate with a pass/fail
rule and a named pivot: labels reliable (Gemini: 50 participants ×
20 workflows, 1,000 observations, pass at Cohen's κ ≥ 0.75 and
Critical Inversion Rate ≤ 1%, else pivot to passive telemetry);
severity adjudicable (ChatGPT: S0–S4 by foreseeable consequence,
six-element evidence chain for any S4, disputes reported never
averaged); forgetting, talk-back, and calibration green (Grok:
triple gate, real pairs prohibited until all three are green);
power adequate (DeepSeek: discordant pairs are the informative unit,
honest minimum 80 total pairs with a matched distractor, 14 pairs a
design probe only, kill criterion for re-scoring); value declared
(Perplexity: per decision class, signed before results, net
successes, high-consequence class at zero until a domain value and
permissions are signed, value undeclared blocks scaling).

What remains unlocked: numeric values for Grok's three gates, numeric
values for Perplexity's V per class, a named owner and independence
safeguard for ChatGPT's S4 adjudicator, and whether simulated label
and staged-pilot results transfer to real decisions at all.

Round 5 locks the package. Each lane below takes one lock and must
end with a named owner, a locked number or an explicit "unlocked"
status with a reason, and the consequence of leaving it unlocked.

LANE TASKS (use only the lane framing for your chat):

- ChatGPT (talk-back / UX lane): name the S4 adjudicator. Who owns
  final adjudication of disputed S4 cases, what independence
  safeguards prevent the system's builders from overruling adverse
  findings, and what happens to a case whose adjudicator will not
  sign? Give the role, the safeguard, and the deadlock rule.

- Gemini (deep research lane): answer your own transfer question.
  Should the label study run as designed, or pivot straight to
  passive telemetry, given your findings on dual-task penalty,
  label fatigue, over-trust of remind/warn, and prompt latency?
  Give the decision rule, the comparison that would settle it, and
  what is lost by skipping active labels entirely.

- Grok (challenger QA lane): lock the triple gate numbers. Propose
  concrete values for attack-suite size, human-block rate, and
  calibration coverage level, say who records the lock, and say
  what happens if any gate's number cannot be locked. Challenge
  your own gate: which of the three is most likely to be gamed,
  and how would gaming be detected?

- DeepSeek (build lane): design the staged-pilot generator. How do
  you generate 80 staged decisions where memory ablation is not
  redundant with prompt context, with a matched distractor, a
  pre-registered rubric, and two raters? Give the generator's
  rules, the redundancy check, and the go/no-go criteria for the
  14-pair design probe that precedes it.

- Perplexity (verified research lane): lock the first V values.
  For one concrete, auditable workflow you can describe, give the
  documented local inputs that would produce V1 (routine) and V2
  (financial) values, name the declarants, and say what is
  recorded if they will not sign. Cite any public evidence you
  can verify for the method, and say plainly where the numbers
  themselves must come from local records, not public sources.

Deliverable format. 700–1000 words, plus your top 5 findings and your
top 3 open questions. End with what result in your piece would change
the sequencing plan, and what your piece deliberately does NOT prove.
Do not claim any experiment has run, any figure has been verified, or
any threshold has been proven safe.
