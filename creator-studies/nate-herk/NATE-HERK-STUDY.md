# Nate Herk — Playlists and Transcripts Study

Date: 28 October 2026. Research only. No video was downloaded, no paid or
private content was accessed, no account was signed into, and nothing was
sent or published.

## Method and tools

- `yt-dlp` 2026.10.26 (installed in a sandbox virtual environment;
  `yt-dlp --version` was checked first; the system Python refused a
  user-level install under PEP 668, so a virtual environment was used).
- Catalogue: `yt-dlp --flat-playlist` on the channel Videos tab
  (https://www.youtube.com/@nateherk/videos, 369 entries) and on each of
  the 18 playlists listed on the Playlists tab (741 memberships).
  De-duplicated by video ID. Flat-playlist entries carry no upload
  timestamp for this channel, so published dates are unavailable from
  this method (see the block record below).
- Transcripts were to be fetched with `yt-dlp --skip-download
  --write-subs --write-auto-subs --sub-langs en --sub-format vtt/best`
  with sleep intervals. That step was blocked (see below) and no
  transcript was fetched.
- Incident during the work: the sandbox `/tmp` directory was cleared
  mid-task, destroying the first scratch dumps and the first yt-dlp
  virtual environment, and losing the background full-metadata job.
  All work was redone with scratch kept inside this study directory.
  The catalogue itself survived because it had already been written
  under `~/workspace`.

## Exact counts

- Playlists enumerated: **18** (the channel's `playlist_count` field
  also returned 18).
- Videos tab entries: **369**.
- Playlist memberships enumerated: **741**.
- Unique public videos catalogued: **554** (union of the above).
  The earlier rough range "540–565 videos" is superseded by this
  enumerated count of 554.
- Videos with a duration in flat data: **510**. Without a duration:
  **44** (mostly Shorts entries whose flat records carry no duration).
- Total catalogued duration (510 videos): **582,909 seconds
  (~161.9 hours)**. Durations of 60 seconds or under: 29 videos;
  over 30 minutes: 53 videos. Longest: "Build & Sell with Claude Code
  (10+ Hour Course)", 36,006 seconds.
- Videos with no title in flat data: **1** (one Grok Bot playlist entry
  returned title `None`).
- Published dates available: **2 of 554** (from the two videos whose
  full metadata succeeded before the block; see below). All other
  published dates are recorded as null, not estimated.
- Transcripts fetched: **0 of the 20 planned**. Transcripts missing:
  all 20, because of the block below. No transcript was invented.

## Block record — YouTube bot check, fetching stopped

During full-metadata extraction (per-video, 50-video chunks, sleep
interval 1–3 seconds), YouTube returned, for 48 of 50 videos in the
first chunk:

> "Sign in to confirm you're not a bot. Use --cookies-from-browser or
> --cookies for the authentication."

Two videos in that chunk succeeded before the block took effect
(`4hKJ9X6rGFo`, `PYjbeY8sGLs` — their upload dates and descriptions
are the only full metadata in the catalogue). A single subtitle fetch
for the flagship voice-receptionist video (`y-cq_Qo4zVo`) failed with
the same error. Per the stop rules, all YouTube fetching stopped at
that point: no sign-in, no cookies, no workaround, no aggressive
retry, and no other route around the block was used. The consequence
is that this study is a catalogue-and-titles study, not a transcript
study. Every skill extraction below is labelled title-inferred and
unverified against a transcript.

## Addendum — live-browser transcript-panel read, 28 October 2026

After this study was written, the 8 flagship transcript panels were
read in a live browser task (00:40–01:24 IST, 44 minutes,
harness-measured), with no sign-in wall, bot check, download, or
account action. All 8 panels were FETCHED (read in full); the full
spoken text was NOT reproduced and NOT saved as a file, so no
verbatim transcript exists in this study. The status and
summary-level record is in
`transcripts/BROWSER-READ-2026-10-28.md`: broad topic and section
structure only, in paraphrase. For videos 1–8 below, the pattern is
therefore upgraded from title-only to panel-read summary level
only. Steps, settings, prompt wording, template content, and
failure handling are NOT established by that record. Transcripts
fetched as files remain 0 of 20. This addendum does not change the
catalogue counts or durations above.

Channel facts observed during the playlists-tab extraction, before the
block: channel "Nate Herk | AI Automation", channel ID
`UC2ojq-nuP8ceeHqiroeKhBA`, handle `@nateherk`, follower count
1,100,000 as returned. The channel description began: "I'm Nate Herk,
an AI educator featured in Forbes and Inc., and the Amazon bestselling
author of Becoming AI Native. I left Goldman Sachs to build an AI
consultancy, scaled it to $100K/month, and exited in December 2025. I
also founded AI Automation Society, a global community of 450,000+
members…" (truncated in the extraction output; the full description
file was lost in the `/tmp` clear and was not re-fetched).

