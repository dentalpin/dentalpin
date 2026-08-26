"""Shared catalog-name resolution for display surfaces.

Catalog items store their names as i18n JSONB (``{"es": ..., "en": ...}``).
Every surface that renders a human-readable treatment name — invoices,
plans, notes, timeline seeds, agent tools — resolves that dict through
this single helper instead of hand-rolled ``names.get(...)`` chains.

History: each locale PR used to edit five scattered copies of the chain
(#275 follow-ups); payments/service.py even kept a bare ``es → en`` with
no catch-all. Centralizing means a new language (e.g. ``ar``) is one
tuple append away from being resolved everywhere.
"""

from __future__ import annotations

# Preferred display order. The clinic's operative language is Spanish
# historically; English is the universal fallback. Everything after is
# best-effort before the any-non-empty catch-all below.
CATALOG_NAME_PRIORITY: tuple[str, ...] = (
    "es",
    "en",
    "fr",
    "pt",
    "ta",
    "de",
    "hu",
    "ar",
)


def catalog_name(names: dict | None) -> str | None:
    """Resolve a display name from a catalog ``names`` JSONB dict.

    Priority order per :data:`CATALOG_NAME_PRIORITY`, then any non-empty
    translation (items created under a core-only locale never degrade to
    ``None``/internal code), else ``None``. Whitespace-only strings are
    treated as missing.
    """
    if not isinstance(names, dict):
        return None

    def usable(value: object) -> bool:
        return bool(isinstance(value, str) and value.strip())

    for lang in CATALOG_NAME_PRIORITY:
        value = names.get(lang)
        if usable(value):
            return value  # type: ignore[return-value]
    return next((v for v in names.values() if usable(v)), None)
