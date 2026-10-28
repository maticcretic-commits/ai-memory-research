# AI Memory Research — Round 6 Synthesis
Date: 2026-10-27 morning IST. Sources: verbatim replies in `inbox/`
(DeepSeek, Grok, Gemini, ChatGPT, Perplexity). Copilot abstained (region wall,
app route only — lane decision still parked with Nitesh). This synthesis is
Jarvis's own report, separate from the verbatim replies; no partner view is
merged into another partner's reply. Round 6 asked each partner to settle one
of the four conflicts Round 5 exposed, not to add a new lock. Nothing in
Round 6 has been run; every settlement below is a proposal, a rule, or an
audit verdict, not a result.

## The five lanes, in one line each
- DeepSeek (calibration threshold): metric locked as stated-confidence ECE
  with reliability-diagram monotonicity; number UNLOCKED; 14-pair probe must
  not be gated on calibration, 80-pair run may carry a provisional gate only,
  and a stable estimate needs 100–150 scored pairs.
- Grok (appointing bodies): UNLOCKED — no individual, appointing body, or
  budget authority for ISA or IGR; one person may not hold both roles, nor
  either role plus the relabelling/audit trail; S4 appeal mechanism entirely
  undefined; an unappointed role cannot certify anything.
- Gemini (telemetry why-gap): a conditional micro-interaction labelling phase
  IS coherent, but only as a bounded recalibration probe — one 3-way choice
  at the point of failure, non-modal, 3-second auto-dismiss, capped at 3 per
  15 minutes, starting on high response-time variance or 3 consecutive
  rejections, stopping on stabilisation or 50 samples; status UNLOCKED, because
  the variance trigger and latency cap are uncalibrated and no owner is assigned.
- ChatGPT (early-unlock conflict): REJECTED — adopt Grok's simultaneous
  three-gate discipline, constrained by Perplexity's declared-value eligibility
  rule; an undo rate below 2% is evidence and a readiness-review signal only,
  never authorisation; first entry is the earliest eligible, declared-value,
  low-consequence class with all gates green and V resolved.
- Perplexity (audit of what is locked): NONE of the four settlements can be
  certified as locked from the record it was given — each is unlocked and
  unverified, with a named record that would move it one step and a falsifier
  that would kill it. No fifth lock added.

## Convergences — what Round 6 actually settles
1. **Gate discipline governs entry, early unlock does not.** ChatGPT rejects
   the provisional unlock on governance grounds, and Perplexity independently
   blocks any undeclared class through the value gate. The two verdicts arrive
   by different routes — ChatGPT from rule adjudication, Perplexity from
   evidence audit — and they agree on the operative rule: no class proceeds
   on an inferred or retrospective value, and no single behavioural metric
   waives an independent prerequisite. Gemini's Round 5 sequencing consequence
   is therefore not the governing rule after Round 6. What survives of Gemini's
   motivation is ChatGPT's replacement entry point: learn from real pairs as
   soon as the evidence permits, and do not delay once it does, without a
   documented blocker.
2. **Independence is a named external body, not a title.** Grok and Perplexity
   converge here, and Grok supplies the reason Perplexity's audit requires:
   appointment alone does not establish certification, because a nominating
   body may still control the evidence, decision, or appeal. The ISA certifies
   a safety disposition, the IGR certifies the process that produced it, and
   the relabelling trail feeds both — so the same person cannot hold any two
   of those positions without validating their own work product. Until a body
   with independent budget authority accepts appointment, removal, and funding,
   both roles remain titles, not controls, and any document signed under them
   lacks institutional force in Grok's verdict.
3. **The telemetry compromise is conditional, not settled.** Gemini designs
   the probe precisely enough to judge, and Perplexity refuses to presume it
   safe: brevity alone does not show that a quick reason prompt escapes
   dual-task penalty, label fatigue, over-trust, or latency. Read together,
   the compromise stands only if it is run as Gemini specifies — bounded,
   variance-triggered, capped, validated against a random-prompt control —
   and only if its acceptance criteria (primary-task performance, repeated-use
   label quality, inappropriate reliance, end-to-end delay) are frozen before
   results. Without those criteria, Perplexity's verdict holds: reasons remain
   unknown or inferred, and active prompting cannot be presumed acceptable.
