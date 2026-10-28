# Architecture — the 100-repo composition, written as design

*Synthesized from 100 deep-researched agent-memory systems (Waves 1–4; see
`RESEARCH.md`) plus a neuroscience→AI mapping track (see
`../goals/ai-agent-memory-milestone-repo/hidden_files/neuro-mapping-v1.md`).
Status: v0.2 design. All modules are stubs; each section ends with the open
questions the ongoing research must answer before implementation. Questions
marked [ANSWERED] have a defined mechanism or mathematics — implementation
is still pending.*

## The gap this architecture fills

All 100 surveyed systems do **memory → context**: retrieve relevant memories,
inject them into the prompt, and let the model decide on its own. None ranks
candidate options. None recommends an action with calibrated confidence. None
exposes *why this option, with what evidence, at what confidence* as a
first-class output.

This architecture composes the strongest decision-relevant mechanisms found —
each from a different system, none of which combines them — into a single
**memory → DECISION** pipeline. The end-to-end cycle is specified in
`DECISION.md`.

## Data flow

```
candidate options (from the agent planner)
        │
        ▼
┌───────────────────┐
│ 0. decision       │── Soar preference cycle, reimplemented in LLM form:
│   (orchestrator)  │   propose → preference-rank (better/worse/reject/
│                   │   prohibit) → select; impasse → subgoal deliberation.
│                   │   selvedge rejected-choice injection: entity-keyed
│                   │   records (rationale, rejected approaches,
│                   │   what-would-change-your-mind) stop recurrences.
├───────────────────┤
│ 1. resolver       │── deterministic contradiction resolution + ACC-style
│                   │   monitor→controller: graded conflict score routes to
│                   │   tiered strategies. LongMemory conflict-gating:
│                   │   unresolved contradictions are WITHHELD, not downranked.
├───────────────────┤
│ 2. reflect        │── memory → conclusion: draws conclusions from memories;
│                   │   cached standing answers ("mental models").
├───────────────────┤
│ 3. sop            │── basal-ganglia-style fast path: cheap procedure match
│                   │   before deliberation, confidence floor → fallback.
│                   │   Cerebellar micro-tuning of SOPs from telemetry.
├───────────────────┤
│ 4. constraints    │── negative constraints + Rescorla-Wagner outcome
│                   │   feedback (helped/misled re-ranking); dopamine-signed
│                   │   surprise δ: negative δ creates/strengthens avoidance.
├───────────────────┤
│ 5. temporal       │── recency × salience × fusion; outcome-weighted
│                   │   utility; Ebbinghaus two-level forgetting.
├───────────────────┤
│ 6. confidence     │── OFC-style valuation to a common scale, then
│                   │   drift-diffusion accumulation to a caution bound;
│                   │   second-order (metacognitive) calibration pass.
└───────────────────┘
        │
        ▼
ranked options + calibrated confidence + audit trail

tiers (orthogonal): hippocampal two-stage memory — fast episodic log +
consolidated semantic store with "sleep" consolidation; PFC-gated core;
labile-on-recall self-editing with age-scaled edit resistance.
```

---

## 0. `decision` — Soar preference cycle (orchestrator) [NEW in v0.2]

**Purpose.** The decision layer itself — the outer loop every other module
serves. Reimplements the ONLY full decision cycle found across all 100
repos (Soar): propose candidate operators from current state → attach
preferences in the vocabulary *better / worse / reject / prohibit /
indifferent* → select the preferred candidate → on **impasse** (no clear
winner), spawn a subgoal and deliberate. Memory modules feed it evidence;
the confidence module calibrates its verdict.

**Inputs → Outputs.** `(state, candidates) → (selection | impasse(subgoals),
preference_log)`.

**Pattern inspiration.** SoarGroup/Soar (W3): propose → preference-rank →
select → impasse-deliberation. License: GitHub NOASSERTION vs README BSD
claim — verify LICENSE.md before any reuse; reimplement the *cycle*, never
copy code. masondelan/selvedge (W4): rejected-choice injection —
entity-keyed decision records carrying rationale, rejected approaches, and
what-would-change-your-mind, checked at propose-time. Experimental evidence:
rejected choices recurred 4/6 without memory, 0/6 with injected records.

**Open questions.**
- How are preferences *computed* from memory evidence? (Proposal: each
  module emits preference votes — temporal scores → better/worse,
  constraints → reject/prohibit, SOP fit → better — aggregated here.
  Needs a vote-aggregation rule.)
- Impasse taxonomy: tie vs conflict vs no-candidate need different subgoal
  strategies. What are the trigger thresholds?
- Where does the DDM caution bound live relative to impasse detection?
  (Proposal: impasse fires when no candidate crosses within a time budget.)

