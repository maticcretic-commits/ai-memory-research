# v0.4 design brief — evidence-driven conflict handling

*Prepared 14 Oct 2026 (evening) from the v0.3 eval results. No code changed; this is the build spec for the next implementation pass.*

## 1. The measured failure

`evals/reports/decision-bench-2026-10-14.json` (300 constructed tasks, seed 7, verified):

| variant | n | NDCG | accuracy | ECE |
|---|---|---|---|---|
| standard | 173 | 0.889 | 0.607 | 0.154 |
| **conflicting** | 63 | 0.801 | **0.413** | **0.212** |
| sparse | 34 | 0.772 | 0.206 | 0.339 |
| tie | 30 | 0.924 | 0.733 | 0.118 |

Conflicting-evidence tasks are the clear weak spot: worst accuracy, worst calibration. (Sparse is low-accuracy by design — the caution mechanism correctly returns "undecided" there; impasse rate 0.667 is the system working, not failing.)

## 2. Why it fails — the flat discount

`mm/confidence.py:275-277`, in the metacognitive second pass:

```python
if conflict_score > 0:
    penalty = 0.3 * conflict_score
    adjusted = max(0.05, adjusted - penalty)
```

Every unit of conflict costs 0.3 confidence, regardless of *what* the conflict is. A contradiction between two shaky rumors and a contradiction where one side has strong, fresh, corroborated evidence get the same treatment. Worse: `mm/resolver.py` is still a `NotImplementedError` stub — the ACC-style monitor (contradiction count × severity × stakes) that should produce a *graded* conflict score was never implemented, so `conflict_score` reaching the confidence pass has no measured meaning.

This contradicts the repo's own neuro grounding (ARCHITECTURE.md §4, RESEARCH.md neuro track):
- **ACC conflict monitoring (Botvinick 2001):** conflict is graded, and it *recruits control* — it doesn't just subtract confidence.
- **Expected value of control (Shenhav 2013):** control recruitment is cost-sensitive and proportional to expected payoff — a flat rate is the opposite of this.
- **Dopamine prediction error (Schultz 1997):** the teaching signal is *signed* and magnitude-scaled; the brain weights conflicting evidence by reliability (precision), not by a constant.

## 3. The design — precision-weighted conflict

### 3a. Implement the cheap monitor first (prerequisite)

The resolver's v0.2 policy is already specified: a cheap monitor that always runs, emitting a graded score = contradiction count × severity × stakes (pure counting over `MemoryRecord` provenance fields — deterministic, no LLM). Implement *only the monitor* in v0.4; the controller's tiered strategies (low/medium/high) stay stubbed. The confidence pass needs the graded score; it doesn't need the full resolver.

### 3b. Replace the flat penalty with a precision-weighted one

For the winning option, compute evidence precision **P** from already-specified fields:

```
P = provenance.confidence × recency_weight × corroboration
```

(`provenance.confidence` and bi-temporal fields come from the mnemonic-pattern primitives in ARCHITECTURE.md §4; `corroboration` = fraction of independent records agreeing.)

Then:

```
conflict_penalty = κ × M × (1 − P)
```

- **M** = graded conflict magnitude from the monitor (3a).
- **κ** = single scaling constant, tuned on the bench (see §4).
- When the winning side's evidence is precise (P → 1), conflict is *resolved disagreement* — barely dents confidence. When both sides are mushy (P → 0), confidence falls toward the impasse bound and the system says "undecided" instead of guessing.

### 3c. Conflict raises the caution bound, not just cuts confidence (EVC)

Separate two things the flat penalty conflates:
- **Confidence cut** (3b): how much do I believe the winner?
- **Bound raise**: conflict also raises the DDM caution bound — the system *deliberates longer* under conflict (Shenhav's expected value of control). Bound_raise = λ × M, with λ a second tunable. This is the "slow down under conflict" behavior; the tie variant's strong numbers (acc 0.733) suggest the bound machinery already handles near-ties well.

### 3d. Outcome-conditioned conflict learning (the 100-repo finding)

RESEARCH.md already adopts Rescorla-Wagner re-ranking for `constraints` (mnemoverse pattern: memories reweighted by whether they helped or misled). Extend it to conflict features: track which *kinds* of conflict (source-type pairs, topic classes) preceded correct vs wrong outcomes. Conflict on historically-discriminative features becomes signal (smaller κ for that class); conflict on historically-misleading features keeps full weight. This is the repo's own rejected-choice-injection lesson applied one level up: decision memory should change how future conflicts are priced.

## 4. Eval criteria (re-run `decision-bench-v1`, same seed)

- conflicting accuracy **0.413 → ≥ 0.55**, ECE **0.212 → ≤ 0.15**
- no regression on standard (acc ≥ 0.60, ECE ≤ 0.16)
- sparse stays "undecided"-heavy (impasse rate ≈ current, not collapsed into guessing)
- new slice to add: tasks where the monitor withholds (LongMemory gating) must route to "undecided," never to a wrong confident answer

## 5. Open tunables (v0.4 research targets, not guesses)

κ scale · M normalization across stakes levels · precision composition weights (provenance vs recency vs corroboration) · λ bound-raise rate · conflict-class taxonomy for 3d.

## 6. Honest caveats

- The bench is synthetic (300 constructed tasks, one seed). Real validation needs conflict slices from LongMemEval/LoCoMo-style data — the bench measures the mechanism, not the world.
- `provenance.confidence` fields are stub-level today; P is only as good as the provenance the tiers module writes.
- Nothing here needs a partner model or any spend — it's all local code + the existing harness.
