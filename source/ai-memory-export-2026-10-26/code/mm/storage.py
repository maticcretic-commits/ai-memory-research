"""storage - owned SQLite storage for v0.5 memory records (Phase-3 chunk 3).

Design doc 2.2: "Own the storage layout (1922/S8). SQLite/owned storage
behind a stable interface - not a black-box vector DB." This module is
that interface. The write gate (mm.write_gate) is the ONLY way records
enter; the Janitor (mm.janitor) mutates lifecycle metadata only through
the whitelist below; consolidation works on dict snapshots loaded from
here. Nothing else touches the tables.

THE SEAL, ENFORCED AT THE STORAGE LAYER (chunk 2 promised it in the
gate; chunk 3 makes the store itself refuse):
- An admitted record's CONTENT columns (text, content, type, epistemic
  tier, provenance, salience, ...) are immutable once inserted. There is
  no update path for them: update_metadata() accepts ONLY the lifecycle
  whitelist (tier, last_accessed, access_count, decay_score,
  superseded_with_replacement) and raises on anything else. Inserting a
  second record with an existing id raises. A correction therefore
  CANNOT overwrite history - it arrives as a new record whose provenance
  names supersedes=[old id], and the gate closes the old one via the
  metadata whitelist (tier -> archive, superseded flag). Perfect
  verbatim recall is now a storage property, not a convention.

Gate outcomes persist asymmetrically, on purpose:
- admitted -> records table (sealed).
- queued   -> review_items table (full record serialized, awaiting
              resolution; NOT in records - it never landed).
- rejected -> gate_log table only (id + verdict + reasons + time).
              Rejected content is never persisted anywhere: a G0
              secrets/PII rejection must not become a stored secret.
              (Gate rejection reasons never contain record content -
              they name the gate and the rule, per mm.write_gate.)

Access events persist too (access_events table), so the Janitor's
half-life instrumentation survives restarts - "instrumented from day
one" now means instrumented across processes.

Migration policy: additive only. CREATE TABLE IF NOT EXISTS + a
schema_meta version row. No destructive migration, ever, without the
founder's explicit approval (standing boundary).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from mm.access_control import ReadAuthorizer, ReaderContext
from mm.janitor import AccessEvent, Janitor, JanitorReport
from mm.reflect import MemoryRecord, Provenance
from mm.write_gate import GateOutcome, WriteGate

SCHEMA_VERSION = "5"

# v0.6 additive migration: the immune threat class (instinct 2) adds
# decay_exempt to records. Older DBs get the column via ALTER TABLE;
# CREATE TABLE already carries it for fresh stores.
def _migrate_v2(conn: "sqlite3.Connection") -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(records)")}
    if "decay_exempt" not in cols:
        conn.execute(
            "ALTER TABLE records ADD COLUMN decay_exempt "
            "INTEGER NOT NULL DEFAULT 0")
        conn.commit()


# Red-Team Round 4 additive migration: access events gain an actor
# (WHO read - the read-authorization audit identity). Older DBs get
# the column via ALTER TABLE with '' (anonymous/legacy) as the
# default; CREATE TABLE already carries it for fresh stores.
def _migrate_v3(conn: "sqlite3.Connection") -> None:
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(access_events)")}
    if "actor" not in cols:
        conn.execute(
            "ALTER TABLE access_events ADD COLUMN actor "
            "TEXT NOT NULL DEFAULT ''")
        conn.commit()


# Red-Team Round 5 additive migration: access events gain the
# query that surfaced the record (the retrieval-share circuit
# breaker's distinct-query condition, Fo 3359). Older DBs get
# the column via ALTER TABLE with '' (uninstrumented) as the
# default; CREATE TABLE already carries it for fresh stores.
def _migrate_v4(conn: "sqlite3.Connection") -> None:
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(access_events)")}
    if "query" not in cols:
        conn.execute(
            "ALTER TABLE access_events ADD COLUMN query "
            "TEXT NOT NULL DEFAULT ''")
        conn.commit()

# Benchmark Wave 2 (B2) additive migration: records gain the
# bi-temporal validity window (valid_at / invalid_at). Older DBs
# get the columns via ALTER TABLE with NULL (unbounded) as the
# default; CREATE TABLE already carries them for fresh stores.
def _migrate_v5(conn: "sqlite3.Connection") -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(records)")}
    for col in ("valid_at", "invalid_at"):
        if col not in cols:
            conn.execute(
                f"ALTER TABLE records ADD COLUMN {col} TEXT")
    conn.commit()


# Design consult (2026-10-21) additive migration: records gain
# dispute_refs (v0.6) - the cross-shard dispute tag cache (JSON
# list of open dispute ids). Older DBs get the column via ALTER
# TABLE with '[]' (not disputed) as the default; CREATE TABLE
# already carries it for fresh stores.
def _migrate_v6(conn: "sqlite3.Connection") -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(records)")}
    if "dispute_refs" not in cols:
        conn.execute(
            "ALTER TABLE records ADD COLUMN dispute_refs "
            "TEXT NOT NULL DEFAULT '[]'")
        conn.commit()


# The ONLY record fields any post-insert write may touch. Everything
# else is sealed content. Janitor lifecycle + gate side effects
# (supersession close-out, duplicate access refresh) use exactly these.
# Benchmark Wave 2 (B2 spec): invalid_at joins the whitelist - the
# spec's single sanctioned post-seal content-adjacent write, made
# by the supersession close-out at the moment a correction lands
# (lifecycle-class, like tier: it records WHEN the record stopped
# being in force, never what it said). valid_at is set at insert
# only and is NOT whitelisted.
# Design consult (2026-10-21, ruling T3): dispute_refs joins the
# whitelist on the same lifecycle-class basis - it records THAT
# the record is currently contested (the mesh's dispute tag
# cache), never what it says. Written only by the mesh
# (mm.shards.Core) via update_metadata; the dispute record and
# its audit trail remain authoritative, and Core reconciles the
# cache from them on restore.
METADATA_WHITELIST = {
    "tier", "last_accessed", "access_count", "decay_score",
    "superseded_with_replacement", "invalid_at", "dispute_refs",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    salience REAL NOT NULL DEFAULT 0.5,
    type TEXT NOT NULL DEFAULT 'fact',
    epistemic_tier TEXT NOT NULL DEFAULT 'unknown',
    explicit INTEGER NOT NULL DEFAULT 0,
    owner TEXT NOT NULL DEFAULT '',
    gathered_how TEXT NOT NULL DEFAULT '',
    consent_scope TEXT NOT NULL DEFAULT '',
    tier TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL DEFAULT 0.0,
    last_accessed REAL NOT NULL DEFAULT 0.0,
    access_count INTEGER NOT NULL DEFAULT 0,
    decay_score REAL NOT NULL DEFAULT 1.0,
    ttl_class TEXT NOT NULL DEFAULT 'session',
    invalidation_contract TEXT NOT NULL DEFAULT '',
    superseded_with_replacement INTEGER NOT NULL DEFAULT 0,
    episodic_record_id TEXT,
    prov_confidence REAL NOT NULL DEFAULT 1.0,
    prov_contradicts TEXT NOT NULL DEFAULT '[]',
    prov_supersedes TEXT NOT NULL DEFAULT '[]',
    prov_valid_from TEXT,
    prov_recorded_at TEXT,
    write_audit TEXT NOT NULL DEFAULT '{}',
    decay_exempt INTEGER NOT NULL DEFAULT 0,
    valid_at TEXT,
    invalid_at TEXT,
    dispute_refs TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS access_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL,
    at REAL NOT NULL,
    kind TEXT NOT NULL DEFAULT 'retrieval',
    actor TEXT NOT NULL DEFAULT '',
    query TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS review_items (
    record_id TEXT PRIMARY KEY,
    record_json TEXT NOT NULL,
    reasons TEXT NOT NULL DEFAULT '[]',
    queued_at TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    resolution TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS gate_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL,
    verdict TEXT NOT NULL,
    reasons TEXT NOT NULL DEFAULT '[]',
    at TEXT NOT NULL
);
"""


