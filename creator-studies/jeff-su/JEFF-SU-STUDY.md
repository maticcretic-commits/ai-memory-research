# Jeff Su — Playlists and Transcripts Study

Date: 28 October 2026. Research only. No video was downloaded, no paid
or private content was accessed, no account was signed into, and
nothing was sent or published.

## Method and tools

- `yt-dlp` 2026.10.26, installed in a sandbox virtual environment
  (`/tmp/yt-dlp-venv-jeff`); `yt-dlp --version` was checked first.
  The system Python refused a user-level install under PEP 668, so a
  virtual environment was used. The venv was left in /tmp and is
  ephemeral; the study files below are the durable record.
- Catalogue: `yt-dlp --flat-playlist` on the channel Videos tab
  (https://www.youtube.com/@JeffSu/videos, 199 entries) and on each of
  the 13 playlists listed on the Playlists tab (268 memberships).
  De-duplicated by video ID. Flat-playlist entries carry no upload
  timestamp for this channel, so published dates are unavailable from
  this method and are recorded as unknown, not estimated. Flat data
  also carries no per-video descriptions, so no description was read.
- Transcripts were to be fetched with `yt-dlp --skip-download
  --write-subs --write-auto-subs --sub-langs en` with sleep intervals.
  That step was blocked (see below) and no transcript was fetched.

## Exact counts

- Playlists enumerated: **13** (the channel's `playlist_count` field
  also returned 13).
- Videos tab entries: **199**.
- Playlist memberships enumerated: **268**.
- Unique public videos catalogued: **204** (union of the above).
  Earlier research gave only a subscriber range for this channel
  (roughly 1.2–1.9 million across sources of different dates); no
  earlier video count was reused. The flat-data follower count
  returned during enumeration was 1,940,000; it is reported as
  returned, not as a verified live count.
- Channel as returned: Jeff Su, `UCwAnu01qlnVg1Ai2AbtTMaA`, @JeffSu.
- Videos with a duration in flat data: **201**. Without a duration:
  **3** (all in the "Increase Your Productivity at Work" playlist).
- Total catalogued duration (201 videos): **112,926 seconds
  (~31.4 hours)**. No video is 60 seconds or under in flat data; none
  exceeds 30 minutes. Longest: "My Simple Claude Cowork System (for
  normal people)", 1,278 seconds (21 minutes 18 seconds).
- Videos with no title in flat data: **3** (IDs 9ql1CQfxWxQ,
  al1QXFQjq1s, O8TzmWQTLx4). Their titles are recorded as unknown,
  not guessed.
- Published dates available: **0 of 204**.
- Transcripts fetched: **0 of the 20 planned**. Transcripts missing:
  all 20, because of the block below. No transcript was invented.

## Block record — YouTube bot check, fetching stopped

A single subtitle-only fetch attempt for the prompts-database video
(`Oo_GGWV9Hys`) returned HTTP Error 429 (Too Many Requests) and:

> "Sign in to confirm you're not a bot. Use --cookies-from-browser or
> --cookies for the authentication."

Per the stop rules, all per-video fetching stopped at that point: no
sign-in, no cookies, no workaround, no aggressive retry, and no other
route around the block was used. The consequence is that this study
is a catalogue-and-titles study, not a transcript study. Every skill
extraction below is labelled title-inferred and unverified against a
transcript or description.

## Per-playlist summaries

| Playlist | Entries | Known durations | Total seconds |
|---|---|---|---|
| Claude Cowork Tutorials (by Jeff Su) | 4 | 4 | 4,360 |
| Notion for Productivity | 18 | 18 | 11,475 |
| Hidden Gems of Google Workspace | 18 | 18 | 9,259 |
| The AI Edge: Work Smarter, Not Harder | 47 | 47 | 35,686 |
| MacBook Tips & Tricks | 11 | 11 | 5,944 |
| Think Outside the Box | 5 | 5 | 2,410 |
| Succeed in the Workplace | 27 | 27 | 12,597 |
| Be Productive at Life | 31 | 31 | 17,399 |
| LinkedIn Tips & Tricks | 10 | 10 | 4,622 |
| Common Interview Questions and Answers | 18 | 18 | 7,292 |
| the vlog | 10 | 10 | 5,875 |
| Increase Your Productivity at Work | 48 | 45 | 24,849 |
| How to Land Job Interviews | 21 | 21 | 10,324 |

Themes, from playlist names and member titles only: the largest
playlists are AI-at-work tutorials ("The AI Edge", 47) and general
productivity ("Increase Your Productivity at Work", 48). Career and
interview content is a second large block (three playlists, 66
memberships). Notion and Google Workspace each have a dedicated
playlist of 18. A small, recent Claude Cowork playlist (4 videos)
sits alongside the AI Edge material.

## Flagship videos — title identification only

Transcript type for every video below: **none — NOT FETCHED**.
"Found" means a title match in the catalogue; it establishes nothing
about the video's contents beyond its title.

