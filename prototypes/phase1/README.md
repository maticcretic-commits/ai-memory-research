# Phase 1 prototypes — Batch 1

Separate harness beside the mm code. No file under
`source/ai-memory-export-2026-10-26/code/mm/` was edited. Stdlib only.
Synthetic data only. No network, no accounts, no sending.

## Batch 1 (27 October 2026)

1. **conventions.py** (Jeff Su J3) — frozen, hashed conventions document;
   `check()` reports violations, never rewrites output. Frozen hash is
   verified with `freeze()` / `verify_frozen()`.
2. **prompts_db.py** (Jeff Su J2) — versioned prompt library. Records
   are sealed; corrections arrive as new versions with a supersedes link.
   Exact duplicates are not new versions. Secret content and missing
   fields are rejected.
3. **inbox_classifier.py** (Nate Herk N7) — rule-based labelling of
   synthetic messages. Actions are only `label_only` and
   `draft_for_review`. Ties and empty signal go to review. There is no
   send path.

## Run

```sh
cd ~/workspace/ai-memory-research/prototypes/phase1
python3 -m unittest discover -s tests -v
```

Tests were written before the implementations: the first run failed
with 14 errors (modules missing). The second run, after implementation,
must pass all 14 tests. Results are recorded in RUN-LOG.md.

## Batch 2 (28 October 2026)

4. **workflow_graph.py** (Nate Herk N1) — steps with explicit
   dependencies, topological order, `$step_id` outputs. Cycles, missing
   dependencies, unknown tools, and step errors fail closed before or
   during the run, with the log preserved.
5. **subagents.py** (Nate Herk N2) — sub-agents as tools with an allowed
   list and a step limit. Outward tools are proposed, never executed,
   and return `needs_approval`.
6. **tool_registry.py** (Nate Herk N3, MCP pattern) — schema and
   permission checked before any call, every attempt audited, outward
   tools require the explicit approval value. `list_tools()` exposes
   schemas only, never functions.

Batch 2 tests were written first (16 tests, all failing for missing
modules), then implemented. Full suite: 30 tests passing.

## Batch 3 (28 October 2026)

7. **retrieval.py** (Nate Herk N6) — token-overlap retrieval over a
   synthetic corpus, Jaccard scores surfaced on every result, never
   used as permission. Empty queries rejected; the corpus is never
   mutated.
8. **clarifying_loop.py** (Nate Herk N8) — the 95% loop. Proceed only
   at confidence 0.95 or above with no missing fields; one question
   per missing field; three questions unresolved escalates to a human.
9. **storyboard.py** (Sirio Berati S1–S3) — text-only storyboard spec
   with a credits block. Every scene names a source and a licence;
   captions and total duration capped. No image or video is generated.
10. **core_workflow.py** (Jeff Su J1) — Capture, Organise, Review,
    Engage. Low confidence goes to a review queue and engage refuses
    it; engage produces a draft only.
11. **master_prompt.py** (Jeff Su J4) — one prompt from a frozen
    template, pinned to the frozen conventions hash. A mismatch or a
    missing slot is rejected; no unfilled placeholder may remain.

Batch 3 tests were written first (23 tests, all failing for missing
modules), then implemented. Full suite: 53 tests passing.

## Batch 4 (28 October 2026) — Phase 1 complete

12. **workspace_adapters.py** (Jeff Su J6) — synthetic workspace
    adapters. No credentials, no network, no real account. Fetch
    returns copies of synthetic items; every output is a draft only.
13. **brand_rulebook.py** (Sirio Berati, brand rulebook) — frozen,
    hashed rulebook. Credits in a frame, a forbidden claim, or an
    off-palette colour is a violation.
14. **character_consistency.py** (Sirio Berati, hard problem) — a
    check, not a solution. A depiction must match the sheet's
    reference id and overlap its description by at least half its
    tokens; a missing reference fails closed. The spec states plainly
    that consistency is not solved and is unverified on real
    depictions.

Batch 4 tests were written first (15 tests, all failing for missing
modules), then implemented. Full suite: 68 tests passing. Phase 1 is
complete: all prototype groups in the plan are built — Jeff Su J1–J4
and J6, Nate Herk N1–N3 and N6–N8, Sirio Berati S1–S3 plus the brand
rulebook and character-consistency spec.

## Governance

- Every fixture is labelled synthetic. No real email, prompt, task, or
  person is represented.
- Confidence is surfaced, never used as permission. Nothing here gates
  a real decision, and no calibration claim is made.
- The next batches (workflow graph, sub-agents as tools, MCP registry,
  retrieval over a synthetic corpus, visual storyboard spec) follow the
  same rule: frozen spec, synthetic fixtures, tests first, run log.
  Voice calls, live scraping, and real pairs stay blocked per
  CREATOR-SKILLS-IMPLEMENTATION.md Part C.
