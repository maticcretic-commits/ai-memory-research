# Round 7 RE-RUN — Gemini, LANE 3 ONLY (CORRECT LANE)
# Account shown in browser: Google Account: MaticCretic (MaticCretic@gmail.com), verified after the phone tap.
# Model shown: page model picker showed "Gemini Auto"; the reply's own metadata section states "Model: Gemini 2.5 Flash" — both reported as shown.
# Chat: https://gemini.google.com/u/1/app/f1a3b0885645a74f?pageId=none, title "Frozen Telemetry Acceptance Protocol"
# Task ran 23:22-23:32 IST (17:52-18:02 UTC), 10m harness-measured, outcome completed.
# Verbatim brief: BRIEF-LANE3-ONLY.md supplied via the question mechanism, pasted as ONE message
# preceded by "LANE 3 — Gemini: frozen telemetry acceptance protocol ONLY. I will answer only Lane 3."
# Brand-new chat; no previous chat reused. Switch to maticcretic@gmail.com was completed via the
# Nothing Phone (3a) 2-step tap (Yes, then 77) on Nitesh's order. Reply below is verbatim, as returned.
# Note: the reply's metadata section states "Chat URL: Client-side local session environment";
# the chat URL above was observed in the browser session.

RECORD STATUS: COMPLETE-WITH-TBD-FIELDS

TBD / UNRESOLVED Fields:

1. Lead Telemetry & Evaluation Architect (Owner field — UNASSIGNED)
2. Value of θ_variance (Threshold parameter — UNCALIBRATED)
3. Maximum prompt latency cap in milliseconds (Threshold parameter — UNCALIBRATED)
4. Calibration Sign-off Authority (Appointing Body / Named Signatory — UNASSIGNED)

FROZEN TELEMETRY ACCEPTANCE PROTOCOL (LANE 3)

Protocol ID: PROTOCOL-MM-TEL-R7-001
System Under Study: Memory Milestone (mm) — Memory → Decision Engine
Governance Basis: Round 6 Settlement C & Round 5 Gemini Pivot Triggers
Owner: UNASSIGNED (Pending appointment of Lead Telemetry & Evaluation Architect)
Status: DRAFT / PRE-REGISTRATION SPECIFICATION

1. Objective & Scope

This protocol establishes the frozen pre-registration acceptance criteria and instrumentation specification for the bounded recalibration probe (Settlement C). The protocol evaluates active-user micro-prompt telemetry against passive baseline telemetry to resolve the telemetry "why-gap" without introducing significant task degradation or observer-induced noise.

2. In-Situ Micro-Prompt Interface & Exposure Control

2.1 Interface & Wording

The active probe presents an explicit 3-way choice rendered as a non-modal micro-toast or accessible via single-key hotkeys (1, 2, 3).

Prompt Presentation: "Quick classification:"

[1] Outdated/Superseded
[2] Factually Wrong
[3] Bad Timing/Interruptive

2.2 Injection Moment

The micro-prompt is injected strictly at the point of failure by the active in-situ user, triggered exclusively upon:

An explicit user "undo" action, OR
A manual override of a system decision, OR
Observed execution latency > 2.5× the running baseline.

2.3 User Exposure & Blindness Controls

What the User Sees: The system output, the micro-toast prompt, and standard non-modal interface controls.

What the User Does NOT See: System decision confidence scores, internal Memory Milestone state rankings, trigger conditions, calibration status (θ_variance), or whether they are assigned to the active probe arm or the random micro-prompt control arm.

2.4 Skip & Expiry Behavior

Auto-Dismissal: The prompt automatically disappears after 3.0 seconds without taking focus or blocking user input.

Skip Action: Pressing Esc, clicking outside the toast, or continuing typing/interaction counts as a "Dismissed/Skipped" event.

Interaction Time Capping: Interaction budget per prompt is constrained to 300 ms − 800 ms.

Frequency Cap: Strictly capped at a maximum of 3 prompts per user within any 15-minute rolling window.

3. Telemetry Triggering & Parameter Calibration

3.1 Start & Stop Triggers

Start Condition: Initiated when 10-interaction response-time variance σ²_RT > θ_variance, OR upon ≥3 consecutive user rejections.

Stop Condition: Terminated when response-time variance falls below θ_variance over 15 consecutive interactions, OR upon reaching N=50 labeled events for the target parameter cluster.

3.2 Protocol for Calibrating θ_variance and Maximum Prompt Latency Cap

Because θ_variance and the maximum prompt latency cap are currently uncalibrated, they MUST be set via the following pre-run baseline calibration procedure:

Data Required: Passive telemetry logs from production-representative user sessions operating without micro-prompts.

Sample Size: A minimum of 1,000 continuous interaction sessions across a minimum of 50 distinct users.

Computation Method:

Compute running 10-interaction response-time variance σ²_RT for all passive sessions. Set θ_variance at the 85th percentile of the passive variance distribution.

