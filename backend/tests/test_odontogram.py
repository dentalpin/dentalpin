"""Tests for odontogram module endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership, User
from app.core.auth.service import hash_password


@pytest.fixture
async def odontogram_setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    """Set up a clinic with patient for odontogram tests."""
    # Get user from /me endpoint
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = response.json()["data"]["user"]["id"]

    # Create clinic
    clinic = Clinic(
        id=uuid4(),
        name="Test Dental Clinic",
        tax_id="B12345678",
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
        role="dentist",  # Dentist has odontogram permissions
    )
    db_session.add(membership)
    await db_session.commit()

    # Create patient via API
    patient_response = await client.post(
        "/api/v1/patients",
        headers=auth_headers,
        json={
            "first_name": "Juan",
            "last_name": "Garcia",
            "phone": "+34666123456",
            "email": "juan@example.com",
        },
    )
    patient_id = patient_response.json()["data"]["id"]

    return {
        "clinic_id": str(clinic.id),
        "user_id": user_id,
        "patient_id": patient_id,
    }


@pytest.mark.asyncio
async def test_get_empty_odontogram(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test getting odontogram for patient with no records."""
    patient_id = odontogram_setup["patient_id"]

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["patient_id"] == patient_id
    assert len(data["teeth"]) == 0
    assert "condition_colors" in data
    assert "available_conditions" in data
    assert "surfaces" in data