### Found by title

1. **Prompts database in Notion** — "How to Build a Prompts Database
   in Notion (template included)!"
   https://www.youtube.com/watch?v=Oo_GGWV9Hys
   Title-inferred pattern only: a Notion database of prompts with a
   template included. The properties (type, use case, output format,
   app, example output) are from the earlier dossier's web research,
   not from this video. Unverified against a transcript.
2. **Productivity system** — "My Simple Productivity System (for
   normal people)!" https://www.youtube.com/watch?v=7M6bIeVbCqA and
   "The Productivity System I Taught to 6,642 Googlers"
   https://www.youtube.com/watch?v=oO9GLC2iKy8
   Title-inferred pattern only: a personal productivity system taught
   to Googlers. Whether either video teaches the CORE
   (Capture–Organise–Review–Engage) steps is unverified.
3. **Google Workspace + Gemini** — "Master 85% of Google Gemini in 12
   Minutes" https://www.youtube.com/watch?v=Uy6LcpyGj7w, in the
   "Hidden Gems of Google Workspace" playlist alongside Gmail, Docs,
   Sheets, Calendar, and Meet tip videos.
   Title-inferred pattern only: a compressed Gemini tutorial. Which
   Workspace apps are covered, and whether emails are drafted in the
   user's own voice, is unverified.
4. **Notion organisation** — "How I Organize My Life | Notion Tour
   2026" https://www.youtube.com/watch?v=_RTqbo5ZZ2k and "Master 80%
   of Notion with this ONE Feature"
   https://www.youtube.com/watch?v=4Fu23_l9F_o
   Title-inferred pattern only: a Notion tour and a single-feature
   tutorial. Neither title names a Command Center, and no Command
   Center video was found by title.

### Not found by exact title (recorded, not assumed)

- **Conventions file / rulebook.** No catalogue title contains
  "convention", "rulebook", or "conventions file". Closest titles are
  the Notion tour and organisation videos above. Unverified whether
  any video teaches it.
- **Master prompt + style guide.** No title contains "master prompt"
  or "style guide". Closest: "Master the Perfect ChatGPT Prompt
  Formula (in just 8 minutes)!"
  https://www.youtube.com/watch?v=jC4v5AS4RIM — a prompt-formula
  video, not established as a master-prompt or style-guide video.
- **Decision framework for new tools.** No title contains "decision
  framework" or names a tool-evaluation test. Unverified whether any
  video teaches it.
- **Notion Command Center.** No title contains "Command Center".
- **"10 ChatGPT Life Hacks".** No title matches. Closest: "4 ChatGPT
  Hacks that Cut My Workload in Half"
  https://www.youtube.com/watch?v=6hRO1q8vv60, "5 Ways I Actually Use
  ChatGPT at Work!" https://www.youtube.com/watch?v=EDkaQj7K5_c, and
  "Top 8 ChatGPT Productivity Tips for Work!"
  https://www.youtube.com/watch?v=Q07rFZtc2Ao.

## Skill extraction — title-inferred only

Nothing in this section was read from a transcript or description.
Each item is what the title alone establishes, plus what it does not.

- **Prompts database.** Title establishes: a Notion prompts database
  exists as a taught pattern, with a template. Not established: the
  database properties, triage flow, or pinning behaviour.
- **Productivity system.** Title establishes: a simple system for
  normal people, and a system taught to 6,642 Googlers. Not
  established: the CORE steps, review cadence, or tooling.
- **Workspace + Gemini.** Titles establish: compressed Gemini
  tutorials and per-app Workspace tip videos. Not established: any
  end-to-end workflow (transcript to action items, email drafting,
  formula writing).
- **Notion organisation.** Titles establish: tours, templates, and
  single-feature mastery. Not established: a Command Center layout
  or a conventions file.
- **ChatGPT at work.** Titles establish: short hack/tip videos built
  on workplace use. Not established: the "10 Life Hacks" video or
  its corporate use cases.

## Single most useful workflow pattern

The prompts-database pattern — a reusable Notion database of prompts
with a template included — is the most directly reusable pattern in
the catalogue, because its title names both the artefact (database)
and the reusable form (template). It is **title-inferred and
unverified**: its fields, triage flow, and behaviour are not
established by this study and must not be treated as known until a
transcript or the video is studied through an unblocked route. It
also matches prototype J2 (prompts database) already built in Phase 1
on synthetic data only; this study adds no evidence to that
prototype.

## Honest limits

- Transcripts were not read; videos were not watched end to end.
- No description was read (flat data carries none per video).
- Auto-caption accuracy is not assessable: no caption was obtained.
- Paid courses, private communities, template packs, and the
  Systems Academy site were not accessed.
- Subscriber and view figures are not verified by this study.
- Three titles and three durations are missing from flat data and
  are recorded as unknown.
