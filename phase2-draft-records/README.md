# Phase 2 draft records

Signed-ready draft records in the Round 7 format. They join the Round 7
audit packet; they do not certify anything. Every record is DRAFT, its
owner is UNASSIGNED, its TBD fields are named, and its signature block
is blank. No name, body, number, gate status, or measured result is
invented in any of them.

- [J5 — Decision framework for new tools](sandbox://workspace/ai-memory-research/phase2-draft-records/DRAFT-RECORD-J5.md)
- [N9 — Partner-engagement template](sandbox://workspace/ai-memory-research/phase2-draft-records/DRAFT-RECORD-N9.md)
- [S4 — Brand rulebook for the faceless channels, restated not changed](sandbox://workspace/ai-memory-research/phase2-draft-records/DRAFT-RECORD-S4.md)

Verification: `python3 verify_drafts.py` checks form only (DRAFT status,
UNASSIGNED owner, at least five TBD fields, blank signature block, no
lock or certification claim). The checker was written first and failed
on the missing records; after the records were written it passes.
Reading the records remains the control for invented names or numbers.

Governance: CREATOR-SKILLS-IMPLEMENTATION.md Part C stands. Phase 3
(voice, live scraping, real pairs, sending channel) stays blocked.
