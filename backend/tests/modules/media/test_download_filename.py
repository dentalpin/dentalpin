"""Unit pins for download filename sanitization (#560).

The stored filename comes from the uploader, so header-breaking
characters must never reach Content-Disposition verbatim.
"""

import pytest

from app.modules.media.router import _safe_filename


def test_safe_filename_keeps_plain_names():
    assert _safe_filename("informe.pdf") == "informe.pdf"


@pytest.mark.parametrize(
    "raw",
    [
        'evil".pdf',
        "back\\slash.pdf",
        "line\nbreak.pdf",
        "carriage\rreturn.pdf",
    ],
)
def test_safe_filename_strips_header_breakers(raw):
    cleaned = _safe_filename(raw)
    assert '"' not in cleaned
    assert "\\" not in cleaned
    assert cleaned.isprintable()


@pytest.mark.parametrize("raw", [None, "", "   ", '"""'])
def test_safe_filename_falls_back_to_document(raw):
    assert _safe_filename(raw) == "document"


def test_safe_filename_keeps_unicode_letters():
    assert _safe_filename("presupuesto-año.pdf") == "presupuesto-año.pdf"