4. **Calibration has a metric and a sample-size floor, but no number and no
   transfer.** DeepSeek locks ECE and shows why 14 and even 80 pairs cannot
   stabilise it, and why a passing aggregate can mask uniform underconfidence.
   Perplexity adds the transfer problem DeepSeek leaves implicit: staged or
   synthetic perturbations are not naturalistic distribution shifts, so a
   staged pass cannot establish real-world closure even if a number were
   locked. A frozen protocol with independently adjudicated real pairs could
   provisionally establish how closure will be judged; it would still leave
   threshold validity unlocked until those pairs are run.
5. **Owners are the missing piece in every lane.** DeepSeek needs a
   calibration-gate authority to name the ECE value, sample definition, and
   tolerance. Gemini needs a Lead Telemetry & Evaluation Architect. ChatGPT
   needs an accountable person to verify gate evidence, resolve V, and
   authorise first entry. Grok needs appointing bodies with budget authority.
   Perplexity needs a threshold owner and an independent adjudicator. No lane
   names one. Rules without owners are the pattern of Round 6: the governance
   is clearer than in Round 5, and the executability is not.

## The Perplexity caveat — read it before quoting its verdict
Perplexity states plainly that it was given stated constraints and summaries
of earlier rounds, not the four settlement texts, Gemini's Round 4 report,
appointment instruments, telemetry protocol, or calibration results. Its
"unlocked" verdict is therefore an evidence judgment about the audit packet
it received, not proof that every proposal is defective — it says so itself.
That distinction matters for the synthesis: ChatGPT's governance rule,
Grok's separation reasoning, Gemini's probe design, and DeepSeek's metric
stand as proposals on their own terms; Perplexity certifies none of them
because the primary records that would certify them were not in its packet.
A future audit round that supplies those texts could move a settlement to
provisionally locked without changing a word of the proposal. Conversely,
supplying the texts will not rescue a proposal whose falsifier is already
triggered — an undeclared class admitted through the value gate, a
claim-maker signing their own certification, or a threshold chosen after
inspecting its validation set.

## What is locked, what is not — scorecard after Round 6
Locked (as rules, not results): gate discipline over early unlock; undo below
2% as monitoring/review signal only; ISA/IGR/relabelling separation by
record type; micro-interaction probe shape (3-way choice, non-modal,
3-second dismiss, 3 per 15 minutes, variance/rejection triggers, 50-sample
cap, random-prompt control); ECE as the calibration metric; mechanism-fault
routing overriding a passing ECE on a uniform underconfidence pattern.
Unlocked: ISA and IGR individuals, appointing bodies, budget authority, and
the entire S4 appeal mechanism; V numbers, declarant names, and local records
for any class; calibration accuracy number, tolerance, sample definition,
threshold owner, and independent adjudicator; telemetry variance trigger,
latency cap, and protocol owner; simulated-to-real transfer for every design;
and the audit packet itself, which Perplexity did not receive.
Experiments run: still 0 of 5 designs in this round, and 0 across the programme.

## Next round direction
Round 7 should stop re-arguing the rules and start producing the records
Round 6 names: (1) the primary settlement texts, handed to the auditor in
full, so Perplexity's next verdict can certify or falsify rather than report
an absent packet; (2) named appointing bodies and owners for ISA, IGR,
telemetry, and calibration, with the conflict and recusal rules Perplexity
lists; (3) a frozen telemetry acceptance protocol and a frozen calibration
protocol with independently adjudicated real pairs, so the probe and the
threshold can be judged prospectively; (4) one declared-value, low-consequence
decision class put through ChatGPT's entry sequence on paper, to test whether
the entry rule selects anything at all. Until those records exist, the package
is governed but not executable — and that, rather than any single threshold
or role, is Round 6's central finding.
