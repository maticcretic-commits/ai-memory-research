# AI Memory Research — Round 6 brief: settle, do not add

Date: 2026-10-27. This is Round 6 of the Memory Milestone (mm) research programme.
mm is memory → DECISION, not just memory → context. On its own record: 829 tests
green, LongMemEval-S R@1 0.712 / MRR 0.797, six red-team rounds to zero critical
success in the final round. Its open gaps: calibration gate (a) still FAIL
(underconfident agent path), zero real production decision pairs, proactive speech
built as gated proposals only, with no sending channel. No experiment has run yet;
every lock below is a commitment, not a result.

## What Round 5 locked (commitments, not results)

- DeepSeek: an 80-pair staged-pilot generator with redundancy gate R1–R5 and a
  14-pair probe with go/no-go criteria G1–G5. Passing the probe vets legibility
  only and never licenses real pairs.
- Grok: triple gate — 240 attack cases in three equal strata of 80, human-block
  rate ≥ 98%, calibration coverage ≥ 90%, recorded by an Independent Gate Recorder
  (IGR) as a timestamped, hashed, write-once certificate.
- ChatGPT: an Independent Safety Adjudicator (ISA) by role, with binding authority
  over disputed S4 cases and a fail-closed deadlock rule: no signature means
  UNRESOLVED, NOT CLEARED.
- Perplexity: no numeric V established. Auditable starting workflow is
  accounts-payable invoice exception handling, with formulas and declarant roles
  frozen before results; refusal is recorded as NOT DECLARED / BLOCKED.
- Gemini: pivot straight to passive telemetry for real production pairs, bypassing
  the planned 50-participant active labelling phase, on the ground that the
  measurement distorts what it measures.

Fail-closed is the default in every lane, independence is enforced by separation,
disputes are never averaged or silently resolved, and everything material is
pre-registered before results.

## Round 6 task: settle four conflicts, do not add new locks

Answer ONLY your lane below, in 700–1000 words, plus your top 5 findings and
your top 3 open questions. End with a named owner, a locked number, or an
explicit "unlocked" status with a reason — and the consequence of leaving it
unlocked. Do not invent a number, a name, or a result that is not established.
If a settlement cannot be locked, say so plainly and state what record, decision,
or experiment would lock it.

### Lane 1 — ChatGPT (talk-back / governance): the early-unlock conflict

Settle Gemini's early unlock versus Grok/Perplexity gate discipline. Gemini's
Round 5 sequencing consequence: if Cohort B undo rates fall below 2%, provisionally
unlock the triple gate for low-consequence real pairs BEFORE V numbers are
resolved. Grok's rule: real pairs only when all three gates are simultaneously
green, and postponing after they are met is also a violation. Perplexity's rule:
a class without a declared value stays out of value-based real-pair evaluation.
Decide: which rule governs, and what evidence — if any — could reopen the other?
State exactly what an undo rate below 2% does and does not unlock, for which
decision classes, and what V status is required. Address Gemini's own Round 4
position (pivot only if labels fail κ ≥ 0.75 / inversion ≤ 1%) versus its Round 5
pivot before that test runs. If you keep a provisional unlock, give its expiry,
its audit record, and the fail-closed revert trigger. If you reject it, state
what replaces it as the first real-pair entry point.

### Lane 2 — Grok (challenger QA): appointing bodies for ISA and IGR

Name the appointment problem, do not restate the roles. Neither the ISA
(ChatGPT) nor the IGR (Grok) names an individual, an appointing body, or a
budget authority. Decide: who appoints each role, who can remove each role, and
who funds them, with the independence safeguards that make appointment and
removal by the development chain impossible. Decide whether one person may hold
both ISA and IGR, and whether either may also own DeepSeek's third-party
relabelling and audit trail — give a reason grounded in the records each role
certifies, not a general preference for separation. Include the S4 appeal
mechanism: who can appeal an ISA disposition, on what grounds, within what
window, and what happens to the disputed case while the appeal is pending.
State what remains unlocked if no appointing body will sign, and whether an
unappointed ISA or IGR can certify anything at all.

### Lane 3 — Gemini (deep research): the telemetry why-gap compromise

Decide whether a micro-interaction labelling phase is a coherent compromise or
the passive-telemetry pivot undone. Gemini states the gap plainly: passive
signals show a rejection but not why — wrong memory, superseded memory, or bad
timing all look identical — and calibration against perceived trust becomes
inferential only. Its own fallback reintroduces labelling at smaller scale when
response-time variance is high, to recalibrate talk-back timing. Design that
phase precisely: what is labelled, by whom, at what moment, at what cost to the
primary task, and what it recovers that passive telemetry cannot. Give the
trigger that starts it, the trigger that stops it, and the comparison that
would show it measures the pipeline rather than the study artefact. If the
compromise is incoherent, say so and give the alternative: either accept the
why-gap with its stated limits, or run the original labelling study after all,
with the observer-effect controls that would make its results trustworthy.

### Lane 4 — DeepSeek (build): the calibration closing threshold

Close the calibration FAIL with a number, or state why it cannot be closed yet.
Grok locks calibration coverage (≥ 90% of classes mapped and probe-tested) but
not a calibration accuracy threshold that closes the underconfident-agent FAIL
from Round 1. Coverage without accuracy lets a class be mapped and still wrong.
Propose the numeric accuracy threshold, the metric it is measured on, the
dataset and sample size it is measured over, and the confidence interval or
tolerance around it. Decide whether that threshold gates the 14-pair probe, or
only the 80-pair run, or both — and what happens to the probe if the threshold
is unmet at probe time. Address the mechanism question from Round 4: if the
underconfident pattern holds on 100% of scored pairs (or ≥ 90% with zero
discordant confidence–accuracy dissociations), re-scoring stops and the defect
is routed as a mechanism fault. Does your threshold distinguish a threshold
artefact from a structural decoupling of confidence and evidence, and how?

### Lane 5 — Perplexity (verified research): what is actually locked

Audit the other four settlements, do not add a fifth lock. For each of the
four items above, state: locked, provisionally locked, or unlocked — with the
evidence record that would be required to move it one step, and what would
falsify it. Check specifically: does any proposed early unlock survive
Perplexity's V rule (a class without a declared value stays blocked)? Does
any proposed appointing body survive the separation rule (the person who makes
the claim never certifies it)? Does any micro-interaction labelling proposal
reintroduce the active-labelling failure modes Gemini cited in Round 4
(dual-task penalty, label fatigue, over-trust, latency)? Does any calibration
threshold survive the simulated-to-real transfer problem (all current evidence
is staged or synthetic)? End with a one-page lock table: item, status, owner
or appointing body, number or explicit unlocked reason, and consequence of
leaving it unlocked. If a settlement in another lane cannot be verified from
its own terms, mark it unverified rather than averaging it into a pass.

## Standing rules for this round

- Check sign-in first. If signed out, stop immediately, do not sign in, do not
  start a chat, and do not send this brief. Report the sign-in state plainly.
- If a bot check, region wall, or CAPTCHA appears, sit out and report it plainly.
- Do not publish, send, pay for, or change anything outside this chat.
- Return the full reply text, the account and model shown (if any), and the
  chat URL, so the reply can be saved verbatim before any synthesis.
