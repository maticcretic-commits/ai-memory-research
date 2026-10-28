# Study: OmniDimension as a voice talk-back channel for AI memory (2026-10-27)

Added at Nitesh's order on 2026-10-27 ("Use this for ai memory", replying to the installed OmniDimension SDK). This is a DESIGN/STUDY note only. Status, verified the same day:

- The Python SDK is installed locally (`omnidimension` 0.6.0, venv `~/workspace/omnidim/.venv`). Its method surface below was verified by local introspection only — no network call was made.
- NO account has been created, NO API key has been set or collected, NO memory content has been sent anywhere, NO call has been made, and NO signup or payment has happened. Nothing from the mm system or the live-memory records has left this machine.
- Anything that would send memory content to OmniDimension, make a call, or spend credit needs Nitesh's explicit word first, plus the privacy review in the risks section below.

## What OmniDimension is (from its own docs, verified 2026-10-27)

A cloud platform to "build, test, deploy, and monitor conversational AI voice agents with no-code tools and APIs". Voice phone calls, web chat, WhatsApp, and SIP across 100+ integrations (homepage). Its docs list: agent configuration (sections, instructions, welcome message, conversational flow), 1000+ voices across 90+ languages, a numbers shop covering 70+ countries, a knowledge base for grounding answers in the user's own documents, bulk outbound calls, SIP trunking (Twilio, RingCentral, Vonage, Exotel imports), WhatsApp, and integrations (HubSpot, Salesforce, Slack, Cal.com, Google Calendar, Zapier, custom APIs). An API key comes from the API management dashboard and is set as `OMNIDIM_API_KEY`.

## Verified SDK surface (installed 0.6.0, local introspection, dummy key, zero network calls)

`Client(api_key, base_url)` — basic SDK needs only `requests`; the `[mcp]` extra adds FastAPI/uvicorn/fastmcp/Pydantic. MIT licence per package metadata. Sub-objects and methods:

- `agent`: create / get / list / update / delete; versions (save, list, diff, restore, rename, delete); post-call actions (add, list, update, delete).
- `call`: `dispatch_call`, `get_call_log`, `get_call_logs`.
- `knowledge_base`: create / list / delete, attach / detach, `can_upload`.
- `phone_number`: list / search / purchase / release, attach / detach, import from Twilio / SIP / Exotel.
- `account`: `balance` (the SDK README describes this as checking remaining credit, the minutes it buys, and concurrency headroom before dialling).
- `simulation`: create / get / list / update / delete, start / stop, `enhance_prompt`.
- `voices`: list cloned voices, create / get / update / delete cloned voice, samples.
- `providers`: list LLMs, STT, TTS, voices; `get_voice`, `list_all`.
- `bulk_call`, `integrations`, `workflow`, `reseller`, plus raw `get`/`post`/`put`/`patch`/`delete`/`request` HTTP verbs.

Caution — provenance of this SDK: the installed package metadata names home-page `github.com/kevin-omnidim/omnidim-sdk` and author `kevin@omnidim.io`, while the docs quickstart leads with the TypeScript SDK (`@omnidim-ai/sdk`) and the PyPI listing seen during research was version 0.2.19. The installed 0.6.0 may be a newer or differently-maintained build than the docs describe. Verify which SDK build is official before any production use; do not treat method names above as the documented API until they are confirmed against the live API reference with a real key.

## Why it fits the mm talk-back gap — and where it does not

mm's own record (25 Oct 2026): proactive speech exists only as gated proposals, with NO sending channel; zero real production decision pairs; calibration gate (a) still FAIL. The Round 1–7 programme locked, as rules: talk-back as its own layer, silence as a measured success, confidence per claim with no permission from high confidence, four separate states (proposal, approval, action, verified outcome), and fail-closed defaults.

OmniDimension maps onto that gap in these specific places:

1. **A sending channel, at last — but only under the gate.** `call.dispatch_call` is the outbound voice action. It must sit behind the existing proposal → approval → action sequence, never be driven directly by a memory hit. A memory record proposing a call is not permission to dial.
2. **Simulation before real pairs.** `simulation` (create/start/stop) matches the programme's safety-first order: synthetic rehearsal first, real pairs last. Any voice talk-back design should be simulation-tested with synthetic content before a single real memory record is spoken.
3. **Verified outcome.** `get_call_log` / `get_call_logs` give a post-action record to close the loop — proposal, approval, action, verified outcome — instead of assuming a dialled call landed.
4. **Cost/concurrency pre-check.** `account.balance` before dispatch mirrors the predeclared-value / cost-ceiling rule: check credit and headroom first, refuse (silence) when the budget or the value declaration is unresolved.
5. **Versioned agent behaviour.** Agent versions (save/diff/restore) are the closest analogue to mm's versioned supersession: when the agent's instructions change, the old version stays addressable and diffable, never silently overwritten.
6. **Grounding is the danger, not the feature.** `knowledge_base.attach` would let an agent answer from uploaded documents. Uploading memory records there hands private, possibly stale or poisoned content to a third-party service and lets it shape answers. That is both a privacy disclosure and a new poisoning surface. No raw memory record, live-memory row, or case material goes into a knowledge base without an explicit, per-upload approval and a redaction/provenance review.

## Open questions (unsettled — nothing below is claimed)

- Account, API key, pricing/credits, and phone-number acquisition (purchase vs Exotel import for India calling): not checked; all need Nitesh's dashboard steps.
- Data handling: retention, deletion, and processing terms for call audio/transcripts and knowledge-base uploads were NOT checked in the docs. Verify before any personal or case data flows.
- Hindi/Hinglish voice quality: 90+ languages are claimed; no Hindi voice was tested, and no call was placed.
- Per-decision driving: whether mm code can drive one decision → one gated call through the SDK, or whether agents must be configured in the dashboard first, is untested without a key.
- Official SDK status (see caution above).

## Suggested next steps (NOT done — awaiting Nitesh's word)

1. Partner brief: one lane asking each partner what a voice talk-back channel must record (proposal, approval, dispatch, call log, cost check) to stay auditable under the Round 5–7 gates, and what it must never do (auto-dial, KB upload of raw records, unlogged calls).
2. Key setup via the secure flow, then a read-only verification only: list agents + check balance. No calls, no uploads.
3. Simulation-only test with synthetic content (no real memory data) once a key exists, measuring silence/interruption behaviour before any real pair.

If Nitesh picks none of these, this note stays as study material only, and no OmniDimension use happens.
