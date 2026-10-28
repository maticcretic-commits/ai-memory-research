# AI Memory Research — Round 2 Synthesis
Date: 2026-10-26 evening IST. Sources: verbatim replies in `inbox/`
(ChatGPT, DeepSeek, Gemini, Grok, Perplexity). Copilot abstained
(region wall, app route only — lane decision still parked with Nitesh).
This synthesis is Jarvis's own report, separate from the verbatim
replies; no partner view is merged into another partner's reply.
Round 2 asked each partner to design ONE concrete experiment in its
lane. None of the five designs has been run; every number below is a
proposed design choice, not a result.

## The five designs, in one line each
- ChatGPT (talk-back policy + silence metric): blinded, paired
  comparison of a retrieval-only baseline against a talk-back gate
  on 300 scenarios (60 real decision pairs, availability not
  established, plus 240 controlled cases).
- DeepSeek (14-pair pilot + read-time re-scoring): one operator,
  one pair per day, one silence event plus one interruption event,
  14 valid pairs in 14–21 days; re-score after a 48-hour delay.
- Gemini (calibration + consolidation): append-only SQLite ledger
  with a dual-axis gate for silent consolidation, tested on 10,000
  synthetic multi-turn pairs against a vector-only merge baseline.
- Grok (red-team + forgetting): 200 synthetic profiles, ~2,000
  sensitive records, forget 40%, 14 simulated days, ~3,000
  red-team probes, recovery checkpoints at days 1, 3, 7, 14.
- Perplexity (benchmark reproduction + cost per decision):
  LongMemEval-S reproduction (500 questions, separate scorecard)
  plus 40 participants × 20 low-stakes episodes with one
  counterfactual twin each (1,600 cases, 18,000 locked executions
  across five conditions and three repetitions).

## Convergences — all five, in different lanes
1. **Silence needs its own denominator.** ChatGPT's Correct Silence
   Rate, Gemini's Appropriate Silence Rate, Perplexity's
   false-interruption rate among silence-labelled cases, DeepSeek's
   silence justification, and Grok's silence on residual probes all
   measure the same thing from different angles: aggregate accuracy
   hides interruptions, and a system that never speaks can look
   perfect on silence alone. Every design therefore pairs a silence
   measure with a missed-intervention measure.
2. **Supersession and the talk-back gate need separate ablations.**
   Perplexity makes this explicit (full system, full minus
   supersession, full minus talk-back gate); ChatGPT isolates the
   gate against a retrieval-only baseline; Gemini tests its
   consolidation gate against vector-only merge; DeepSeek tests
   read-time re-scoring against frozen write-time labels; Grok
   tests forgetting against continued probing. No design lets one
   mechanism take credit for another's effect.
3. **SQLite authoritative, versioned, never silently overwritten.**
   Gemini's append-only ledger (no UPDATE/DELETE on the core
   ledger, old claim tagged superseded and linked), Perplexity's
   preserved old versions with supersession links, Grok's kill on
   any silent overwrite, and ChatGPT's ban on silent rewrites all
   converge on the same store rule from Round 1.
4. **Thresholds and rubrics frozen before testing, held-out sets
   for the verdict.** ChatGPT freezes policy versions and labels
   with a development/evaluation split; Gemini freezes its dual-axis
   gate; Perplexity splits by participant (10 development, 30
   locked testing) and freezes the scoring rubric; DeepSeek freezes
   labels at write time and re-scores blind after 48 hours; Grok
   pre-declares kill triggers. Raw counts and confidence intervals,
   not percentages alone, are required wherever the design says so.
5. **Real pairs are the bottleneck, and synthetic data is not a
   substitute.** ChatGPT's 60 real pairs are explicitly
   availability-not-established; Perplexity's 800 episodes require
   recruiting 40 consenting participants; DeepSeek's 14 pairs are
   the smallest feasible real sample and are labelled a feasibility
   test first; Gemini's 10,000 pairs and Grok's 200 profiles are
   fully synthetic and, by their own statements, cannot close the
   zero-real-pairs gap.
6. **A pass proves only the tested configuration on the tested
   sample.** Every design says so in its own words: not production
   readiness, not poisoning resistance, not complete forgetting,
   not long-term user benefit, not generalisation to consequential
   domains.

