# Research log — learn-and-build traceability

*Every scaffold decision links to its source. Rule: patterns and interfaces
only — no copied code from any surveyed system, ever. When a stub becomes a
real implementation, log the answering research here with its source.*

## Decision → source map (v0.1)

| Scaffold decision | Source (Wave 1) | What we took (pattern only) | License note |
|---|---|---|---|
| `reflect`: memory → conclusion op; cached standing answers ("mental models"); background reconciliation | vectorize-io/hindsight — `reflect`, mental models, knowledge-page reconciliation | The *operation shape* (conclude, don't dump context) and the *caching idea*; all code original | MIT — pattern reuse fine |
| `sop`: intent → procedure matching; offline trajectory → SOP distillation | volcengine/OpenViking skill-extraction pipeline; NevaMind-AI/memU session→skill track + dumb-storage/smart-agent split | The *pipeline shape* (distill successes into executable procedures) | OpenViking is **AGPL-3.0** — read-only inspiration, reimplement from scratch; memU: GitHub reports NOASSERTION vs README Apache-2.0 badge — verify before any reuse |
| `constraints`: negative constraints from failure trajectories | OpenViking reflection-guided guardrails; MemoriLabs/Memori tool-execution telemetry | The *idea* (failures as first-class inhibitory memory) | Same AGPL caution as above; Memori: NOASSERTION flag — verify |
| `resolver`: deterministic recency-based supersession + provenance log | MemoriLabs/Memori deterministic conflict resolution; hindsight "what holds *now*" reconciliation | The *determinism principle* (no LLM judgment at resolve time) | Memori license verify-before-reuse (see above) |
| `temporal`: recency × salience ranking; multi-signal fusion | mem0ai/mem0 temporal reasoning + parallel fusion (semantic/BM25/entity); getzep/graphiti time-bounded edges; thedotmack/claude-mem progressive disclosure | The *ranking formula shape* and *cost-aware retrieval* idea | mem0 Apache-2.0; graphiti Apache-2.0; claude-mem Apache-2.0 (OSS core) |
| `tiers`: core/archive split; narrow audited edit tools | letta-ai/letta core memory + memory tools (MemGPT lineage); claude-mem hook capture | The *tiering* and *agent-operated maintenance* concepts | letta Apache-2.0; claude-mem Apache-2.0 |
| `confidence`: scored options with evidence + rationale | rohitg00/agentmemory confidence-scored entries; hindsight disposition traits | The *confidence-on-evidence* signal idea; disposition as *posture knob* concept | agentmemory Apache-2.0; hindsight MIT |
| Eval harness pillars (LongMemEval-cleaned, LoCoMo) + adversarial/procedural/privacy dimensions | HF survey `hf-survey-v1.md` (14 notable datasets) | Dataset *selection*, not code | LongMemEval-cleaned MIT ✓; LoCoMo-MC10 **CC-BY-NC-4.0** — research use only, never commercial |
| Repo license: Apache-2.0 | Survey license flags (AGPL traps: OpenViking, honcho, basic-memory; NOASSERTION: memU, Memori) | Permissive licensing as a *design constraint* | Apache-2.0 chosen; never copy AGPL code |

## Decision → source map (v0.2 — Waves 2–4 + neuro track)

| Scaffold decision | Source (Waves 2–4 / neuro) | What we took (pattern only) | License note |
|---|---|---|---|
| `decision`: Soar preference cycle (propose → preference-rank → select → impasse→subgoals) as the canonical decision-layer reference | SoarGroup/Soar (W3) | The *cycle shape*; preference vocabulary better/worse/reject/prohibit/indifferent | **NOASSERTION** vs README BSD claim — verify LICENSE.md before any reuse; reimplement, never copy |
| `decision`: rejected-choice injection at propose-time (entity-keyed records: rationale, rejected approaches, what-would-change-your-mind) | masondelan/selvedge (W4) | The *injection mechanism*; experimental evidence 4/6 recurrences → 0/6 with records | License TBD — verify before reuse |
| `constraints`: Rescorla-Wagner helped/misled outcome re-ranking | mnemoverse/mcp-memory-server (W4) | The *learning rule* (prediction-error re-ranking) | MIT covers MCP server only; ranking engine proprietary — steal the rule, not the code |
| `constraints`/`temporal`: dopamine-signed surprise δ (negative δ creates/strengthens avoidance ∝ \|δ\|; positive δ boosts salience) | Neuro track §4 (Schultz 1997; Hollerman & Schultz 1998) | The *signed teaching signal*; answers specificity-vs-decay | Public science — no license constraint |
| `resolver`: conflict-gated strict recall (withhold, don't downrank) | CaviraOSS/LongMemory (W2) | The *gating policy* for unresolved contradictions | License check pending |
| `resolver`: ACC monitor→controller split (graded conflict score routes strategy) | Neuro track §8 (Botvinick 2001; Shenhav 2013) | *Monitor ≠ resolver*; cheap always-on monitor, score-invoked control; answers lazy-vs-eager | Public science |
| `resolver`: bi-temporal provenance (provenance.confidence + supersedes + validFrom/recordedAt) | modeled-information-format/mnemonic (W4) | The *conflict/time primitives* for the resolution log | License TBD — verify before reuse |
| `resolver`: dialectic reconciliation (background deriver + query-time agent) | plastic-labs/honcho (W2) | The *two-phase reconciliation* idea | **AGPL-3.0** — reimplement, never copy |
| `temporal`: outcome-weighted memory utility (helpful memories rank higher) | kitfunso/hippo-memory + caspianmoon/memoripy (W3); synthesis-all Tier 2 | The *utility reweighting* signal in fusion | Licenses TBD — verify |
| `temporal`: salience field + salience-dependent Ebbinghaus decay; two-level forgetting (retrieval decay vs storage prune) | Neuro track §§5, 11 (McGaugh 2004; Ebbinghaus 1885; Anderson & Schooler) | The *tagging axis* and *forgetting-as-generalization* design | Public science |
| `confidence`: drift-diffusion accumulation (drift = Σw·evidence → caution bound); confidence = f(margin, evidence, time) | Neuro track §7 (Ratcliff 1978 — invented for a memory task; Ratcliff & McKoon 2008) | The *scoring algebra* — answers calibration with math | Public science |
| `confidence`: OFC-style common-currency valuation before accumulation | Neuro track §9 (Padoa-Schioppa & Assad 2006) | *Valuation ≠ accumulation* separation for legible audit | Public science |
| `confidence`: second-order (metacognitive) calibration pass + calibration curves | Neuro track §10 (Fleming 2024) | *Don't ask the decider how sure it is*; log (confidence, outcome) pairs | Public science |
| `tiers`: hippocampal two-stage consolidation (fast log + semantic store + "sleep" replay) | Neuro track §1 (Diekelmann & Born 2010; CLS theory) | The *consolidation job* design with PFC tagging rule | Public science |
| `tiers`: reconsolidation protocol (labile-on-recall; scope + age-scaled resistance) | Neuro track §6 (Nader 2000) | The *edit-on-read* protocol with boundary conditions | Public science |
| `tiers`: PFC intake gating; tiny explicit core budget | Neuro track §2 (Goldman-Rakic; Miller & Cohen) | *Gating at ingest*; ≤2k-token core with promotion policy | Public science |
| `sop`: basal-ganglia fast path (cheap match before deliberation; confidence-floor fallback) | Neuro track §3 (Redgrave 1999; Barto 1995) | The *habit-vs-deliberation* arbitration | Public science |
| `sop`: cerebellar micro-tuning of procedures from telemetry | Neuro track §12 (Ito) | *Nudge-don't-discard* for small deviations | Public science |
| `reflect`: session distillation + decision provenance; auto-dream reconciliation | topoteretes/cognee (W1+W2); Mirix-AI/MIRIX (W3) | The *distillation* and *background reconciliation* patterns | cognee: check license; MIRIX license TBD |
| License red lines (Waves 2–4, hard) | synthesis-all.md §License red lines | **AGPL-3.0**: honcho, basic-memory, OpenViking — patterns only, never code. **NOASSERTION/custom/closed**: TencentDB-Agent-Memory, memtrace-public (Proprietary EULA — treat as closed), Memori, Soar, memU, general-agentic-memory, agentic_shared_memory, LLM-ACTR, reflexion (use the paper), HippocampAI, YourMemory, snap-research/locomo | Verify every LICENSE file before any reuse; prefer papers over code |

## The learn-and-build loop (how this file grows)

1. **Research** answers a stub's TODO question (paper, repo, experiment).
2. The stub becomes a real implementation — original code only.
3. The answering source is logged in the table above (new row).
4. `evals/` keeps the implementation honest.

## Sources consulted so far

- `../goals/ai-agent-memory-milestone-repo/hidden_files/repo-list-v1.md` — 111 ranked repos
- `../goals/ai-agent-memory-milestone-repo/hidden_files/wave1-findings.md` — 12 deep cards + composition
- `../goals/ai-agent-memory-milestone-repo/hidden_files/hf-survey-v1.md` — models/datasets/spaces + eval shortlist
- `../goals/ai-agent-memory-milestone-repo/hidden_files/synthesis-all.md` — full 100-repo mechanism inventory (Waves 1–4), Tier 1–3 adopts, license red lines
- `../goals/ai-agent-memory-milestone-repo/hidden_files/neuro-mapping-v1.md` — 12 neuroscience→AI mappings (DDM, RPE, ACC, OFC, reconsolidation, …)
- Papers phase (arXiv, journals) — harvest launched 14 Oct 2026; results pending.
- YouTube/video corpus — harvest launched 14 Oct 2026; results pending.

## Eval findings (v0.3 harness, first real runs — 14 Oct 2026)

Full reports: `evals/reports/recall-baseline-2026-10-14.json`,
`evals/reports/decision-bench-2026-10-14.json`.

**Recall half (LongMemEval-S, 500 items, baseline-tfidf reference):**
recall@1 0.644 / recall@5 0.84 / recall@10 0.902 / MRR 0.733.
This is the harness's own TF-IDF baseline — the floor `mm.temporal`
must beat once implemented, NOT a milestone-system number.
Weakest ability: `single-session-preference` (recall@1 0.23) — lexical
retrieval fails on "what do I prefer?" questions; temporal must rank on
entity/salience, not word overlap. Temporal-reasoning and multi-session
are the baseline's strengths (recall@10 0.92–0.96).

**Decision half (300 synthetic tasks, ground truth by construction,
real DDM+Soar pipeline):** NDCG 0.86, selection accuracy 0.53–0.63,
cross_rate 0.60, ECE ~0.15, Brier ~0.24.
- `sparse` variant (weak evidence): cross_rate 0.0 — the medium-stakes
  bound correctly holds everything back; all options return the 0.35
  undecided prior. The caution mechanism works as specified.
- `conflicting` variant (heavy opposition): hardest — accuracy 0.41,
  ECE 0.21. Contradictory evidence degrades both ranking and
  calibration. OPEN: this is the exact case metacognition should rescue;
  currently the conflict penalty is a flat 0.3×score, not evidence-driven.
- `tie` variant (seeded near-ties): tie-impasse rate 0.67 — the Soar
  cycle catches two-thirds of genuine near-ties; the rest slip through
  as false-confident selections. OPEN: tighten tie_epsilon or route
  through DDM accumulation before selecting.
- First harness bug caught and fixed: the initial generator produced
  too little evidence per option for the bound, so nothing crossed and
  every option returned 0.35 — selection degraded to input order. Lesson
  encoded: the harness now reports `cross_rate`; any run with
  cross_rate ≈ 0 on non-sparse variants is a harness/evidence-scale
  bug, not a module result.
