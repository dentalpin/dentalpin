"""Booking can always be switched off once its professional left (#1149)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from booking_helpers import configure, professional
from sqlalchemy import delete

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.online_booking.models import BookingSettings

SETTINGS = "/api/v1/online_booking/settings"


async def _remove_membership(db, clinic_id, user_id):
    await db.execute(
        delete(ClinicMembership).where(
            ClinicMembership.user_id == user_id, ClinicMembership.clinic_id == clinic_id
        )
    )
    await db.commit()


async def _stale_settings(client, db_session, auth_headers, test_clinic):
    pro = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, pro.id)
    await _remove_membership(db_session, test_clinic.id, pro.id)
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    current = await client.get(SETTINGS, headers=headers)
    assert current.status_code == 200
    assert current.json()["data"]["professional_id"] == str(pro.id)
    return headers, current.json()["data"]


@pytest.mark.asyncio
async def test_disabling_with_a_removed_professional_saves_and_clears_it(
    client, db_session, auth_headers, test_clinic
):
    headers, config = await _stale_settings(client, db_session, auth_headers, test_clinic)
    saved = await client.put(SETTINGS, headers=headers, json={**config, "enabled": False})
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["enabled"] is False
    assert saved.json()["data"]["professional_id"] is None
    stored = await db_session.get(BookingSettings, test_clinic.id, populate_existing=True)
    assert stored.enabled is False
    assert stored.professional_id is None
    public = await client.get(f"/api/v1/online_booking/public/{test_clinic.id}/config")
    assert public.status_code == 404


@pytest.mark.asyncio
async def test_enabling_with_a_removed_professional_is_still_refused(
    client, db_session, auth_headers, test_clinic
):
    headers, config = await _stale_settings(client, db_session, auth_headers, test_clinic)
    saved = await client.put(SETTINGS, headers=headers, json={**config, "enabled": True})
    assert saved.status_code == 422
    assert "Invalid professional" in saved.json()["message"]


@pytest.mark.asyncio
async def test_a_foreign_clinics_professional_is_never_stored(
    client, db_session, auth_headers, test_clinic
):
    other = Clinic(id=uuid4(), name="Other Clinic", tax_id="B87654321", address={}, settings={})
    db_session.add(other)
    await db_session.flush()
    foreign = await professional(db_session, other.id)
    await db_session.commit()
    headers = {**auth_headers, "X-Clinic-ID": str(test_clinic.id)}
    config = (await client.get(SETTINGS, headers=headers)).json()["data"]
    body = {**config, "enabled": False, "professional_id": str(foreign.id)}
    saved = await client.put(SETTINGS, headers=headers, json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["professional_id"] is None
    stored = await db_session.get(BookingSettings, test_clinic.id, populate_existing=True)
    assert stored.professional_id is None
    enabled = await client.put(
        SETTINGS,
        headers=headers,
        json={**body, "enabled": True, "public_url": "https://example.invalid/book"},
    )
    assert enabled.status_code == 422