@pytest.mark.asyncio
async def test_create_tooth_record(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test creating a new tooth record."""
    patient_id = odontogram_setup["patient_id"]

    response = await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/11",
        headers=auth_headers,
        json={
            "general_condition": "healthy",
            "surface_updates": [
                {"surface": "O", "condition": "caries"},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tooth_number"] == 11
    assert data["tooth_type"] == "permanent"
    assert data["general_condition"] == "healthy"
    assert data["surfaces"]["O"] == "caries"
    assert data["surfaces"]["M"] == "healthy"


@pytest.mark.asyncio
async def test_update_tooth_surfaces(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test updating multiple surfaces on a tooth."""
    patient_id = odontogram_setup["patient_id"]

    # Create initial record
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/16",
        headers=auth_headers,
        json={"general_condition": "healthy"},
    )

    # Update surfaces
    response = await client.patch(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/16",
        headers=auth_headers,
        json={
            "surface_updates": [
                {"surface": "O", "condition": "filling"},
                {"surface": "M", "condition": "caries"},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["surfaces"]["O"] == "filling"
    assert data["surfaces"]["M"] == "caries"
    assert data["surfaces"]["D"] == "healthy"  # Unchanged


@pytest.mark.asyncio
async def test_get_full_odontogram(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test getting full odontogram after adding teeth."""
    patient_id = odontogram_setup["patient_id"]

    # Create records for several teeth
    teeth = [11, 12, 21, 36]
    for tooth_num in teeth:
        await client.put(
            f"/api/v1/odontogram/patients/{patient_id}/teeth/{tooth_num}",
            headers=auth_headers,
            json={"general_condition": "healthy"},
        )

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["teeth"]) == 4


@pytest.mark.asyncio
async def test_bulk_update_teeth(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test bulk updating multiple teeth at once."""
    patient_id = odontogram_setup["patient_id"]

    response = await client.patch(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/bulk",
        headers=auth_headers,
        json={
            "updates": [
                {
                    "tooth_number": 14,
                    "general_condition": "crown",
                    "surface_updates": [{"surface": "O", "condition": "crown"}],
                },
                {
                    "tooth_number": 15,
                    "general_condition": "missing",
                },
                {
                    "tooth_number": 16,
                    "surface_updates": [
                        {"surface": "O", "condition": "filling"},
                        {"surface": "M", "condition": "filling"},
                    ],
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 3

    # Verify each tooth
    tooth_14 = next(t for t in data if t["tooth_number"] == 14)
    assert tooth_14["general_condition"] == "crown"

    tooth_15 = next(t for t in data if t["tooth_number"] == 15)
    assert tooth_15["general_condition"] == "missing"

    tooth_16 = next(t for t in data if t["tooth_number"] == 16)
    assert tooth_16["surfaces"]["O"] == "filling"
    assert tooth_16["surfaces"]["M"] == "filling"


@pytest.mark.asyncio
async def test_get_tooth_history(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test getting history for a specific tooth."""
    patient_id = odontogram_setup["patient_id"]

    # Create initial record
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/26",
        headers=auth_headers,
        json={"general_condition": "healthy"},
    )

    # Update it a few times
    await client.patch(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/26",
        headers=auth_headers,
        json={"surface_updates": [{"surface": "O", "condition": "caries"}]},
    )

    await client.patch(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/26",
        headers=auth_headers,
        json={"surface_updates": [{"surface": "O", "condition": "filling"}]},
    )

    # Get history
    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/26/history",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3  # Created + 2 updates


@pytest.mark.asyncio
async def test_get_patient_odontogram_history(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test getting complete odontogram history for a patient."""
    patient_id = odontogram_setup["patient_id"]

    # Create several tooth records
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/11",
        headers=auth_headers,
        json={"general_condition": "healthy"},
    )
    await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/21",
        headers=auth_headers,
        json={"general_condition": "caries"},
    )

    # Get full history
    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/history",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2


@pytest.mark.asyncio
async def test_invalid_tooth_number(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test that invalid tooth numbers are rejected."""
    patient_id = odontogram_setup["patient_id"]

    # 99 is not a valid FDI tooth number
    response = await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/99",
        headers=auth_headers,
        json={"general_condition": "healthy"},
    )
    assert response.status_code == 400
    assert "Invalid tooth number" in response.json()["message"]


@pytest.mark.asyncio
async def test_invalid_condition(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test that invalid conditions are rejected."""
    patient_id = odontogram_setup["patient_id"]

    response = await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/11",
        headers=auth_headers,
        json={"general_condition": "invalid_condition"},
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_invalid_surface(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test that invalid surfaces are rejected."""
    patient_id = odontogram_setup["patient_id"]

    response = await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/11",
        headers=auth_headers,
        json={
            "surface_updates": [{"surface": "X", "condition": "caries"}],
        },
    )
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_deciduous_teeth(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test that deciduous teeth are handled correctly."""
    patient_id = odontogram_setup["patient_id"]

    # 51 is a deciduous tooth (upper right central incisor)
    response = await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/51",
        headers=auth_headers,
        json={"general_condition": "caries"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tooth_number"] == 51
    assert data["tooth_type"] == "deciduous"
    assert data["general_condition"] == "caries"


@pytest.mark.asyncio
async def test_tooth_notes(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test adding clinical notes to a tooth."""
    patient_id = odontogram_setup["patient_id"]

    response = await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/36",
        headers=auth_headers,
        json={
            "general_condition": "root_canal",
            "notes": "Root canal treatment completed. Post scheduled for 2 weeks.",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["notes"] == "Root canal treatment completed. Post scheduled for 2 weeks."


@pytest.mark.asyncio
async def test_patient_not_found(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test accessing odontogram for non-existent patient."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/odontogram/patients/{fake_id}/odontogram",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient, odontogram_setup: dict) -> None:
    """Test that unauthenticated requests are rejected."""
    patient_id = odontogram_setup["patient_id"]

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram",
    )
    assert response.status_code == 401


@pytest.fixture
async def receptionist_setup(
    db_session: AsyncSession, client: AsyncClient, odontogram_setup: dict
) -> dict:
    """Set up a receptionist user (no odontogram.write permission)."""
    clinic_id = odontogram_setup["clinic_id"]

    # Create receptionist user
    receptionist = User(
        id=uuid4(),
        email="receptionist@test.clinic",
        password_hash=hash_password("TestPass12345"),
        first_name="Test",
        last_name="Receptionist",
        is_active=True,
    )
    db_session.add(receptionist)
    await db_session.flush()

    # Create receptionist membership
    membership = ClinicMembership(
        id=uuid4(),
        user_id=receptionist.id,
        clinic_id=clinic_id,
        role="receptionist",
    )
    db_session.add(membership)
    await db_session.commit()

    # Login as receptionist (using form data as expected by OAuth2PasswordRequestForm)
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "receptionist@test.clinic",
            "password": "TestPass12345",
        },
    )
    login_data = login_response.json()
    if "access_token" not in login_data:
        raise ValueError(f"Login failed: {login_data}")
    token = login_data["access_token"]

    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "patient_id": odontogram_setup["patient_id"],
    }


@pytest.mark.asyncio
async def test_receptionist_cannot_write_odontogram(
    client: AsyncClient, receptionist_setup: dict
) -> None:
    """Test that receptionists cannot modify odontogram."""
    patient_id = receptionist_setup["patient_id"]
    headers = receptionist_setup["headers"]

    response = await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/11",
        headers=headers,
        json={"general_condition": "caries"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_receptionist_cannot_read_odontogram(
    client: AsyncClient, receptionist_setup: dict
) -> None:
    """Test that receptionists cannot read odontogram."""
    patient_id = receptionist_setup["patient_id"]
    headers = receptionist_setup["headers"]

    response = await client.get(
        f"/api/v1/odontogram/patients/{patient_id}/odontogram",
        headers=headers,
    )
    assert response.status_code == 403


# ============================================================================
# Treatment Tests
# ============================================================================
@pytest.mark.asyncio
async def test_treatment_not_found(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test getting a non-existent treatment."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await client.get(
        f"/api/v1/odontogram/treatments/{fake_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_positional_fields_on_tooth_record(
    client: AsyncClient, auth_headers: dict[str, str], odontogram_setup: dict
) -> None:
    """Test updating positional fields (displaced/rotated) on tooth record."""
    patient_id = odontogram_setup["patient_id"]

    # Create tooth with positional markers
    response = await client.put(
        f"/api/v1/odontogram/patients/{patient_id}/teeth/43",
        headers=auth_headers,
        json={
            "general_condition": "healthy",
            "is_displaced": True,
            "is_rotated": True,
            "displacement_notes": "Rotated 15 degrees mesially",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["is_displaced"] is True
    assert data["is_rotated"] is True
    assert data["displacement_notes"] == "Rotated 15 degrees mesially"