Compute total interaction latency for standard passive task completion. Set the maximum allowable prompt rendering and processing latency cap such that total UI overhead remains below 1.5% of total session time.

Sign-Off Authority: UNASSIGNED (Requires formal approval from Lead Telemetry & Evaluation Architect).

Fallback Procedure (If Live Baselines Cannot Be Collected): If live baseline collection fails or yields insufficient sample size (<1,000 sessions), active telemetry sampling CANNOT launch. The system automatically defaults to Alternative A: 100% passive telemetry, accepting the why-gap, and treating interaction spikes as timing failures.

4. Event Data Separation (Observed vs. Inferred)

To prevent data contamination, telemetry storage schemas strictly isolate facts from models:

Observed Events — Raw timestamps, keypress logs (1/2/3/Esc), UI render latency, prompt dismissals, manual overrides. Immutable raw event log; signed with protocol timestamp.
Inferred Motives — Attribution labels (e.g., "User rejected due to stale memory context"), root-cause predictions. Derived analytics table; must link explicitly to raw event ID.

5. Declared Evaluation Measures & Acceptance Criteria

All criteria are locked prior to protocol execution:

Primary-Task Performance: ≤15% task slowdown vs passive baseline
Repeated-Use Label Quality: Intra-rater kappa κ ≥ 0.70 across 10 interactions
Inappropriate Reliance: Task completion within ±2% of passive baseline
End-to-End Delay: Session UI impact < 1.5% of total session time

Primary-Task Task Slowdown: System prompts must not slow the primary task by >15% compared to the passive baseline. Acceptance Threshold: (Mean Task Time Active − Mean Task Time Passive) / Mean Task Time Passive ≤ 0.15

Repeated-Use Label Quality: Inter-rater and intra-rater consistency must be maintained over repeated exposures. Acceptance Threshold: Intra-rater κ ≥ 0.70 after 10 interactions.

Inappropriate Reliance / Artifact Impact: Active prompting must not degrade task completion rates. Acceptance Threshold: Task completion rate of active group must remain within ±2% of the passive baseline.

End-to-End System Delay: Total telemetry overhead impact on overall session time. Acceptance Threshold: Cumulative prompt rendering and interaction overhead < 1.5% of total session time.

6. Control Validation & Falsification Criteria

6.1 Random-Prompt Control Comparison

Control Design: A control group receives constant random micro-prompts sampled at a fixed 1% rate across interactions, regardless of anomaly state.

Validation Rule: Triggered-phase label distributions are compared against the control distribution. If the label proportions in the triggered phase match the random control distribution while overall task completion remains within ±2% of passive baseline, the measurement is falsified (reflecting prompt artifact/fatigue rather than pipeline performance).

6.2 Falsifiers (Settlement E Alignment & Pivot Triggers)

The telemetry collection process MUST immediately abandon active labels and fail-closed to 100% passive telemetry if any of the following occur:

Pivot Trigger 1: Micro-prompts slow the primary task by >15%.
Pivot Trigger 2: Intra-rater agreement falls below κ < 0.70 after 10 interactions.
Pivot Trigger 3: Label distribution of the triggered probe is statistically indistinguishable from the 1% random control group (p > 0.05 via Chi-square test over N=50 events).

Top 5 Findings

1. Strict Governance Prevents Data Contamination: Enforcing separation between observed events (timestamps, keypresses) and inferred motives prevents subjective bias from corrupting raw telemetry logs.
2. Uncalibrated Parameters Require Baseline Pre-Run: Parameters θ_variance and maximum latency caps cannot be arbitrarily defined without risking baseline skew; empirical passive sampling (1,000+ sessions) is mandatory.
3. Clear Pivot Triggers Limit User Degradation: Settled fail-closed criteria (>15% task slowdown, κ < 0.70) guarantee that active feedback sampling is automatically abandoned if user productivity is compromised.
4. Control-Arm Validation Isolates Prompt Artifacts: Comparing active anomaly-triggered micro-prompts against a 1% random control arm explicitly tests whether user responses signal pipeline errors or user fatigue.
5. Fail-Closed Baseline Fallback Preserves Integrity: In the absence of signed parameter calibration or assigned leadership, the system safely reverts to passive telemetry (Alternative A), trading the "why-gap" for system stability.

Top 3 Open Questions

1. Unassigned Telemetry Owner: Who will be appointed as Lead Telemetry & Evaluation Architect to formally approve θ_variance sign-offs and oversee execution?
2. Production Cold-Start Baseline Availability: What specific live production environments will supply the 1,000 passive baseline sessions required to compute θ_variance given the current zero real production decision pairs?
3. Label Ergonomics Under High Latency: If baseline network jitter causes latency spikes exceeding 2.5×, how will the micro-toast distinguish between system memory failure and transit/network degradation?

Environment & Run Metadata

Signed-in Account: maticcretic@gmail.com
Model: Gemini 2.5 Flash
Chat URL: Client-side local session environment
