Build Lane — Smallest Feasible Build Order for Memory Milestone

Sequencing principle

The Round 2 portfolio failed to sequence because it treated five experiments as parallel tracks. The build order here inverts that: pick the one path that produces real decision pairs — the acknowledged bottleneck — and make the other two quick builds strictly subordinate to it, as instrumentation on the same pilot rather than standalone projects. Nothing below has been run. Effort figures are engineering estimates, not measured.

Step 1 — Write-time provenance + hook-based secret blocking (est. 3–5 engineer-days)

What: On every memory write to the SQLite authority, stamp a provenance record (source, timestamp, writer identity, session, derived-vs-observed flag) in an append-only side table; add a pre-write hook that pattern-matches secrets and blocks or quarantines the write before it lands. No retrieval changes, no re-scoring, no UI.

Why first: It is the only quick build that must precede the pilot, because provenance captured after the fact is unrecoverable, and a leaked secret during a 14-day pilot would contaminate the pilot itself. It is also cheap: one schema migration plus one interceptor on the existing write path.

Unlocks: (a) Every pilot pair becomes auditable and attributable, which is what makes the 14-pair pilot interpretable rather than anecdotal; (b) the append-only ledger design from Round 2 gets a live writer instead of staying synthetic; (c) the red-team forgetting test later gains a real substrate to run against. This step does not test anything about decision quality — it only makes later steps trustworthy.

Step 2 — Read-time re-scoring on the existing retrieval path (est. 4–7 engineer-days)

What: A thin scoring layer applied after hybrid retrieval: per-claim and per-action confidence annotated at read time, with the 48-hour re-scoring loop from the Round 2 pilot design wired to it. Confidence is surfaced, never used to gate — preserving the Round 1 rule that high confidence grants no permission.

Why second: It depends on Step 1's provenance (re-scoring without a source record is just a number with no referent), and it is the minimum instrumentation the 14-pair pilot needs to produce a decision-relevant signal rather than a retrieval score. It is also the smallest probe of the known calibration-gate FAIL: if the underconfident agent path persists here, the pilot will show it early and cheaply.

Unlocks: The pilot becomes measurable on the axis that matters — did a re-scored memory change what the system recommended? This is the first place the "memory → DECISION" claim gets any empirical contact at all, and it is deliberately weak contact: 14 pairs, no control arm.

Step 3 — The 14-pair pilot itself, instrumented by Steps 1–2 (est. 2–3 weeks elapsed, ~1 engineer-day/week)

What: Run the Round 2 pilot as designed — 14 pairs, 14–21 days, 48-hour re-scoring — but with Steps 1–2 as its data plane. Log every talk-back surface emitted (surface/remind/warn/ask/explain/silence) even though nothing is sent, so the gated-proposal-only limitation is measured rather than hidden.

Why third, not first: Starting the pilot before provenance and re-scoring exist would burn the scarcest resource — real human pairs — on data too thin to interpret. The pilot is the bottleneck; protect it.

Unlocks: The first real decision pairs in the record, a first honest read on the calibration gap, and a natural kill criterion: if the pilot yields no pair where a re-scored memory visibly altered a recommendation, the decision-driving claim is unsupported at this scale and the next build should be the blinded gate (Round 2 experiment 1), not more pilot.

Deliberately NOT built in this first pass

No talk-back sending channel. Proposals stay gated; no email/chat/push. Sending before the blinded gate would create unblinded exposure with no measured benefit.

No silent-consolidation / 10k synthetic-pair ledger gate. The ledger table exists from Step 1, but the dual-axis consolidation gate is deferred — it needs a real writer population first.

No red-team forgetting suite. Kill triggers and 200-profile adversary runs wait until there is a live system worth attacking.

No LongMemEval-S reproduction or counterfactual twins. Reproduction is a verification task, not a build task, and should be run by someone who did not build the system.

No threshold reconciliation. Thresholds stay explicitly unreconciled; the pilot reports raw pairs and disagreement counts, not pass/fail.

No cost-model extension beyond whatever Step 2 incidentally logs.

Top 5 findings

Only one of the three quick builds is truly pre-pilot: provenance and secret blocking must precede the pilot; re-scoring can be built in parallel but must land before the pilot's first 48-hour scoring window.

The pilot is the bottleneck, so it should be last, not first — starting it uninstrumented wastes the scarcest resource.

The calibration FAIL is cheaply probed by Step 2 on real pairs, which is a better first signal than another synthetic sweep.

Provenance-first also retrofits the Round 2 ledger design with a live writer, collapsing two tracks into one.

The gated-proposal-only limitation is measurable without building a sending channel, by logging emitted-but-unsent talk-back — a zero-risk way to size the missing channel's value.

Top 3 open questions

Does 14 pairs have any power to distinguish "memory drove the decision" from "memory was present"? If not, what is the minimum pair count the pilot must reach before Step 3 is worth its elapsed time?

What is the kill criterion for Step 2? If re-scoring reproduces the underconfident path on all 14 pairs, do we fix calibration before the pilot or run the pilot anyway to gather pairs?

Who owns provenance integrity when the writer identity is the agent itself — does self-stamped provenance count as independent, or does it need an external witness?

What would change this sequencing

If, during Step 1, provenance capture turns out to require touching the retrieval path (rather than only the write path), Steps 1 and 2 collapse into one build and the pilot slips — the cheap-first assumption breaks. Likewise, if early Step 2 instrumentation shows the calibration gap is systematic rather than sporadic, the blinded gate should jump ahead of the pilot, because the pilot would then be measuring a known-broken scorer.

What this piece deliberately does not prove

It does not claim any experiment has run, any internal figure (829 tests, 0.712 R@1, 0.797 MRR, zero red-team success) is verified, or any threshold is safe. It does not show the pilot will produce decision pairs, that re-scoring improves decisions, or that provenance prevents leaks in practice — only that this order is the cheapest path to finding out.