## 1. `reflect` — memory → conclusion

**Purpose.** The core differentiator. Instead of returning retrieved context
for the agent to interpret, `reflect` *reasons over memories to a
conclusion*: answers, dispositions, and standing judgments. Frequently asked
standing questions get cached answers ("mental models") rewritten in the
background as memory evolves — so a deciding agent boots from settled
answers, not raw recall. Conclusions feed preference evaluation in §0.

**Inputs → Outputs.** `(records: list[MemoryRecord], question: str, disposition)
→ Conclusion(text, confidence, evidence_ids[], generated_at)`.
Background job: `refresh_models()` rewrites cached standing answers.

**Pattern inspiration.** hindsight's `reflect` operation (the only first-class
memory→conclusion mechanism in the wave), its mental models as cached
standing answers, and its background knowledge-page reconciliation ("what
holds *now*"). Plus: cognee's session distillation + decision provenance
(W2); MIRIX auto-dream background reconciliation (W3).

**Open questions.**
- What exactly should `reflect` compute — a free-text conclusion, a
  structured disposition-aware answer, or both? What is the output contract?
- When is a cached standing answer invalidated? (Contradiction arrival?
  temporal decay? explicit agent edit?)
- How do disposition traits change conclusions without becoming
  prompt-injection surface?

## 2. `sop` — procedure matcher

**Purpose.** Constrain the option space with procedural knowledge: match the
current intent to executable playbooks (SOPs) distilled from past successful
trajectories. An option that no known procedure can execute is down-ranked.
Runs as a **basal-ganglia-style fast path**: a cheap similarity gate *before*
the expensive reflect/confidence pipeline — with a confidence floor below
which the system falls back to full deliberation (mirroring how humans
revert to prefrontal control when habits fail).

**Inputs → Outputs.** `(intent: str, procedures: store) → ranked list[Procedure]`;
`extract_sop(trajectory) → Procedure` (distillation, offline).
Telemetry hook: `tune_sop(procedure, execution_telemetry)` — cerebellar-style
micro-tuning: repeated small deviations nudge parameters; large failures
feed `constraints` instead.

**Pattern inspiration.** OpenViking's skill-extraction pipeline (successful
multi-turn trajectories → reusable SOPs); memU's session→skill distillation
and its dumb-storage/smart-agent split; alibaizhanov/mengram (W4)
experience-driven procedural memory — clearest differentiator in its niche.
Neuro: basal ganglia action selection (fast path), cerebellar error-driven
fine-tuning (micro-tuning).

**Open questions.**
- What is the minimal SOP schema (steps? preconditions? success telemetry?)?
- What success threshold promotes a trajectory to a durable SOP?
- How are SOPs versioned when the environment changes under them?
- Where exactly is the confidence floor for fast-path vs deliberation?

## 3. `constraints` — negative-constraint store + outcome feedback

**Purpose.** Learn what *not* to do — and keep learning from every outcome.
Past failure trajectories become negative constraints injected at decision
time. On top of that, a **Rescorla-Wagner outcome feedback** loop: after an
action, report whether the memory behind it *helped* or *misled*; prediction
error re-ranks the memory. The dopamine-signed variant: every executed
action records `predicted_outcome`; on observed outcome, signed surprise
`δ = outcome − prediction`. Positive δ boosts the salience of involved
records; negative δ *creates or strengthens a negative constraint* with
strength ∝ |δ|.

**Inputs → Outputs.** `(task_signature) → list[NegativeConstraint]`;
offline `learn_constraint(failure_trajectory) → NegativeConstraint`;
online `report_outcome(memory_id, helped: bool, surprise: float)`.

**Pattern inspiration.** OpenViking's reflection-guided guardrails / negative
constraint injection; Memori's tool-execution telemetry; mnemoverse
mcp-memory-server (W4): Rescorla-Wagner helped/misled re-ranking — MIT
covers only their MCP server, the ranking engine is proprietary: steal the
*learning rule*, never the code. Neuro: dopamine reward-prediction error,
signed (Schultz 1997) — the negative channel is first-class avoidance
learning, not just absence of reward.

**Open questions.**
- [ANSWERED — mechanism defined] Specificity vs decay: negative δ creates /
  strengthens constraints with strength ∝ |δ|; constraints decay as the
  environment changes (a constraint from a since-fixed bug must die).
  Implementation pending.
- How is `task_signature` computed so constraints generalize without
  over-firing? (Still open.)
- Who audits constraint injection? (Audit trail requirement.)

## 4. `resolver` — deterministic conflict resolver + conflict monitor

