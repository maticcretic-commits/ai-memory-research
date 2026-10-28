# DeepSeek — AI Memory Research Round 2 (verbatim)
- Lane: Build the 14-pair pilot + read-time re-scoring
- Browser task: completed 2026-10-26, 22:02-22:03 IST (measured, 1m)
- Signed in: no sign-in prompt shown, new chat started, brief sent exactly as written
- Model name shown in UI: not visible — only "DeepThink" and "Search" options
- Chat: https://chat.deepseek.com/a/chat/s/82890422-c609-4eab-8a80-91e03b0ee9d6

---

Round 2 Report: The 14-Pair Pilot — One Production Decision Pair Per Day, with Read-Time Re-Scoring

Hypothesis

H1 (primary): A 14-day pilot in which a single human operator records exactly one memory-grounded production decision pair per day — one "silence" event (memory was available but not surfaced) and one "interruption" event (memory was surfaced and forced a decision) — will produce a read-time re-scoring trace that distinguishes useful memory activation from noise at a rate better than chance, using only the operator's own contemporaneous judgments.

H2 (secondary): Re-scoring the same 14 pairs at read time (after the full pilot completes) will change at least 3 of the 14 original activation labels, demonstrating that in-the-moment judgment is insufficiently stable for production calibration — a finding that directly challenges the Round 1 assumption that per-claim confidence can be captured accurately at write time.

The pilot deliberately produces zero claims about model quality, retrieval accuracy, or generalization. It produces one claim: whether a single human can generate and re-score a small, auditable decision-pair corpus without the corpus collapsing into either trivial agreement or incoherent noise.

Exact Setup

Operator and substrate. One human operator (me) uses a locally hosted assistant with a SQLite-backed memory store. No cloud model. The memory store is seeded with 14 days of the operator's own prior written notes, emails, and task logs — approximately 40–60 distinct memory entries per day, filtered to entries the operator explicitly authored. This is not a synthetic dataset. It is the operator's real working record for a two-week period.

Daily protocol. Each working day, at end of day, the operator reviews the day's assistant interactions and identifies exactly one production decision pair:

Pair element A (silence): A moment when memory existed and was relevant, but the assistant did not surface it. The operator records: what memory, why it was relevant, and what decision was made without it.

Pair element B (interruption): A moment when the assistant surfaced memory and the operator changed or confirmed a decision because of it. The operator records: what memory, what decision was pending, and what changed.

If no such pair occurred on a given day, the operator records "null day" and the day does not count toward the 14. The pilot stops at 14 valid pairs, not 14 calendar days.

Read-time re-scoring. After all 14 pairs are collected, the operator re-reads each pair without access to the original labels. For each pair, the operator answers three questions on a 1–5 scale: (1) Was the silence justified? (2) Was the interruption useful? (3) Would I want this memory surfaced again in a similar situation? The original labels and the re-scored labels are compared. A change of ≥2 points on any question counts as a "flip."

Storage. All pairs, original labels, and re-scored labels live in a single SQLite table. The authoritative record is the pair ID, timestamp, original label, and re-scored label. No vector store is involved. This is deliberate: the pilot tests the decision trace, not retrieval.

Dataset Size

14 valid pairs = 28 events (14 silence, 14 interruption). Null days excluded. Expected collection window: 14–21 calendar days. If fewer than 10 valid pairs are collected in 21 days, the pilot fails to reach minimum viability and is reported as a feasibility failure, not a hypothesis test.

The read-time re-scoring produces 42 re-score judgments (14 pairs × 3 questions). The comparison produces at most 14 "flip" opportunities.

Metrics

Primary metric: Flip rate. Proportion of the 14 pairs where re-scoring changes the original judgment by ≥2 points on any of the three questions. Pass threshold: 3/14 flips (21.4%). If flip rate is below 3/14, the original in-the-moment labels are considered stable enough to serve as a calibration anchor. If flip rate is ≥3/14, in-the-moment labeling is demonstrably unstable and must not be used as ground truth.

Secondary metric: Silence justification rate. Proportion of the 14 silence events where the operator's re-scored answer to "Was the silence justified?" is ≥4 (on 1–5). Pass threshold: ≥10/14 (71.4%). This tests whether the operator can distinguish "memory should have spoken" from "memory was right to stay quiet." A low rate means the operator cannot reliably judge silence — a critical finding for the Round 1 claim that silence is a measured success.

Tertiary metric: Interruption precision. Proportion of the 14 interruption events where the re-scored answer to "Was the interruption useful?" is ≥4. Pass threshold: ≥10/14. This tests whether surfaced memory was actually decision-relevant, not merely present.

Interruption/silence balance metric. The pilot enforces a 1:1 ratio by design (one of each per pair). Any day where the operator cannot identify both a silence and an interruption is a null day. This is not a metric but a structural constraint. It prevents the corpus from becoming all interruptions (memory shouting) or all silences (memory mute).

