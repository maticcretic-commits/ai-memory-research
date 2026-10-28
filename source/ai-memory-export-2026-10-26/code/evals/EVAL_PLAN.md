# Eval plan — what "milestone-grade" means

*v0.3: harness is real — `evals/run_evals.py` has `list`, `recall`,
`decision` subcommands; `qa` client implemented 2026-10-15
(`evals/qa_client.py`, OmniRoute-backed answer + judge, judge-pin rule
documented) — first wired run the day the five free-provider keys land.
`run_evals.py` v0.1 stub retired 14 Oct 2026.*

## Protocol facts (verified 14 Oct 2026, web-checked)

- **Pin the S-split, not V2.** The official current dataset is
  `xiaowu0162/longmemeval-cleaned` (MIT; the original HF dataset is
  deprecated since May 2026). We pin `longmemeval_s_cleaned.json`.
  **LongMemEval-V2 (May 2026) is a different agentic-context protocol, NOT
  the same QA protocol** — never substitute it.
- **Current leaderboard bar** (agent-memory-leaderboard, 2026, LongMemEval-S
  claims): agentmemory V4 96.2% (481/500), PwC Chronos 95.6%, Mastra OM
  high 94.9%. **Caveats (his research bar): all self-reported, single runs,
  judges vary** (one system used a non-standard GPT-OSS-120B judge).
  Milestone-grade = top the board on a **re-run with fixed models and one
  documented judge**, not by quoting these numbers.
- **LoCoMo facts:** official repo `snap-research/locomo` (ACL 2024,
  arXiv:2402.17753); the adversarial category expects *refusal* (key is
  `adversarial_answer`, not `answer`); CC-BY-NC-4.0 research-only —
  confirmed still the right call. LoCoMo QA-pair counts float (~1,540–
  1,986) depending on how repos count; our runs report their own count.
- **Run-cost reference:** deep-recall's published 500-Q run cost $2.43
  (29 Sep 2026) — one data point for budgeting our harness runs.
- **No public equivalent exists** for the decision half (ranked options +
  calibration) — the benchmark itself is our design work (see below).

## Design principle

Every mechanism in `mm/` ships with an eval or it doesn't ship. The harness
has two halves: **recall** (does memory retrieve the right things?) and
**decision** (do ranked, confidence-scored options beat the alternative?).
The recall half reuses public benchmarks. The decision half doesn't exist
yet — designing it is itself a milestone contribution.

## The harness (v0.3 build order)

### 1. QA pillars — memory → context correctness
| Dataset | License | Role |
|---|---|---|
| `xiaowu0162/longmemeval-cleaned` (500 Qs, 5 abilities) | MIT ✓ | Core QA: extraction, multi-session reasoning, temporal, updates, abstention |
| `Percena/locomo-mc10` | **CC-BY-NC-4.0** — research use only, never commercial | Second QA pillar |

### 2. Adversarial dimension — what breaks memory
| Dataset | License | Role |
|---|---|---|
| `sumitaidev/agent-memory-resilience-benchmark` (+ Kaggle mirror) | Apache-2.0 | Poisoning / negative transfer: does the resolver + constraints hold? |

### 3. Procedural dimension — the thinnest coverage, our differentiation
| Dataset | License | Role |
|---|---|---|
| `shiweid1/Procedure_Memory_System_Benchmark` | MIT ✓ | Skills/workflows memory — scores the `sop` module directly |

### 4. Forgetting / privacy dimension
| Dataset | License | Role |
|---|---|---|
| `wwj95/privacy-aware-memory-benchmark` | CC-BY-4.0 | What should NOT be remembered — scores forgetting policy |

### 5. The scoreboard
- [`agent-memory-leaderboard/leaderboard`](https://huggingface.co/spaces/agent-memory-leaderboard/leaderboard)
  (939 likes) — the public scoreboard for agent-memory systems.
  **Milestone-grade = top this board**, not just beat our own baselines.

## The missing benchmark (v0.3 must design it)

No existing benchmark scores **memory → ranked-option recommendation with
calibrated confidence** — the milestone's core claim. v0.3 designs it:
- Task set: multi-option decisions where the right answer depends on recalled
  evidence (not just QA).
- Metrics: option-ranking quality (e.g. NDCG over options) + calibration error
  of confidence scores + audit-trail completeness (can a human verify why?).
- This benchmark is a publishable contribution on its own.

## License hygiene in evals

- LongMemEval-cleaned (MIT): safe everywhere.
- LoCoMo-MC10 (CC-BY-NC-4.0): **research only**. Any commercial demo must
  swap this pillar out. Flagged, not ignored.

## Runner

`run_evals.py` — v0.1 stub. Prints this plan and exits; honest about not
running anything yet.
