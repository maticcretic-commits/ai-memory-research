Round 4 — Build lane: the power question

The question, restated precisely. "Memory drove the decision" means: with memory removed or scrambled and everything else held fixed, the decision changes. "Memory was merely present" means: the decision is invariant to memory ablation, or the memory was redundant with context available anyway. The distinguishing experiment is therefore not a correlation between memory presence and decision quality; it is a counterfactual ablation — the decision must be causally sensitive to memory, and the sensitivity must be attributable to the memory content rather than to the act of retrieval.

What a pair is, for power purposes. A "decision pair" is one trial: same task, same agent configuration, two arms — (a) memory intact, (b) memory ablated or substituted with a matched distractor (same length, same retrieval cost, wrong content). The outcome is binary or ordinal on a pre-registered decision rubric fixed before the run. Counting pairs where memory "was there and the decision was good" tells you nothing; only discordant pairs (arms disagree) carry information. That is the first place a naive pilot overstates itself.

Minimum pilot worth its elapsed time. For a paired binary design, the informative statistic is the discordant-pair count, not total N. With a sign test (or exact McNemar), detecting a true discordance rate of 0.70 in favor of the memory arm at α = 0.05 one-sided and power 0.80 requires roughly 15–20 discordant pairs. If the base discordance rate is 30–40% (itself unknown, which is the point), that implies 60–100 total pairs for a defensible pilot, and if you want a confidence interval on the discordance rate narrow enough to plan a scale decision, closer to 150–200 pairs. Below ~60 total pairs, a "significant" result is fragile to one or two flips; a null is uninformative. My honest minimum worth the elapsed time: 80 total pairs, ~25 discordant expected, pre-registered rubric, two raters on a sample, and the ablation distractor matched on length and retrieval cost. Anything smaller is a feasibility probe, not evidence.

What the 14-pair pilot can and cannot show. Fourteen pairs, with perhaps 4–6 discordant, can show: the pipeline runs end to end, the ablation is technically clean (no leakage, no crash asymmetry), the rubric is ratable with acceptable inter-rater agreement, and the discordance rate is nonzero. It cannot show a causal effect at any conventional confidence — the exact sign-test p-value on 5 discordant in the favorable direction is ~0.03 only under the strongest assumption, and one flip destroys it — nor can it estimate effect size, nor distinguish memory-driven from retrieval-cost-driven (the distractor arm does that only if it is matched, which 14 pairs cannot validate), nor support any claim about the underconfident agent path. The 14-pair pilot's only legitimate output is a go/no-go on the design, plus an empirical discordance rate to power the real pilot.

Kill criterion for read-time re-scoring. If the underconfident path (low-confidence decisions despite memory support) reproduces on every pair in the pilot — i.e., the agent's stated confidence is depressed independent of arm — then re-scoring at read time is not rescuing signal, it is laundering a fixed bias. Pre-registered kill: if the underconfident pattern holds on 100% of scored pairs (or ≥ 90% with zero discordant confidence–accuracy dissociations), stop read-time re-scoring, do not tune the calibration gate on the same pairs, and route the failure to the calibration lane as a mechanism defect (likely confidence decoupled from evidence) rather than a scoring defect. Re-scoring may only continue if at least a pre-set minority of pairs show confidence tracking arm-conditional evidence.

Sequencing implication. Because zero production decision pairs exist, the 80-pair pilot must be built from synthetic or staged decisions with a documented generator, and its results are then explicitly non-transferable to production until real pairs exist. That ordering — design pilot, then real-pair collection, then causal claim — is the sequencing the kill criterion protects.

Top 5 findings

1. The informative unit is the discordant pair; total N is the wrong denominator and inflates apparent power.

2. A defensible minimum is ~80 total pairs (~25 discordant), not 14; 14 pairs is a design probe only.

3. Memory "driven" requires ablation with a matched distractor, or retrieval cost confounds content.

4. A 14-pair pilot can validate the pipeline and rubric but cannot support any effect claim.

5. Reproducing the underconfident path on every pair is a mechanism defect; read-time re-scoring is then illegitimate, not a fix.

Top 3 open questions

1. What is the true base discordance rate, and can a staged generator produce decisions where memory ablation is not redundant with prompt context?

2. How should the rubric handle ordinal decisions so McNemar-type tests remain valid without collapsing information?

3. What inter-rater agreement floor justifies treating staged-pair decisions as ground truth?

What would change the sequencing plan in this piece. If a staged 80-pair pilot shows a discordance rate near zero (memory never changes the decision), the causal claim is unsupported and the plan should pivot from "demonstrate memory-driven decisions" to "measure where memory is redundant," deferring production-pair collection until a task class with real memory sensitivity is found. Conversely, a clean, distractor-controlled effect would justify moving real-pair collection ahead of further synthetic work.

What this piece deliberately does NOT prove. It does not claim any experiment has run, that the 14-pair or 80-pair figures are anything but design arithmetic, that any threshold is safe, or that the mm internal record (829 tests, LongMemEval-S figures, red-team rounds, calibration FAIL) has been verified. It does not establish that memory does drive decisions, only what would be required to distinguish that from mere presence.
