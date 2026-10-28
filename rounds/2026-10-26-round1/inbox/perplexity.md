# Perplexity — AI Memory Research Round 1 (verbatim)
- Lane: Verified research
- Browser task: completed 2026-10-26, 20:53-20:55 IST (measured, 2m)
- Signed in: account shown MaticCretic, Free plan, recent chats visible
- Model name shown in UI: none visible — generic "Model" control only
- Response showed "Finished 16s"
- Brief sent in a new chat
- Source chat: https://www.perplexity.ai/search/60e1c6ba-f635-4b90-ae22-3fba07d262d1
- Note from browser report: inline source citations shown in the Perplexity UI are not reproduced in the body below.

---

AI Memory Research — Round 1

Individual verified-research report | Evidence cutoff: October 26, 2026

1. Assessment of Memory Milestone

Memory Milestone's important distinction is memory → decision: choosing among options under constraints, rather than merely supplying retrieved context.

The supplied record reports 829 passing tests, LongMemEval-S R@1 0.712/MRR 0.797, six red-team rounds ending with zero critical successes, failed underconfidence calibration, and zero production decision pairs. These are user-provided assertions, not independently verified results: no repository, logs, evaluation configuration, or decision dataset was supplied. Passing tests and a clean final attack round therefore do not establish production reliability.

LongMemEval evaluates extraction, multi-session reasoning, updates, temporal reasoning, and abstention. Its official project describes 500 questions. MM's retrieval scores should not be equated with answer accuracy or decision quality without its scoring definitions and retrieval-unit specification.

Recommendation: preserve MM's proposal-only boundary while testing whether remembered evidence improves decisions, including decisions to abstain.

2. How memory works

The useful functional categories are:

• Short-term: active conversation and task state.
• Episodic: particular events, actions, and outcomes.
• Semantic: durable facts and preferences.
• Procedural: reusable workflows, rules, and skills.

These are engineering mappings borrowed from cognitive science—not evidence that an agent implements human memory. Semantic memory also differs from semantic search: one describes stored knowledge; the other describes retrieval by meaning.

For MM, I propose this explicit lifecycle:

1. Encoding: capture observations with speaker, source, event time, ingestion time, permissions, and uncertainty.
2. Storage: retain original evidence separately from extracted claims and inferred rules.
3. Retrieval: select evidence relevant to the present question or candidate decision.
4. Consolidation: derive summaries or SOPs from episodes, retaining provenance.
5. Forgetting: expire, redact, or delete material under policy.
6. Reconsolidation: revise a retrieved claim through a versioned update, rather than silently overwriting history.

Generative Agents provides a foundational example of experience storage, higher-level reflection, and retrieval for planning. Biological reconsolidation offers a narrower analogy: retrieval can destabilize memories, but does not invariably do so; strength, age, and retrieval conditions matter.

Storage and ranking

SQLite, vectors, and graphs are not mutually exclusive. SQLite FTS5 supports text search; sqlite-vec adds vector search. Graphiti represents temporal relationships and provenance, combining semantic, keyword, and graph retrieval.

Proposed MM baseline: SQLite as the authoritative record, keyword/vector candidate retrieval, and optional graph expansion. Compare this against simpler alternatives before adding operational complexity.

Treat "recency × salience" as a hypothesis, not a universal law. Recent information should not automatically override an older authoritative constraint. Rank only after permissions and temporal applicability checks; evaluate relevance, trust, salience, and recency separately.

3. How memory talks back

I propose five distinct outputs:

• Surface: relevant evidence during an active task.
• Remind: a consented obligation near its actionable window.
• Warn: a concrete conflict, anomaly, or constraint violation.
• Ask: missing information could change the preferred option.
• Explain: show supporting sources, rejected options, uncertainty, and applicable constraints.

Stay silent when evidence is irrelevant, duplicated, unauthorized, expired, or too weak to justify interruption. These are proposed policies, not experimentally established thresholds.

Calibration means confidence should match observed correctness frequency. Temperature scaling is an established post-processing technique in classification, but its success there does not establish suitability for MM's decision scores.

For MM, distinguish evidence confidence, predicted outcome probability, and authority to act. High confidence does not grant permission. Given the reported underconfidence failure, do not simply increase scores: validate recalibration on held-out decisions.

Keep proposal generation separate from sending. A future sender should require approval bound to recipient, channel, exact content, expiry, and current permissions, then revalidate before execution.

4. Failures, security, and privacy

A June 2026 preprint introduces MPBench and identifies four memory-write channels, nine structural vulnerabilities, and six attack classes. Its authors report that more aggressive memory writing/retrieval can increase exploitability and that existing prompt-injection defenses do not fully cover memory poisoning. These are study findings, not universal attack rates.

Proposed MM controls:

• Immune write-defense: quarantine untrusted writes; never promote retrieved instructions into policy automatically.
• Source trust: record provenance and distinguish independent corroboration from repeated copies.
• Conflict resolution: preserve competing claims with validity intervals and explicit supersession.
• Access control: enforce tenant and user boundaries before retrieval and output.
• PII/secrets: minimize collection, redact before indexing, and avoid storing credentials.
• Janitor: propagate deletion into summaries, embeddings, caches, and backup-retention processes.
• Sentinel channels: distinguish suspicious evidence from authorized behavioral instructions.

A concrete repository warning: Graphiti's reference servers explicitly lack authentication, authorization, and prompt-injection protection; production deployments must supply these controls.

Testing should include delayed poisoning, cross-user leakage, forged provenance, stale constraints, contradictory updates, deletion resurrection, and excessive abstention—not only successful recall.

5. Verified developments, costs, and experiments

LongMemEval-V2, released in 2026, broadens evaluation toward experienced agents: 451 questions, five abilities, and histories reaching 500 trajectories/115 million tokens. It measures answer accuracy and query latency, including workflow knowledge, environment gotchas, and premise awareness. This is closer to MM's procedural ambitions, but remains distinct from production decision-outcome validation.

Useful licensed components include Graphiti and LongMemEval-V2 under Apache-2.0, and LangGraph's open-source library under MIT. These licenses do not establish identical rights for every dependency, dataset, or hosted service.

MM's costs remain unknown. Measure ingestion, embedding, reflection, retrieval, reranking, storage, deletion, and audit overhead per useful decision.

Next experiments: reproduce the reported benchmark; compare no-memory, hybrid retrieval, and full MM; ablate reflection, temporal ranking, and source trust; collect consented shadow-mode decision pairs; assess calibration and interruption burden before enabling sending.

Top 5 findings

1. MM's reported results remain unverified without artifacts.
2. Recall quality is not decision quality; production outcome evidence is missing.
3. Memory poisoning requires persistent-write defenses, not only prompt filtering.
4. LongMemEval-V2 adds workflow and premise-awareness evaluation.
5. Proposal quality, confidence, and execution authority should be tested separately.

Top 3 open questions

1. What outcome makes an MM decision correct, and over what time horizon?
2. Can MM improve decision utility without increasing poisoning, leakage, or unwanted interruptions?
3. Can forgetting remove sensitive derived information while preserving a useful, privacy-respecting audit trail?
