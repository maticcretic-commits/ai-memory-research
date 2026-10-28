# The decision cycle — memory → DECISION, end to end

*How the milestone turns candidate options into a recommended action with
calibrated confidence. Each step names the system it descends from — patterns
only, no copied code (see RESEARCH.md for license traceability). Module
designs live in ARCHITECTURE.md; this doc is the cycle that runs them in
order.*

```
propose → score with memory evidence → confidence-calibrate (DDM)
        → resolve conflicts → recommend + rationale → outcome feedback
```

---

## 1. Propose candidates

The agent planner proposes candidate options (actions, tool sequences,
answers) from current state. Two mechanisms sharpen the proposal set before
anything is scored:

- **Soar-style proposal.** Operators are proposed from state with
  applicability conditions — the only full propose/select cycle found
  across all 100 repos. *Descends from: SoarGroup/Soar (W3).*
- **Basal-ganglia fast path.** `sop.match` runs first as a cheap similarity
  gate. A high-confidence procedure match can short-circuit straight to
  execution (with telemetry attached); below the confidence floor the full
  cycle runs. Humans revert to prefrontal control when habits fail; so do
  we. *Descends from: neuro track §3 (Redgrave 1999; Barto 1995).*
- **selvedge rejected-choice injection.** Entity-keyed decision records —
  rationale, rejected approaches, what-would-change-your-mind — are checked
  at propose-time. A candidate matching a rejected record is pruned or
  flagged with its prior rationale before preferences attach. Experimental
  evidence: rejected choices recurred 4/6 without memory, 0/6 with injected
  records. *Descends from: masondelan/selvedge (W4).*

## 2. Score with memory evidence

Surviving candidates are scored against memory evidence, in this order:

1. `resolver` cleans the record set — deterministic rules, Soar preference
   vocabulary (better/worse/reject/prohibit) structuring precedence;
   unresolved contradictions are withheld (LongMemory gating), never
   silently downranked. *Memori / hindsight / LongMemory / mnemonic.*
2. `reflect` draws conclusions; cached mental models answer standing
   questions. *hindsight `reflect`; cognee distillation.*
3. `temporal` ranks evidence: recency × salience × multi-signal fusion ×
   outcome-weighted utility (memories that helped past decisions rank
   higher). *mem0; hippo-memory/memoripy.*
4. `sop` fit and `constraints` penalties attach as **preference votes**:
   temporal scores → better/worse; constraints → reject/prohibit; SOP
   fit → better. The decision layer aggregates the votes.
   *OpenViking; Soar preferences.*
5. **OFC-style valuation** maps each candidate's heterogeneous evidence into
   one scalar on a common scale — *before* accumulation. Valuation and
   accumulation stay separate and inspectable. *Neuro track §9
   (Padoa-Schioppa & Assad 2006).*

## 3. Confidence-calibrate via drift-diffusion

Per surviving candidate, accumulate `drift = Σ w_i · evidence_i` toward a
**caution bound** — per-task stakes set bound height (high stakes demand
more evidence). First across wins; ties within margin → impasse (see §6).

- **Confidence** = f(crossing margin, total evidence, accumulation time):
  fast crossing on strong drift → high confidence; slow grind near the
  bound → low confidence.
- **Second-order (metacognitive) pass.** A separate scorer — not the
  decider — reviews the trace: evidence stream, crossing margin, conflict
  score, historical accuracy of similar decisions from the episodic log.
  Never ask the decider how sure it is.
- **Calibration infrastructure.** Every decision logs (stated confidence,
  outcome); calibration curves render in evals. This is what makes the
  numbers *calibrated* rather than merely scored.
- *Descends from: Ratcliff DDM (1978 — invented for a memory task);
  neuro OFC + Fleming 2024 metacognition; agentmemory/hippo-memory
  confidence signals.*

## 4. Resolve conflicts

ACC-style, after scoring: a **graded conflict score** (contradiction count ×
severity × stakes) is computed over the top candidates' supporting evidence.

- **Low** → proceed with the DDM winner.
- **Medium** → provenance-weighted adjudication among contenders
  (mnemonic-style bi-temporal provenance: who said it, when, with what
  confidence, what it supersedes).
- **High** → escalate to the agent/LLM or refuse to decide — with the
  conflict surfaced, never hidden.

Unresolved contradictions stay withheld from the recommendation
(LongMemory gating). The monitor is cheap and always runs; the controller
is invoked by score — this is the lazy-vs-eager answer.
*Descends from: neuro ACC (Botvinick 2001); LongMemory; Memori; mnemonic.*

## 5. Recommend + rationale

Output per decision: **ranked options, calibrated confidence, evidence
citations, rationale, DDM trace, audit trail.** A human can overrule the
ranking from the trail alone.

## 6. Outcome feedback — the loop closes

The chosen action's **predicted outcome is recorded at decision time**.
On observed outcome:

- **Rescorla-Wagner re-ranking:** report whether the memories behind the
  decision *helped* or *misled*; prediction error re-ranks them.
  *Descends from: mnemoverse/mcp-memory-server (W4) — steal the learning
  rule, not the proprietary engine.*
- **Dopamine-signed constraint learning:** δ = outcome − prediction.
  Negative δ *creates or strengthens a negative constraint* with strength
  ∝ |δ| (first-class avoidance learning); positive δ boosts the salience
  of the records involved. Constraints decay as the environment changes.
  *Descends from: neuro track §4 (Schultz 1997).*

The decision improves the memory that made it. That is the learn-and-build
loop, running inside the product.

## 7. Impasse handling (Soar)

When no candidate crosses the bound within budget (**tie**), evidence
contradicts irreconcilably (**conflict**), or no candidate survives pruning
(**no-candidate**): spawn a **subgoal** — gather more evidence, ask the
agent/human, relax constraints — then re-enter the cycle at step 1.
Impasse type determines the subgoal strategy. *Descends from: Soar
impasse-deliberation.*
