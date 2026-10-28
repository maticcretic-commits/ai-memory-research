"""episodic - elephant matriarch long-horizon recall (instinct 5).

The matriarch's value is not raw recall - it is knowing, years later,
WHICH waterhole mattered in the drought year, and the social context
around it. This module retrieves full event EPISODES with provenance,
not just top-k fragments:

- Episode chains follow episodic_record_id pointers (semantic -> episode,
  episode -> episode), so a fact surfaces the event that produced it.
- Relational context rides along: who said it (owner), how it was
  gathered (gathered_how), the dispute state (declared contradictions),
  the conflict relations - on dispute the mind falls back to the episode
  (design doc 2.2 item 1).
- Rare-event survival weighting: the sole surviving record of its class
  gets a retrieval boost when the query matches the class - the
  matriarch does not give the common answer to the drought question.

Rule-based, zero LLM. Reads only - never mutates the store.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Retrieval boost for the sole surviving record of its (type, ttl_class).
RARE_CLASS_BOOST = 1.5


@dataclass
class EpisodeLink:
    record_id: str
    relation: str   # self | episode | contradicts | supersedes


@dataclass
class Episode:
    """One full event episode: the semantic fact plus the chain behind
    it, with relational context intact."""
    head_id: str
    chain: list[EpisodeLink]          # episode chain, head-first
    owners: list[str]
    gathered_how: list[str]
    dispute_ids: list[str]           # declared contradictions in the chain
    superseded_ids: list[str]


def _snapshot(store):
    """The store's system-path snapshot (Red-Team Round 5):
    episode assembly scans the whole store for chain context
    and class uniqueness - that is system work, not a reader
    extraction, so it uses snapshot() where the store offers
    it and is never noted on the canary watch."""
    snap = getattr(store, "snapshot", None)
    return snap() if snap is not None else store.all_records()


def valid_at_instant(rec, t) -> bool:
    """B2 (Benchmark Wave 2): is this record IN FORCE at instant
    t? The validity window is [valid_at, invalid_at): valid_at
    None falls back to the record's own timestamp (a record
    written before the window existed was in force from when it
    was recorded); invalid_at None = still in force. This is
    the one window rule - episodic as-of recall and the eval
    harness's windowed retriever both use it."""
    start = rec.valid_at or rec.timestamp
    if t < start:
        return False
    if rec.invalid_at is not None and t >= rec.invalid_at:
        return False
    return True


def valid_at_day(rec, t) -> bool:
    """B2 granularity follow-up: the same window rule read at DAY
    precision, for corpora whose evidence clock is day-granular
    (Benchmark Wave 2 correction / corpus idea 3492: LongMemEval-S
    temporal haystacks carry sessions timestamped later the SAME
    DAY as the question and the dataset treats them as answerable
    evidence; the instant rule filtered 74 gold sessions there).

    Semantics: start = valid_at or the record timestamp (the same
    fallback); in force iff start.date() <= t.date() AND
    (invalid_at is None OR t.date() < invalid_at.date()) - the
    interval stays end-exclusive, read in day units, so a record
    stops being in force ON its invalidation day. A record whose
    start day is after the question day is still excluded: day
    precision does NOT reopen future leakage, it only stops
    punishing same-day evidence. Production as-of recall keeps
    valid_at_instant; this predicate is for benchmark-mode
    windows matched to a corpus's evidence granularity."""
    start = rec.valid_at or rec.timestamp
    if start.date() > t.date():
        return False
    if rec.invalid_at is not None and t.date() >= rec.invalid_at.date():
        return False
    return True


