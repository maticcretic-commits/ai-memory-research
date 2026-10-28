# AI Memory Research — Round 3 brief (to send, lane framing added per partner)

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

Round 1 established the architecture: SQLite as the authoritative
record with hybrid retrieval and metadata filtering first, versioned
supersession with history preserved and no silent overwrites, talk-back
as its own layer (surface, remind, warn, ask, explain, silence), and
confidence judged per claim and per action, with high confidence
granting no permission.

Round 2 produced five experiment designs, none yet run. ChatGPT:
blinded, paired talk-back gate versus retrieval-only baseline on 300
scenarios (60 real pairs, availability not established, plus 240
controlled), Correct Silence Rate primary, pass at silence at least
90% and critical omissions at most 2%. DeepSeek: one operator, one
decision pair per day, 14 valid pairs in 14–21 days, re-scored after
48 hours, fewer than 10 valid pairs a feasibility failure. Gemini:
append-only SQLite ledger with a dual-axis silent-consolidation gate
(extraction confidence over 0.90 plus supersession confidence over
0.85) on 10,000 synthetic pairs versus a vector-only merge baseline.
Grok: 200 synthetic profiles, forget 40% of ~2,000 sensitive records,
~3,000 red-team probes over 14 simulated days, with kill triggers
including recovery over 5% at day 7 and any silent overwrite. Perplexity:
LongMemEval-S reproduction (500 questions, separate scorecard) plus
40 participants × 20 low-stakes episodes with counterfactual twins
(1,600 cases, 18,000 executions), pass at joint success up at least
5 points over retrieval-only and cost per successful decision at most
1.25× retrieval-only.

Round 2 left the thresholds unreconciled, the cost model in only one
lane, and the real-pair bottleneck unsolved. Round 3 stops designing
in parallel and starts sequencing.

Your lane task. Design, in your lane only, one concrete piece of the
sequencing plan below. Do not redesign the other lanes' experiments.
Do not claim any experiment has run, any figure has been verified, or
any threshold has been proven safe. State what your piece deliberately
does NOT settle.

LANE TASKS (use only the lane framing for your chat):

- ChatGPT (talk-back / UX lane): design the shared reporting
  scorecard for all five Round 2 experiments. One page per experiment,
  scores never merged across experiments, synthetic and real results
  always reported separately, silence and missed-intervention rates
  always shown together, raw counts beside every percentage. Say
  exactly what a reader must be able to check from the scorecard
  before trusting any single result.

- Gemini (deep research lane): design the label-reliability study
  that Round 2 depends on. Can consenting participants supply
  reliable contemporaneous decision labels, and how would we know?
  Give the exact setup, sample size, agreement metric, and pass/fail
  rule, and say what happens to the Perplexity and DeepSeek designs
  if labels prove unreliable.

- Grok (challenger QA lane): design the stop / pivot / scale
  decision tree across all five Round 2 experiments. For each
  experiment, name the result that stops it, the result that pivots
  it (and to what), and the result that scales it. Include your
  Round 2 kill triggers as hard stops, and challenge the sequencing
  itself: what is the most dangerous order to run these in?

- DeepSeek (build lane): design the smallest feasible build order.
  What gets implemented first, second, and third, with what effort
  and what each step unlocks? Start from your 14-pair pilot, the
  write-time provenance and hook-based secret blocking quick builds,
  and read-time re-scoring. Say what you deliberately do NOT build
  in this first pass.

- Perplexity (verified research lane): design the cost ceiling and
  the evidence check on the interruption tradeoff. What cost per
  successful decision would make the full system not worth it
  versus retrieval-only, how is that ceiling measured, and what
  public evidence exists on the interruption-versus-missed-warning
  tradeoff users actually accept? Cite sources you can verify, and
  say plainly where no public evidence exists.

Deliverable format. 700–1000 words, plus your top 5 findings and your
top 3 open questions. End with what result in your piece would change
the sequencing plan, and what your piece deliberately does NOT prove.
