"""Reason intervals stay within the 0..60 months the settings panel offers.

Before #1244 ``PUT /recalls/settings`` stored any integer: a negative
interval suggested a recall already overdue, and a huge one overflowed
``date`` so ``GET /recalls/suggestions/next`` answered 500.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.patients.models import Patient
from app.modules.recalls.service import RecallSettingsService

SUGGEST = "/api/v1/recalls/suggestions/next?patient_id={pid}&treatment_category_key=preventivo"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-6, -1, 61, 600, 100000, 6.5, True, "6"])
async def test_put_rejects_interval_outside_panel_range(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, bad
):
    res = await client.put(
        "/api/v1/recalls/settings",
        json={"reason_intervals": {"hygiene": bad}},
        headers=auth_headers,
    )
    assert res.status_code == 422, res.text

    stored = (await client.get("/api/v1/recalls/settings", headers=auth_headers)).json()["data"]
    assert stored["reason_intervals"]["hygiene"] == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("good", [0, 1, 60])
async def test_put_accepts_interval_bounds(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, good
):
    res = await client.put(
        "/api/v1/recalls/settings",
        json={"reason_intervals": {"hygiene": good}},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["reason_intervals"]["hygiene"] == good


@pytest.mark.asyncio
async def test_zero_interval_means_no_suggestion(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
):
    await client.put(
        "/api/v1/recalls/settings",
        json={"reason_intervals": {"hygiene": 0}},
        headers=auth_headers,
    )
    res = await client.get(SUGGEST.format(pid=test_patient.id), headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["data"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [-6, 61, 100000])
async def test_suggestion_skips_stored_out_of_range_interval(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    legacy: int,
):
    """A row saved before the bound existed gives no suggestion, not a 500
    or a recall that is overdue on creation."""
    settings = await RecallSettingsService.get_or_create(db_session, test_clinic.id)
    settings.reason_intervals = {**settings.reason_intervals, "hygiene": legacy}
    await db_session.commit()

    res = await client.get(SUGGEST.format(pid=test_patient.id), headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["data"] is None
