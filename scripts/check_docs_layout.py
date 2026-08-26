#!/usr/bin/env python3
"""Enforce the `/docs` folder taxonomy (issue #67).

CI fails if any of the following is violated:

1. A markdown file lives at `docs/` root that is NOT in the root allowlist.
2. A folder exists directly under `docs/` that is NOT in the folder allowlist.
3. An image asset (`.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp`) lives
   anywhere under `docs/` outside `docs/screenshots/` or `docs/diagrams/`.
4. `docs/adr/` breaks its numbering contract (issue #299): a file that
   doesn't match ``NNNN-kebab-title.md``, two ADRs sharing a number
   (PR #291 shipped a second 0009 and every check stayed green), a gap
   in the sequence (ADRs are never deleted, only superseded), or a
   first-line heading whose number disagrees with the filename.

The taxonomy + routing rule is documented in:
- root `CLAUDE.md` ("Documentation policy")
- `docs/README.md` (decision tree + folder descriptions)

Run::

    python scripts/check_docs_layout.py            # exit 1 on violations
    python scripts/check_docs_layout.py --list     # print the allowlists

Mirrors the read-only posture of ``backend/scripts/generate_catalogs.py``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"

ROOT_FILES_ALLOWED: frozenset[str] = frozenset(
    {
        "README.md",
        "glossary.md",
        "events-catalog.md",
        "modules-catalog.md",
    }
)

FOLDERS_ALLOWED: frozenset[str] = frozenset(
    {
        "user-manual",
        "features",
        "technical",
        "modules",
        "adr",
        "checklists",
        "diagrams",
        "screenshots",
        "workflows",
        # VitePress portal that renders the rest of /docs (ADR 0009).
        # It owns the build pipeline only — no documentation content lives
        # here. See docs/portal/README.md.
        "portal",
    }
)

IMAGE_EXTS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
)
IMAGE_FOLDERS: frozenset[str] = frozenset({"screenshots", "diagrams"})

ADR_NON_NUMBERED: frozenset[str] = frozenset({"README.md", "TEMPLATE.md"})
ADR_FILENAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
# First line of every ADR: "# NNNN — Title" (em dash, per TEMPLATE.md).
ADR_HEADING = re.compile(r"^# (\d{4}) — \S")


def check_adrs(adr_dir: Path) -> list[str]:
    """The `docs/adr/` numbering contract (issue #299).

    The README states it ("zero-padded sequence, never reused; never
    delete an ADR, supersede it") and PR #291 proved nothing enforced
    it: a second 0009 merged cleanly because the *filenames* differed.
    Since #300 removed the hand-maintained index, the directory listing
    IS the index — these invariants are what keep it trustworthy.
    """
    violations: list[str] = []
    if not adr_dir.is_dir():
        return [f"{adr_dir} is not a directory — nothing to check."]

    by_number: dict[int, list[str]] = {}
    for entry in sorted(adr_dir.iterdir()):
        if entry.name.startswith(".") or entry.name in ADR_NON_NUMBERED:
            continue
        match = ADR_FILENAME.match(entry.name)
        if entry.is_dir() or not match:
            violations.append(
                f"docs/adr/{entry.name}: does not match NNNN-kebab-title.md "
                "(zero-padded number, lowercase kebab-case, .md)."
            )
            continue
        number = int(match.group(1))
        by_number.setdefault(number, []).append(entry.name)

        heading = entry.read_text(encoding="utf-8").split("\n", 1)[0]
        heading_match = ADR_HEADING.match(heading)
        if not heading_match:
            violations.append(
                f"docs/adr/{entry.name}: first line must be "
                f"'# {match.group(1)} — <title>', found {heading!r}."
            )
        elif heading_match.group(1) != match.group(1):
            violations.append(
                f"docs/adr/{entry.name}: heading number "
                f"{heading_match.group(1)} disagrees with the filename. "
                "One of them is wrong — check which number is actually free."
            )

    for number, names in sorted(by_number.items()):
        if len(names) > 1:
            violations.append(
                f"docs/adr/: number {number:04d} is used by {len(names)} "
                f"files ({', '.join(names)}). ADR numbers are never reused — "
                "renumber the newest to the next free number."
            )

    if by_number:
        expected = set(range(1, max(by_number) + 1))
        for missing in sorted(expected - set(by_number)):
            violations.append(
                f"docs/adr/: number {missing:04d} is missing from the "
                "sequence. ADRs are never deleted — supersede instead "
                "(see docs/adr/README.md)."
            )

    return violations


def check() -> list[str]:
    violations: list[str] = []

    if not DOCS.is_dir():
        return [f"{DOCS} is not a directory — nothing to check."]

    for entry in sorted(DOCS.iterdir()):
        if entry.name.startswith("."):
            continue  # ignore .DS_Store etc — git ignores them anyway
        if entry.is_file():
            if entry.suffix == ".md" and entry.name not in ROOT_FILES_ALLOWED:
                violations.append(
                    f"docs/{entry.name}: markdown not allowed at docs/ root. "
                    "Move to a topic folder (see docs/README.md)."
                )
            elif entry.suffix in IMAGE_EXTS:
                violations.append(
                    f"docs/{entry.name}: image at docs/ root. "
                    "Move to docs/screenshots/ or docs/diagrams/."
                )
        elif entry.is_dir() and entry.name not in FOLDERS_ALLOWED:
            violations.append(
                f"docs/{entry.name}/: folder not in the taxonomy. "
                f"Allowed folders: {', '.join(sorted(FOLDERS_ALLOWED))}."
            )

    # Image-placement check across the whole docs/ tree.
    for path in DOCS.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        rel = path.relative_to(DOCS)
        top = rel.parts[0] if rel.parts else ""
        if top not in IMAGE_FOLDERS:
            violations.append(
                f"docs/{rel.as_posix()}: image outside docs/screenshots/ "
                "or docs/diagrams/."
            )

    violations.extend(check_adrs(DOCS / "adr"))

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the allowlists and exit 0.",
    )
    args = parser.parse_args()

    if args.list:
        print("Root files allowed:")
        for name in sorted(ROOT_FILES_ALLOWED):
            print(f"  {name}")
        print("\nTopic folders allowed:")
        for name in sorted(FOLDERS_ALLOWED):
            print(f"  {name}/")
        print(f"\nImage extensions: {', '.join(sorted(IMAGE_EXTS))}")
        print(f"Image folders only: {', '.join(sorted(IMAGE_FOLDERS))}")
        return 0

    violations = check()
    if violations:
        print("docs layout violations:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print(
            "\nSee docs/README.md and the 'Documentation policy' section "
            "of root CLAUDE.md for the taxonomy.",
            file=sys.stderr,
        )
        return 1

    print("docs layout OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
