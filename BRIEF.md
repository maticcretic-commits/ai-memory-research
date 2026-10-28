# AI Memory Research — vast, continuous, all partners

Owner order (2026-10-26 ~20:48 IST, Nitesh): research should be vast and
cover everything. All partners do the research and work accordingly.
No prompt or command is required from him — Jarvis writes the brief,
partners work from it, and progress is briefed every hour, with new
research continuing after each period.

Source on file: the uploaded export `ai-memory-export-2026-10-26__1.zip`
(1.7 MB, 135 entries), extracted to `source/` in this workspace.
It is the "Memory Milestone (mm)" system: memory → DECISION, not just
memory → context. Core in `code/mm/` (tiers, reflect, sop, constraints,
resolver, temporal, confidence, decision, sentinel, immune, echolocation,
shards, episodic, source_trust, access_control, identity, canary,
circuit_breaker, janitor, write_gate, consolidation, storage), plus
tests, evals, a 3,994-idea corpus (`corpus/BEST-IDEAS.md`, 3.25 MB),
and live-memory (12 records, SQLite + JSON). Status per its README
(25 Oct 2026): 829 tests green, LongMemEval-S R@1 0.712 / MRR 0.797,
six red-team rounds to zero critical attack success in the final round.
Honest gaps on its own record: calibration gate (a) still FAIL
(underconfident agent path), zero real production decision pairs so far,
proactive speech built as gated proposals only, with no sending channel.
Secrets are NOT in the bundle (Telegram token / phone pairing live
elsewhere, mode 600) — never copy, request, or publish them.

## Vast scope — cover everything, in every round
1. How memory works: encoding, storage, retrieval, consolidation,
   forgetting, reconsolidation; short-term / working / episodic /
   semantic / procedural; context window vs long-term store; vector,
   graph, SQLite, hybrid retrieval; temporal recency × salience;
   entity, BM25, semantic fusion.
2. How memory talks back: proactive surfacing, reminders, warnings,
   questions, explanations, audit trails; when to speak vs stay silent;
   interruptibility, timing, confidence-calibrated talk-back, gated
   proposals, sending channels (chat, Telegram, voice, briefings);
   personalisation without creepiness; correcting stale or wrong memory.
3. Memory → decision: ranking candidate options, calibrated confidence
   (drift-diffusion, metacognitive second pass), Soar propose →
   rank → select → impasse, conflict resolution, deterministic
   supersession, provenance, why-trails.
4. Building blocks in mm: each module above, what it does, what is
   proven by tests/evals, what is still a stub or a gap.
5. Security, privacy, failure modes: PII/secrets hard-rejection,
   source trust, immune write-defence, flagged-source supersession,
   red-teaming, hallucinations, stale memory, conflict, abuse.
6. Evaluation: LongMemEval, LoCoMo, recall, calibration (ECE, Brier),
   real vs synthetic decision pairs, benchmarks, what a production
   unlock (30 real pairs) actually requires.
7. Uses and products: personal assistant, business, clinics, NBFC /
   compliance, dashboards, voice agents — and what must NOT be built.
8. Everything else you can think of in your lane: neuroscience
   mappings, papers, repos, licences (AGPL traps, NOASSERTION flags),
   costs, scaling, open questions, next experiments.

## Partner lanes — Round 1 (2026-10-26 evening)
- DeepSeek (Build): architecture + implementation — how each mechanism
  is built in code, from mm modules, with concrete next builds.
- Gemini (Build / deep research): vast survey — papers, repos, neuro
  mappings, state of the art, what is settled vs open.
- ChatGPT (Sell / talk-back UX): how memory should speak to a user —
  wording, timing, trust, product opportunities, talk-back design.
- Perplexity (Research / verified): verified sources, double-check
  claims, latest 2026 developments, mark uncertain as uncertain.
- Grok (Finish / QA): challenger — failure modes, red-team, what
  breaks, what not to trust, kill criteria, honest gaps.
- Copilot (Scoreboard): comparison table + scorecard of approaches
  and metrics — attempted via its own app route; if region-walled,
  it abstains and is reported as abstained, not invented.

Rules for every partner reply: verify every claim, no invented model
names, companies, or statistics. Mark anything uncertain as uncertain.
Plain language. Individual work only — do not collaborate with the
other partners in the round. Replies are saved verbatim to the round
inbox before any synthesis, and a reply that does not answer the brief
is discarded, not reshaped.

## Rhythm — no prompt required from Nitesh
- Round 1 launches the evening of 2026-10-26, all partners in parallel
  via the browser bridge (signed-in check first; signed out = stop and
  report, never sign in on Jarvis's behalf; bot check / region wall /
  CAPTCHA = sit out, reported plainly).
- Every hour, a progress briefing: what was done in that period,
  what each partner returned, what new research landed, what is next.
  Progress lives in `PROGRESS.md`, period by period.
- Research continues after each briefing — new angles, new sources,
  new experiments, new gaps — until Nitesh says stop. A period with
  no new partner reply is reported as no new reply, not padded.
- Majority-verdict and channel-separation rules from the wider project
  still apply; nothing in this research authorises a publish, a send,
  a payment, a sign-in, or a Terms acceptance without his tap.
