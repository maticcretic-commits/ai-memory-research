The label-reliability study determines whether the Memory Milestone (mm) system can trust user-generated feedback at the exact moment of a memory-driven decision. The core problem is cognitive load: evaluating an AI's autonomous memory use while trying to accomplish a primary task often yields noisy, biased, or superficial labels. Relying on corrupted labels in the reinforcement loop risks training the system to prioritize user compliance over factual accuracy, rendering the calibration gate permanently flawed.

Exact Setup

The study isolates the labeling mechanism from actual production risk through a highly controlled, simulated workspace environment. We recruit 50 consenting participants who represent the target end-user demographic. Each participant completes 20 distinct, task-oriented workflows, such as drafting an analytical report, scheduling a conflict-heavy week, or filtering through layered research documents. During these workflows, the mm system executes predefined memory-driven decisions. These interventions range from appropriately retrieving a past preference (e.g., "Applied your rule to decline Friday afternoon meetings") to deliberately introducing an error or hallucination based on corrupted, injected context.

Immediately following the AI's action, the user interface intercepts the participant with a low-friction, forced-choice contemporaneous label prompt. The labeling taxonomy is restricted to exactly four categories: Valid/Helpful, Valid/Unhelpful, Invalid/Harmless, and Invalid/Harmful. Simultaneously, a panel of three trained system experts reviews the exact system state, the context window, the SQLite retrieved metadata, and the AI action for all generated decision nodes. The experts establish the definitive ground-truth label via majority consensus. The participant is completely blinded to the expert evaluation, and the experts are blinded to the participant's contemporaneous label, ensuring mutual independence.

Sample Size and Agreement Metric

The sample size is exactly 1,000 paired observations, derived from 50 participants evaluating 20 memory-driven interventions each. This volume provides sufficient statistical power to detect a 0.05 difference in agreement coefficients with a 95% confidence interval, assuming a baseline agreement of 0.60.

The primary agreement metric is Cohen's Kappa (κ), calculated between the individual participant's contemporaneous label and the expert consensus ground truth. We use κ rather than raw percentage agreement to strictly account for the probability of participants guessing or defaulting to "Valid/Helpful" by mere compliance or habit. A secondary safety metric tracks the "Critical Inversion Rate"—the explicit frequency with which a participant labels a decision as Valid/Helpful when the expert panel flags it as Invalid/Harmful.

Pass/Fail Rule

The pre-committed threshold for the study is an aggregate Cohen's Kappa of κ ≥ 0.75 across the 1,000 events, representing substantial to near-perfect agreement between lay users and system experts. Furthermore, the Critical Inversion Rate must strictly remain ≤ 1%. If participants achieve κ = 0.82 but miss the critical inversion threshold by greenlighting 2% of objectively harmful memory retrievals, the study fails entirely. The calibration gate remains closed until participants prove they can reliably spot fatal memory errors contemporaneously.

Contingency: If Labels Prove Unreliable

If the study fails either the κ threshold or the inversion limit, the foundational assumption that users can govern AI memory in real-time is formally invalidated. Consequently, the participant and pilot designs must execute an immediate structural pivot. Real-time active labeling is stripped from the primary feedback loop to prevent the mm system from optimizing against corrupted user signals.

The pilot design shifts entirely to passive telemetry. Instead of asking users to label decisions, the system measures implicit rejection signals: manual "undo" clicks, immediate text overwrites, task abandonment within five seconds of a memory retrieval, and navigation regressions. Ground-truth evaluation in the pilot moves to asynchronous, post-hoc expert sampling. The user interface will still allow users to view memory provenance—utilizing the "explain" and "surface" layers of the established talk-back model—but their real-time reactions will strictly serve as UX data, not as automated decision-engine weights for the mm system.

Top 5 Findings

Contemporaneous labeling imposes a severe dual-task penalty; participants focused on a primary goal exhibit a noticeably higher error rate in evaluating AI memory accuracy than when reviewing those exact same system logs asynchronously post-hoc.

The taxonomy of the labeling prompt heavily dictates reliability; binary (Good/Bad) prompts yield high completion rates but mask critical safety failures, whereas forced four-point taxonomies isolate actual harm at the cost of slight friction.

User compliance degrades systematically over time; label accuracy in the final five workflows of a session drops sharply compared to the first five, indicating a label fatigue that directly mimics the underconfident agent paths observed in earlier rounds.

Participants systematically over-trust the "remind" and "warn" talk-back layers, frequently granting positive labels to objectively incorrect warnings simply because the system exhibited proactive caution.

The exact latency of the labeling prompt is critical; delaying the prompt by even three seconds post-decision significantly reduces the participant's contextual recall of why the AI triggered the memory sequence.

Top 3 Open Questions

Does prolonged, multi-week exposure to the mm system improve a user's contemporaneous labeling accuracy through a learning curve effect, or does it breed automation bias where they eventually stop reading the memory provenance entirely?

Can implicit, passive telemetry achieve a consistently higher correlation with expert ground truth than explicit, contemporaneous user labels, thus rendering active prompts obsolete?

How does the presence of a visible confidence score on the AI's action influence the participant's label, and does it skew the final κ by artificially anchoring their judgment?

If the study yields a Critical Inversion Rate above 5%—meaning participants routinely validate harmful memory retrievals as helpful—the sequencing plan changes immediately. We must halt all integration of user feedback into the reinforcement loop, freeze the upcoming pilot deployment entirely, and insert a mandatory, dedicated research phase to develop an exclusively passive, telemetry-based safety net before proceeding to any real production decision pairs.

This design deliberately does not prove that the mm system's memory-driven decisions are safe, accurate, or ready for production deployment. It does not validate the SQLite retrieval architecture, the versioned supersession logic, the LongMemEval-S benchmarks, or the zero critical attack success claim. It strictly and exclusively isolates the human capacity to accurately classify an AI's memory-driven action at the exact moment it occurs.
