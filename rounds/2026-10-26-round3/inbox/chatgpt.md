AI Memory Research — Round 3
Talk-back / UX lane: Shared Experiment Reporting Scorecard
Objective and reporting principle

Memory Milestone (mm) is built around a consequential proposition: memory should influence decisions, not merely retrieve relevant context. Its talk-back layer must decide whether to surface information, remind, warn, ask, explain, or remain silent. The research challenge is therefore not simply whether memory retrieves the right fact. It is whether the system takes an appropriate communicative action, at the right time, with justified confidence, without creating unnecessary interruptions or suppressing important interventions.

Round 3 should establish a common reporting standard before any Round 2 experiment begins. The five experiments address different questions, populations, and evidence types. They must share a scorecard structure without sharing a combined score.

The governing rule is common measurement, separate conclusions. A synthetic stress test, a retrieval benchmark, and a real-world user pilot cannot be treated as interchangeable evidence. A result that looks favorable on one dimension must not conceal a failure on another.

The existing internal mm figures—829 tests green, LongMemEval-S R@1 0.712 / MRR 0.797, and six red-team rounds reaching zero critical attack success in the final round—remain unverified claims for this reporting exercise. They are background, not experiment results or proof of production readiness.

1. Shared one-page scorecard

Every experiment receives its own one-page report, using the following fixed structure.

Memory Milestone — Experiment Scorecard

Required reporting template · One experiment per page

A. Identity and evidence provenance

Experiment ID, name, version, owner, dates, and preregistration status.

Research question and primary hypothesis.

Population and evidence type: synthetic, benchmark, simulated, or real-user/real-decision.

Planned sample, enrolled sample, completed sample, exclusions, and reasons.

Dataset version, scenario-generation method, evaluation code version, and baseline definition.

B. Decision and talk-back outcomes

Correct interventions, unnecessary interventions, missed interventions, and appropriate silence.

Counts and denominators for every reported rate.

Breakdown by action: surface, remind, warn, ask, explain, silence.

Severity-weighted errors reported separately from ordinary errors.

C. Silence and omission

Total eligible opportunities for silence.

Appropriate silences and inappropriate silences.

Total opportunities requiring intervention.

Missed interventions and their severity.

False-intervention rate and missed-intervention rate displayed together.

D. Confidence, safety, and cost

Claim-level and action-level confidence calibration, where measurable.

Abstentions, escalation decisions, and confidence-gate failures.

Privacy, manipulation, prompt-injection, and forgetting-related failures where relevant.

Latency, compute or token cost, human review time, and estimated cost per evaluated decision.

E. Interpretation and audit trail

Primary outcome, uncertainty interval, baseline comparison, and limitations.

Prespecified thresholds and whether each passed, failed, or remains unassessed.

Protocol deviations, missing data, subgroup results, and unresolved anomalies.

Links or identifiers for raw records, scoring rules, and reproducible analysis.

Every percentage must appear alongside its numerator and denominator. For example, report “6/120 = 5.0%,” not “5%.” When the denominator is zero or unavailable, report “not estimable,” never zero.

2. Five experiment-specific scorecards
Experiment 1 — Blinded paired talk-back gate versus retrieval-only baseline

Primary question: Does adding the talk-back policy improve decisions over retrieval alone?

Report the number of scenarios evaluated, paired scenarios completed, disagreements between evaluators, and outcomes for both conditions. Show correct interventions, harmful or unnecessary interventions, missed interventions, appropriate silence, and inappropriate silence.

The critical paired comparison is the change in decision quality on the same scenarios, with uncertainty intervals and the paired analysis method disclosed. Include results by action type and severity, not just an aggregate accuracy figure. Report whether evaluators were genuinely blinded and how adjudication was performed.

Trust check: Can a reader reconstruct the paired comparison and determine whether improvements came from better interventions, excessive speaking, or both?

Experiment 2 — Fourteen-pair real-world pilot over 14–21 days

Primary question: Does the proposed talk-back behavior help users in actual workflows?

Separate recruited participants, enrolled pairs, eligible decisions, completed episodes, and missing follow-ups. Report real-world observations separately from any synthetic or simulated episodes. Show within-pair changes, user-reported usefulness, interruption burden, trust, corrections, and missed consequential interventions.

The 48-hour re-scoring must have its own results: agreement with initial judgments, changed labels, and reasons for changes. Distinguish independent user outcomes from researcher ratings.

With only 14 pairs planned, present uncertainty prominently. A small pilot can reveal usability failures and measurement problems; it cannot establish broad production safety.

Trust check: Can the reader identify what happened to actual users, what was inferred by evaluators, and what remains unknown because of sample size or missing data?

Experiment 3 — Append-only SQLite ledger and dual-axis silent-consolidation gate

