# Sirio Berati — Playlists and Transcripts Study

Date: 28 October 2026. Research only. No video was downloaded, no paid
or private content was accessed, no account was signed into, and
nothing was sent or published.

## Channel identity — as verified

The reported handles were @heysirio / @SirioBerati. They do not both
resolve to a YouTube channel:

- `@heysirio` — yt-dlp returned HTTP Error 404 (Not Found) for
  `https://www.youtube.com/@heysirio/videos`. No channel was studied
  under this handle.
- `@SirioBerati` — verified and studied. Channel name "Sirio",
  channel ID `UCNuJJ38qSq8LMiltOZTgzaw`, verified channel,
  149,000 followers as returned, channel URL
  https://www.youtube.com/@SirioBerati.

Channel description as returned: "Hey friend, I'm Sirio. An AI
creator, educator & builder based in Canada. Founder of
enhancor.ai. I create tools, content, and systems to help you scale
creativity with AI. Whether you're a solo creator, agency, or brand.
If you've ever felt overwhelmed by all the AI hype, this channel is
your safe space. Real workflows, creative experiments, and things I
wish I had when I was getting started."

Channel tags as returned: digital creator, ai, growth, creator,
filmmaking, apps, apis, tech.

Identity note: the public record also ties Sirio Berati to the
Instagram handle @sirio (2018 reporting) and to the domain
sirioberati.com. Those are not YouTube handles and were not treated
as channel evidence. Only the @SirioBerati channel above was
catalogued. If a second YouTube channel exists under another name,
it is outside this study.

## Method and tools

- `yt-dlp` 2026.10.26, installed in a sandbox virtual environment
  kept inside this study directory (`_scratch/venv`; the system
  Python refused a user-level install under PEP 668).
- Catalogue: `yt-dlp --flat-playlist -J` on the Videos tab, the
  Shorts tab, and the Playlists tab of @SirioBerati. Flat-playlist
  data carries titles, IDs, URLs, and durations for long-form videos;
  Shorts entries carry no duration in flat data, so Shorts durations
  are recorded as null, not estimated. Published dates and
  descriptions are not present in flat data and were not recovered
  (see block record).
- Transcripts: one subtitle fetch was attempted and blocked (see
  block record). No further fetch was attempted.
- Web search was used only to resolve the channel identity (see
  above). No course syllabus, template pack, or paid content was
  accessed.

## Exact counts

- Playlists enumerated: **0**. The Playlists tab returned 0 entries.
  No public playlist was found; none is claimed.
- Videos tab entries: **45**, all with durations, totalling
  **44,277 seconds (~12.3 hours)**. Longest: "How I Create
  Consistent & Realistic AI Characters (Full Workflow)", 3,056
  seconds (~51 minutes).
- Shorts tab entries: **90**. Durations not available in flat data.
- Unique public videos catalogued: **135** (45 + 90, zero overlap
  between the two tabs).
- Transcripts fetched: **0 of the 20 planned**. No transcript was
  invented.
- Videos with no title in flat data: 0.

Catalogue files: `catalogue.json` (with channel metadata and counts)
and `catalogue.csv` (135 rows + header).

## Block record — YouTube bot check, fetching stopped

Full per-video metadata extraction failed with:

> Sign in to confirm you're not a bot. Use --cookies-from-browser or
> --cookies for the authentication.

A single subtitle fetch (video `mi_ubF8_n8A`, subtitles only, no
video download) failed with the same error. Per the stop rules, all
YouTube fetching beyond flat-playlist enumeration stopped at that
point: no sign-in, no cookies, no workaround, no aggressive retry.
The consequence is that this study is a catalogue-and-titles study,
not a transcript study. Every skill extraction below is labelled
title-inferred and unverified against a transcript or a watched
video.

## Per-playlist summaries

None. No public playlists were returned, so there is nothing to
summarise. The channel's organisation, as far as the public tabs
show, is two lists: Videos (45) and Shorts (90).

## Transcript targets — all NOT FETCHED

The 20 prioritised targets below were selected from titles matching
the brief's topics. All are NOT FETCHED; their content is not
described beyond the title.

Visual storytelling / story-first and personal branding:
1. `37OnFjuCDR8` — "Will AI replace creators?" (330s)
2. `VbwJ9uZJuys` — "Let me blow your mind with this secret Al business model" (1,663s)

AI image craft and character/style references:
3. `mi_ubF8_n8A` — "How I Create Consistent & Realistic AI Characters (Full Workflow)" (3,056s)
4. `E-BenZQSGog` — "The SECRET Photoshop Killer (NEW Insane AI Editing + Character Consistency)" (331s)
5. `13Tv_1Kutho` — "Is This the End of Real Actors? (Create Unlimited Consistent & Realistic AI Influencers)" (905s)
6. `PD7LRblgDv8` — "She Isn't Real (The ULTIMATE Al Influencer Tutorial)" (1,211s)
7. `mCavxK7UJ84` — "She Isn't Real (The DEFINITIVE Al Influencer Pipeline)" (1,060s)
8. `NpfEKTXBxrY` — "She Isn't Real (The DEFINITIVE AI Influencer Tutorial)" (973s)
9. `D7J--ohBWxU` — "I gave my AI influencer a consistent voice (new method)" (833s)
10. `M1NsJHcX9rY` — "The CHEAPEST way to run Al UGC Ads (Claude +Seedance)" (2,175s)