**Purpose.** Contradictory memories must never reach scoring unresolved — and
unresolved contradictions must never be silently downranked into reasoning
either. Two stages, mirroring the anterior cingulate cortex: a cheap
**monitor** that always runs and emits a graded conflict score
(contradiction count × severity × stakes), and a **controller** that picks
the resolution strategy by score. Resolution itself stays deterministic
(auditable, reproducible), now structured by Soar's preference vocabulary:
*better / worse / reject / prohibit* outrank raw recency.

**Inputs → Outputs.** `(records) → (surviving_records, withheld_records,
resolution_log)`. Withheld records (LongMemory conflict-gating) are excluded
from reasoning but retained and surfaced — never silently dropped.
Every resolution logged with winner, loser, rule applied.

**Pattern inspiration.** Memori's deterministic supersession with temporal
provenance; hindsight's background contradiction reconciliation; CaviraOSS/
LongMemory (W2): conflict-gated strict recall — unresolved contradictions
WITHHELD, not downranked; modeled-information-format/mnemonic (W4):
per-record `provenance.confidence` + `supersedes` relation + bi-temporal
(validFrom/recordedAt) triad — richest conflict/time primitives; plastic-labs/
honcho dialectic reconciliation (AGPL-3.0 — reimplement, never copy).
Neuro: ACC conflict monitoring (monitor ≠ resolver; control recruited by
score).

**Open questions.**
- [ANSWERED — mechanism defined] Lazy vs eager: the monitor always runs
  (cheap); the controller is invoked by conflict score. Implementation
  pending.
- Precedence rule details: high-confidence old facts vs low-confidence new
  claims — exact weighting of provenance.confidence × recency?
- Conflict-score thresholds for low/medium/high tiers?
- Near-duplicate merge vs contradiction resolve — different ops, shared
  plumbing?

## 5. `temporal` — temporal fusion ranker + outcome-weighted utility

**Purpose.** Score evidence by **recency × salience × fusion**, now with
**outcome-weighted utility**: records whose evidence helped past decisions
get a utility boost (the memory that wins decisions gets heard more).
Salience is a first-class field set at ingest (prediction-error magnitude,
user emphasis, error cost) — amygdala-style tagging — and decay is
salience-dependent (Ebbinghaus curve with per-record time constants).
Forgetting is two-level: **retrieval decay** (fast, reversible strength
loss) vs **storage pruning** (only after sustained sub-threshold retrieval
across a consolidation cycle) — forgetting as generalization, not janitor.

**Inputs → Outputs.** `(records, query, now) → list[(record, score)]`
ranked descending; each score carries its signal breakdown.

**Pattern inspiration.** mem0's temporal reasoning + parallel multi-signal
fusion; graphiti's time-bounded edges; claude-mem's progressive disclosure
(cost-aware retrieval); kitfunso/hippo-memory + caspianmoon/memoripy (W3):
per-memory outcome feedback reweighting ranking. Neuro: amygdala salience
tagging; Ebbinghaus/adaptive forgetting (Anderson & Schooler: forgetting
tracks environmental need probability).

**Open questions.**
- Fusion weights: learned, fixed, or per-query? (Still open.)
- Where does progressive disclosure plug in — cost-bounded retrieval tiers?
- Utility half-life: how fast should outcome-boosts fade without
  reinforcement?

## 6. `tiers` — self-editing memory tiers

**Purpose.** The agent maintains its own memory, designed as a hippocampal
two-stage system: a fast append-only **episodic log** (cheap writes,
recency-weighted) plus a consolidated **semantic store** (expensive writes,
interference-resistant). A background `consolidate()` ("sleep") replays the
log, distills repeated patterns into the semantic store, and prunes —
PFC-tagged: only salient, decision-referenced, or surprising records
consolidate; the rest decay. The prompt-resident **core** tier stays tiny
(≤2k tokens) with PFC-like intake gating and an explicit promotion/demotion
policy. Self-editing follows the **reconsolidation protocol**: recall makes
*only the retrieved record* labile until task end; edit resistance scales
with record age and confirmation count.

**Inputs → Outputs.** `read_core() / edit_core(op) → audit entry`;
`archive_search(query) → records`; `promote(record) / demote(record)`;
`consolidate() → distillation report`.

**Pattern inspiration.** letta's core/archive split + agent-operated memory
tools (MemGPT lineage); claude-mem's hook capture; agiresearch/A-mem (W3):
Zettelkasten-style new-rewrites-old; agentscope-ai/ReMe (W2): Auto Dream
opcodes (CREATE/CORROBORATE/REFINE/CORRECT) with confidence strengthening.
Neuro: hippocampal systems consolidation + sleep replay (CLS theory);
prefrontal gating; reconsolidation boundary conditions (Nader 2000).