def _dt_to_str(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _dt_from_str(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def record_to_dict(r: MemoryRecord) -> dict:
    """Full JSON-safe serialization (review queue + round-trip tests)."""
    return {
        "id": r.id, "text": r.text, "content": r.content,
        "timestamp": _dt_to_str(r.timestamp), "source": r.source,
        "salience": r.salience, "type": r.type,
        "epistemic_tier": r.epistemic_tier, "explicit": r.explicit,
        "owner": r.owner, "gathered_how": r.gathered_how,
        "consent_scope": r.consent_scope, "tier": r.tier,
        "created_at": r.created_at, "last_accessed": r.last_accessed,
        "access_count": r.access_count, "decay_score": r.decay_score,
        "ttl_class": r.ttl_class,
        "invalidation_contract": r.invalidation_contract,
        "superseded_with_replacement": r.superseded_with_replacement,
        "episodic_record_id": r.episodic_record_id,
        "provenance": {
            "confidence": r.provenance.confidence,
            "contradicts": list(r.provenance.contradicts),
            "supersedes": list(r.provenance.supersedes),
            "valid_from": _dt_to_str(r.provenance.valid_from),
            "recorded_at": _dt_to_str(r.provenance.recorded_at),
        },
        "write_audit": r.write_audit,
        "decay_exempt": r.decay_exempt,
        "valid_at": _dt_to_str(r.valid_at),
        "invalid_at": _dt_to_str(r.invalid_at),
        "dispute_refs": list(r.dispute_refs or []),
    }


def record_from_dict(d: dict) -> MemoryRecord:
    p = d.get("provenance", {})
    return MemoryRecord(
        id=d["id"], text=d["text"], content=d.get("content", ""),
        timestamp=_dt_from_str(d["timestamp"]) or datetime.utcnow(),
        source=d.get("source", ""), salience=d.get("salience", 0.5),
        type=d.get("type", "fact"),
        epistemic_tier=d.get("epistemic_tier", "unknown"),
        explicit=bool(d.get("explicit", False)),
        owner=d.get("owner", ""), gathered_how=d.get("gathered_how", ""),
        consent_scope=d.get("consent_scope", ""),
        tier=d.get("tier", "active"),
        created_at=d.get("created_at", 0.0),
        last_accessed=d.get("last_accessed", 0.0),
        access_count=d.get("access_count", 0),
        decay_score=d.get("decay_score", 1.0),
        ttl_class=d.get("ttl_class", "session"),
        invalidation_contract=d.get("invalidation_contract", ""),
        superseded_with_replacement=bool(
            d.get("superseded_with_replacement", False)),
        episodic_record_id=d.get("episodic_record_id"),
        decay_exempt=bool(d.get("decay_exempt", False)),
        valid_at=_dt_from_str(d.get("valid_at")),
        invalid_at=_dt_from_str(d.get("invalid_at")),
        dispute_refs=list(d.get("dispute_refs", []) or []),
        provenance=Provenance(
            confidence=p.get("confidence", 1.0),
            contradicts=list(p.get("contradicts", [])),
            supersedes=list(p.get("supersedes", [])),
            valid_from=_dt_from_str(p.get("valid_from")),
            recorded_at=_dt_from_str(p.get("recorded_at")),
        ),
        write_audit=d.get("write_audit", {}),
    )


class SealedRecordError(Exception):
    """Raised on any attempt to mutate sealed record content."""


class SQLiteStore:
    """The owned store. Write-gate in, metadata-whitelist updates,
    dict snapshots out (the shape janitor/consolidation already eat)."""

    def __init__(self, path: str, identity_authority=None,
                 canary_watch=None, canaries: int = 0) -> None:
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        _migrate_v2(self._conn)
        _migrate_v3(self._conn)
        _migrate_v4(self._conn)
        _migrate_v5(self._conn)
        _migrate_v6(self._conn)
        self._conn.execute(
            "INSERT OR IGNORE INTO schema_meta(key, value) VALUES "
            "('version', ?)", (SCHEMA_VERSION,))
        self._conn.commit()
        self.gate = WriteGate()
        # Red-Team Round 4: the read authorizer behind the
        # authorized read API (get_for / search_for /
        # all_records_for). The raw reads below remain the
        # in-process system path (gate, janitor, consolidation);
        # reader-facing surfaces use the authorized ones.
        self.authorizer = ReadAuthorizer()
        # Red-Team Round 5: identity binding (mm/identity.py).
        # When an authority is wired, writes under a REGISTERED
        # writer identity and authorized reads under a
        # REGISTERED reader id require the bound capability
        # token; unregistered identities keep the legacy
        # declared path. Default None = Round-4 behaviour.
        self.identity_authority = identity_authority
        # Red-Team Round 5: canary tripwire (mm/canary.py). The
        # watch is told about every record the reader-facing
        # read methods return; snapshot() (the system path) is
        # never noted. canaries=N seeds bait records at
        # construction (the deployment default posture) and
        # auto-wires a watch when none is given.
        self.canary_watch = canary_watch
        if canaries:
            from mm.canary import CanaryWatch, seed_canaries
            if self.canary_watch is None:
                self.canary_watch = CanaryWatch()
            seed_canaries(self, count=canaries,
                          watch=self.canary_watch)
        elif self.canary_watch is not None:
            # A store reopened with its watch: re-register the
            # canaries it already holds, so trips keep working
            # across restarts.
            from mm.canary import CANARY_OWNER, CANARY_SOURCE
            from mm.canary import _marker_of
            for r in self._snapshot().values():
                if r.owner == CANARY_OWNER and r.source == CANARY_SOURCE:
                    self.canary_watch.register(r.id, _marker_of(r))

    def close(self) -> None:
        self._conn.close()

    def __len__(self) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM records").fetchone()[0]

    def __contains__(self, record_id: str) -> bool:
        return self._conn.execute(
            "SELECT 1 FROM records WHERE id = ?",
            (record_id,)).fetchone() is not None

    # -- the write path (gate-mediated, the only way in) -----------------

    def write(self, record: MemoryRecord,
              token: str | None = None) -> GateOutcome:
        """Run the write gate against the stored records and persist the
        outcome asymmetrically (see module docstring).

        Red-Team Round 5: with an identity authority wired, a
        write under a REGISTERED writer identity must present
        that identity's capability token; otherwise the write is
        refused HERE, before the gate runs - a spoof accrues no
        track record and pollutes no dispute surface. The
        refusal is logged like any rejection (the content is
        never persisted)."""
        auth = self.identity_authority
        if (auth is not None
                and auth.is_writer_registered(record.owner,
                                              record.source)
                and not auth.verify_writer(token, record.owner,
                                           record.source)):
            reasons = [
                "identity binding: writer identity "
                f"({record.owner!r}, source root "
                f"{(record.source or '').split('/')[0].strip().lower()!r}) "
                "is registered - a verifying capability token is "
                "required (Red-Team Round 5)"]
            self._conn.execute(
                "INSERT INTO gate_log(record_id, verdict, reasons, "
                "at) VALUES (?, 'rejected', ?, ?)",
                (record.id, json.dumps(reasons),
                 datetime.utcnow().isoformat()))
            self._conn.commit()
            return GateOutcome(verdict="rejected", reasons=reasons,
                               record=record)
        existing = self._snapshot()
        outcome = self.gate.admit(record, existing)
        at = datetime.utcnow().isoformat()
        self._conn.execute(
            "INSERT INTO gate_log(record_id, verdict, reasons, at) "
            "VALUES (?, ?, ?, ?)",
            (record.id, outcome.verdict,
             json.dumps(outcome.reasons), at))
        if outcome.verdict == "admitted":
            try:
                self._insert_sealed(record)
            except SealedRecordError:
                # The gate admitted it but the seal refused (existing
                # id). Log the refusal truthfully, then propagate.
                self._conn.execute(
                    "INSERT INTO gate_log(record_id, verdict, reasons, "
                    "at) VALUES (?, 'rejected-sealed', ?, ?)",
                    (record.id,
                     json.dumps(["id already exists - sealed store "
                                 "refused overwrite"]), at))
                self._conn.commit()
                raise
            # Persist gate side effects on OTHER records (whitelist only):
            # G4 close-on-replacement losers; G3 duplicate access refresh
            # (n/a here - a duplicate is rejected, not admitted).
            audit = record.write_audit or {}
            for loser_id in audit.get("close_on_replacement", []):
                # B2 (Benchmark Wave 2): supersession closes the
                # loser's validity window at the correcting
                # record's timestamp - the moment it stopped
                # being in force (whitelist write, see
                # METADATA_WHITELIST note).
                self.update_metadata(
                    loser_id, tier="archive",
                    superseded_with_replacement=True,
                    invalid_at=_dt_to_str(record.timestamp))
        elif outcome.verdict == "queued":
            self._conn.execute(
                "INSERT OR REPLACE INTO review_items(record_id, "
                "record_json, reasons, queued_at, resolved, resolution) "
                "VALUES (?, ?, ?, ?, 0, '')",
                (record.id, json.dumps(record_to_dict(record)),
                 json.dumps(outcome.reasons), at))
        elif outcome.verdict == "rejected":
            # If the gate rejected as an exact duplicate, it refreshed the
            # original's access count in-memory; persist that one field.
            for reason in outcome.reasons:
                if reason.startswith("exact duplicate of "):
                    dup_id = reason.split("exact duplicate of ", 1)[1]
                    dup_id = dup_id.split(";", 1)[0].strip()
                    if dup_id in existing:
                        self.update_metadata(
                            dup_id,
                            access_count=existing[dup_id].access_count)
        self._conn.commit()
        return outcome

    def _insert_sealed(self, r: MemoryRecord) -> None:
        """Insert one admitted record. Existing id -> SealedRecordError:
        history is never overwritten, corrections are new records."""
        # B2 (Benchmark Wave 2): ingest stamps the validity window
        # open at the record's own timestamp when the writer left
        # it unset (spec: valid_at = record timestamp when unset).
        if r.valid_at is None:
            r.valid_at = r.timestamp
        try:
            self._conn.execute(
                "INSERT INTO records(id, text, content, timestamp, source,"
                " salience, type, epistemic_tier, explicit, owner,"
                " gathered_how, consent_scope, tier, created_at,"
                " last_accessed, access_count, decay_score, ttl_class,"
                " invalidation_contract, superseded_with_replacement,"
                " episodic_record_id, prov_confidence, prov_contradicts,"
                " prov_supersedes, prov_valid_from, prov_recorded_at,"
                " write_audit, decay_exempt, valid_at, invalid_at,"
                " dispute_refs)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,"
                "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (r.id, r.text, r.content, _dt_to_str(r.timestamp),
                 r.source, r.salience, r.type, r.epistemic_tier,
                 1 if r.explicit else 0, r.owner, r.gathered_how,
                 r.consent_scope, r.tier, r.created_at, r.last_accessed,
                 r.access_count, r.decay_score, r.ttl_class,
                 r.invalidation_contract,
                 1 if r.superseded_with_replacement else 0,
                 r.episodic_record_id, r.provenance.confidence,
                 json.dumps(r.provenance.contradicts),
                 json.dumps(r.provenance.supersedes),
                 _dt_to_str(r.provenance.valid_from),
                 _dt_to_str(r.provenance.recorded_at),
                 json.dumps(r.write_audit),
                 1 if r.decay_exempt else 0,
                 _dt_to_str(r.valid_at),
                 _dt_to_str(r.invalid_at),
                 json.dumps(list(r.dispute_refs or []))))
        except sqlite3.IntegrityError as e:
            raise SealedRecordError(
                f"record {r.id!r} already exists - sealed records are "
                "never overwritten; write a correction as a NEW record "
                "with provenance.supersedes") from e

    # -- reads ------------------------------------------------------------

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        return record_from_dict({
            "id": row["id"], "text": row["text"],
            "content": row["content"], "timestamp": row["timestamp"],
            "source": row["source"], "salience": row["salience"],
            "type": row["type"], "epistemic_tier": row["epistemic_tier"],
            "explicit": bool(row["explicit"]), "owner": row["owner"],
            "gathered_how": row["gathered_how"],
            "consent_scope": row["consent_scope"], "tier": row["tier"],
            "created_at": row["created_at"],
            "last_accessed": row["last_accessed"],
            "access_count": row["access_count"],
            "decay_score": row["decay_score"],
            "ttl_class": row["ttl_class"],
            "invalidation_contract": row["invalidation_contract"],
            "superseded_with_replacement": bool(
                row["superseded_with_replacement"]),
            "episodic_record_id": row["episodic_record_id"],
            "provenance": {
                "confidence": row["prov_confidence"],
                "contradicts": json.loads(row["prov_contradicts"]),
                "supersedes": json.loads(row["prov_supersedes"]),
                "valid_from": row["prov_valid_from"],
                "recorded_at": row["prov_recorded_at"],
            },
            "write_audit": json.loads(row["write_audit"]),
            "decay_exempt": bool(row["decay_exempt"]),
            "valid_at": row["valid_at"],
            "invalid_at": row["invalid_at"],
            "dispute_refs": json.loads(row["dispute_refs"]),
        })

    def _get_raw(self, record_id: str) -> MemoryRecord | None:
        row = self._conn.execute(
            "SELECT * FROM records WHERE id = ?",
            (record_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def _snapshot(self) -> dict[str, MemoryRecord]:
        rows = self._conn.execute("SELECT * FROM records").fetchall()
        return {r["id"]: self._row_to_record(r) for r in rows}

    def snapshot(self) -> dict[str, MemoryRecord]:
        """The SYSTEM path: a full snapshot for in-process
        components (write gate input, janitor wiring, episode
        assembly's scans, consolidation). Never noted on the
        canary watch - system components scanning the store are
        not extractions (Red-Team Round 5)."""
        return self._snapshot()

    def _note_reads(self, records, actor: str) -> None:
        """Tell the canary watch (if wired) what a reader-facing
        read returned. Only canary records register - the watch
        itself decides."""
        if self.canary_watch is None:
            return
        for rec in records:
            self.canary_watch.note_access(rec.id, actor=actor)

    def get(self, record_id: str) -> MemoryRecord | None:
        rec = self._get_raw(record_id)
        if rec is not None:
            self._note_reads([rec], "raw")
        return rec

    def all_records(self) -> dict[str, MemoryRecord]:
        """Reader-facing full read: every record, noted on the
        canary watch as a raw-API read. In-process components
        that mean the system path use snapshot() instead."""
        snap = self._snapshot()
        self._note_reads(snap.values(), "raw")
        return snap

    @staticmethod
    def _rank(records, query: str,
              limit: int = 10) -> list[MemoryRecord]:
        """The one ranking rule: case-insensitive token overlap
        over text+content, salience as tiebreak weight,
        deterministic order (-score, id). Shared by the raw
        search and the authorized search so an authorized
        reader's ranking is provably the same function of the
        records they may see - and of nothing else."""
        tokens = {t for t in query.lower().split() if t}
        if not tokens:
            return []
        scored = []
        for rec in records:
            body = f"{rec.text} {rec.content}".lower()
            hits = sum(1 for t in tokens if t in body)
            if hits:
                scored.append((hits * (1.0 + rec.salience), rec))
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return [rec for _, rec in scored[:limit]]

    def _search_raw(self, query: str,
                    limit: int = 10) -> list[MemoryRecord]:
        return self._rank(self._snapshot().values(), query,
                          limit=limit)

    def search(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        """Minimal owned retrieval: case-insensitive token overlap over
        text+content, salience as tiebreak weight. Deterministic; the
        hybrid ranker (design doc 2.4) layers on top of this later."""
        out = self._search_raw(query, limit=limit)
        self._note_reads(out, "raw")
        return out

    # -- authorized reads (Red-Team Round 4, class A10 residue) ------
    # The read model for reader-facing surfaces: a ReaderContext
    # names who is asking and the authorizer decides per record
    # (mm/access_control.py). Denied == absent: get_for returns
    # None for a forbidden id exactly as for a missing one, so
    # the API is not an existence oracle. The raw reads above
    # remain the in-process system path.

    def _reader_bound(self, reader: ReaderContext,
                      token: str | None) -> bool:
        """Red-Team Round 5 identity binding for reads: a
        REGISTERED reader id must present its capability token.
        Denial is indistinguishable from absence, per Round 4 -
        an unbound read returns exactly what a forbidden one
        does. System readers are the in-process boundary and
        are not token-bound (declared in mm/identity.py)."""
        auth = self.identity_authority
        if auth is None or reader.system:
            return True
        if not auth.is_reader_registered(reader.reader_id):
            return True
        return auth.verify_reader(token, reader.reader_id)

    def get_for(self, reader: ReaderContext,
                record_id: str,
                token: str | None = None) -> MemoryRecord | None:
        if not self._reader_bound(reader, token):
            return None
        rec = self._get_raw(record_id)
        if rec is None:
            return None
        ok, _ = self.authorizer.can_read(reader, rec)
        if not ok:
            return None
        self._note_reads([rec], reader.reader_id)
        return rec

    def search_for(self, reader: ReaderContext, query: str,
                   limit: int = 10,
                   token: str | None = None) -> list[MemoryRecord]:
        """Authorize-then-rank (Red-Team Round 6). Round 4's
        version ranked over the FULL store and filtered the
        top 3*limit afterwards: the withheld records were
        never returned, but they shaped the answer - returned
        counts dropped when restricted records occupied the
        window (an existence oracle), planted probe records
        were displaced by invisible ones (a rank/vocabulary
        oracle), and an authorized reader could be served an
        EMPTY page while their own matching records sat below
        the window (measured recall@10 0.000). Now the
        snapshot is filtered through the authorizer FIRST and
        the unchanged ranking runs over the authorized subset
        alone: the result is a pure function of what this
        reader may see, identical whether or not any
        restricted record exists."""
        if not self._reader_bound(reader, token):
            return []
        allowed = self.authorizer.filter_records(
            reader, self._snapshot())
        out = self._rank(allowed.values(), query, limit=limit)
        self._note_reads(out, reader.reader_id)
        return out

    def all_records_for(self,
                        reader: ReaderContext,
                        token: str | None = None
                        ) -> dict[str, MemoryRecord]:
        if not self._reader_bound(reader, token):
            return {}
        out = self.authorizer.filter_records(reader,
                                             self._snapshot())
        self._note_reads(out.values(), reader.reader_id)
        return out

    # -- the ONLY post-insert mutation path (lifecycle whitelist) --------

    def update_metadata(self, record_id: str, **fields) -> None:
        """Mutate lifecycle metadata ONLY. Any content field raises
        SealedRecordError - the seal is enforced here, not by convention."""
        bad = set(fields) - METADATA_WHITELIST
        if bad:
            raise SealedRecordError(
                f"fields {sorted(bad)} are sealed content; only "
                f"{sorted(METADATA_WHITELIST)} may change after insert")
        if not fields:
            return
        if record_id not in self:
            raise KeyError(f"unknown record {record_id!r}")
        sets, vals = [], []
        for k, v in fields.items():
            if k == "superseded_with_replacement":
                v = 1 if v else 0
            if k == "dispute_refs":
                v = json.dumps(list(v or []))
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(record_id)
        self._conn.execute(
            f"UPDATE records SET {', '.join(sets)} WHERE id = ?", vals)
        self._conn.commit()

    def sync_metadata(self, rec: MemoryRecord) -> None:
        """Persist a (possibly janitor-mutated) record's lifecycle fields."""
        self.update_metadata(
            rec.id, tier=rec.tier, last_accessed=rec.last_accessed,
            access_count=rec.access_count, decay_score=rec.decay_score,
            superseded_with_replacement=rec.superseded_with_replacement)

    # -- review queue (persisted) ------------------------------------------

    def pending_review(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM review_items WHERE resolved = 0").fetchall()
        return [{"record": record_from_dict(json.loads(r["record_json"])),
                 "reasons": json.loads(r["reasons"]),
                 "queued_at": r["queued_at"]} for r in rows]

    def resolve_review(self, record_id: str, resolution: str) -> bool:
        cur = self._conn.execute(
            "UPDATE review_items SET resolved = 1, resolution = ? "
            "WHERE record_id = ? AND resolved = 0",
            (resolution, record_id))
        self._conn.commit()
        return cur.rowcount > 0

    def gate_log(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM gate_log ORDER BY seq").fetchall()
        return [{"record_id": r["record_id"], "verdict": r["verdict"],
                 "reasons": json.loads(r["reasons"]), "at": r["at"]}
                for r in rows]

    # -- access events + janitor wiring -------------------------------------

    def log_access(self, record_id: str, at: float,
                   kind: str = "retrieval", actor: str = "",
                   query: str = "") -> None:
        self._conn.execute(
            "INSERT INTO access_events(record_id, at, kind, actor, "
            "query) VALUES (?, ?, ?, ?, ?)",
            (record_id, at, kind, actor, query))
        self._conn.commit()

    def access_events(self) -> list[AccessEvent]:
        rows = self._conn.execute(
            "SELECT * FROM access_events ORDER BY seq").fetchall()
        return [AccessEvent(record_id=r["record_id"], at=r["at"],
                            kind=r["kind"],
                            actor=r["actor"] or "",
                            query=r["query"] or "") for r in rows]

    def load_janitor(self,
                     attributed_resurrection: bool = False) -> Janitor:
        """A Janitor pre-loaded with the persisted access log, so
        half-life estimation survives restarts. Deployments pass
        attributed_resurrection=True to wire the Round-4 A14ii
        fix (only attributed, non-owner accesses resurrect)."""
        j = Janitor(
            attributed_resurrection=attributed_resurrection)
        j.access_log = self.access_events()
        return j

    def run_janitor(self, janitor: Janitor, now: float,
                    dry_run: bool = False) -> JanitorReport:
        """One wired lifecycle pass against the real store.

        Dry-run changes nothing (store or log). A live run persists:
        lifecycle metadata for every touched record + any access events
        the janitor logged during the pass (e.g. rehydration hits)."""
        records = self._snapshot()
        known_events = len(janitor.access_log)
        report = janitor.run(records, now, dry_run=dry_run)
        if not dry_run:
            touched = {op.record_id for op in report.ops}
            for rid in touched:
                if rid in records:
                    self.sync_metadata(records[rid])
            for ev in janitor.access_log[known_events:]:
                self.log_access(ev.record_id, ev.at, ev.kind,
                                actor=ev.actor, query=ev.query)
        return report
