"""Tests for professionals feature - associating appointments with professionals."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password


@pytest.fixture
async def clinic_with_professionals(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    """Set up a clinic with admin, dentist, and hygienist users."""
    # Get admin user from /me endpoint (wrapped in ApiResponse)
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    admin_user_id = response.json()["data"]["user"]["id"]

    # Create clinic
    clinic = Clinic(
        id=uuid4(),
        name="Professional Test Clinic",
        tax_id="B12345678",
        address={"street": "Test St", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(clinic)
    await db_session.flush()

    # Create admin membership
    admin_membership = ClinicMembership(
        id=uuid4(),
        user_id=admin_user_id,
        clinic_id=clinic.id,
        role="admin",
    )
    db_session.add(admin_membership)

    # Create dentist user
    dentist = User(
        id=uuid4(),
        email="dentist@test.com",
        password_hash=hash_password("TestPass123"),
        first_name="Dr. Juan",
        last_name="Dentista",
        is_active=True,
    )
    db_session.add(dentist)
    await db_session.flush()

    dentist_membership = ClinicMembership(
        id=uuid4(),
        user_id=dentist.id,
        clinic_id=clinic.id,
        role="dentist",
    )
    db_session.add(dentist_membership)

    # Create hygienist user
    hygienist = User(
        id=uuid4(),
        email="hygienist@test.com",
        password_hash=hash_password("TestPass123"),
        first_name="Maria",
        last_name="Higienista",
        is_active=True,
    )
    db_session.add(hygienist)
    await db_session.flush()

    hygienist_membership = ClinicMembership(
        id=uuid4(),
        user_id=hygienist.id,
        clinic_id=clinic.id,
        role="hygienist",
    )
    db_session.add(hygienist_membership)

    # Create receptionist user (should NOT appear in professionals list)
    receptionist = User(
        id=uuid4(),
        email="receptionist@test.com",
        password_hash=hash_password("TestPass123"),
        first_name="Ana",
        last_name="Recepcion",
        is_active=True,
    )
    db_session.add(receptionist)
    await db_session.flush()

    receptionist_membership = ClinicMembership(
        id=uuid4(),
        user_id=receptionist.id,
        clinic_id=clinic.id,
        role="receptionist",
    )
    db_session.add(receptionist_membership)

    # Create inactive dentist (should NOT appear in professionals list)
    inactive_dentist = User(
        id=uuid4(),
        email="inactive@test.com",
        password_hash=hash_password("TestPass123"),
        first_name="Pedro",
        last_name="Inactivo",
        is_active=False,
    )
    db_session.add(inactive_dentist)
    await db_session.flush()

    inactive_membership = ClinicMembership(
        id=uuid4(),
        user_id=inactive_dentist.id,
        clinic_id=clinic.id,
        role="dentist",
    )
    db_session.add(inactive_membership)

    # Default cabinet so appointment tests resolve the cabinet FK.
    from app.modules.agenda.models import Cabinet

    db_session.add(
        Cabinet(
            id=uuid4(),
            clinic_id=clinic.id,
            name="Gabinete 1",
            color="#3B82F6",
            display_order=0,
            is_active=True,
        )
    )

    await db_session.commit()

    return {
        "clinic_id": str(clinic.id),
        "admin_id": admin_user_id,
        "dentist_id": str(dentist.id),
        "hygienist_id": str(hygienist.id),
        "receptionist_id": str(receptionist.id),
        "inactive_dentist_id": str(inactive_dentist.id),
    }


# =============================================================================
# GET /api/v1/auth/professionals tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_professionals(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test that professionals endpoint returns only dentists and hygienists (PaginatedApiResponse)."""
    response = await client.get("/api/v1/auth/professionals", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()["data"]
    assert len(data) == 2  # Only dentist and hygienist

    # Check that all returned professionals have valid roles
    roles = {p["role"] for p in data}
    assert roles == {"dentist", "hygienist"}

    # Check structure
    for prof in data:
        assert "id" in prof
        assert "email" in prof
        assert "first_name" in prof
        assert "last_name" in prof
        assert "role" in prof


@pytest.mark.asyncio
async def test_list_professionals_excludes_inactive(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test that inactive professionals are excluded."""
    response = await client.get("/api/v1/auth/professionals", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()["data"]
    professional_ids = {p["id"] for p in data}

    # Inactive dentist should not be in the list
    assert clinic_with_professionals["inactive_dentist_id"] not in professional_ids


@pytest.mark.asyncio
async def test_list_professionals_excludes_non_professionals(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test that non-professional roles (receptionist, admin) are excluded."""
    response = await client.get("/api/v1/auth/professionals", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()["data"]
    professional_ids = {p["id"] for p in data}

    # Receptionist and admin should not be in the list
    assert clinic_with_professionals["receptionist_id"] not in professional_ids
    assert clinic_with_professionals["admin_id"] not in professional_ids


@pytest.mark.asyncio
async def test_list_professionals_without_auth(client: AsyncClient) -> None:
    """Test that professionals endpoint requires authentication."""
    response = await client.get("/api/v1/auth/professionals")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_marked_professional_is_listed_and_schedulable(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
    db_session: AsyncSession,
) -> None:
    """An admin with ``is_professional`` appears in the list and can take appointments.

    Professional-ness is a membership flag, not a role — a solo
    admin-dentist must not need a second user account (Telegram
    report, 2026-07-31).
    """
    from uuid import UUID as _UUID

    from sqlalchemy import update

    admin_id = clinic_with_professionals["admin_id"]
    await db_session.execute(
        update(ClinicMembership)
        .where(
            ClinicMembership.user_id == _UUID(admin_id),
            ClinicMembership.clinic_id == _UUID(clinic_with_professionals["clinic_id"]),
        )
        .values(is_professional=True)
    )
    await db_session.commit()

    # Listed, with the admin role intact.
    response = await client.get("/api/v1/auth/professionals", headers=auth_headers)
    assert response.status_code == 200
    by_id = {p["id"]: p for p in response.json()["data"]}
    assert admin_id in by_id
    assert by_id[admin_id]["role"] == "admin"

    # And accepted as the professional on an appointment.
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Solo", "last_name": "Clinic"},
    )
    patient_id = patient_response.json()["data"]["id"]

    response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": admin_id,
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-02T10:00:00Z",
            "end_time": "2026-05-02T10:30:00Z",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["professional_id"] == admin_id


# =============================================================================
# Professional validation in appointments
# =============================================================================


@pytest.mark.asyncio
async def test_create_appointment_with_valid_professional(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test creating appointment with a valid professional (dentist)."""
    # Create patient first (wrapped in ApiResponse)
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    patient_id = patient_response.json()["data"]["id"]

    # Create appointment with dentist (wrapped in ApiResponse)
    response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_with_professionals["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-01T10:00:00Z",
            "end_time": "2026-05-01T10:30:00Z",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["professional_id"] == clinic_with_professionals["dentist_id"]


@pytest.mark.asyncio
async def test_create_appointment_with_hygienist(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test creating appointment with a hygienist."""
    # Create patient first (wrapped in ApiResponse)
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    patient_id = patient_response.json()["data"]["id"]

    # Create appointment with hygienist (wrapped in ApiResponse)
    response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_with_professionals["hygienist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-01T11:00:00Z",
            "end_time": "2026-05-01T11:30:00Z",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["professional_id"] == clinic_with_professionals["hygienist_id"]


@pytest.mark.asyncio
async def test_create_appointment_with_invalid_professional_role(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test that creating appointment with non-professional role fails."""
    # Create patient first (wrapped in ApiResponse)
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    patient_id = patient_response.json()["data"]["id"]

    # Try to create appointment with receptionist (should fail)
    response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_with_professionals["receptionist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-01T12:00:00Z",
            "end_time": "2026-05-01T12:30:00Z",
        },
    )
    assert response.status_code == 400
    assert "Invalid professional" in response.json()["message"]


@pytest.mark.asyncio
async def test_create_appointment_with_nonexistent_professional(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test that creating appointment with non-existent professional fails."""
    # Create patient first (wrapped in ApiResponse)
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    patient_id = patient_response.json()["data"]["id"]

    # Try to create appointment with non-existent professional
    response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": "00000000-0000-0000-0000-000000000000",
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-01T13:00:00Z",
            "end_time": "2026-05-01T13:30:00Z",
        },
    )
    assert response.status_code == 400
    assert "Invalid professional" in response.json()["message"]


@pytest.mark.asyncio
async def test_update_appointment_professional(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test updating appointment to a different professional."""
    # Create patient first (wrapped in ApiResponse)
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    patient_id = patient_response.json()["data"]["id"]

    # Create appointment with dentist (wrapped in ApiResponse)
    create_response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_with_professionals["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-02T10:00:00Z",
            "end_time": "2026-05-02T10:30:00Z",
        },
    )
    appointment_id = create_response.json()["data"]["id"]

    # Update to hygienist (wrapped in ApiResponse)
    update_response = await client.put(
        f"/api/v1/agenda/appointments/{appointment_id}",
        headers=auth_headers,
        json={"professional_id": clinic_with_professionals["hygienist_id"]},
    )
    assert update_response.status_code == 200
    assert (
        update_response.json()["data"]["professional_id"]
        == clinic_with_professionals["hygienist_id"]
    )


@pytest.mark.asyncio
async def test_update_appointment_to_invalid_professional(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test that updating appointment to invalid professional fails."""
    # Create patient first (wrapped in ApiResponse)
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    patient_id = patient_response.json()["data"]["id"]

    # Create appointment with dentist (wrapped in ApiResponse)
    create_response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_with_professionals["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-03T10:00:00Z",
            "end_time": "2026-05-03T10:30:00Z",
        },
    )
    appointment_id = create_response.json()["data"]["id"]

    # Try to update to receptionist (should fail)
    update_response = await client.put(
        f"/api/v1/agenda/appointments/{appointment_id}",
        headers=auth_headers,
        json={"professional_id": clinic_with_professionals["receptionist_id"]},
    )
    assert update_response.status_code == 400
    assert "Invalid professional" in update_response.json()["message"]


# =============================================================================
# Professional included in appointment response
# =============================================================================


@pytest.mark.asyncio
async def test_appointment_response_includes_professional(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test that appointment response includes professional info."""
    # Create patient first (wrapped in ApiResponse)
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    patient_id = patient_response.json()["data"]["id"]

    # Create appointment (wrapped in ApiResponse)
    create_response = await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_with_professionals["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-04T10:00:00Z",
            "end_time": "2026-05-04T10:30:00Z",
        },
    )
    assert create_response.status_code == 201
    data = create_response.json()["data"]

    # Check professional is included
    assert "professional" in data
    assert data["professional"] is not None
    assert data["professional"]["id"] == clinic_with_professionals["dentist_id"]
    assert data["professional"]["first_name"] == "Dr. Juan"
    assert data["professional"]["last_name"] == "Dentista"


@pytest.mark.asyncio
async def test_list_appointments_includes_professional(
    client: AsyncClient,
    auth_headers: dict[str, str],
    clinic_with_professionals: dict,
) -> None:
    """Test that listing appointments includes professional info."""
    # Create patient first (wrapped in ApiResponse)
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={"first_name": "Test", "last_name": "Patient"},
    )
    patient_id = patient_response.json()["data"]["id"]

    # Create appointment
    await client.post(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        json={
            "patient_id": patient_id,
            "professional_id": clinic_with_professionals["dentist_id"],
            "cabinet": "Gabinete 1",
            "start_time": "2026-05-05T10:00:00Z",
            "end_time": "2026-05-05T10:30:00Z",
        },
    )

    # List appointments (PaginatedApiResponse)
    response = await client.get(
        "/api/v1/agenda/appointments",
        headers=auth_headers,
        params={"start_date": "2026-05-05T00:00:00Z", "end_date": "2026-05-05T23:59:59Z"},
    )
    assert response.status_code == 200
    data = response.json()

    assert len(data["data"]) == 1
    appointment = data["data"][0]
    assert "professional" in appointment
    assert appointment["professional"]["first_name"] == "Dr. Juan"