## Per-playlist summary

Counts are playlist memberships as curated by the channel; playlists
overlap, and membership is not a complete topic index (for example,
the Voice Agents playlist holds 2 videos while 15 catalogued titles
mention voice/Vapi). Median durations are over videos with a duration.

| Playlist | Videos | Median duration (s) | Theme, from titles |
|---|---|---|---|
| AI News | 2 | 626 | Short AI-news roundups. |
| Grok Bot | 5 | 1,292 | Grok Bot concepts, inbox use, build-and-sell course. |
| Hermes Agent | 2 | 3,503 | Personal Hermes assistant setup and course. |
| Codex | 21 | 1,234 | Codex mastery, skills, build-and-sell courses. |
| Antigravity | 1 | 873 | One video on Nano Banana 2 + Antigravity image tools. |
| Claude Code Shorts | 18 | 122 | Short Claude Code tips and demos. |
| The AI Automation Society Podcast | 47 | 1,004 | Interviews and tests (models, skills, agencies). |
| Claude Code | 117 | 992 | The largest playlist: Claude Code skills, tests, courses. |
| Voice Agents | 2 | 2,515 | Voice-agent beginner guide; lead-calling voice agent. |
| AI Business Shorts | 30 | n/a (no durations) | Short business/monetisation takes. |
| Monetizing AI Automation | 38 | 1,083 | Selling workflows, retainers, one-person businesses. |
| AI Shorts | 15 | 53 | Short demos and takes, many Claude/Blender. |
| n8n Shorts | 112 | 93 | Short n8n agent demos and claims. |
| n8n Tips & Tricks | 81 | 929 | n8n techniques, RAG, migration, Claude Code for n8n. |
| AI Masterclasses | 54 | 1,482 | Long courses (Claude Code, n8n agents, Codex, SaaS). |
| No-Code AI Automations | 39 | 1,080 | No-code beginner guides: inbox, RAG, swarms. |
| n8n Workflow Tutorials | 86 | 1,116 | Step-by-step n8n builds, many with free templates. |
| AI Agent Tutorials | 71 | 1,156 | Step-by-step agent builds, many with free templates. |

Title keywords across all 554 titles: "agent" 281, "n8n" 260,
"Claude Code" 81, "RAG" 27, "beginner" 26, "voice" 20, "MCP" 14,
"Codex" 12, "course" 12, "Grok" 9, "Vapi" 6. The channel's centre of
gravity, by title, is no-code n8n agent builds, with Claude Code as
the second pole.

## Flagship videos — title-inferred skill extraction (UNVERIFIED)

Transcript status for every video below: **NOT FETCHED — blocked**
(see block record). No transcript was auto-generated or manual in
hand, so the "transcript type" for each is: unknown. The patterns
below are inferred from the video title and playlist membership only.
Where a title does not state a step, the entry says so. Nothing here
is presented as heard or read in the video.

1. **Voice receptionist** — "I Built an AI Voice Receptionist with
   Vapi and n8n MCP (free template)",
   https://www.youtube.com/watch?v=y-cq_Qo4zVo, 2,061 s, playlist:
   AI Agent Tutorials. Title-inferred pattern: Vapi voice front end;
   n8n back end exposed through MCP; a free template is offered.
   Trigger, lookup/booking steps, failure handling, and human-review
   point: not stated in the title; unverified.
2. **Client onboarding** — "How to Build a Client Onboarding AI Agent
   with n8n (Step-by-Step Tutorial, No Code)",
   https://www.youtube.com/watch?v=Wpwbm3zCymk, 1,260 s. Title-inferred
   pattern: n8n onboarding agent, step-by-step, no code. Steps,
   data sources, and review point: not stated in the title; unverified.
