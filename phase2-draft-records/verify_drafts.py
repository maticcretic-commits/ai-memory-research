"""Verify Phase 2 draft records.

Checks, for each of the three draft records (J5, N9, S4):
- the file exists;
- status is DRAFT, owner is UNASSIGNED, and the record states it
  certifies nothing;
- at least five TBD fields are named;
- a blank signature block is present (underscores, no filled name);
- no lock or certification claim is made ("is locked", "is certified",
  "hereby certifies" must not appear).

This checker verifies form only. It does not sign, freeze, or certify
anything, and it cannot detect an invented name or number by itself:
the records were written with TBD placeholders throughout, and the
checker is one control among the Round 7 rules, not a substitute for
reading them.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
RECORDS = ("DRAFT-RECORD-J5.md", "DRAFT-RECORD-N9.md", "DRAFT-RECORD-S4.md")
FORBIDDEN = ("is locked", "is certified", "hereby certifies", "hereby approves")


def check(path: pathlib.Path) -> list[str]:
    failures: list[str] = []
    if not path.exists():
        return [f"missing file: {path.name}"]
    text = path.read_text(encoding="utf-8")
    for required in ("Status: DRAFT", "Owner: UNASSIGNED", "certifies nothing"):
        if required not in text:
            failures.append(f"{path.name}: missing {required!r}")
    if text.count("TBD") < 5:
        failures.append(f"{path.name}: fewer than 5 TBD fields")
    if "___________________________" not in text:
        failures.append(f"{path.name}: no blank signature block")
    lowered = text.lower()
    for phrase in FORBIDDEN:
        if phrase in lowered:
            failures.append(f"{path.name}: forbidden claim {phrase!r}")
    return failures


def main() -> int:
    failures: list[str] = []
    for name in RECORDS:
        failures.extend(check(HERE / name))
    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"OK: {len(RECORDS)} draft records, all DRAFT, owner UNASSIGNED, TBD fields named, signatures blank.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
