"""Tests for odontogram timeline endpoints."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership


@pytest.fixture
async def timeline_setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    """Set up a clinic with patient for timeline tests."""
    # Get user from /me endpoint
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = response.json()["data"]["user"]["id"]

    # Create clinic
    clinic = Clinic(
        id=uuid4(),
        name="Timeline Test Clinic",
        tax_id="B98765432",
        address={"street": "Test St", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(clinic)
    await db_session.flush()

    # Create dentist membership for user
    membership = ClinicMembership(
        id=uuid4(),
        user_id=user_id,
        clinic_id=clinic.id,
        role="dentist",
    )
    db_session.add(membership)
    await db_session.commit()

    # Create patient via API
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={
            "first_name": "Maria",
            "last_name": "Timeline",
            "phone": "+34666789012",
            "email": "maria@example.com",
        },
    )
    patient_id = patient_response.json()["data"]["id"]

    return {
        "clinic_id": str(clinic.id),
        "user_id": user_id,
        "patient_id": patient_id,
    }


@pytest.mark.asyncio
async def test_get_timeline_empty(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test getting timeline for patient with no history."""
    patient_id = timeline_setup["patient_id"]

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram/timeline",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 0
    assert data["dates"] == []


@pytest.mark.asyncio
async def test_get_timeline_single_date(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test timeline shows single date after one modification."""
    patient_id = timeline_setup["patient_id"]

    # Create a tooth record
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/11",
        headers=auth_headers,
        json={"general_condition": "caries"},
    )

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram/timeline",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["dates"]) == 1
    assert data["dates"][0]["change_count"] >= 1


@pytest.mark.asyncio
async def test_get_timeline_multiple_dates_from_history(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test timeline aggregates changes by date."""
    patient_id = timeline_setup["patient_id"]

    # Create multiple tooth records (same day)
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/11",
        headers=auth_headers,
        json={"general_condition": "caries"},
    )
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/12",
        headers=auth_headers,
        json={"general_condition": "filling"},
    )
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/21",
        headers=auth_headers,
        json={"general_condition": "healthy"},
    )

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram/timeline",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    # All changes on same day = 1 date entry
    assert data["total"] == 1
    # Multiple changes aggregated
    assert data["dates"][0]["change_count"] >= 3


@pytest.mark.asyncio
async def test_get_odontogram_at_date_returns_empty_state(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test getting odontogram at date before any modifications."""
    patient_id = timeline_setup["patient_id"]

    # Create some current state
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/11",
        headers=auth_headers,
        json={"general_condition": "caries"},
    )

    # Query for date in the past (before creation)
    # UTC: the state above was written with the server clock, so a local
    # "yesterday" east of UTC is still today in UTC and the row shows up.
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram/at?date={yesterday}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    # No teeth at that date
    assert len(data["teeth"]) == 0
    assert len(data["treatments"]) == 0


@pytest.mark.asyncio
async def test_get_odontogram_at_date_includes_metadata(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test that historical odontogram includes all metadata."""
    patient_id = timeline_setup["patient_id"]

    # Create state
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/36",
        headers=auth_headers,
        json={"general_condition": "root_canal"},
    )

    today = date.today().isoformat()
    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram/at?date={today}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]

    # Should include standard odontogram metadata
    assert "condition_colors" in data
    assert "available_conditions" in data
    assert "surfaces" in data
    assert data["patient_id"] == patient_id


@pytest.mark.asyncio
async def test_timeline_patient_not_found(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test timeline endpoint with non-existent patient."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/odontogram/patients/{fake_id}/odontogram/timeline",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_odontogram_at_date_patient_not_found(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test odontogram at date endpoint with non-existent patient."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    today = date.today().isoformat()

    response = await client.get(
        f"/api/v1/odontogram/patients/{fake_id}/odontogram/at?date={today}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_odontogram_at_date_invalid_date_format(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test odontogram at date endpoint with invalid date format."""
    patient_id = timeline_setup["patient_id"]

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram/at?date=invalid-date",
        headers=auth_headers,
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_timeline_unauthorized(client: AsyncClient, timeline_setup: dict) -> None:
    """Test timeline endpoint without authentication."""
    patient_id = timeline_setup["patient_id"]

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram/timeline",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_surface_updates_tracked_in_timeline(
    client: AsyncClient, auth_headers: dict[str, str], timeline_setup: dict
) -> None:
    """Test that surface updates are included in timeline."""
    patient_id = timeline_setup["patient_id"]

    # Create tooth then update surfaces
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/46",
        headers=auth_headers,
        json={"general_condition": "healthy"},
    )
    await client.patch(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/46",
        headers=auth_headers,
        json={"surface_updates": [{"surface": "O", "condition": "caries"}]},
    )
    await client.patch(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/46",
        headers=auth_headers,
        json={"surface_updates": [{"surface": "O", "condition": "filling"}]},
    )

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram/timeline",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    # All changes on same day
    assert data["total"] >= 1
    # Multiple changes tracked
    assert data["dates"][0]["change_count"] >= 3
