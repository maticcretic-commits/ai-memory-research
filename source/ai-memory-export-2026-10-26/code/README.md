# Memory Milestone (`mm`)

## Current status — 25 Oct 2026

Built in phases by an AI partner council (Muse, ChatGPT as Head of
Operations, Gemini as auditor, Grok, Fo) under a human founder, from a
research base of 100+ surveyed repositories, papers and videos, and a
3,994-idea internal corpus.

- **Phase 1–2:** conflict monitor and decision cycle (propose →
  preference-rank → select → impasse), drift-diffusion confidence with
  a metacognitive second pass, gate (d) PASS, gate (b) PASS.
- **Phase 3:** memory schema v0.5 frozen; fail-closed quality-gated
  writes (secrets/PII hard-rejected); SQLite store as the only way in;
  Janitor with deliberate algorithmic forgetting; consolidation daemon
  opt-in (off by default).
- **Phase 4:** the autonomous memory agent — sentinel channels
  (anomaly instinct), immune write-defence, echolocation self-probing,
  per-lane shards, episodic recall — assembled as ears/mind/mouth.
  Hard-gate actions (spending, publishing, accounts, rights,
  irreversible) are queued for the founder, never executed.
- **Security:** six adversarial red-team rounds against a sandbox copy
  drove critical attack success to zero in the final round. Latest
  fix (25 Oct 2026): a flagged source can no longer supersede its own
  records, or vouch for another's supersession, without two clean,
  independent corroborations.
- **Tests:** 829 counted checks, all green, plus 7 legacy suites.
- **Benchmarks:** LongMemEval-S (n=500) chunked retrieval R@1 0.712 /
  MRR 0.797.

Honest gaps, on the record: calibration gate (a) remains an open FAIL
(the agent path runs underconfident); zero real production decision
pairs logged so far — calibration still rests on synthetic harness
pairs, and 30 real pairs is the set evaluation unlock; proactive
speech is built as gated proposals only, with no sending channel.

Large evaluation datasets are not stored in this repo (see
`.gitignore`); regenerate them with the scripts in `evals/`.

**Vision: memory → DECISION.**

Every agent memory system we surveyed does **memory → context**: recall facts,
inject them into a prompt, and leave the deciding to the model. This repo builds
**memory → DECISION**: a memory layer that ranks candidate options and recommends
actions with **calibrated confidence**, backed by a full audit trail of *why*.

```
                    ┌──────────────────────────────────────────────┐
                    │              AGENT (LLM planner)              │
                    │   proposes candidate options / actions       │
                    └──────────────────────┬───────────────────────┘
                                           │ candidates
                                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                        mm — memory milestone                      │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐      │
│  │ reflect  │  │   sop    │  │constraints│  │   resolver   │      │
│  │ memory→  │  │ procedure│  │ negative  │  │ deterministic│      │
│  │conclusion│  │ matching │  │constraints│  │   conflict   │      │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │  resolution  │      │
│       │             │              │        └──────┬───────┘      │
│       └─────────────┴──────────────┴───────────────┘              │
│                              │ evidence                           │
│                    ┌─────────▼──────────┐                        │
│                    │     temporal        │  recency × salience    │
│                    │      fusion         │  time-aware ranking    │
│                    └─────────┬──────────┘                        │
│                              ▼                                   │
│                    ┌──────────────────┐                          │
│                    │    confidence     │  calibrated scores over  │
│                    │     scorer        │  ranked candidate options│
│                    └─────────┬────────┘                          │
│                              ▼                                   │
│              ranked options + confidence + audit trail            │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ tiers — self-editing memory tiers (core / archive)        │    │
│  │ the agent maintains its own memory via audited tools      │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## Status: v0.3 — decision cycle implemented, the rest still stubs

The decision half of the system now runs. `mm.confidence` (OFC valuation →
drift-diffusion accumulation → DDM confidence → metacognitive pass →
calibration log) and `mm.decision` (Soar propose → preference-rank →
select, with selvedge rejected-choice injection and tie/conflict/
no-candidate impasse) are **implemented**, wired to the v0.2 spec in
`DECISION.md`, and covered by `tests/test_v03.py` (all passing). First-cut
parameters (stakes→bound mapping, drift weights, impasse thresholds) are
documented as tunable priors — the eval harness refines them.
The remaining modules (`reflect`, `sop`, `constraints`, `resolver`,
`temporal`, `tiers`) are still stubs; their TODOs name the exact research
questions that unlock them. This is deliberate — we **learn and build in
alternating loops**: research answers a question, the stub becomes real,
evals keep it honest.

## Module map

| Module | Job | Pattern source (Wave 1) |
|---|---|---|
| `mm.reflect` | memory → conclusion; cached standing answers | hindsight `reflect` + mental models |
| `mm.sop` | match intent to procedural playbooks (SOPs) | OpenViking skill extraction; memU skill track |
| `mm.constraints` | negative constraints learned from failures | OpenViking failure trajectories; Memori tool telemetry |
| `mm.resolver` | deterministic contradiction resolution | Memori recency supersession; hindsight reconciliation |
| `mm.temporal` | recency × salience time-aware ranking | mem0 temporal reasoning + multi-signal fusion |
| `mm.tiers` | self-editing core/archive tiers, audited | letta core memory; claude-mem progressive disclosure |
| `mm.confidence` | calibrated scores over ranked options | agentmemory confidence scoring; hindsight disposition |

See `ARCHITECTURE.md` for the full design and `RESEARCH.md` for the
learn-and-build traceability log.

## Roadmap

- **v0.1 — scaffold (this):** architecture, interfaces, eval plan. Stubs only.
- **v0.2 — mechanisms:** implement `reflect`, `resolver`, `temporal` first
  (highest decision-relevance); `sop`, `constraints`, `tiers`, `confidence` follow
  as research answers land.
- **v0.3 — eval harness (BUILT 14 Oct 2026):** `evals/run_evals.py` runs today:
  `recall` (LongMemEval-S pinned split, retrieval metrics, 500 items,
  baseline-tfidf reference: recall@1 0.644 / recall@5 0.84 / MRR 0.733 —
  the floor mm.temporal must beat), `decision` (the memory→decision
  benchmark, ground truth by construction: NDCG 0.86–0.89, selection
  accuracy 0.53–0.63, ECE ~0.15 on the real v0.3 DDM+Soar pipeline),
  `qa` (full answer+judge protocol — specced, wired when the answer model
  lands via OmniRoute). Findings logged in RESEARCH.md §eval-findings.
- **v0.4 — milestone demo:** an agent that takes a goal, recalls, reflects,
  ranks options with confidence, acts, and shows its audit trail — then takes on
  the public agent-memory leaderboard.

## Contributing (learn-and-build rules)

1. **Patterns, never copied code.** Every surveyed system is Apache-2.0/MIT
   except where flagged — and even then, we reimplement patterns from scratch.
   AGPL-licensed systems (e.g. OpenViking) are *read-only inspiration*: steal the
   pattern, never the code. See `RESEARCH.md`.
2. **A stub becomes real only when its research question is answered**, and the
   answer is logged in `RESEARCH.md` with its source.
3. **No implementation without an eval.** v0.3's harness gates every mechanism.
4. **Stay honest:** files must say what's stub vs real. No aspirational
   docstrings describing behavior that doesn't exist.

## License

Apache-2.0. See `LICENSE`. (Chosen deliberately: permissive, commercial-safe;
the research survey flagged AGPL copyleft traps we will not touch.)