3. **Personal assistant** — "How to Build a Personal Assistant AI
   Agent in n8n (Step-by-Step, No Code)",
   https://www.youtube.com/watch?v=ZP4fjVWKt2w, 3,992 s, playlists:
   AI Agent Tutorials, n8n Workflow Tutorials, No-Code AI Automations.
   Whether Telegram is the front end: not stated in the title;
   unverified. Title-inferred pattern: one personal-assistant agent
   in n8n, no code.
4. **Agent that builds teams** — "I Built an AI Agent that Builds
   Teams of Agents in n8n (free template)",
   https://www.youtube.com/watch?v=Ik8OHT3w4pE, 1,198 s. Title-inferred
   pattern: a meta-agent that generates a team of specialised
   sub-agents; a free template is offered. Team structure and
   debugging: not stated in the title; unverified.
5. **Lead nurturing** — "Step By Step: Automating Lead Nurturing with
   No Code in n8n",
   https://www.youtube.com/watch?v=fWtXJswvUcA, 1,391 s. Title-inferred
   pattern: no-code lead-nurture automation. Trigger, channels, and
   personalisation steps: not stated in the title; unverified. This
   was the only title matching lead nurturing in the catalogue.
6. **Email agent** — "How to Create an AI Email Agent with n8n (No
   Code, Step-by-Step Tutorial)",
   https://www.youtube.com/watch?v=YFrej2oSldo. Title-inferred pattern:
   n8n email agent, step-by-step. Whether it drafts for review or
   sends, and its policy/knowledge source: not stated in the title;
   unverified.
7. **Inbox agent** — "From Zero to Inbox Agent (Full Beginner's
   Course, No-Code)",
   https://www.youtube.com/watch?v=HN0oWxbF2bM, 2,253 s, playlists:
   n8n Workflow Tutorials, No-Code AI Automations, AI Agent Tutorials.
   Title-inferred pattern: a full beginner course building an inbox
   agent. Classification, labelling, and review steps: not stated in
   the title; unverified.
8. **Claude Code skills / 95% rule** — "Master 95% of Claude Code
   Skills in 28 Minutes",
   https://www.youtube.com/watch?v=zKBPwDpBfhs, 1,639 s. Title-inferred
   pattern: Claude Code skills taught to a stated 95% coverage claim
   in 28 minutes. Any "ask until 95% confident" prompting rule: not
   stated in the title; unverified. No title in the catalogue contains
   "95%" with "confidence" or "prompting".
9. **Partner model** — "The 3-Step System Behind My $20K/Month AI
   Agency Retainers",
   https://www.youtube.com/watch?v=DoHPZf7jEQ4, 1,715 s, playlist:
   Monetizing AI Automation. Title-inferred pattern: a 3-step system
   behind retainer revenue; the dollar figure is the creator's claim
   in the title, not a verified result. The three steps: not stated
   in the title; unverified. No catalogue title names "Becoming AI
   Native" or a retainer template.
10. **n8n beginner course** — "n8n Masterclass: Build AI Agents &
    Automate Workflows (Beginner to Pro)",
    https://www.youtube.com/watch?v=ZHH3sr234zY, 5,503 s. Title-inferred
    pattern: beginner-to-pro n8n masterclass. Curriculum: not stated
    in the title; unverified.
11. **RAG / retrieval** — "From Zero to RAG Agent: Full Beginner's
    Course (no code)",
    https://www.youtube.com/watch?v=cCD303XsUjI, 1,360 s.
    Title-inferred pattern: a beginner RAG-agent course. Vector
    store, chunking, and evaluation: not stated in the title;
    unverified.
12. **MCP pattern** — "n8n's Native MCP Integration (without the
    hype)", https://www.youtube.com/watch?v=VTEg8uJ4yxo, 929 s.
    Title-inferred pattern: n8n's native MCP integration explained.
    Tool schemas and permission behaviour: not stated in the title;
    unverified.
13. **Personal assistant 2.0** — "AI Personal Assistant 2.0 | This
    Agent Calls Other Agents (No Code) in n8n",
    https://www.youtube.com/watch?v=9G-5SiShBKM, 1,603 s.
    Title-inferred pattern: an assistant agent that calls other
    agents as tools. Which sub-agents and how failures surface: not
    stated in the title; unverified.
