## Experiment: paired decisions under changing memory

**Hypothesis:** A memory system that explicitly resolves supersession and separately gates interruptions will produce more correct, appropriately quiet decisions than retrieval-only memory, at an acceptable measured cost.

This is a proposed experiment, not a completed evaluation. All sample sizes, thresholds, and budgets below are design choices, not verified performance figures. I conducted this work independently; I have not verified the system's internal figures.

## 1. Benchmark reproduction and scope

Use LongMemEval as the public reproduction anchor. Its published benchmark contains 500 questions covering information extraction, multi-session reasoning, temporal reasoning, knowledge updates, and abstention. These abilities overlap with the Round 1 concerns, but answering memory questions is not equivalent to making useful decisions.

Run all 500 questions from the repository's LongMemEval-S release. Pin the repository commit, dataset checksum, inference settings, prompt, and evaluator configuration before execution. The official repository supports timestamped-history inputs and question-ID/output records evaluated through its supplied script.

Reproduce that procedure, not a claimed leaderboard score. Report any unavailable dependency or changed judge as a reproduction deviation. Use one available, version-pinned answering model throughout; its identity remains unresolved until access and reproducibility are checked. Publish that choice before collecting results.

This reproduction and the decision extension below form one experiment with separate scorecards. Never combine their scores.

## 2. Exact decision dataset

Recruit 40 consenting participants, each contributing 20 de-identified, low-stakes decision episodes: 800 episodes total. Examples include scheduling preferences, document routing, or whether an optional reminder was useful. Exclude medical, legal, financial, and emergency decisions.

Each episode must contain:

- A timestamped memory history available before the decision.
- The actual task and contemporaneous permission state.
- A participant-confirmed acceptable action and acceptable talk-back behavior.
- Evidence showing whether a remembered claim was current, superseded, unresolved, or irrelevant.

Create one participant-approved counterfactual twin per episode, changing exactly one decision-relevant condition. This produces 800 pairs, or 1,600 cases. The original episodes are real; the twins are constructed tests and must be labelled accordingly. This does not create 800 observed causal comparisons.

Split by participant: 10 participants for development and 30 for locked testing. Thus, development contains 400 cases; testing contains 1,200.

Balance the locked set across four primary strata: changed facts, unresolved conflicts, permission-sensitive decisions, and irrelevant memories. Require half the test cases to have "no unsolicited talk-back" as the correct label. Failure to obtain these quotas postpones testing rather than permitting silent substitutions.

## 3. Conditions and ablations

Use the same model, task instructions, embedding configuration, and decoding settings across five conditions:

1. No persistent memory.
2. Retrieval-only hybrid memory.
3. Full proposed system.
4. Full system without supersession resolution.
5. Full system without the separate talk-back gate.

For memory-enabled conditions, SQLite is the authoritative record. Metadata filtering precedes vector ranking. Store claim IDs, source timestamps, validity intervals, supersession links, and permission scope. Preserve old versions rather than overwriting them.

The full system returns a structured action proposal, per-claim confidence, action confidence, supporting claim IDs, permission status, and one talk-back label: silence, surface, remind, warn, ask, or explain. Silence suppresses unsolicited communication, not the requested task output.

Fix retrieval at eight records and a 2,000-token evidence budget. Use the development split to freeze confidence thresholds. Run three repetitions per condition, resetting memory between cases. The locked decision evaluation therefore contains 18,000 executions. All actions remain sandboxed; nothing is sent or changed externally.

## 4. Metrics and pass/fail rules

Primary outcome: joint decision success—acceptable task action, valid permission handling, and correct talk-back behavior together.

Also report:

- Stale-memory reliance and unsupported-claim rates.
- False-interruption rate among silence-labelled cases.
- Missed-intervention rate among intervention-required cases.
- Counterfactual sensitivity: whether each pair changes behavior correctly.
- Claim and action Brier scores, measuring confidence against correctness.
- Audit completeness, median latency, and 95th-percentile latency.

Participants establish labels before viewing outputs. Two blinded graders score every locked case; disagreements receive adjudication, with unresolved cases reported separately. Freeze the scoring rubric beforehand.

The full system passes only if all conditions hold:

- Joint success improves over retrieval-only by at least five percentage points, with a participant-clustered 95% confidence interval excluding zero.
- False interruptions are at most 5%; missed interventions at most 10%.
- No unauthorized action proposals occur.
- Every decision has a complete evidence-and-permission audit record.
- Fully allocated cost per successful decision is no more than 1.25 times retrieval-only.

These are proposed engineering gates, not established safety standards.

## 5. Cost-per-decision measurement

Record actual billed tokens, cached-token categories, retries, embedding calls, ingestion, retrieval compute, and storage. Freeze dated provider prices; official pricing distinguishes input, output, and cached-input charges. Do not substitute a remembered price or invent a dollar forecast.

Report three denominators: every attempted decision, every jointly successful decision, and incremental successes over retrieval-only. Include failed calls and silent outcomes.

Separate cold-start cost, including initial ingestion, from warm-operation cost. Allocate ingestion across the observed decisions for that participant; also show sensitivity at 10, 100, and 1,000 decisions. Keep experimental grading and participant-compensation costs separate from operating cost, but disclose both.

## 6. Failure modes, redesign triggers, and limits

Public-benchmark contamination, retrospective labels, artificial twins, grader bias, unequal context exposure, and model nondeterminism could distort results. Participant clustering reduces neither selection bias nor retrospective hindsight. Report exclusions and disagreements, and publish de-identified artifacts only with consent.

If supersession removal changes nothing, investigate retrieval coverage before adding complexity. If the talk-back gate reduces interruptions but increases missed warnings, redesign its threshold or inputs. If gains disappear after charging ingestion and retries, simplify the memory pipeline.

Passing would support this configuration on this sample—not production readiness. It would not prove resistance to poisoning, complete forgetting, long-term user benefit, generalization to consequential domains, or safe autonomous execution.

## Top 5 findings

1. LongMemEval provides a reproducible memory-evaluation anchor, not evidence of real decision benefit.
2. Real episodes and constructed counterfactuals must remain separately identified.
3. Silence needs its own denominator; aggregate accuracy can hide interruptions.
4. Cost must include failures, ingestion, retries, and silent decisions.
5. Supersession and talk-back require separate ablations to identify their contributions.

## Top 3 open questions

1. Can participants provide sufficiently reliable contemporaneous decision labels?
2. Will measured benefits persist across longer histories and different models?
3. What interruption-versus-missed-warning tradeoff will users actually accept?