def episode_for(store, record_id: str, depth: int = 5,
                reader=None, as_of=None) -> Episode:
    """Assemble the full episode behind one record: follow
    episodic_record_id pointers up to `depth`, collecting relational
    context (owner, gathered_how) and dispute state. Never follows
    into a cycle.

    Finding 11 (ChatGPT review): episodic_record_id is SEALED content
    (storage layer) - it cannot be forged post-hoc; only the writer
    sets it, and the write gate checks authorization. Dangling links
    are skipped, cycles are broken, but a malicious writer's chain is
    still that writer's claim - episodes are evidence, never proof.

    Red-Team Round 4: with a ReaderContext attached, assembly is
    authorized per record (mm/access_control.py) - an unreadable
    head yields an empty episode, and chain links, named relations
    and context the reader may not read are dropped. This runs ON
    TOP OF the Round-1 ownership rule below: the pointer rule
    governs what a chain may claim; the reader rule governs what
    THIS reader may see of it.

    Benchmark Wave 2 (B2): as_of=<datetime> assembles the episode
    AS IT stood at that instant - the head, chain links, and
    named relations are filtered to records in force at as_of
    (valid_at_instant). A head not in force at as_of yields an
    empty episode: at that instant, this memory was not true
    yet (or no longer was)."""
    records = _snapshot(store)
    authorizer = getattr(store, "authorizer", None)

    def readable(rec) -> bool:
        if reader is None or authorizer is None:
            return True
        return authorizer.can_read(reader, rec)[0]

    head = records.get(record_id)
    if head is None or not readable(head):
        return Episode(head_id=record_id, chain=[], owners=[],
                       gathered_how=[], dispute_ids=[], superseded_ids=[])
    if as_of is not None and not valid_at_instant(head, as_of):
        return Episode(head_id=record_id, chain=[], owners=[],
                       gathered_how=[], dispute_ids=[], superseded_ids=[])
    chain: list[EpisodeLink] = [EpisodeLink(record_id=head.id, relation="self")]
    seen = {head.id}
    owners = [head.owner] if head.owner else []
    gathered = [head.gathered_how] if head.gathered_how else []
    disputes = list(head.provenance.contradicts)
    superseded = list(head.provenance.supersedes)
    current = head
    for _ in range(depth - 1):
        nxt_id = current.episodic_record_id
        if not nxt_id or nxt_id in seen:
            break
        nxt = records.get(nxt_id)
        if nxt is None:
            break
        # Red-Team Round 1 (class A10): a chain pointer is the
        # writer's claim, not a capability. Before this rule, any
        # record could point episodic_record_id at a restricted or
        # canary record and pull it into its own episode - and into
        # answer() evidence. Follow a pointer only within the head's
        # own ownership, or into an episodic event record (shared
        # context by design) - never into another owner's facts.
        if nxt.owner != head.owner and nxt.type != "episodic":
            break
        # Red-Team Round 4: and never SHOW a link this reader may
        # not read, whichever rule let the chain claim it.
        if not readable(nxt):
            break
        # B2: in as-of mode, never follow into a record that was
        # not in force at the query instant.
        if as_of is not None and not valid_at_instant(nxt, as_of):
            break
        seen.add(nxt_id)
        chain.append(EpisodeLink(record_id=nxt_id, relation="episode"))
        if nxt.owner and nxt.owner not in owners:
            owners.append(nxt.owner)
        if nxt.gathered_how and nxt.gathered_how not in gathered:
            gathered.append(nxt.gathered_how)
        for d in nxt.provenance.contradicts:
            if d not in disputes:
                disputes.append(d)
        for s in nxt.provenance.supersedes:
            if s not in superseded:
                superseded.append(s)
        current = nxt
    # named relations around the whole chain
    # Red-Team Round 4: declared relations are claims too - before
    # this filter, a writer could name ANY record in `contradicts`
    # (planted dangling-first, the A11 pattern) and the relation
    # pass pulled it into the chain, and into answer() evidence,
    # without the pointer rule ever applying. With a reader
    # attached, a named relation the reader cannot read is not
    # shown. The dispute/superseded ID lists are filtered the
    # same way: an unreadable record's id is not metadata the
    # reader is entitled to.
    for link in list(chain):
        rec = records.get(link.record_id)
        if rec is None:
            continue
        for d in rec.provenance.contradicts:
            if d not in seen:
                target = records.get(d)
                if target is not None and not readable(target):
                    continue
                if (as_of is not None and target is not None
                        and not valid_at_instant(target, as_of)):
                    continue
                chain.append(EpisodeLink(record_id=d, relation="contradicts"))
                seen.add(d)
        for s in rec.provenance.supersedes:
            if s not in seen:
                target = records.get(s)
                if target is not None and not readable(target):
                    continue
                if (as_of is not None and target is not None
                        and not valid_at_instant(target, as_of)):
                    continue
                chain.append(EpisodeLink(record_id=s, relation="supersedes"))
                seen.add(s)
    if reader is not None:
        disputes = [d for d in disputes
                    if records.get(d) is None
                    or readable(records[d])]
        superseded = [s for s in superseded
                      if records.get(s) is None
                      or readable(records[s])]
    if as_of is not None:
        disputes = [d for d in disputes
                    if records.get(d) is None
                    or valid_at_instant(records[d], as_of)]
        superseded = [s for s in superseded
                      if records.get(s) is None
                      or valid_at_instant(records[s], as_of)]
    return Episode(head_id=record_id, chain=chain, owners=owners,
                   gathered_how=gathered, dispute_ids=disputes,
                   superseded_ids=superseded)


def recall_episodes(store, query: str, limit: int = 5,
                    depth: int = 5, reader=None,
                    as_of=None) -> list[Episode]:
    """Long-horizon recall: search for candidate heads, then assemble
    each one's full episode. The rare-class boost applies: the sole
    surviving record of its (type, ttl_class) is boosted when it
    matches, so rare answers surface instead of being buried by the
    common ones.

    Finding 12 (ChatGPT review): the boost is a RANKING adjustment,
    not evidence of truth - it never enters authorization, decision
    confidence, or contradiction resolution. "Sole surviving record"
    uses the same live-record scope as the Janitor's class-uniqueness
    check (non-superseded records).

    Red-Team Round 4: with a reader attached, candidate heads the
    reader may not read never become episodes (the boost still
    ranks only the visible set - ranking is computed over all
    records for class-uniqueness scope, but an invisible head is
    not surfaced, boosted or not)."""
    records = _snapshot(store)
    hits = store.search(query, limit=limit * 3)
    if reader is not None:
        authorizer = getattr(store, "authorizer", None)
        if authorizer is not None:
            hits = [h for h in hits
                    if authorizer.can_read(reader, h)[0]]
    if as_of is not None:
        # B2: candidate heads must be in force at the query
        # instant - a superseded or not-yet-valid head never
        # becomes an episode in as-of mode.
        hits = [h for h in hits if valid_at_instant(h, as_of)]
    # class uniqueness over the live (non-superseded) store
    def is_sole(rec) -> bool:
        return not any(
            o.id != rec.id and o.type == rec.type
            and o.ttl_class == rec.ttl_class
            and not o.superseded_with_replacement
            for o in records.values())
    ranked = []
    for rec in hits:
        boost = RARE_CLASS_BOOST if is_sole(rec) else 1.0
        ranked.append((boost * (1.0 + rec.salience), rec))
    ranked.sort(key=lambda x: (-x[0], x[1].id))
    return [episode_for(store, rec.id, depth=depth, reader=reader,
                        as_of=as_of)
            for _, rec in ranked[:limit]]
