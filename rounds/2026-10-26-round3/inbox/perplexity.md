The ceiling should be the predeclared value of one additional successful decision over retrieval-only—not a universal dollar amount per AI response. Reject the full system when its incremental cost exceeds that value, or when it costs more without improving decisions. Public research supports a genuine interruption–awareness tradeoff, but does not establish an acceptable false-warning/missed-warning ratio for mm.

1. Define the economic rejection rule

Treat mm’s supplied performance, security, calibration, and production-readiness figures as unverified internal claims. They cannot establish willingness to pay or decision value.

For the same eligible decision population and evaluation period, define:

C_F, C_R: attributable costs of full mm and retrieval-only.

S_F, S_R: independently adjudicated successful decisions.

V: maximum acceptable expenditure per additional success, declared before outcome inspection.

Report cost per success, C_F/S_F and C_R/S_R, but make the adoption decision using:

ICER = (C_F − C_R) / (S_F − S_R).

The proposed rule is: full mm is economically unacceptable when ICER > V, assuming positive incremental success. If incremental success is zero or negative and cost is higher, retrieval-only dominates. If estimates remain uncertain, do not convert that uncertainty into an adoption claim.

Equivalently, the maximum full-system budget is:

C_Fmax = C_R + V(S_F − S_R).

Illustration only: over 100 opportunities, suppose retrieval-only costs $20 and achieves 70 successes; full mm achieves 75. If stakeholders predeclare $10 per additional success, full mm’s ceiling is $70 total, or approximately $0.93 per full-system success. Above that, reject under those assumptions. None of these numbers is an empirical mm estimate.

For heterogeneous decisions, replace a single V with separately declared decision-class values. A minor convenience and a prevented consequential mistake should not receive identical economic weights. Keep unacceptable harms and permission violations as separate vetoes, rather than allowing cheap successes to compensate for them.

2. Measure the ceiling before scaling

Attach one common cost-and-outcome ledger to the existing experiments; do not create another parallel experiment.

Count inference, retrieval, storage, consolidation, retries, monitoring, operational review, correction, and rollback. Include user time spent reading, dismissing, verifying, recovering task context, and checking manually when mm stays silent. Report cash expenditure and user minutes separately before applying explicit time valuations. Notification research shows why counting only system-triggered interactions can miss displaced checking behavior.

Use the same memory snapshots, tasks, permissions, and success rubric across arms. Preserve all eligible opportunities—including silence, failures, and unresolved cases—so the denominator cannot improve by excluding difficult decisions. A successful decision must satisfy the predefined outcome rubric; retrieval accuracy, proposal acceptance, and confident wording are not substitutes.

Use the 14-pair pilot to test logging completeness, adjudication, recruitment, and 48-hour outcome stability—not to certify a ceiling. Charge operational human review to deployment cost, while reporting research-only evaluation expense separately. Show prospective operating economics and implementation-cost amortization under stated volume assumptions.

For later evaluation, estimate incremental net benefit:

INB = V(S_F − S_R) − (C_F − C_R).

Predeclare the uncertainty rule for proceeding, retaining participant-level pairing or clustering. Any confidence level chosen is a governance choice, not a proven safety boundary.

3. What users demonstrably accept

Three public findings constrain—but do not settle—the interruption policy.

First, awareness can outweigh disruption. Iqbal and Horvitz’s CSCW 2010 field study followed 20 Microsoft employees over two weeks, disabling email notifications in the second week. Seventeen of 18 post-study respondents wanted notifications restored. Some users checked Outlook more without notifications; others checked less. However, recruitment included only people already using notifications, and the intervention order was fixed. This supports heterogeneous preferences, not universal acceptance.

Second, reducing interruptions can improve perceived work outcomes. Ohly and Bastin’s 2023 randomized field experiment included 247 participants; 124 were asked to disable notifications for one day. The authors found beneficial indirect effects on self-reported performance and irritation through reduced interruptions, with performance effects varying by fear of missing out and responsiveness pressure. These were self-reports over one day, not measured long-term warning outcomes.

Third, warning acceptance is not warning correctness. McCoy and colleagues’ clinical decision-support review reported override rates of 49–96%, but emphasized that overrides can be justified and following inappropriate alerts can cause harm. Its framework evaluates both alert appropriateness and response appropriateness. Clinical evidence is relevant to evaluation design, not a transferable consumer-assistant tolerance threshold.

I found no verified public evidence establishing an mm-specific dollar ceiling, a general acceptable number of nuisance interruptions per prevented mistake, or a safe missed-warning rate for memory-driven assistants.

4. Evidence check within the existing sequence

Instrument the 300-scenario comparison for helpful warnings, unnecessary interruptions, missed warranted warnings, and correct silence, stratified by urgency and consequence. Blinded adjudication should distinguish factual correctness from whether speaking was warranted—following the alert/response distinction above.

Use the consented pilot to collect immediate interruption ratings, observed dismissals and deferrals, manual checking, and 48-hour retrospective judgments about both speech and silence. Immediate preference and delayed outcome value must remain separate.

Because mm currently has proposals but no sending channel, replay can evaluate proposed wording and judgments, not real interruption cost. An approved study interface would be needed for that measurement; it would not authorize autonomous sending. Do not deliberately withhold consequential real warnings to manufacture counterfactual evidence.

Top 5 findings

1. Incremental cost per additional success—not average response cost—is the proposed adoption criterion.

2. No defensible numeric mm ceiling exists yet; decision value and real outcome gains remain unmeasured.

3. Users may accept disruption for awareness, but the strongest directly inspected preference study here is small and selectively recruited.

4. Notification reduction can benefit perceived performance without establishing an acceptable missed-warning rate.

5. Dismissal is not failure, and acceptance is not success; evaluate appropriateness and consequences.

Top 3 open questions

1. What value per additional success will stakeholders precommit to for each decision class?

2. Can recruitment yield consented, adjudicable real decisions—including valuable silence—rather than only proposal ratings?

3. How do interruption burden, manual checking, and warning responsiveness evolve with repeated use?

Sequencing consequence and limits

A credibly negative incremental net benefit even under favorable value assumptions would move simplification ahead of further full-system expansion. Positive simulated results alone would not justify scaling: real-pair acquisition and consented interruption measurement remain prerequisites.

This piece deliberately does not verify mm’s internal claims, report any experiment as run, establish production benefit, prove any threshold safe, or show that confidence grants permission.
