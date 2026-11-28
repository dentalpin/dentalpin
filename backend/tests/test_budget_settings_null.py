"""Budget settings: no null in, no 500 out (#1276).

``PATCH /auth/clinic/settings/budget`` stored an explicit ``null`` for
the day settings, then answered 500 because the reader did ``int(None)``
— after the commit. From then on ``GET`` answered 500 too, so the
settings page could not load the value to fix it.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic

URL = "/api/v1/auth/clinic/settings/budget"
DAY_KEYS = ("budget_expiry_days", "plan_auto_close_days_after_expiry")
ALL_KEYS = (*DAY_KEYS, "budget_reminders_enabled", "budget_public_auth_disabled")


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ALL_KEYS)
async def test_patch_rejects_null_and_stores_nothing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
    key: str,
) -> None:
    r = await client.patch(URL, json={key: None}, headers=auth_headers)
    assert r.status_code == 422, r.text

    await db_session.refresh(test_clinic)
    assert key not in (test_clinic.settings or {})


@pytest.mark.asyncio
@pytest.mark.parametrize("key", DAY_KEYS)
@pytest.mark.parametrize("value", [6, 181, 0, -5])
async def test_patch_rejects_out_of_range_days(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    key: str,
    value: int,
) -> None:
    r = await client.patch(URL, json={key: value}, headers=auth_headers)
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_patch_still_accepts_valid_values_and_partial_updates(
    client: AsyncClient, auth_headers: dict[str, str], test_clinic: Clinic
) -> None:
    r = await client.patch(
        URL,
        json={"budget_expiry_days": 45, "plan_auto_close_days_after_expiry": 7},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    r = await client.patch(URL, json={"budget_reminders_enabled": True}, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["budget_expiry_days"] == 45
    assert data["plan_auto_close_days_after_expiry"] == 7
    assert data["budget_reminders_enabled"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [None, "abc", True, 0, 9999, 12.5])
async def test_get_falls_back_to_default_for_a_stored_bad_value(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    db_session: AsyncSession,
    bad: object,
) -> None:
    """Rows written before the PATCH rejected null must not 500 the page."""
    test_clinic.settings = {
        **(test_clinic.settings or {}),
        "budget_expiry_days": bad,
        "plan_auto_close_days_after_expiry": bad,
    }
    await db_session.commit()

    r = await client.get(URL, headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["budget_expiry_days"] == 30
    assert data["plan_auto_close_days_after_expiry"] == 30

    # And the admin can save a real value over it.
    r = await client.patch(
        URL, json={"plan_auto_close_days_after_expiry": 60}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["plan_auto_close_days_after_expiry"] == 60
