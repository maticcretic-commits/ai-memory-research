# AI Memory Research — Round 2

**Lane:** Talk-back policy experiment and silence metric
**Approach:** Individual proposal; designed to test whether memory improves decisions without unnecessarily interrupting users.

## Executive summary

My experiment tests one specific question: **Can an AI memory system recognize when remembered information should influence a decision, communicate uncertainty when necessary, and remain silent when speaking would add no value?**

The central problem is not whether the system can retrieve a memory. It is whether the system knows what to do with it. A remembered preference may be useful in one situation, irrelevant in another, and dangerously outdated in a third.

I propose a controlled, paired evaluation of five talk-back actions: *surface, remind, warn, ask,* and *explain.* Every test case receives a reference judgment about the appropriate action, including when the correct action is silence.

The experiment focuses on stale and conflicting memories because Round 1 identified them as a primary failure mode. It also addresses the evidence gap: laboratory performance must not be presented as proof of real-world decision improvement.

The deliverable is a reproducible experiment specification, not a claim that the proposed system has already passed testing.

## 1. Hypothesis

When memory has a separate talk-back policy, it will make fewer unnecessary interruptions and fewer harmful omissions than a baseline that surfaces relevant retrieved memories directly, without an explicit decision about whether to speak.

The policy should choose among six outcomes:

| Outcome | When it should be used |
|---|---|
| Surface | A relevant memory materially improves the current answer or decision. |
| Remind | A previously established commitment or preference is relevant now. |
| Warn | A credible risk, conflict, or consequential outdated assumption needs attention. |
| Ask | Missing or conflicting information could change the recommended action. |
| Explain | The user needs to understand why memory influenced a recommendation or action. |
| Silence | No memory-based intervention would meaningfully improve the outcome. |

These outcomes are not necessarily mutually exclusive in a real product. For this first experiment, each case receives one primary action to make scoring reproducible.

## 2. Exact experiment setup

Experiment name: Talk-Back Decision Gate, version 1.

Design: A blinded, paired comparison between two policies on the same cases.

- **Policy A — Retrieval-only baseline:** Retrieve relevant memories using the available memory mechanism and surface the highest-ranked relevant memory according to a fixed presentation rule. It has no separate intervention decision.
- **Policy B — Talk-back gate:** Use the same retrieved memories, then choose one of the six outcomes based on relevance, freshness, conflict, decision impact, confidence, and the cost of interrupting the user.

The two policies receive identical user requests and memory records. This isolates the contribution of the talk-back decision layer as far as the implementation permits. Neither policy may silently rewrite a stored memory or treat confidence as permission to take an action.

### Dataset

Use 300 decision scenarios:

- **60 real decision pairs:** Consented, de-identified examples in which a remembered fact or preference could affect a later decision. These must be collected prospectively; their availability is not established.
- **240 controlled scenarios:** Constructed cases that vary memory age, conflicting versions, uncertainty, relevance, consequences, and whether speaking is useful.

The controlled set should include clear-silence cases, necessary warnings, ambiguity requiring clarification, harmless stale memories, and cases where the newest memory supersedes an older one.

Create a scenario specification before generating the cases. Two independent reviewers label the appropriate primary action and the acceptable response. A third reviewer resolves disagreements. Reviewers should not know which policy generated a response.

If 60 genuine decision pairs cannot be collected, run the controlled evaluation separately and report the real-world evidence requirement as unmet. Do not substitute synthetic cases and describe the result as real-world validation.

### Execution procedure

1. Freeze the two policy versions, prompts, thresholds, and memory records.
2. Run both policies on all available scenarios using the same model configuration and tool permissions.
3. Record the chosen action, response text, cited memory identifiers, confidence by claim, and execution time.
4. Score results against the reviewers' reference labels.
5. Inspect every harmful warning omission, unnecessary interruption, unsupported claim, and stale-memory error.
6. Repeat the run with a fixed, predeclared repeat count if outputs are stochastic. Report variability rather than selecting the best run.

The model and infrastructure are deliberately unspecified because the existing system's internal implementation has not been independently verified.

## 3. Metrics

The experiment needs to measure both the cost of speaking and the cost of remaining silent.

### Primary metric: Silence quality

**Correct Silence Rate (CSR)**

CSR = Correct silence decisions / Cases where silence is appropriate

A silent decision is correct only if the policy does not surface, remind, warn, ask, or explain based on memory. Ordinary answers to the user's request are allowed; silence means no unnecessary memory-specific intervention.

CSR alone is insufficient: a system that never speaks could score perfectly on a set containing only silence-eligible cases.

Therefore, measure these companion metrics:

- **Unnecessary Intervention Rate:** Interventions on cases where reviewers judged silence appropriate, divided by all silence-eligible cases.
- **Critical Omission Rate:** Cases where the policy stays silent despite a necessary warning or clarification, divided by all cases requiring that intervention.
- **Action Accuracy:** Percentage of cases where the selected primary action matches the reference label.
- **Stale-Memory Error Rate:** Percentage of cases where the policy relies on a superseded or materially outdated memory without acknowledging the problem.
- **Unsupported Memory Claim Rate:** Percentage of memory-based claims that lack support in the recorded memory evidence.
- **Interruption Burden:** Total unnecessary memory-specific interventions per 100 scenarios, reported alongside their severity and estimated user effort.

These are proposed metrics, not established industry benchmarks. The denominators and severity labels must be frozen before testing.

## 4. Pass/fail criteria

Policy B passes only if it satisfies all of the following predeclared thresholds:

| Metric | Pass threshold |
|---|---|
| Correct Silence Rate | At least 90% |
| Critical Omission Rate | At most 2% |
| Stale-Memory Error Rate | At most 5% |
| Unsupported Memory Claim Rate | At most 1% |
| Action Accuracy | At least 85% |
| Unnecessary interventions | At least 30% fewer than Policy A |

These are proposed engineering acceptance thresholds, not empirically validated safety limits.

Also require that Policy B does not increase critical omissions relative to Policy A. Report raw counts and confidence intervals, not percentages alone. With a small dataset, apparently strong percentages may still have substantial uncertainty.

Failure rule: Any severe, reproducible case in which the policy uses a known-superseded memory to justify a consequential recommendation triggers a safety review, even if aggregate thresholds pass.

## 5. Risks and what could go wrong

- **Reviewer disagreement:** Whether a memory intervention is useful can be subjective. Mitigation: independent labels, written decision rules, agreement reporting, and adjudication.
- **Artificial scenarios:** Constructed cases may be easier than real conversations. Mitigation: report real and synthetic results separately.
- **Baseline unfairness:** A retrieval-only baseline may be deliberately weak. Mitigation: use a reasonable, frozen presentation rule and publish both configurations.
- **Metric gaming:** The policy may improve silence scores by speaking less everywhere. Mitigation: jointly enforce the critical omission, action accuracy, and warning requirements.
- **Privacy and selection bias:** Real decision pairs may reveal sensitive details or overrepresent users who agree to participate. Mitigation: consent, data minimization, de-identification, restricted access, and a documented sampling procedure.
- **Repeated testing and tuning:** Changing thresholds after observing failures can inflate apparent performance. Mitigation: use a development set for tuning and a held-out evaluation set for the final decision.

## 6. What result would change the design?

Three outcomes would drive a redesign:

1. **High unnecessary intervention rate:** Introduce a higher evidence threshold for low-impact reminders and require a clear decision benefit before speaking.
2. **High critical omission rate:** Separate safety-critical warnings from ordinary conversational interventions, with explicit escalation rules that do not depend solely on confidence.
3. **High stale-memory error rate:** Strengthen version and supersession checks before retrieval results can influence talk-back decisions. A memory with unresolved conflicts should trigger clarification or abstention rather than an unqualified assertion.

If Policy B reduces interruptions but increases harmful omissions, I would reject the current gate rather than accept the trade-off as an overall improvement.

If it performs well on controlled cases but poorly on real decision pairs, I would prioritize improving the real-world evaluation set and recalibrating the policy using actual user outcomes.

## 7. What this experiment deliberately does NOT prove

This experiment does not prove that memory improves long-term user outcomes, that users trust or prefer the policy, or that silence is always desirable. It does not establish resistance to deliberate memory poisoning, complete forgetting, or adversarial attacks. Nor does it establish that the underlying memory store, retrieval rankings, or confidence estimates are correct.

Even a successful result would establish only that the tested talk-back policy performs acceptably on the evaluated scenarios under the stated conditions.

## Top 5 findings

1. Silence must be evaluated against cases where speaking is necessary, not just cases where silence is appropriate.
2. Unnecessary interruptions and harmful omissions are separate failure modes; both require explicit thresholds.
3. Stale-memory handling must be evaluated as a distinct safety outcome.
4. Paired comparisons can isolate the contribution of a talk-back layer more effectively than evaluating it in isolation.
5. Controlled tests are useful for reproducibility, but genuine decision pairs are essential for understanding performance in real use.

## Top 3 open questions

1. Can we obtain enough consented, de-identified real decision pairs to test whether memory interventions actually improve decisions?
2. How should we measure interruption cost when a brief warning is mildly annoying but prevents a consequential mistake?
3. Should safety-critical warnings follow a separate policy from reminders and explanations, and what evidence should authorize that separation?

**Recommendation:** Run this as a gated research experiment, not a product launch criterion by itself. The first milestone is a reproducible paired evaluation with transparent labels, a defensible baseline, and separately reported results for synthetic and real decision scenarios.
