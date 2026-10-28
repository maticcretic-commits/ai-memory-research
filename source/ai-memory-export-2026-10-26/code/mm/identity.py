"""identity - non-malleable identity binding (Red-Team Round 5).

Rounds 3-4 priced DECLARED identities at zero, and both records
said the residue out loud: the trust registry's identity is an
(owner, source-root) pair of strings anyone can type, and
Round 4's ReaderContext is equally a declared string. A lane
that can simply TYPE the founder lane's owner has the founder
lane's standing - the registry and the authorizer both reason
about claims, and a claim costs nothing to copy. This module
is Fo's strong form (corpus 3358) as a first increment:
provenance bound to something held, not something said.

Design: capability tokens, issued in-process.

- An IdentityAuthority is the deployment's registrar. At lane
  registration it issues an opaque token (256 bits from the
  OS CSPRNG) bound to exactly one principal: a WRITER
  principal (owner, source root) - the registry's identity -
  or a READER principal (reader_id).
- The authority keeps ONLY SHA-256 hashes of tokens (its
  sidecar persists hashes, never tokens). Verification hashes
  the presented token and compares the binding. A token
  verifies for its own principal and no other: replaying a
  stolen token under different strings fails the binding
  comparison, not just the hash lookup.
- Re-registration ROTATES: the old token's hash is dropped
  and stops verifying immediately. Revocation is explicit.
- Tokens never appear in record content, gate logs, or the
  store's tables. Content is data; no code path in this
  program consults record content as a credential - a token
  string pasted into a record is inert text there (harness
  class E3 measures exactly that).

Enforcement is wiring-shaped, like Rounds 2-4 (the store
takes identity_authority=...; defaults unchanged):

- store.write(record, token=None): if the record's writer
  identity is REGISTERED, the write is refused at the store
  boundary unless the token verifies for that identity -
  refused before the gate runs, so a spoof accrues no track
  record and pollutes no dispute surface. Unregistered
  identities keep the legacy declared path.
- get_for / search_for / all_records_for(reader, ...,
  token=None): if the reader_id is REGISTERED and the reader
  is not a system reader, reads deny (indistinguishable from
  absence, per Round 4) unless the token verifies for that
  reader_id.

What this CAN and CANNOT prove (stated, not hidden): a token
is a capability - in-process, whoever presents it IS the
principal. Binding kills spoofing-by-declaration (typing the
victim's strings), cross-principal replay (binding mismatch),
and theft-from-content (tokens are never in content). It
cannot stop an attacker who has already stolen the token
object itself, or who calls the raw in-process APIs - that is
the same declared trust boundary Rounds 1-4 drew around the
raw store API and the system reader: code inside the process
is trusted; the binding disciplines every path a PRINCIPAL
touches, it does not pretend a process can distrust itself.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets

from mm.source_trust import source_root

_TOKEN_BYTES = 32  # 256-bit capabilities


def _hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def writer_identity(owner: str, source: str) -> tuple[str, str]:
    """The registry's writer identity for (owner, source):
    (owner normalised, source root) - one meaning of 'who is
    speaking' across the gate, the registry, and this module."""
    return ((owner or "").strip().lower(), source_root(source))


class IdentityAuthority:
    """Registrar + verifier for capability-bound identities."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path
        # sha256(token) -> binding. Writer bindings are
        # ("writer", owner, root); reader bindings ("reader", id).
        self._tokens: dict[str, tuple] = {}
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for h, b in raw.items():
                self._tokens[h] = tuple(b)

    # -- registration ---------------------------------------------------

    def register_writer(self, owner: str, source: str) -> str:
        """Issue (or rotate) the capability for a writer
        identity. Any previous token for this identity dies."""
        ident = writer_identity(owner, source)
        self._drop_binding(("writer",) + ident)
        return self._issue(("writer",) + ident)

    def register_reader(self, reader_id: str) -> str:
        """Issue (or rotate) the capability for a reader id."""
        rid = (reader_id or "").strip()
        self._drop_binding(("reader", rid))
        return self._issue(("reader", rid))

    def revoke_writer(self, owner: str, source: str) -> bool:
        return self._drop_binding(
            ("writer",) + writer_identity(owner, source))

    def revoke_reader(self, reader_id: str) -> bool:
        return self._drop_binding(("reader", (reader_id or "").strip()))

    # -- queries ----------------------------------------------------------

    def is_writer_registered(self, owner: str, source: str) -> bool:
        ident = ("writer",) + writer_identity(owner, source)
        return ident in self._tokens.values()

    def is_reader_registered(self, reader_id: str) -> bool:
        return ("reader", (reader_id or "").strip()) \
            in self._tokens.values()

    def registered_writers(self) -> list[tuple[str, str]]:
        return sorted((b[1], b[2]) for b in self._tokens.values()
                      if b[0] == "writer")

    def registered_readers(self) -> list[str]:
        return sorted(b[1] for b in self._tokens.values()
                      if b[0] == "reader")

    # -- verification -------------------------------------------------------

    def verify_writer(self, token: str | None, owner: str,
                      source: str) -> bool:
        """True only if `token` is a live capability bound to
        exactly this (owner, source root) identity."""
        if not token:
            return False
        binding = self._tokens.get(_hash(token))
        if binding is None:
            return False
        return hmac.compare_digest(
            repr(binding), repr(("writer",)
                                + writer_identity(owner, source)))

    def verify_reader(self, token: str | None, reader_id: str) -> bool:
        if not token:
            return False
        binding = self._tokens.get(_hash(token))
        if binding is None:
            return False
        return hmac.compare_digest(
            repr(binding),
            repr(("reader", (reader_id or "").strip())))

    # -- internals ----------------------------------------------------------

    def _issue(self, binding: tuple) -> str:
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        self._tokens[_hash(token)] = binding
        self._save()
        return token

    def _drop_binding(self, binding: tuple) -> bool:
        dead = [h for h, b in self._tokens.items() if b == binding]
        for h in dead:
            del self._tokens[h]
        if dead:
            self._save()
        return bool(dead)

    def _save(self) -> None:
        if not self.path:
            return
        raw = {h: list(b) for h, b in self._tokens.items()}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, sort_keys=True)
        os.replace(tmp, self.path)


__all__ = ["IdentityAuthority", "writer_identity"]