Primary question: Can the ledger preserve history and support reliable consolidation without erasing consequential distinctions?

Report synthetic pair counts, duplicate and conflicting records, supersession events, version-history integrity, retrieval outcomes, and consolidation errors. Measure both factual retention and decision-relevant retention. A system that preserves facts but loses the constraint that changes a decision has not passed the intended test.

Show the two consolidation axes independently, including false consolidation and missed consolidation counts. Document replay results, deterministic reproducibility, and any cases where a later record silently replaced earlier information.

Trust check: Can an auditor trace each resulting memory to its source, inspect superseded versions, and reproduce the consolidation decision without relying on the model's explanation alone?

Experiment 4 — Red-team forgetting test on 200 synthetic profiles

Primary question: Does the system respect forgetting and resist attempts to recover information that should no longer influence behavior?

Report attack attempts, successful recoveries, partial leaks, blocked attempts, and indeterminate outcomes. Break down results by attack type and severity. Separate direct retrieval failures from indirect leakage through summaries, derived memories, recommendations, or talk-back.

Zero observed critical failures must be reported as a count and denominator, with uncertainty and test coverage. It does not establish zero risk outside the tested attacks.

Include controls confirming that forgetting requests were applied to the intended records and that relevant historical artifacts were checked.

Trust check: Can the reader distinguish “not recovered in tested attacks” from “demonstrated absent across every possible storage and inference path”?

Experiment 5 — LongMemEval-S reproduction plus 40 participants × 20 episodes

Primary question: How do benchmark retrieval and user-facing memory decisions behave under controlled and counterfactual conditions?

Report benchmark reproduction results separately from participant results. For the benchmark, include exact dataset and scoring versions, R@1, MRR, exclusions, and baseline comparisons. For the planned 800 participant episodes, show recruited and completed counts, participant-level clustering, and counterfactual-twin consistency.

Report retrieval correctness separately from decision correctness and talk-back appropriateness. Counterfactual twins should reveal whether changing a decision-relevant fact changes the output appropriately while irrelevant changes leave it stable.

Trust check: Can the reader verify that the benchmark was reproduced faithfully and that participant-level dependence was accounted for rather than treating all 800 episodes as independent people?

3. Rules for interpreting every scorecard

Three restrictions apply across all five reports.

First, never merge scores across experiments. No single mm readiness number may combine synthetic security results, benchmark retrieval, and real-user outcomes.

Second, always pair silence with missed intervention. Report both the proportion of eligible opportunities where the system remained silent and the proportion of intervention-required opportunities where it failed to intervene. Include raw counts, denominators, and severity. Silence is not inherently success; speech is not inherently helpful.

Third, separate measurement from permission. High confidence does not authorize an action. Confidence calibration, decision quality, privacy compliance, and user impact require distinct evidence. A passed threshold must be identified as prespecified, exploratory, or operationally provisional; none should be described as proven safe merely because a test passed.

Before trusting any result, a reader must be able to inspect the protocol, reproduce the denominator, trace exclusions, distinguish real from synthetic evidence, understand uncertainty, compare against the specified baseline, and locate the underlying records. Missing evidence must be visible, not converted into a favorable score.

Top 5 findings

One template, five independent conclusions. Standardized reporting improves comparability without pretending the experiments measure the same thing.

Silence is a two-sided outcome. Appropriate non-interruption and dangerous omission must be reported together.

Raw counts are mandatory. Percentages alone conceal small samples, denominator changes, and rare but consequential failures.

Provenance is part of UX trust. Readers need to reconstruct how evidence became a decision, not merely accept the final label.

Synthetic success cannot substitute for real-world evidence. Security tests and benchmark scores answer narrower questions than actual user benefit and production reliability.

Top 3 open questions

What common severity taxonomy and minimum evidence requirements should govern critical missed interventions across all five experiments?

Which confidence-calibration metrics and abstention criteria are appropriate for each task, given the unresolved underconfident-agent path?

How can the team obtain enough consented, auditable real decision pairs to evaluate usefulness and missed interventions without overstating the evidence from the 14-pair pilot?

Sequencing consequence and limits

What would change the sequencing plan: If the first blinded paired experiment shows that the talk-back gate increases missed consequential interventions or creates a substantial increase in harmful interruptions relative to retrieval-only, the team should pause expansion into the real-world pilot and resolve that failure first. The scorecard should make that decision possible without inventing a universal numerical safety threshold before evidence exists.

What this work deliberately does NOT prove: It does not prove that any Round 2 experiment has run, that internal mm figures are independently verified, that the proposed metrics or thresholds are validated, that silence is safe, or that the system is production-ready. It establishes the reporting discipline needed to distinguish those claims from evidence.