Face-swap / character replacement and image-to-video:
11. `m7cdSfIiALE` — "WAN Animate just broke the internet (Open-Source Character Replacement)" (1,011s)
12. `Mi0sonWTlbI` — "Unlimited AI Influencer videos (Full ComfyUI Infinitetalk Tutorial & Setup)" (1,225s)
13. `bwJ8Xl6PxkM` — "VEO 3 KILLER!! This Is the Future of AI Filmmaking (Consistent Multi-Shot Videos)" (858s)
14. `_kYAkogj9WE` — "Create Seamless AI Films from One Image (Consistent Characters & Backgrounds)" (732s)
15. `O0uyyb2EKWw` — "Kling 2.6 Pro is the future of cinema!!" (868s)
16. `DbuS0s4ywoQ` — "Seedance 2 Just Changed AI UGC Ads (Full Breakdown)" (1,475s)
17. `d6spCMcfkew` — "Dear Higgsfield, I reverse engineered you in 12 hours" (1,306s)

Image craft, editing, and teaching guides:
18. `dXz1qkLc9PQ` — "I Replaced 8 Hours of Video Editing with This (Open Source)" (1,218s)
19. `AgLijG7t1QU` — "Make AI copy emotions from any scene (open source workflow)" (892s)
20. `ie4PBhWTO1c` — "Draw-to-Edit with Nano Banana (Free and Open-Source Workflow)" (714s)

No other transcript was attempted. Shorts were not given separate
transcript attempts; their titles are catalogued only.

## Skill extraction — title-inferred only, unverified

Nothing in this section is established from a transcript or from
watching a video. Each item states what the title names and what is
not known. No course syllabus is attributed to Sirio Berati: no
public syllabus was found, and his presence is Shorts/portfolio-led.

1. **Consistent-character workflow (the recurring spine).** Titles
   name the same problem from several angles: a "Full Workflow" for
   consistent and realistic AI characters (`mi_ubF8_n8A`), consistent
   characters and backgrounds from one image (`_kYAkogj9WE`),
   consistent multi-shot videos (`bwJ8Xl6PxkM`), character
   consistency in editing (`E-BenZQSGog`), and a consistent voice
   for an AI influencer (`D7J--ohBWxU`). What the titles do NOT
   establish: the reference-image method, any style-lock or weight
   value, the frame-by-frame drift check, or whether consistency
   holds across a full series. Those remain unknown until a
   transcript is studied.
2. **AI influencer pipeline.** Three long-form titles use the "She
   Isn't Real" series framing and name a pipeline and tutorials
   (`mCavxK7UJ84`, `PD7LRblgDv8`, `NpfEKTXBxrY`), plus UGC-ads
   titles naming Claude + Seedance (`M1NsJHcX9rY`) and a Seedance 2
   breakdown (`DbuS0s4ywoQ`). Steps, tools in order, costs, and
   failure handling are not established from titles.
3. **Image-to-video and character replacement.** Titles name WAN
   Animate character replacement (`m7cdSfIiALE`), a ComfyUI
   InfiniteTalk tutorial (`Mi0sonWTlbI`), Kling 2.6 (`O0uyyb2EKWw`),
   and a Higgsfield reverse-engineering piece (`d6spCMcfkew`).
   Start/end frames, camera movement, and prompt structure are not
   established from titles.
4. **Open-source editing workflows.** Titles name open-source
   video-editing replacement (`dXz1qkLc9PQ`), emotion copying from a
   scene (`AgLijG7t1QU`), and a draw-to-edit Nano Banana workflow
   (`ie4PBhWTO1c`). The actual tools, setup steps, and limits are
   not established from titles.
5. **Story-first and branding content is thin in titles.** No title
   on either tab names visual storytelling, a story-first method, a
   personal-branding framework, or a teaching course by name. The
   channel description names "real workflows, creative experiments"
   and tools/systems for scaling creativity. Any story-first or
   branding skill must not be claimed from this catalogue; it would
   need transcript or portfolio evidence.
6. **Public web material (context only, not video evidence).** A
   public Seedance prompt-engineering guide exists on his domain
   (seedance-prompt-guide.sirioberati.com, found by web search), and
   a public GitHub account under the name sirioberati hosts an
   enhancor draw-to-edit project. These corroborate the
   tool-building side of the channel description. They were not
   studied as video transcripts and no syllabus is attributed from
   them.

## Single most useful visual-storytelling pattern found

Title-inferred only: **one reference, one character, many shots** —
the pattern named across the consistent-character titles: lock a
character (and background) from one image, then carry it through
multi-shot films, influencer videos, and UGC ads, with a consistent
voice added as a separate step. This is the most reusable pattern in
the catalogue because it is the only one repeated across long-form
titles in different formats. It is **unverified**: no reference
method, weight, drift check, or success rate is established by this
study, and it must not be treated as a known workflow until a
transcript or the video is studied through an unblocked route.

## Honest limits

- Transcripts read: 0. Videos watched end to end: 0. This is a
  catalogue-and-titles study.
- The tutorial catalogue is thinner than the other two creators'
  (Jeff Su, Nate Herk): 45 long-form videos, 0 public playlists, 90
  Shorts. No course syllabus is attributed to Sirio Berati.
- Shorts content is not guessed: Shorts titles are catalogued, their
  spoken content is unknown, and most Shorts carry no captions in
  any case.
- Income and growth claims in titles (for example "$4M", "$2.7M a
  year", "Guaranteed") are reported as title wording only, not
  verified results.
- Channel follower count (149,000) is the value returned by the
  flat-playlist channel record on 28 October 2026, not a live
  re-check.