**Open questions.**
- Consolidation schedule: on a timer, on log-size threshold, or on
  decision-boundary events? (Still open.)
- What edit operations are safe to expose? Guardrails against self-lobotomy?
- Labile-window edge cases: concurrent tasks touching the same record?

## 7. `confidence` — drift-diffusion confidence scorer [UPDATED v0.2]

**Purpose.** The output contract of the whole system — and where the
milestone is won or lost. Every surviving candidate option gets a
**calibrated confidence score**, cited evidence, and a rationale.

**[ANSWERED — with mathematics]** The scoring algebra the scaffold was
missing is now defined, from the neuro track (Ratcliff 1978 — invented for
a *memory* task; the decision math started as memory math):
1. **OFC-style valuation**: map each candidate's heterogeneous evidence
   (SOP fit, temporal scores, constraint penalties, reflect conclusions)
   into one scalar on a common scale — *before* accumulation. Valuation
   and accumulation stay separate and inspectable (biology separates them;
   the separation is what makes the audit trail legible).
2. **Drift-diffusion accumulation**: per candidate, `drift = Σ w_i ·
   evidence_i`; accumulate toward a **caution bound** (per-task stakes set
   bound height — high stakes demand more evidence). First across wins;
   ties within margin → impasse.
3. **Confidence** = f(crossing margin, total evidence, accumulation time):
   fast crossing on strong drift → high confidence; slow grind near the
   bound → low confidence.
4. **Second-order (metacognitive) pass**: confidence is computed *separately
   from* the decision — a distinct scorer reviews the trace (evidence
   stream, margin, conflict score, historical accuracy of similar decisions
   from the episodic log). Never ask the decider how sure it is.
5. **Calibration infrastructure**: log (stated confidence, outcome) pairs
   from day one; render calibration curves in evals — this is how the
   module becomes *calibrated* rather than merely scored.

**Inputs → Outputs.** `(options, evidence_bundle) → list[ScoredOption]`
ranked by confidence descending. `ScoredOption = (option, confidence ∈ [0,1],
evidence_ids[], rationale, audit_ref)` — plus the DDM trace
(evidence stream, bound, crossing margin) for audit.

**Pattern inspiration.** agentmemory / hippo-memory / memoripy
confidence-scored entries (confidence signals on *evidence*); hindsight
disposition traits as decision-posture knobs; tao-hpu/cognitive-workspace
metacognitive controller (PoC — steal the design). Neuro: DDM, OFC
valuation, Fleming 2024 metacognition.

**Open questions (remaining).**
- Bound parameterization: exact mapping from task stakes to bound height?
- Evidence→drift weights: how do temporal scores, SOP fit, constraint
  penalties map to w_i? (Fixed? learned from calibration data?)
- Audit content: what must the trail contain for a human to overrule?
- Implementation of the whole pipeline (pending).

---

## Open questions — status ledger (v0.2)

**Answered with mechanism/mathematics (implementation pending):**
1. **Calibration** — what grounds the numbers? → Drift-diffusion + OFC
   valuation + second-order metacognitive pass + calibration curves.
   (Was: "no surveyed system calibrates; needs new eval." Now: math defined.)
2. **Scoring algebra** — how do evidence, conflicts, constraints move the
   score? → `drift = Σ w_i · evidence_i` accumulated to a caution bound;
   constraint penalties as negative drift; conflict score gates the tier.
3. **Constraint specificity vs decay** → signed surprise δ creates /
   strengthens constraints (∝ |δ|); constraints decay as the environment
   changes.
4. **Lazy vs eager resolution** → ACC-style: cheap monitor always runs;
   controller invoked by conflict score.
5. **Precedence beyond recency** → Soar preference vocabulary
   (better/worse/reject/prohibit) + LongMemory withhold-on-contradiction.

**Still open (research or design decisions needed):**
- Preference vote aggregation across modules (§0).
- Impasse taxonomy and trigger thresholds (§0).
- DDM bound ↔ task-stakes mapping; evidence→drift weight mapping (§7).
- `task_signature` granularity for constraint matching (§3).
- Mental-model invalidation policy (§1).
- SOP schema, promotion threshold, versioning (§2).
- Fusion weights: learned / fixed / per-query (§5).
- Consolidation schedule and core membership policy (§6).
- Audit-trail content standard for human overrule (all modules).

## Non-goals for v0.2

- A vector/graph store implementation (store-agnostic; use existing
  backends later).
- The LLM calls themselves (v0.2 defines *where* and now *the math*,
  not the prompts).
- Production hardening, auth, multi-tenancy.
