# DeepSeek — AI Memory Research Round 1 (verbatim)
- Lane: Build
- Browser task: completed 2026-10-26, 20:53-20:56 IST (measured, 2m)
- Signed in: new chat started, brief sent exactly as written, response finished streaming
- Model name shown in UI: none visible — only "DeepThink" and "Search" toggles shown
- Chat: https://chat.deepseek.com/a/chat/s/96f49cd0-2d50-41d5-9f56-e0136315f876

---

Build Lane Report: How Memory Mechanisms Are Actually Built

Scope note: I found no public source describing the internal code of "Memory Milestone" (mm). All claims below are about the broader field, or explicitly marked as inference about what mm likely does given its described modules. I did not collaborate with other partners.

1. How Memory Works in Code

Encoding. Production systems converge on a write path that does more than embed raw text. A-Mem creates atomic "notes" with structured attributes (context description, keywords, tags, embedding) and uses an LLM to decide links to existing notes. Graphiti ingests "episodes" and runs LLM-based entity extraction and resolution before writing triples to Neo4j. Agent Brain adds a Perception Gate and Deduplication Guard before typed storage. The lesson for mm: if encoding is just embed(text) → insert, it is behind the 2025-2026 frontier. An audit trail requires capturing why a memory was admitted, not only what it says.

Storage substrates. The three common substrates have distinct scaling profiles. A 2026 Zenodo benchmark reports vector stores remain fastest and most storage-efficient beyond 1M entries (~68 ms at 1M, 12.7 GB), knowledge graphs grow super-linearly (~84 ms, 18.4 GB) due to query planning, and attention-memory is most expensive at scale. This is a preprint, not peer-reviewed; treat numbers as indicative. Hybrid designs are the consensus: vector base + graph overlay + attention for recency. mm's module list (tiers, temporal ranking, graph-ish SOP matching) suggests a hybrid, but without code visibility I cannot confirm whether it runs SQLite+vector, Neo4j, or in-process indexes.

Retrieval and recency × salience. Generative Agents established the canonical scoring: recency (exponential decay), importance (LLM-rated at write time), relevance (cosine), normalized and weighted. A sharp critique argues write-time importance is a frozen prediction that cannot condition on the query, making it a bias rather than a prior; an ablation found a position-blind baseline beat a shipped blend carrying recency and importance at 15% each. This is directly relevant to mm's "confidence" and "temporal ranking" modules: if confidence is stamped at write time and never revised at read time, calibration failure is structurally likely. mm's FAIL calibration gate is consistent with this failure mode, though I cannot prove causation.

Consolidation and forgetting. Letta/MemGPT popularized sleep-time compute: asynchronous background agents reorganize memory between sessions. A-Mem's "memory evolution" lets new memories rewrite attributes of old ones—powerful but dangerous without versioning. Agent Brain reported a transparent 1.9pp regression when enabling its Dream Cycle consolidation pipeline; this is a useful counterexample to assuming consolidation always helps. Janitor-style deliberate forgetting needs provenance: deleting a memory without recording why it was deleted destroys the audit trail mm claims to prioritize.

2. How Memory Talks Back

I found no public system that implements confidence-calibrated proactive speech with real sending channels. mm's gated proposals without a sending channel are actually safer than most deployed systems, which either speak unconditionally or expose a raw send tool. The design question is what gate condition should be: a fixed confidence threshold is brittle; a calibrated probability that the proposal is wanted now is better, but requires decision-pair training data—which mm has zero of. Until those pairs exist, any gate is a prior, not a learned policy.

Silence should be the default. A memory system that surfaces something every time retrieval confidence exceeds 0.5 will interrupt constantly. The field lacks a standard "silence evaluation" metric; this is an open build opportunity.

3. Failure Modes, Security, and Testing

Injection and poisoning. Any write path that calls an LLM on user-controlled content is a poisoning surface. Graphiti's async pipeline runs entity extraction, contradiction detection, and community summarization—each an LLM call that can hallucinate a spurious entity or wrong merge, corrupting the graph persistently. mm's "immune write-defence" module is the right instinct; I cannot verify its coverage.

PII and secrets. The milepost project (a Claude Code diary, not a research system) implements a mechanical PreToolUse hook that blocks secret-shaped content from landing in the diary. This is a concrete, cheap pattern mm could adopt: regex/hook-based blocking at write time, not prompt-based "please summarize secrets."

Testing. mm's 829 tests and six red-team rounds are strong signals. The missing piece is decision-level evaluation: LongMemEval measures retrieval accuracy, not whether the ranked decision was correct or well-calibrated. Zero real production decision pairs means the calibration gate is being evaluated against synthetic distributions only.

4. Next Builds for mm (Proven vs Stub)

Proven in field, likely buildable quickly: write-time provenance records (Graphiti, Agent Brain); hook-based secret blocking (milepost); read-time importance re-scoring instead of frozen write-time scores.

Stub-level in field, high uncertainty: calibrated proactive gating (no public implementation with sending); consolidation that reliably improves rather than regresses (Agent Brain's regression is a warning); graph memory evolution without versioning (A-Mem exposes the risk).

Concrete next experiment: instrument one production decision pair per day for two weeks. Log the candidate set, the ranked choice, the confidence, and the human outcome. Even 14 pairs would tell you whether the underconfidence is structural (scores cluster high but wrong) or a threshold artifact.

Top 5 Findings

1. Write-time importance scores are structurally unable to condition on the query; an ablation showed a position-blind baseline beat a recency+importance blend. mm's calibration failure may share this root.

2. Vector stores scale better than graphs past 1M entries, but graphs provide auditability and relational reasoning.

3. Consolidation is not monotonically helpful: Agent Brain reported a 1.9pp regression from its Dream Cycle.

4. Mechanical secret blocking at write time (hook-based) is simpler and more reliable than prompt-based policies.

5. No public system implements a calibrated proactive speech gate with a real sending channel; mm's gated proposals are at the safer edge of current practice.

Top 3 Open Questions

1. What is the minimum viable decision-pair dataset size for calibrating a proactive gate? (No source gives a number; uncertain.)

2. Does mm's "immune write-defence" run at the hook layer or the prompt layer? (Unverifiable without code.)

3. Can memory evolution be made safe with append-only provenance, or does rewriting old attributes inherently destroy auditability? A-Mem raises the question but does not answer it.