14. **Agent swarm** — "Building an AI Agent Swarm in n8n Just Got So
    Easy", https://www.youtube.com/watch?v=vpyllOeLhs4, 1,539 s.
    Title-inferred pattern: a multi-agent swarm in n8n.
    Orchestration and logging: not stated in the title; unverified.
15. **Voice agents beginner guide** — "Learn Voice Agents Now, Thank
    Me Later (Full Beginner's Guide)",
    https://www.youtube.com/watch?v=zWLZ3bVVwD8, 2,515 s, playlist:
    Voice Agents. Title-inferred pattern: a full beginner guide to
    voice agents. Platform and steps: not stated in the title;
    unverified.

### Sampled videos (cap-limited: 5 of the planned 2-per-playlist sample)

16. **Codex** — "Master 97% of Codex in 1 Hour (full course)",
    https://www.youtube.com/watch?v=3TdD8Qv5Tk8, 3,659 s.
17. **Grok Bot** — "Every Grok Bot Concept Explained for Normal
    People", https://www.youtube.com/watch?v=NyfYxpXiw_0, 1,292 s.
18. **n8n Tips & Tricks** — "3 AI Workflows Step-by-Step
    (Beginner's Guide to n8n)",
    https://www.youtube.com/watch?v=06Beyp_iDL0, 2,663 s.
19. **AI Masterclasses** — "n8n AI Agent Masterclass | AI Nodes Made
    Simple", https://www.youtube.com/watch?v=EzS2PIjyeQQ, 3,050 s.
20. **Podcast playlist** — "How to Sell Claude Workflows (Without
    Starting an Agency)",
    https://www.youtube.com/watch?v=zpS6JGJNaGg, 485 s.

No transcripts were fetched for these either. The remaining playlists
(AI News, Hermes Agent, Antigravity, Claude Code Shorts, AI Business
Shorts, AI Shorts, n8n Shorts) received no transcript sample: the
20-transcript cap was reached by the flagship list first, and then
the block stopped all fetching. Their titles are in the catalogue.

## Single most useful workflow pattern (title-inferred, unverified)

The voice-receptionist pattern: a voice front end (Vapi) calling an
n8n back end exposed as MCP tools, with lookup, availability,
booking, and handoff steps and a free template. It is the most
reusable pattern in the catalogue because it is the one flagship
whose title names both sides of the integration (front end + back
end + MCP) and a reusable artefact (template). It remains unverified
against any transcript: the steps, failure handling, and human-review
point are not established by this study and must not be treated as
known until a transcript or the video itself is studied from a route
that is not blocked.

## Honest limits

- Transcripts were not saved as files; the 8 flagship transcript
  panels were read in a live browser on 28 October 2026 (see
  `transcripts/BROWSER-READ-2026-10-28.md`) at summary level only,
  with no verbatim text reproduced or saved. Videos were not
  watched end to end. No auto-caption error assessment is possible
  because no captions were obtained as files.
- Skill extraction above rests on titles and playlist membership
  only. Titles are marketing text; they may overstate coverage
  ("95%", "97%", revenue figures) and omit failure handling.
- Published dates are null for 552 of 554 videos. No date-based
  claim (growth over time, recency of a pattern) is made.
- Durations are flat-playlist values for 510 videos; 44 are missing.
  View counts were removed from the catalogue because flat-playlist
  values were inconsistent and unvalidated.
- Paid content (Skool community, courses, template packs behind
  paywalls) and private content were not accessed, and no template
  was downloaded.
- The catalogue is the union of the Videos tab and the 18 listed
  playlists. A video in neither (unlisted in playlists and beyond
  the Videos tab pagination) would be missing; the count 554 is the
  enumerated count by this method, not a claim about YouTube's
  internal total.

## Files

- `catalogue.json` — full catalogue (554 videos; titles, URLs,
  durations where available, published dates where available,
  playlist memberships, block record).
- `catalogue.csv` — same catalogue in CSV form.
- `transcripts/` — no transcript files; see
  `transcripts/NOT-FETCHED.md` (yt-dlp block) and
  `transcripts/BROWSER-READ-2026-10-28.md` (live-browser panel
  read, 8 of 8 FETCHED, full text not saved).
- `_scratch/` — chunk URL lists and the 2-record metadata fragment
  that survived the block; the yt-dlp virtual environment was
  removed after use.
