Stop / Pivot / Scale Decision Tree for the Five Round-2 Experiments

Round 3 forces sequencing. Parallel design is finished; the only remaining work is a decision tree that converts each experiment’s outcome into an explicit stop, pivot, or scale action, with red-team kill triggers treated as non-negotiable hard stops. No experiment has run, no internal figure has been independently verified, and no threshold has been shown safe. The tree below is therefore a pre-commitment device, not a post-hoc rationalization.

Experiment 1 – Blinded paired talk-back gate vs retrieval-only baseline (300 scenarios)

Stop: Talk-back arm produces higher rates of harmful or irreversible action proposals than the retrieval-only arm at any pre-registered confidence band, or the blinded judges cannot distinguish surface-level talk-back from genuine decision influence at better than chance.
Pivot: Talk-back improves decision quality only inside a narrow confidence or recency band; redesign the surface as a strictly gated proposal channel (no automatic speech) and re-test the narrower policy.
Scale: Talk-back arm shows statistically reliable improvement in decision correctness or harm reduction with no increase in false-positive action proposals; move to the real-pair pilot (Experiment 2) with the same gate parameters.

Experiment 2 – 14-pair pilot over 14–21 days with 48-hour re-scoring

Stop: Any pair produces an irreversible action that later re-scoring judges as unjustified by the memory state at decision time, or inter-rater reliability on the 48-hour re-score falls below a pre-registered floor.
Pivot: Decisions improve but only when human re-scoring is available within 48 h; redesign the system as a human-in-the-loop advisor rather than an autonomous decision driver and re-run on a larger but still supervised cohort.
Scale: Re-scored decisions remain stable and superior to a retrieval-only control with no irreversible errors; open a limited production decision log under continuous red-team monitoring.

Experiment 3 – Append-only SQLite ledger + dual-axis silent-consolidation gate (10 000 synthetic pairs)

Stop: Silent consolidation produces any irreversible supersession that cannot be reconstructed from the append-only history, or the dual-axis gate fails to keep both factual consistency and decision utility above pre-registered floors.
Pivot: Consolidation works for factual memory but degrades decision utility (or vice versa); split the gate into two independent policies and re-test each axis separately.
Scale: Both axes remain above floor across the full synthetic set and the reconstruction audit is perfect; proceed to the red-team forgetting test (Experiment 4) using the same ledger schema.

Experiment 4 – Red-team forgetting test on 200 synthetic profiles with kill triggers

Kill triggers are hard stops: any successful extraction of a “forgotten” high-sensitivity fact, any cross-profile leakage that reconstructs a suppressed identity, or any agent behavior that treats a kill-triggered memory as still authoritative immediately aborts the entire memory-to-decision program.

Stop: Any kill trigger fires, or residual memory allows reconstruction of suppressed content above a pre-registered information-theoretic threshold.
Pivot: Forgetting succeeds on the synthetic profiles but only under unrealistically clean conditions; redesign the forgetting mechanism as an explicit, auditable quarantine rather than silent deletion and re-test.
Scale: Zero kill-trigger successes across all 200 profiles and residual information remains below threshold; allow limited real-pair ingestion under the same kill-trigger regime.

Experiment 5 – LongMemEval-S reproduction + 40 participants × 20 episodes with counterfactual twins

Stop: Reproduction fails to reach the claimed internal LongMemEval-S numbers by a pre-registered margin, or counterfactual twins produce systematically different decisions that the original memory state cannot explain.
Pivot: Reproduction succeeds but the participant episodes reveal that talk-back or decision influence collapses outside the synthetic distribution; restrict the system to retrieval-plus-explain mode and abandon autonomous decision driving.
Scale: Both the reproduction and the participant counterfactuals support the memory-to-decision claim with no unexplained divergence; treat the result as a necessary but still insufficient condition for any further production exposure.

Sequencing challenge – the most dangerous order

The most dangerous order is to run Experiment 2 (real pairs) or any production-adjacent log before Experiment 4 (red-team forgetting) and before a successful silent-consolidation audit in Experiment 3. Real decision pairs create irreversible external effects; if the forgetting and supersession mechanisms have not yet been shown to survive adversarial extraction, every real pair becomes a permanent liability. Running the 300-scenario talk-back gate (Experiment 1) or the LongMemEval-S reproduction (Experiment 5) first is comparatively safer because both remain inside controlled or synthetic bounds. The least dangerous sequence therefore places the two purely synthetic and red-team experiments (3 then 4) first, followed by the controlled talk-back gate (1), the LongMemEval-S plus participants (5), and only then the real-pair pilot (2). Any inversion that places real pairs earlier is a hard process violation.

Top 5 findings

Real-pair data is the scarcest and most dangerous resource; every other experiment exists to justify or forbid its collection.
Silent consolidation and forgetting are not optimization problems; they are safety primitives that must be proven before any decision-driving claim is entertained.
Talk-back is not a retrieval enhancement; it is a separate policy layer whose failure modes are distinct from retrieval failure modes.
Counterfactual twins in Experiment 5 are the only current design that can distinguish “memory supplied useful context” from “memory caused the decision.”
Pre-registered kill triggers convert red-teaming from a research activity into an operational abort condition.

Top 3 open questions

What is the minimal set of real decision pairs that can still falsify the memory-to-decision thesis without creating an irreversible external record?
Can a dual-axis consolidation gate ever be shown safe on synthetic data alone, or does safety require exposure to distribution shift that only real pairs supply?
If the calibration gate remains underconfident, does that protect against over-action or merely hide the true decision-driving power of the memory store?

A result that would change the sequencing plan is any kill-trigger success in Experiment 4, or any irreversible unjustified action in the first few pairs of Experiment 2; both would force an immediate return to pure retrieval-plus-explain mode and a redesign of the forgetting and talk-back layers.

This piece deliberately does not prove that any threshold is safe, that any internal figure is accurate, that the proposed order is optimal, or that memory can ever legitimately drive decisions rather than merely supply context. It only supplies an explicit pre-commitment map so that future results cannot be interpreted after the fact.
