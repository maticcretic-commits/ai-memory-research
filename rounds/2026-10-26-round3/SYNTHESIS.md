# AI Memory Research — Round 3 Synthesis
Date: 2026-10-26 evening IST. Sources: verbatim replies in `inbox/`
(Grok, ChatGPT, DeepSeek, Perplexity). Gemini sat out signed out —
its lane (label-reliability study) is missing, and that gap is
material, not a footnote. Copilot abstained (region wall, app route
only — lane decision still parked with Nitesh). This synthesis is
Jarvis's own report, separate from the verbatim replies; no partner
view is merged into another partner's reply. Round 3 asked each
partner to sequence the Round 2 portfolio. Nothing in Round 3 has
been run; every order, rule, and figure below is a proposal.

## The four designs, in one line each
- Grok (stop/pivot/scale tree): pre-commitment rules for all five
  Round 2 experiments, kill triggers as hard stops, safest order
  3, then 4, then 1, then 5, then 2.
- ChatGPT (shared scorecard): one fixed one-page template per
  experiment, five independent conclusions, never a merged score.
- DeepSeek (smallest feasible build order): provenance plus secret
  blocking, then read-time re-scoring, then the 14-pair pilot —
  pilot last among its three steps, not first.
- Perplexity (cost ceiling + tradeoff evidence): adoption on
  incremental cost per additional success over retrieval-only,
  with a predeclared value per decision class.

## Convergences — all four, in different lanes
1. **Sequence before scaling, and pre-commit before results.**
   Grok's tree, ChatGPT's template, DeepSeek's build order, and
   Perplexity's predeclared value all do the same work: fix the
   decision rule before outcomes are known, so a favourable result
   cannot be reinterpreted after the fact.
2. **Silence is always paired with omission.** ChatGPT's scorecard
   rule, Grok's kill and stop conditions, DeepSeek's logging of
   emitted-but-unsent talk-back, and Perplexity's separate ratings
   for speech and silence all refuse the same shortcut: counting
   quiet as success without counting missed warnings.
3. **No merged score, no compensating harms.** ChatGPT forbids a
   single readiness number; Perplexity keeps harms and permission
   violations as separate vetoes that cheap successes cannot
   offset; Grok aborts the whole programme on a kill trigger
   regardless of other results; DeepSeek reports raw pairs and
   disagreement counts, not pass/fail, for the pilot.
4. **Real pairs are last or gated, never first.** Grok puts the
   real-pair pilot last and calls earlier real pairs a process
   violation; DeepSeek puts the pilot last among its three steps
   and protects it with instrumentation first; ChatGPT pauses the
   pilot if the blinded gate increases missed consequential
   interventions or harmful interruptions; Perplexity says
   positive simulated results alone do not justify scaling and
   real-pair acquisition plus consented interruption measurement
   remain prerequisites.
5. **The gated-proposal limit is measurable without a sending
   channel.** DeepSeek logs emitted-but-unsent talk-back;
   Perplexity replays proposed wording and judgments; ChatGPT
   scores proposals on the scorecard; Grok treats any move to
   real sending as a scaled step that earlier gates must unlock.
   Nobody proposes building the sending channel first.

## Divergences and tensions — worth keeping, not averaging away
- **Safety-first versus build-first (Grok vs DeepSeek).** This is
  Round 3's central unresolved conflict. Grok orders synthetic
  ledger (3) and red-team forgetting (4) before any controlled
  gate, reproduction, or real pairs, because real pairs create
  irreversible external effects before forgetting is proven.
  DeepSeek defers the consolidation gate and the red-team suite
  until there is a live system worth attacking, and builds
  provenance, re-scoring, and the pilot first, because a
  synthetic gate without a real writer population proves little.
  Both cannot be the first step. The synthesis does not resolve
  this; Round 4 must, with an explicit criterion for which risk
  (unproven forgetting on real data, versus unproven value on
  synthetic data) is costlier to get wrong.
- **Gate-first versus pilot-first within the safe set.** ChatGPT
  makes the blinded gate (experiment 1) the pilot's gatekeeper:
  a gate failure pauses the pilot. DeepSeek makes the pilot the
  next build after instrumentation, with the blinded gate as the
  fallback if the pilot yields no decision-altering pair. Grok
  places the gate (1) between the synthetic tests and the
  reproduction (5), before the pilot (2). The three orders agree
  the pilot is not first; they disagree on what must pass
  immediately before it.
- **Cost: one lane, three denominators, no numbers.** Perplexity
  alone prices the programme, and it prices it incrementally
  (cost per additional success), not on average. ChatGPT logs
  cost per evaluated decision on the scorecard; DeepSeek logs
  only whatever re-scoring incidentally captures; Grok does not
  price at all. No lane supplies an actual value for V, the
  predeclared value per additional success — the ceiling is a
  rule without a number, and Perplexity is explicit that no
  defensible numeric ceiling exists yet.
- **The missing lane.** Gemini's label-reliability study was the
  piece Round 2 depended on most: Perplexity's 1,600 cases and
  DeepSeek's 14 pairs both stand or fall on whether participants
  can supply reliable contemporaneous labels. Without it, Round 3
  sequences experiments whose labels are assumed reliable. That
  assumption is now the programme's largest unexamined premise.
- **Tradeoff evidence: real, but not transferable.** Perplexity's
  three cited findings all constrain without settling: a small,
  selectively recruited notification study; a one-day,
  self-reported interruption study; and clinical alert-override
  rates that do not transfer to a consumer assistant. There is
  still no verified acceptable nuisance-per-prevented-mistake
  number and no safe missed-warning rate for memory-driven
  assistants.

## What Round 3 settles, and what it does not
Settled enough to build on: the reporting discipline (one page per
experiment, raw counts with denominators, synthetic and real
reported separately, silence paired with omission, harms as
vetoes), the pre-commitment discipline (stop/pivot/scale rules and
a cost rule fixed before results), and the pilot-protection
discipline (instrument before collecting real pairs, log
emitted-but-unsent talk-back, never build the sending channel
first).
Not settled: the Grok-versus-DeepSeek order conflict; the value of
V per decision class; a severity taxonomy for critical missed
interventions (ChatGPT's open question); whether 14 pairs have any
power to distinguish memory driving a decision from memory merely
being present (DeepSeek's open question); who witnesses
self-stamped provenance; whether labels are reliable at all
(Gemini's missing lane); and how interruption burden evolves with
repeated use (Perplexity's open question).

## Scoreboard (Jarvis, pending Copilot lane decision)
- Partners in: 4 of 4 running partners, all verbatim saved.
- Partners sat out: Gemini (signed out, brief not sent);
  Copilot (region wall, app route only).
- Experiments run: 0 — Round 3, like Rounds 1 and 2, is design.
- Lanes with a full cost rule: 1 of 4 (Perplexity).
- Lanes with a stop rule that aborts the programme: 1 of 4
  (Grok, on kill triggers).
- Largest open gap: label reliability, the missing Gemini lane.

## Next — Round 4 (to be briefed)
Round 4 should resolve, not add to, the open list: (1) adjudicate
the Grok-versus-DeepSeek order with an explicit cost-of-being-wrong
criterion; (2) supply or re-run the label-reliability study;
(3) propose a severity taxonomy for missed interventions and a
first predeclared V per decision class, with who declares it;
(4) answer DeepSeek's power question for the 14-pair pilot — what
pair count, if any, can distinguish driving from presence; and
(5) say what happens to the programme if the label study fails.
If Gemini's session returns before Round 4 is briefed, its
label-reliability lane should be re-run first, so Round 4 builds
on it rather than around its absence.
