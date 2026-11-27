"""A printed timestamp is the clinic's local time, never the server's.

A PDF is handed to a patient or filed by the clinic, so the hour on it
has to be the hour they experienced. Two shapes went wrong in the tree:

- ``date.today().strftime("%d/%m/%Y %H:%M")`` — a ``date`` has no time,
  so the footer always read **00:00**. Fixed in ``billing/pdf.py`` at the
  time (#204) and left standing in ``budget/pdf.py`` until #705.
- ``datetime.now()`` / a ``timestamptz`` column rendered as-is — the
  first is the *server's* zone (UTC in the container), the second is UTC
  because that is what the column holds. A budget signed at 01:15 in
  Madrid printed "23:15" on the signed PDF.

``billing/pdf.py`` and ``documents/pdf.py`` are the reference: resolve
``ZoneInfo(clinic.timezone or "UTC")`` once, then
``datetime.now(clinic_tz)`` for "now" and ``.astimezone(clinic_tz)``
before formatting a stored instant.

What this guard checks, and what it cannot: it sees the two shapes above
— a ``now()``/``today()`` without a zone, and a time-of-day format
applied to something that was not converted. A **date-only** format on a
``timestamptz`` column is invisible to it, because the same format is
correct on a ``Date`` column and a static scan cannot tell the two
apart; that is the shape the prescriptions date had (#705), and it needs
a reader, not a regex.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

TIME_OF_DAY = re.compile(r"%[HMIS]")


def _pdf_sources() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(APP_ROOT.rglob("pdf.py")):
        if "__pycache__" in path.parts:
            continue
        out.append((str(path.relative_to(APP_ROOT.parent)), path.read_text(encoding="utf-8")))
    return out


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        owner = func.value
        prefix = owner.id if isinstance(owner, ast.Name) else ""
        return f"{prefix}.{func.attr}" if prefix else func.attr
    return getattr(func, "id", "")


def test_pdf_renderers_stamp_the_clinic_timezone() -> None:
    sources = _pdf_sources()
    assert len(sources) >= 4, f"PDF renderer sweep looks wrong: {len(sources)} files"

    offenders: list[str] = []
    checked = 0

    for rel, src in sources:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)

            # 1. "now" without a timezone, and date.today() at all: both
            #    produce a value in the wrong zone (or no time at all).
            if name in ("datetime.now", "date.today") and not node.args and not node.keywords:
                checked += 1
                offenders.append(
                    f"  {rel}:{node.lineno}: {name}() has no timezone — use datetime.now(clinic_tz)"
                )
                continue

            # 2b. the shared helper prints ``HH:MM`` too (#1180): its first
            #     argument must already be in the clinic's zone.
            if name == "format_pdf_datetime" and node.args:
                checked += 1
                value = ast.get_source_segment(src, node.args[0]) or ""
                if "astimezone(" in value or re.search(r"\bnow\(\s*[^)\s]", value):
                    continue
                offenders.append(
                    f"  {rel}:{node.lineno}: format_pdf_datetime({' '.join(value.split())!r}) "
                    "prints a time without converting to the clinic's zone"
                )
                continue

            # 2. a time-of-day format applied to a value nobody converted
            if name.endswith("strftime") and node.args:
                fmt = node.args[0]
                literal = fmt.value if isinstance(fmt, ast.Constant) else ""
                if not isinstance(literal, str) or not TIME_OF_DAY.search(literal):
                    continue
                checked += 1
                receiver = ast.get_source_segment(src, node.func) or ""
                if "astimezone(" in receiver:
                    continue
                if re.search(r"\bnow\(\s*[^)\s]", receiver):  # now(<zone>)
                    continue
                offenders.append(
                    f"  {rel}:{node.lineno}: {' '.join(receiver.split())!r} formats "
                    f"{literal!r} without converting to the clinic's zone"
                )

    assert checked > 3, f"timestamp sweep looks wrong: {checked} call sites"
    assert not offenders, "\n".join(
        [
            "printed timestamps that are not the clinic's local time:",
            *offenders,
            "",
            "Resolve the zone once — ZoneInfo(clinic.timezone or 'UTC') — as "
            "billing/pdf.py and documents/pdf.py do, then datetime.now(tz) "
            "for 'now' and .astimezone(tz) before formatting a stored value.",
        ]
    )