Pass/Fail Criteria

Pilot passes if: Flip rate ≥3/14 AND silence justification rate ≥10/14 AND interruption precision rate ≥10/14. All three must hold.

Pilot fails if: Any one of the three thresholds is not met. A failure on flip rate means the re-scoring method is too unstable to trust. A failure on silence justification means the operator cannot judge silence reliably. A failure on interruption precision means the surfaced memory was not decision-relevant.

Inconclusive if: Fewer than 10 valid pairs collected. Report as feasibility failure, no hypothesis test.

Risks

Risk 1: Operator bias in pair selection. The operator chooses which moments count as "pairs." This is a convenience sample of convenience samples. Mitigation: the operator must select pairs before reviewing the assistant's full day log, using only a timestamped activity trace. This is imperfect. The pilot does not claim representative sampling.

Risk 2: Re-scoring contamination. After 14 days, the operator remembers the original labels. Mitigation: the re-scoring interface presents pairs in randomized order, strips the original label, and requires the operator to wait 48 hours after the final pair before re-scoring. This reduces but does not eliminate memory contamination. The flip rate is therefore a lower bound on instability.

Risk 3: Null days dominate. If the operator's workflow does not generate both silence and interruption events daily, the pilot stalls. This is itself a finding: the decision-pair format may not be naturally occurring at daily frequency. The pilot reports the null-day rate explicitly.

Risk 4: The pilot proves nothing about model behavior. The assistant's memory surfacing is not instrumented. The operator records what they perceived as silence or interruption. Perception is not ground truth about retrieval. This is the largest limitation.

What Would Change the Design

If flip rate is high (≥5/14): The design changes from "one pair per day" to "two-pass same-day labeling" — the operator labels each pair once at creation and once at end of day, same day, no 48-hour delay. If same-day re-scoring still flips, the problem is not memory decay but labeling instability, and the entire calibration approach needs a different anchor (e.g., external task outcome, not operator judgment).

If silence justification rate is low (<10/14): The design drops silence from the pilot entirely and becomes an interruption-only corpus. Silence as a measured success would be declared unmeasurable at this scale by a single operator.

If interruption precision is low (<10/14): The memory store is too noisy or the operator's relevance threshold is miscalibrated. The design changes to pre-filtered memory — only entries the operator explicitly starred at write time are eligible for surfacing. This tests whether the problem is memory quality or surfacing policy.

What Could Go Wrong (and What This Deliberately Does NOT Prove)

What could go wrong: The operator may unconsciously select pairs that make the hypothesis look good. The pilot may produce 14 pairs that are all cleanly labeled and re-scored with zero flips — not because the method is stable, but because the operator chose only easy cases. The null-day rate may be so high that the pilot never reaches 14. The SQLite store may fail to record timestamps correctly, invalidating the 48-hour delay.

What this deliberately does NOT prove: That memory should be surfaced at a particular confidence threshold. That any model's retrieval is accurate. That the silence/interruption distinction generalizes beyond this one operator. That 14 pairs are sufficient for statistical inference — they are not. That the read-time re-scoring method is reliable at larger scale. That production decision pairs can be collected without dedicated instrumentation. The pilot produces one thing: a feasibility signal about whether a single human can generate and re-score a small decision-pair corpus with enough stability to justify a larger instrumented study. Nothing more.

Top 5 Findings (from design analysis)

The 14-pair format forces a 1:1 silence/interruption constraint that no Round 1 partner proposed. This structural choice directly tests the "silence is a measured success" claim by making silence a required daily output, not an optional observation.

Read-time re-scoring is the only way to detect labeling instability without instrumenting the model. The 48-hour delay is a deliberate contamination control; without it, the flip rate is meaningless.

The primary risk is not model failure but operator selection bias. The pilot's validity rests on pair selection that happens before full-log review — a weak control that must be stated explicitly.

A high flip rate would invalidate per-claim confidence at write time as a calibration source. This is the most consequential possible outcome: it would force the design toward outcome-anchored labels rather than operator-reported confidence.

Null days are data, not failure. If the operator cannot find a silence/interruption pair daily, the decision-pair frequency assumption behind the entire pilot program is wrong.

Top 3 Open Questions

Can a single operator reliably distinguish "silence" from "memory was absent"? The pilot records perception, not retrieval ground truth. If the operator cannot tell the difference, the silence metric is measuring noise.

Is 48 hours sufficient to wash out recall of original labels? No evidence exists on this specific task. The flip rate is a lower bound; the true instability may be higher.

What happens if the operator's real workflow produces zero interruption events for a week? The pilot has no contingency for a memory system that is so conservative it never speaks. This is arguably a success for silence but a failure for the decision-pair method.
