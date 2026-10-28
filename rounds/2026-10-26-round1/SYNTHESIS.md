# AI Memory Research — Round 1 Synthesis
Date: 2026-10-26 evening IST. Sources: verbatim replies in `inbox/`
(ChatGPT, Grok, Perplexity, DeepSeek, Gemini). Copilot abstained
(region wall, app route only — lane decision still parked with Nitesh).
This synthesis is Jarvis's own report, separate from the verbatim
replies; no partner view is merged into another partner's reply.

## Convergences — all five, in different lanes
1. **Memory → decision, not memory → context.** Naive retrieval
   dumping is the old model. The system must rank candidate options
   under constraints, with calibrated confidence and an audit trail
   of why — otherwise recall scores prove nothing about decisions.
2. **Talk-back is its own layer.** Surface, remind, warn, ask,
   explain are distinct behaviours, and silence is a measured
   success, not a failure. No partner found a public system with a
   calibrated proactive gate plus a real sending channel; mm's
   gated proposals with no sending channel are at the safer edge.
3. **Confidence must be per claim, per action, and calibrated on
   real outcomes.** Underconfidence is a defect too — it withholds
   useful memories and degrades ranking. High confidence grants no
   permission. Proposal, approval, action, and verified outcome are
   four separate states.
4. **Hybrid storage, metadata first.** Relational/SQLite as the
   authoritative record, keyword + vector candidates, optional
   graph expansion. Pure vector loses time, IDs, and conflict
   structure; pure graph is brittle and expensive at scale.
   Metadata filtering (time, session, user) plus vector search is
   required for episodic memory; recency × salience is a hypothesis,
   not a law, and must not override an older authoritative constraint.
5. **Stale and conflicting memory is the primary failure mode.**
   Versioned supersession with validity intervals, provenance,
   and history preserved — never silent overwrites. Deleting a
   memory without recording why destroys the audit trail.
6. **Poisoning and incomplete forgetting are open, high-severity
   risks.** Write-path poisoning, ranking inversion, cross-user
   leakage, and deletion that leaves copies in summaries, embeddings,
   caches, and backups. Prompt filtering alone does not cover
   persistent-write attacks. Hook-based secret blocking at write
   time beats prompt-based policies.
7. **Laboratory metrics are not production proof.** All five note,
   in their own words, that mm's figures (829 tests, LongMemEval-S
   R@1 0.712 / MRR 0.797, six red-team rounds to zero critical)
   are internal claims, not independently verified in public
   sources, and that zero real production decision pairs is the
   hard gap. Recall is not decision quality.

## Divergences and tensions — worth keeping, not averaging away
- **Write-time vs read-time scoring (DeepSeek vs the field).**
  DeepSeek argues write-time importance is a frozen prediction
  that cannot condition on the query, citing an ablation where a
  position-blind baseline beat a recency+importance blend — a
  possible structural root for mm's calibration failure, not proven
  causation. Others treat recency × salience as a starting
  principle to tune, not a structural flaw.
- **Consolidation (DeepSeek, Gemini).** Consolidation is not
  always helpful: a cited Dream Cycle regression, and Gemini's
  open question of when destructive summarisation is justified
  without losing nuance. No partner gives a safe consolidation rule.
- **Abstention (Gemini, ChatGPT).** Gemini calls abstention the
  hardest benchmark; ChatGPT calls for a silence metric and a
  small manually reviewed dataset including cases where silence is
  correct. The field has no standard silence metric — an open
  build opportunity.
- **Costs and licences (Perplexity, Grok).** Costs per useful
  decision are unknown and must be measured (ingestion, embedding,
  reflection, retrieval, reranking, storage, deletion, audit).
  Graphiti reference servers are flagged as lacking auth;
  LongMemEval-V2 (2026, 451 questions, up to 500 trajectories)
  is closer to procedural evaluation, still not production
  validation.

## What Round 1 settles, and what it does not
Settled enough to build on: the architecture shape (SQLite
authoritative + hybrid retrieval + explicit temporal/conflict/
confidence modules), the talk-back taxonomy, the four-state
proposal pipeline, and the staged evaluation (recall → freshness
→ conflict → talk-back quality → decision quality → safety →
deletion).
Not settled: calibration (how to fix underconfidence, what
thresholds by consequence, what dataset size calibrates a gate),
consolidation safety, forgetting completeness under extraction
attack, decision regret on real pairs, and the cost per decision.

## Next experiments — the Round 2 brief (see Round 2)
1. Talk-back policy experiment: always-surface vs query-only vs
   value-of-interruption, on identical scenarios, measuring useful
   interventions, unnecessary interruptions, and missed warnings.
2. Calibration experiment: labelled decision dataset, calibration
   by risk category, read-time re-scoring vs frozen write-time
   scores, gate held closed until pre-set criteria are met.
3. Decision audit pilot: one production decision pair per day
   for two weeks (14 pairs), logging candidate set, ranked choice,
   confidence, and human outcome; test whether underconfidence is
   structural or a threshold artefact.
4. Privacy and forgetting experiment: seeded synthetic PII/secrets
   across records, summaries, and indexes; test access boundaries,
   deletion propagation, recovery, and prompt injection.
5. Shadow-mode pairs: consented, low-risk workflow, proposal
   quality and interruption burden measured before any sending
   channel is enabled.

## Scoreboard (Jarvis, pending Copilot lane decision)
- Partners in: 5 of 5 browser partners, all verbatim saved.
- Partners abstained: Copilot (region wall, app route only).
- Replies claiming independent verification of mm's internal
  figures: 0 of 5 — all five treat them as internal claims.
- Gaps all five name: calibration FAIL, zero real decision pairs,
  no sending channel, no silence metric, unknown costs.
