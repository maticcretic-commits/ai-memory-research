# Round 7 RE-RUN 2 — DeepSeek, LANE 4 ONLY (CORRECT LANE)
# Account shown in browser: MaticCretic. Model shown: none displayed (DeepThink/Search controls only).
# Chat: https://chat.deepseek.com/a/chat/s/c14d70e4-b08b-4d01-8011-c994acfd5bec
# Task ran 22:43-22:58 IST (17:13-17:28 UTC), 15m harness-measured, outcome completed.
# Verbatim brief: BRIEF-LANE4-ONLY.md supplied via the question mechanism, pasted as ONE message
# with the required first line "LANE 4 — DeepSeek: frozen calibration protocol ONLY. I will answer only Lane 4."
# No sign-in, publish, send, payment, or Terms acceptance beyond sending the instructed message;
# no bot check, region wall, or CAPTCHA encountered. Reply below is verbatim, as returned.
# Note: the reply's final paragraph claims account/model/chat URL were not provided in its session
# context; the account MaticCretic and chat URL above were observed in the browser session, and no
# model name was displayed.

COMPLETE-WITH-TBD-FIELDS

TBD/UNRESOLVED fields: (1) numeric calibration threshold — TBD, owner UNASSIGNED pending the calibration-gate authority; (2) tolerance offset beyond the +0.02 illustration — TBD; (3) bootstrap CI method parameters (resamples, seed) — TBD unless the ≤0.02 tolerance rule fixes them; (4) sample size in the 100–150 range for the scored run — TBD; (5) freezes: who stamps (role only) — UNRESOLVED role holder; (6) independent adjudicator role — role specified, holder UNASSIGNED; (7) staged-vs-real prospective comparison scope — UNRESOLVED (no production decision pairs exist).

LANE 4 — DeepSeek: Frozen Calibration Protocol (draft, pre-registrable; not signed, not frozen)

Status line. Draft only. Nothing here is a result, a lock, or a calibration claim. ECE ~0.05 is an illustrative default, not a validated threshold. No experiment has been run.

1. Calibration target. Stated-confidence-only Expected Calibration Error (ECE) on memory→decision pairs, with reliability-diagram monotonicity as a co-required criterion. Accuracy alone is not admissible evidence: it cannot distinguish underconfidence from inaccuracy. Target is a threshold plus a mechanism diagnostic, both frozen before scoring.

2. Decision classes. Per pair, the memory system outputs a stated confidence and a decision; the resolved outcome is a binary correct/incorrect label (see §6). The reliability diagram bins stated confidence and plots empirical accuracy; monotonicity requires non-decreasing bin accuracy across bins.

3. ECE metric. ECE = Σ_b (n_b/N)·|acc_b − conf_b| over reliability bins. Stated-confidence-only: no post-hoc temperature scaling, no recalibration before scoring; the frozen binning scheme is part of the hash (§9). Monotonicity check is run independently of the ECE number.

4. Threshold and tolerance rule (number TBD).

Candidate threshold: TBD — numeric value UNRESOLVED. Owner: UNASSIGNED, pending the calibration-gate authority for this build. No number may be entered after any scoring begins.

Tolerance rule (frozen now): pass requires point estimate ≤ threshold AND upper CI bound ≤ threshold + 0.02. The +0.02 is the settlement's illustrative tolerance; if the authority sets a different offset it must be entered here before freeze and is itself TBD until then.

CI straddling the threshold = inconclusive, not pass.

A passing ECE with uniform underconfidence is a false pass (§8 overrides §4).

5. Bootstrap CI. Nonparametric bootstrap over scored pairs; resample with replacement; report percentile CI (method frozen at pre-registration; resample count and seed TBD at freeze). If the number is not frozen first, only the §8 diagnostic is reportable.

6. Sample definition. Stability floor: ECE SD ≈0.038 (n=50), ≈0.026 (n=100), ≈0.015 (n=250); below ~100–150 unstable. Scored set: ≥100–150 resolved pairs (exact N TBD). Roles exactly as in settlement D: the 14-pair probe is coverage/validity only — never gated on calibration; the 80-pair run may carry only a provisional gate, is below the stability floor, and is diagnostic if no pre-registered number exists. Passing never licenses real production pairs.

7. Resolved outcomes and adjudicator (role only). A pair counts only if scored against a resolved outcome — a decision with an independently established correct/incorrect label. Resolved-outcome definition: the label is fixed before the confidence is revealed to the adjudicator, and the adjudicator does not see system confidence. Adjudicator: independent role, not the model builder, not the threshold owner; holder UNASSIGNED. Evidence that would complete: a named appointing record for the adjudicator role and the resolved-labeling procedure.

8. Mechanism-fault override (applies regardless of ECE). Diagnostic: (a) reliability-diagram spread — underconfidence across all bins; (b) AUROC ≈ 0.5; (c) discordance counts — pattern on 100% of pairs, or ≥90% with zero discordant dissociations. If the uniform pattern holds, re-scoring stops and the defect routes as a mechanism fault even if ECE passes. Threshold artefact vs structural decoupling is decided by the pattern, not the number.

9. Pre-registration / freeze steps (role only, no names). Before any run: (i) hash this protocol document (threshold field either filled by the authority or explicitly frozen as diagnostic-only); (ii) hash the binning scheme, bootstrap parameters, tolerance rule, and sample N; (iii) stamp timestamp and role of the freezer. Freezer role: UNRESOLVED — the settlement does not name an appointing body. Post-freeze changes void the pre-registration. Consequence: running the 80-pair run without a pre-registered number = diagnostic only, no confidence-keyed routing.

10. Staged-vs-real comparison. Prospective comparison between staged pairs and real production decision pairs: UNRESOLVED — zero real production decision pairs exist. Staged results cannot substitute. Record that would complete it: a defined real-pair source and count.

11. What this record does not claim. Not signed, not frozen, not appointed, not calibrated, not validated. Threshold unassigned; adjudicator unassigned; freezer role unresolved; real-pair comparison unresolved.

Top 5 findings

Settlement D is governable but not executable: threshold, owner, and freezer role are all absent.

The monotonicity + uniform-underconfidence rule is the real safeguard; ECE alone can false-pass.

80 pairs sit below the stability floor; only ≥100–150 supports a provisional gate.

The 14-pair probe must never be calibration-gated (coverage/validity only).

No resolved real outcome pairs exist, so staged-vs-real comparison is UNRESOLVED, not zero-result.

Top 3 open questions

Who is the calibration-gate authority, and what numeric threshold will it pre-register?

Who stamps/freezes the protocol, and by what appointing record?

What real-pair source will supply resolved outcomes for the prospective comparison?

Sign-in / environment: I did not sign in, accept terms, or take any account action; no bot check, CAPTCHA, or region wall was encountered in this session. Account and model shown to me: not provided (user timezone not provided). Chat URL: not provided in this session context — I cannot report it without inventing it. Uncertain and stated as such.
