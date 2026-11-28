"""Tolerant readers for values stored in ``Clinic.settings`` (JSONB).

``clinic.settings`` is free-form JSON, so a stored value can be anything
an older build, a manual edit or an import wrote. The budget day
settings used to be read with a bare ``int(...)``: one stored ``null``
made ``GET /clinic/settings/budget`` answer 500 and stopped the nightly
plan auto-close cron for every clinic (#1276). Readers go through here
and fall back to the default instead.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

# Bounds the budget settings PATCH enforces for ``budget_expiry_days``
# and ``plan_auto_close_days_after_expiry`` (core/auth/router.py).
BUDGET_DAYS_MIN = 7
BUDGET_DAYS_MAX = 180


def read_budget_days_setting(settings: Mapping[str, Any] | None, key: str, default: int) -> int:
    """Return ``settings[key]`` as a day count within the PATCH bounds.

    A missing key returns ``default`` silently. A stored value that is not
    a whole number in ``BUDGET_DAYS_MIN..BUDGET_DAYS_MAX`` (``null``, a
    string, a bool, out of range) also returns ``default``, with a warning
    so the bad row can be found and fixed.
    """
    if not settings or key not in settings:
        return default
    raw = settings[key]
    value: int | None = None
    if isinstance(raw, int) and not isinstance(raw, bool):
        value = raw
    elif isinstance(raw, str) and raw.strip().isdigit():
        value = int(raw.strip())
    if value is None or not BUDGET_DAYS_MIN <= value <= BUDGET_DAYS_MAX:
        logger.warning(
            "clinic setting %s has invalid value %r; using default %d",
            key,
            raw,
            default,
        )
        return default
    return value
