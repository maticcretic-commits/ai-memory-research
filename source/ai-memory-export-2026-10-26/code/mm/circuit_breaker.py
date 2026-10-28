"""circuit_breaker - retrieval-share circuit breaker
(Red-Team Round 5).

Grok's proposal (corpus 3364) plus the un-built remainder of
Fo's decay-manipulation breaker (corpus 3359). Round 4 built
3359's resurrection subset (only attributed, non-owner
accesses resurrect a cooled record). What remained: watch
RETRIEVAL itself for amplification. A poisoner who cannot
win the write gate can still win the mouth - plant (or
capture) records that every query surfaces, until one
source's view of the world IS the memory's answer. Write-side
defences never see it: nothing is written. The signal lives
in the access log: one source identity's share of what
actually surfaces.

The breaker consumes access events (mm.janitor.AccessEvent;
since Round 5 they carry the query they served) plus a
records snapshot, over a sliding window of the last W
retrieval events:

- per source identity (owner, source root - the registry's
  identity, so 'who is speaking' means one thing): surfaced
  count, distinct non-empty queries, distinct actors
  (principals);
- TRIP when ALL of: window events >= MIN_EVENTS, the
  identity's share of surfaced events >= CEILING (the hard
  ceiling of 3359), and the identity's distinct queries >=
  MIN_DISTINCT_QUERIES. The three conditions are 3359's
  point: one repeated query is a hot record, not
  amplification; raw (never-surfaced) reads are not
  retrieval; and a share below the ceiling is popularity,
  not capture.
- A trip is a BreakerAlert naming the identity, its share,
  its surfaced count, its distinct queries, and EVERY
  principal who surfaced it - the cross-principal alert:
  amplification that reached other lanes is reported with
  those lanes named, not filed as the source's own
  statistic.
- suppressed_identities() returns the tripped set. The
  agent's retrieve accepts breaker= and, when wired, drops a
  tripped identity's hits from what it serves next
  (suppression computed from prior logged traffic, before the
  current query's events land). The alert is the primary
  deliverable; suppression is the opt-in action, exactly
  like Round 4's attributed janitor.

Red-Team Round 6: group aggregation. Round 5's honest limit
was Sybil dilution - split across identities and every
per-identity share sits under the ceiling while the SET
captures retrieval. evaluate() now also aggregates by the
identity's own two dimensions: SOURCE ROOT (lineage) and
OWNER. A group of >= 2 member identities trips on the same
conditions applied to its combined share, the UNION of its
distinct queries, and the union of its principals; the
alert carries level ("root" | "owner") and the full member
list, and suppressed_identities() includes every member -
a wired mouth drops the whole diluted set. A one-member
group is the identity check and emits no group alert.
Known tax, measured in the Round-6 preregistration's FU2c
control and priced in its record: unrelated owners sharing
a common infrastructure root (both filing under
"external/...") aggregate at root level - the breaker
cannot tell shared infrastructure from shared lineage.

Events without a query (legacy rows, direct log calls)
count toward share but cannot add distinct queries - an
uninstrumented deployment under-counts distinctness and so
trips LATER, never earlier: the failure direction is
conservative.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mm.janitor import AccessEvent
from mm.reflect import MemoryRecord
from mm.source_trust import identity_of

# Thresholds (inspectable priors, declared in the Round-5
# preregistration, not tuned to the fixtures).
WINDOW_EVENTS = 200      # sliding window of retrieval events
CEILING = 0.50           # hard share ceiling (Fo 3359)
MIN_EVENTS = 20          # window must hold at least this many
MIN_DISTINCT_QUERIES = 5  # per-identity distinct queries


@dataclass
class BreakerAlert:
    identity: tuple[str, str]      # (owner, source root); for a
                                   # group alert, the first member
    share: float
    surfaced: int
    distinct_queries: int
    principals: list[str]          # every actor who surfaced it
    at: float                      # time of the last window event
    window_events: int
    # Red-Team Round 6: "identity" (the Round-5 alert) or a
    # group level ("root" | "owner"); members lists every
    # identity the alert covers - [identity] for identity
    # alerts, the full diluted set for group alerts.
    level: str = "identity"
    members: list = field(default_factory=list)

    @property
    def cross_principal(self) -> bool:
        """The alert reached beyond the source's own lane(s):
        at least one principal other than a member owner
        surfaced its records."""
        owners = {m[0] for m in self.members} or {self.identity[0]}
        return any(p and p not in owners for p in self.principals)


@dataclass
class _Share:
    surfaced: int = 0
    queries: set = field(default_factory=set)
    principals: set = field(default_factory=set)


class RetrievalShareBreaker:
    """Per-identity retrieval-share tripwire over the access
    log. Pure function of (events, records) - no state, no
    I/O, fully inspectable."""

    def __init__(self, window_events: int = WINDOW_EVENTS,
                 ceiling: float = CEILING,
                 min_events: int = MIN_EVENTS,
                 min_distinct_queries: int = MIN_DISTINCT_QUERIES
                 ) -> None:
        self.window_events = window_events
        self.ceiling = ceiling
        self.min_events = min_events
        self.min_distinct_queries = min_distinct_queries

    def _tally(self, events: list[AccessEvent],
               records: dict[str, MemoryRecord]
               ) -> tuple[dict, int, float]:
        window = [e for e in events if e.kind == "retrieval"]
        window = window[-self.window_events:]
        shares: dict[tuple[str, str], _Share] = {}
        total = 0
        last_at = 0.0
        for e in window:
            rec = records.get(e.record_id)
            if rec is None:
                continue
            total += 1
            last_at = max(last_at, e.at)
            ident = identity_of(rec)
            sh = shares.setdefault(ident, _Share())
            sh.surfaced += 1
            if e.query:
                sh.queries.add(e.query)
            sh.principals.add(e.actor or "")
        return shares, total, last_at

    @staticmethod
    def _groups(shares: dict) -> dict:
        """Aggregate per-identity tallies into the Round-6
        groupings: ("root", root) and ("owner", owner). Each
        group unions its members' surfaced counts, distinct
        queries, and principals."""
        groups: dict[tuple[str, str], dict] = {}
        for (owner, root), sh in shares.items():
            for key in (("root", root), ("owner", owner)):
                g = groups.setdefault(key, {
                    "surfaced": 0, "queries": set(),
                    "principals": set(), "members": set()})
                g["surfaced"] += sh.surfaced
                g["queries"] |= sh.queries
                g["principals"] |= sh.principals
                g["members"].add((owner, root))
        return groups

    def evaluate(self, events: list[AccessEvent],
                 records: dict[str, MemoryRecord]
                 ) -> list[BreakerAlert]:
        """Every identity - and, since Round 6, every
        root/owner GROUP of >= 2 identities - currently over
        the trip conditions."""
        shares, total, last_at = self._tally(events, records)
        out: list[BreakerAlert] = []
        if total < self.min_events:
            return out
        for ident, sh in sorted(shares.items()):
            share = sh.surfaced / total if total else 0.0
            if (share >= self.ceiling
                    and len(sh.queries) >= self.min_distinct_queries):
                out.append(BreakerAlert(
                    identity=ident, share=share,
                    surfaced=sh.surfaced,
                    distinct_queries=len(sh.queries),
                    principals=sorted(sh.principals),
                    at=last_at, window_events=total,
                    members=[ident]))
        for (level, key), g in sorted(self._groups(shares).items()):
            members = sorted(g["members"])
            if len(members) < 2:
                continue  # a one-member group IS the identity check
            share = g["surfaced"] / total if total else 0.0
            if (share >= self.ceiling
                    and len(g["queries"]) >= self.min_distinct_queries):
                out.append(BreakerAlert(
                    identity=members[0], share=share,
                    surfaced=g["surfaced"],
                    distinct_queries=len(g["queries"]),
                    principals=sorted(g["principals"]),
                    at=last_at, window_events=total,
                    level=level, members=members))
        return out

    def suppressed_identities(
            self, events: list[AccessEvent],
            records: dict[str, MemoryRecord]
    ) -> set[tuple[str, str]]:
        """The tripped set - what a wired mouth drops. Group
        alerts contribute every member identity."""
        out: set[tuple[str, str]] = set()
        for a in self.evaluate(events, records):
            out.update(a.members or [a.identity])
        return out

    def share_report(self, events: list[AccessEvent],
                     records: dict[str, MemoryRecord]) -> dict:
        """Every identity's window share (the utility view:
        popularity below the ceiling is visible here, not
        hidden by the trip filter). Round 6 adds the group
        views (per_root / per_owner) on the same terms."""
        shares, total, _ = self._tally(events, records)
        return {
            "window_events": total,
            "per_identity": {
                f"{o}|{r}": {
                    "surfaced": sh.surfaced,
                    "share": (sh.surfaced / total) if total else 0.0,
                    "distinct_queries": len(sh.queries),
                    "principals": sorted(sh.principals),
                }
                for (o, r), sh in sorted(shares.items())},
            "per_group": {
                f"{level}|{key}": {
                    "surfaced": g["surfaced"],
                    "share": (g["surfaced"] / total) if total else 0.0,
                    "distinct_queries": len(g["queries"]),
                    "principals": sorted(g["principals"]),
                    "members": [f"{o}|{r}"
                                for (o, r) in sorted(g["members"])],
                }
                for (level, key), g in sorted(
                    self._groups(shares).items())},
        }


__all__ = ["RetrievalShareBreaker", "BreakerAlert",
           "WINDOW_EVENTS", "CEILING", "MIN_EVENTS",
           "MIN_DISTINCT_QUERIES"]