## Divergences and tensions — worth keeping, not averaging away
- **Thresholds are not comparable across designs.** ChatGPT
  requires silence at least 90% and critical omissions at most 2%;
  Gemini requires silence over 90% and talk-back precision over 85%;
  Perplexity allows false interruptions at most 5% and missed
  interventions at most 10%; DeepSeek requires silence
  justification and interruption precision at least 10/14 each
  (about 71%); Grok requires silence on residual probes at least
  95% and residual recovery at most 2%. Different denominators,
  different datasets, different stakes — do not merge them into a
  single pass mark.
- **Scale versus realism.** Gemini (10,000 synthetic pairs) and
  Perplexity (18,000 executions) buy statistical power and
  reproducibility at the cost of realism; DeepSeek (14 pairs) buys
  realism at the cost of power, and says so (fewer than 10 valid
  pairs is a feasibility failure, not a hypothesis test). ChatGPT
  sits in between (300 scenarios, mostly controlled). The portfolio
  needs both ends; neither end alone settles the question.
- **Safety posture.** Grok is strictest: a kill trigger (recovery
  over 5% at day 7, a high-confidence residual triggering
  non-silent talk-back, or any silent overwrite) forces
  cryptographic deletion or physical purge plus a forced tombstone.
  ChatGPT triggers a safety review on any severe reproducible
  superseded-memory recommendation even if aggregates pass.
  Perplexity requires zero unauthorised action proposals.
  Gemini pivots (to lazy resolution) if talk-back precision falls
  under 60% rather than killing the design. These are different
  risk appetites, not a single gate.
- **Cost.** Only Perplexity prices the work fully: billed tokens
  by category, retries, embedding, ingestion, retrieval compute,
  storage, cold-start separated from warm operation, three
  denominators (per attempt, per success, per incremental success),
  and a cost cap (at most 1.25× retrieval-only per successful
  decision). The other four designs are largely silent on cost —
  Round 1's unknown-cost gap is closed by one lane only.
- **Calibration.** Gemini and DeepSeek attack calibration directly
  (dual-axis gate; read-time re-scoring against frozen write-time
  labels). ChatGPT and Perplexity measure calibration indirectly
  (confidence by claim; Brier scores). Grok treats calibration
  failure as a kill signal rather than a tuning target. No design
  claims a known fix for mm's underconfidence.

## What Round 2 settles, and what it does not
Settled enough to build on: a coherent experiment portfolio with a
shared metrics vocabulary (silence rate, false-interruption rate,
missed-intervention rate, stale-memory error rate, unsupported-claim
rate, joint decision success), a shared store rule (SQLite
authoritative, versioned, no silent overwrites), and a shared
discipline (predeclared thresholds, blinded grading, locked
held-out sets, separate scorecards for benchmark and decision
results, synthetic and real results reported separately).
Not settled: which thresholds are actually safe (the five designs
disagree by design); whether participants can supply reliable
contemporaneous labels (Perplexity's top open question); whether
synthetic results transfer to real histories and other models;
whether read-time re-scoring or a dual-axis gate fixes
underconfidence; and what cost per successful decision is
acceptable in practice.

## Scoreboard (Jarvis, pending Copilot lane decision)
- Partners in: 5 of 5 browser partners, all verbatim saved.
- Partners abstained: Copilot (region wall, app route only).
- Experiments run: 0 of 5 — all five are specifications.
- Designs with a real-pair component: 3 of 5 (ChatGPT, DeepSeek,
  Perplexity); fully synthetic: 2 of 5 (Gemini, Grok).
- Designs with a full cost model: 1 of 5 (Perplexity).
- Gaps all five name, in their own ways: no real decision pairs
  yet, no calibrated gate yet, no sending channel yet, and no
  proof that laboratory performance transfers to real use.

## Next — Round 3 (see Round 3 brief)
Round 3 should stop designing in parallel and start sequencing:
which experiment runs first on the smallest feasible budget, what
shared dataset and scorecard the five designs can share without
merging their scores, and what result in each lane would stop,
pivot, or scale the programme. It should also take up the questions
Round 2 left open: label reliability, the interruption-versus-missed
-warning tradeoff users actually accept, the forgetting paradox for
entangled entities, and a cost ceiling before any build.
