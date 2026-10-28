Round 5 — Staged-Pilot Generator (DeepSeek, build lane)

Purpose and stance

This document designs a generator that would produce 80 staged decision pairs if built and run. Nothing here has been executed. No threshold below is claimed to be safe, and no internal figure (829 tests, LongMemEval-S 0.712/0.797, six red-team rounds) is treated as fact — those are unverified claims and none of them substitute for the pilot evidence this generator is meant to collect.

Generator rules (the 80 pairs)

Unit of generation = one decision pair. A pair is (workflow, decision point, two candidate histories H_mem and H_abl, a matched distractor D, a rubric R, an outcome space). Generation proceeds in five layers:

1. Decision-class sampling. Draw across at least four decision classes (e.g., scheduling, triage/prioritization, resource allocation, customer-facing routing). No class exceeds 30% of pairs. Classes are frozen before generation.

2. Decision-point extraction. For each class, enumerate decision points where a history could legitimately change the answer. The generator's first filter is the counterfactual seed: a small set of prior episodes whose removal would, in the author's stated rationale, plausibly flip or shade the decision. Seeds are written before any pair is built (prevents post-hoc rationalization).

3. Two-history construction. H_mem includes the seed episodes plus ambient noise. H_abl removes only the seed episodes and substitutes topically similar but decision-irrelevant episodes (the ablation filler) so that token count, recency distribution, and topical coverage are held roughly constant. This is the core anti-redundancy move: ablation must not be detectable as "shorter history."

4. Matched distractor D. D is a second history, same structure, that includes a different seed set of equal plausibility, and whose inclusion would push toward a different decision. D is matched on length, recency, and topic mix to H_mem. D exists to test whether the model is using this memory or merely any memory.

5. Rubric pre-registration. Each pair ships with a signed rubric: (a) the decision, (b) the expected direction of the memory effect, (c) a 3–5 point ordinal scale with concrete anchors, (d) an explicit "no difference" anchor, (e) the author's predicted reading. Rubrics and predictions are locked and hash-stamped before any model output is generated.

All 80 pairs are authored by at least two people independently and reconciled; disagreements are logged, not averaged.

The redundancy check

Ablation is not redundant with prompt context only if the following are all demonstrated, pair by pair, before the pair enters the pilot:

R1 — Information sufficiency. With H_abl in the prompt, the decision is underdetermined: the rubric's "no difference / cannot decide from context alone" anchor is the correct pre-model reading.

R2 — Detectability. A blinded judge (not the authors) reading H_mem and H_abl without the decision cannot reliably say which is "the real one" — chance-level performance, pre-registered as ≤ 60% correct over a sample.

R3 — Distractor non-triviality. D must also pass R1: it too must underdetermine the decision on its own, or the pair tests distractor salience, not memory use.

R4 — Prompt-context isolation. H_mem's seed episodes must not be restated anywhere else in the prompt (system prompt, task framing, few-shot examples). A lexical/embedding overlap check flags restatements; flagged pairs are rewritten.

R5 — Outcome divergence. The two readings (H_mem vs H_abl) must map to different rubric anchors, not merely different wording.

Any pair failing R1–R5 is regenerated or retired. The redundancy check is a gate on generation, not a result; passing it says the design is non-redundant, not that memory drives decisions.

Two raters

Each pair is judged independently by two raters blind to condition labels (H_mem/H_abl/D relabeled by a third party). Raters score on the pre-registered rubric, not free-form. Disagreement is reported as raw agreement plus κ; no averaging of disputes — a dispute is a separate record. Raters cannot be the pair authors, and rater assignment is randomized across pairs.

Go/no-go for the 14-pair design probe

The 14-pair probe is explicitly a design probe only (per prior rounds: 14 pairs ≠ power). Go criteria, all pre-registered:

G1. ≥ 12 of 14 pairs pass R1–R5 at authoring time (post-reconciliation).

G2. Rater agreement on the probe: raw agreement ≥ 80% and κ ≥ 0.60 on the primary anchor — a provisional floor, explicitly below the 0.75 main-study target, used only to decide whether the rubric is legible.

G3. Blinded detectability (R2) on probe pairs: judge accuracy ≤ 60%, with the confidence interval reported (no claim of significance at n=14).

G4. Zero pairs where a rater can name the condition from the prompt alone.

G5. All 14 predictions and rubrics locked before any output; audit trail complete.

No-go if G1 fails (regenerate), G2 fails (rubric rewrite, not threshold relaxation), or G4 fails (prompt leakage — redesign). A no-go does not authorize scaling to 80; it sends the package back to authoring. Passing the probe is necessary, not sufficient, and never licenses real-decision pairs (the triple gate remains closed until the calibration FAIL is resolved and real pairs are unprohibited).

Top 5 findings (from this design work)

1. Redundancy is the dominant failure mode; length/topic matching alone is insufficient — R1–R5 are all needed.

2. The distractor must itself pass the underdetermination test, or the pair measures salience, not memory.

3. Pre-registration must include the predicted direction, else post-hoc "memory mattered" is unfalsifiable.

4. 14 pairs can only vet design legibility; κ ≥ 0.60 there is a probe floor, never a main-study claim.

5. Blind relabeling by a third party is load-bearing for rater independence.

Top 3 open questions

1. Who owns the relabeling and audit trail, and is that person independent of the S4 adjudicator (still unnamed from prior rounds)?

2. Can simulated decisions be shown to transfer to real ones, or is the 80-pair pilot structurally limited to simulated transfer claims?

3. What numeric calibration threshold closes the underconfident-agent FAIL, and does it gate the probe or only the 80-pair run?

What would change the sequencing plan

If the 14-pair probe shows R2 detectability above chance (judges reliably identify the real history), the sequencing changes: the 80-pair generator cannot proceed on the current history-construction rules, and the package returns to authoring before any pilot. Conversely, if G2 fails only on rubric legibility while R1–R5 pass, the plan re-sequences rubric design ahead of generation rather than scaling.

What this piece deliberately does NOT prove

It does not claim any pair has been generated, any rater has scored, any κ or detectability figure exists, or that any threshold is safe. It does not verify the internal Memory Milestone figures. It does not close the calibration FAIL, does not produce real production decision pairs, and does not establish that memory drives decisions — only the design under which that could be tested.
