"""A deactivated or removed professional is no longer bookable online (#1100)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from booking_helpers import configure, professional, tomorrow_at
from sqlalchemy import delete

from app.core.auth.models import ClinicMembership
from app.modules.online_booking.exceptions import BookingConflictError, BookingValidationError
from app.modules.online_booking.models import BookingRequest
from app.modules.online_booking.schemas import SettingsInput
from app.modules.online_booking.service import BookingService, reserve

REQUEST = {
    "contact_name": "Synthetic",
    "contact_email": "synthetic@example.com",
    "reason": "checkup",
}


async def _public(client, clinic_id):
    url = f"/api/v1/online_booking/public/{clinic_id}"
    day = tomorrow_at(10).date().isoformat()
    availability = await client.get(f"{url}/availability", params={"day": day})
    request = await client.post(
        f"{url}/requests", json={**REQUEST, "start_time": tomorrow_at(10).isoformat()}
    )
    return availability, request


@pytest.mark.asyncio
async def test_active_professional_stays_bookable(
    client, db_session, test_clinic, open_hours, delivery
):
    pro = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, pro.id)
    availability, request = await _public(client, test_clinic.id)
    assert availability.status_code == 200
    assert availability.json()["data"]["starts"]
    assert request.status_code == 201


@pytest.mark.asyncio
async def test_deactivated_professional_is_not_bookable(
    client, db_session, test_clinic, open_hours, delivery
):
    pro = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, pro.id)
    pro.is_active = False
    await db_session.commit()
    availability, request = await _public(client, test_clinic.id)
    assert availability.status_code == 404
    assert request.status_code == 404
    assert (
        await client.get(f"/api/v1/online_booking/public/{test_clinic.id}/config")
    ).status_code == 404


@pytest.mark.asyncio
async def test_removed_professional_is_not_bookable(
    client, db_session, test_clinic, open_hours, delivery
):
    pro = await professional(db_session, test_clinic.id)
    await configure(db_session, test_clinic.id, pro.id)
    await db_session.execute(
        delete(ClinicMembership).where(
            ClinicMembership.user_id == pro.id, ClinicMembership.clinic_id == test_clinic.id
        )
    )
    await db_session.commit()
    availability, request = await _public(client, test_clinic.id)
    assert availability.status_code == 404
    assert request.status_code == 404


@pytest.mark.asyncio
async def test_reserve_rechecks_the_professional_under_the_lock(
    db_session, test_clinic, open_hours
):
    """Deactivation between the public check and the lock still refuses the hold."""
    pro = await professional(db_session, test_clinic.id)
    config = await configure(db_session, test_clinic.id, pro.id)
    pro.is_active = False
    await db_session.commit()
    start = tomorrow_at(10)
    item = BookingRequest(
        clinic_id=test_clinic.id,
        professional_id=pro.id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        status="pending_confirmation",
        reason="checkup",
        confirmation_deadline=datetime.now(UTC) + timedelta(minutes=10),
    )
    with pytest.raises(BookingConflictError):
        await reserve(db_session, test_clinic.id, config, item, datetime.now(UTC))


@pytest.mark.asyncio
async def test_settings_cannot_enable_booking_for_an_inactive_professional(db_session, test_clinic):
    pro = await professional(db_session, test_clinic.id)
    pro.is_active = False
    await db_session.commit()
    data = SettingsInput(
        enabled=True, public_url="https://example.invalid/book", professional_id=pro.id
    )
    with pytest.raises(BookingValidationError):
        await BookingService.update_settings(db_session, test_clinic.id, data)
    # Saving a disabled configuration that still names them stays possible.
    await BookingService.update_settings(
        db_session, test_clinic.id, data.model_copy(update={"enabled": False})
    )
