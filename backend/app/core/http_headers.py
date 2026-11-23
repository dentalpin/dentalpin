"""Response header helpers."""

from __future__ import annotations

import unicodedata
from urllib.parse import quote


def content_disposition(filename: str) -> str:
    """``attachment`` header for any filename (RFC 6266, #1015).

    Starlette encodes headers as latin-1, so a raw ``ő`` or ``–`` in a name
    raised on the way out. Such a name goes in ``filename*``, next to an
    ASCII fallback. The caller strips quotes and control characters.
    """
    if filename.isascii():
        return f'attachment; filename="{filename}"'
    plain = unicodedata.normalize("NFKD", filename)
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    fallback = "".join(c if c.isascii() else "_" for c in plain)
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"
