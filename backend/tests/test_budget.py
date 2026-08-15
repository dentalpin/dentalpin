"""Tests for the budget module."""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.budget.pricing import allocate_global_discount, net_line_amount
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory, VatType
from app.modules.patients.models import Patient


@pytest.fixture
async def budget_clinic_setup(
    db_session: AsyncSession, auth_headers: dict[str, str], client: AsyncClient
) -> dict:
    """Set up a clinic with patient and catalog item for budget tests."""
    # Get user from /me endpoint
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = response.json()["data"]["user"]["id"]

    # Create clinic
    clinic = Clinic(
        id=uuid4(),
        name="Budget Test Clinic",
        tax_id="B99999999",
        address={"street": "Budget St", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(clinic)
    await db_session.flush()

    # Create admin membership
    membership = ClinicMembership(
        id=uuid4(),
        user_id=user_id,
        clinic_id=clinic.id,
        role="admin",
    )
    db_session.add(membership)

    # Create VAT type
    vat_type = VatType(
        id=uuid4(),
        clinic_id=clinic.id,
        names={"es": "Exento", "en": "Exempt"},
        rate=0.0,
        is_default=True,
        is_system=True,
    )
    db_session.add(vat_type)
    await db_session.flush()

    # Create category
    category = TreatmentCategory(
        id=uuid4(),
        clinic_id=clinic.id,
        key="test_category",
        names={"es": "Test", "en": "Test"},
        display_order=1,
        is_active=True,
        is_system=False,
    )
    db_session.add(category)
    await db_session.flush()

    # Create catalog item
    catalog_item = TreatmentCatalogItem(
        id=uuid4(),
        clinic_id=clinic.id,
        category_id=category.id,
        internal_code="TEST-001",
        names={"es": "Tratamiento Test", "en": "Test Treatment"},
        descriptions={"es": "Descripción", "en": "Description"},
        default_price=100.00,
        vat_type_id=vat_type.id,
        treatment_scope="whole_tooth",
        is_diagnostic=False,
        is_active=True,
        is_system=False,
    )
    db_session.add(catalog_item)

    # Create patient
    patient = Patient(
        id=uuid4(),
        clinic_id=clinic.id,
        first_name="Test",
        last_name="Patient",
        email="patient@test.com",
        phone="+34600000000",
        status="active",
    )
    db_session.add(patient)

    await db_session.commit()

    return {
        "clinic_id": str(clinic.id),
        "user_id": user_id,
        "patient_id": str(patient.id),
        "catalog_item_id": str(catalog_item.id),
        "vat_type_id": str(vat_type.id),
    }


# ============================================================================
# Budget CRUD Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_budgets(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test listing budgets."""
    response = await client.get(
        "/api/v1/budget/budgets",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert "total" in data
    assert "page" in data


@pytest.mark.asyncio
async def test_create_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test creating a budget."""
    response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["patient"]["id"] == budget_clinic_setup["patient_id"]
    assert data["status"] == "draft"
    assert data["version"] == 1
    assert "budget_number" in data
    assert data["budget_number"].startswith("PRES-")


@pytest.mark.asyncio
async def test_get_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test getting a single budget."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Get budget
    response = await client.get(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == budget_id


@pytest.mark.asyncio
async def test_update_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test updating a budget."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Update budget
    response = await client.put(
        f"/api/v1/budget/budgets/{budget_id}",
        json={
            "valid_until": "2024-12-31",
            "patient_notes": "Test notes",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["valid_until"] == "2024-12-31"
    assert data["patient_notes"] == "Test notes"


@pytest.mark.asyncio
async def test_delete_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test soft-deleting a budget."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Delete budget
    response = await client.delete(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    # Verify it's deleted (should return 404)
    get_response = await client.get(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


# ============================================================================
# Budget Item Tests
# ============================================================================


@pytest.mark.asyncio
async def test_add_item_to_budget(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test adding an item to a budget."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Add item
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 2,
            "tooth_number": 11,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["catalog_item_id"] == budget_clinic_setup["catalog_item_id"]
    assert data["quantity"] == 2
    assert data["tooth_number"] == 11
    assert float(data["unit_price"]) == 100.00
    assert float(data["line_total"]) == 200.00


@pytest.mark.asyncio
async def test_update_budget_item(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test updating a budget item."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Add item
    item_response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )
    item_id = item_response.json()["data"]["id"]

    # Update item
    response = await client.put(
        f"/api/v1/budget/budgets/{budget_id}/items/{item_id}",
        json={
            "quantity": 3,
            "notes": "Updated notes",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["quantity"] == 3
    assert data["notes"] == "Updated notes"
    assert float(data["line_total"]) == 300.00


@pytest.mark.asyncio
async def test_remove_budget_item(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test removing an item from a budget."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Add item
    item_response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )
    item_id = item_response.json()["data"]["id"]

    # Remove item
    response = await client.delete(
        f"/api/v1/budget/budgets/{budget_id}/items/{item_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    # Verify budget has no items and totals no longer count the removed line
    budget_response = await client.get(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
    )
    data = budget_response.json()["data"]
    assert len(data["items"]) == 0
    assert float(data["subtotal"]) == 0.0
    assert float(data["total"]) == 0.0


@pytest.mark.asyncio
async def test_item_with_discount(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test adding an item with discount."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Add item with percentage discount
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
            "discount_type": "percentage",
            "discount_value": 10,  # 10% discount
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert float(data["line_discount"]) == 10.00  # 10% of 100
    assert float(data["line_total"]) == 90.00


@pytest.mark.asyncio
async def test_update_item_explicit_null_clears_discount(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """PUT with ``discount_*: null`` clears the line discount and totals follow;
    ``null`` on a NOT NULL field (quantity) is ignored, not applied."""
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={"patient_id": budget_clinic_setup["patient_id"], "valid_from": "2024-01-01"},
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]
    item = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
            "discount_type": "percentage",
            "discount_value": 10,
            "notes": "keep me",
        },
        headers=auth_headers,
    )
    item_id = item.json()["data"]["id"]

    r = await client.put(
        f"/api/v1/budget/budgets/{budget_id}/items/{item_id}",
        json={"discount_type": None, "discount_value": None, "quantity": None},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["discount_type"] is None
    assert data["discount_value"] is None
    assert float(data["line_discount"]) == 0.00
    assert float(data["line_total"]) == 100.00
    assert data["quantity"] == 1  # null on NOT NULL field ignored
    assert data["notes"] == "keep me"  # omitted field untouched

    budget = await client.get(f"/api/v1/budget/budgets/{budget_id}", headers=auth_headers)
    assert float(budget.json()["data"]["total"]) == 100.00


# ============================================================================
# Workflow Tests
# ============================================================================


@pytest.mark.asyncio
async def test_send_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test sending a budget to patient."""
    # Create budget with items
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Add item
    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )

    # Send budget
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/send",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "sent"


@pytest.mark.asyncio
async def test_accept_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test accepting a budget."""
    # Create and send budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/send",
        json={},
        headers=auth_headers,
    )

    # Accept budget with signature
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/accept",
        json={
            "signature": {
                "signed_by_name": "Test Patient",
                "relationship_to_patient": "patient",
            }
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "accepted"


@pytest.mark.asyncio
async def test_reject_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test rejecting a budget."""
    # Create and send budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/send",
        json={},
        headers=auth_headers,
    )

    # Reject budget
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/reject",
        json={
            "signature": {
                "signed_by_name": "Test Patient",
                "relationship_to_patient": "patient",
            }
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "rejected"


@pytest.mark.asyncio
async def test_cancel_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test cancelling a budget."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Cancel budget
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/cancel",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "cancelled"


@pytest.mark.asyncio
async def test_duplicate_budget(client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict):
    """Test duplicating a budget creates a new version."""
    # Create budget with items
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]
    budget_number = create_response.json()["data"]["budget_number"]

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )

    # Duplicate budget
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/duplicate",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["version"] == 2
    assert data["budget_number"] == budget_number  # Same number
    assert data["status"] == "draft"
    assert len(data["items"]) == 1  # Items copied


# ============================================================================
# Workflow Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cannot_edit_sent_budget(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test that sent budgets cannot be edited."""
    # Create and send budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/send",
        json={},
        headers=auth_headers,
    )

    # Try to update sent budget - should fail
    response = await client.put(
        f"/api/v1/budget/budgets/{budget_id}",
        json={
            "patient_notes": "New notes",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cannot_add_items_to_sent_budget(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test that items cannot be added to sent budgets."""
    # Create and send budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )

    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/send",
        json={},
        headers=auth_headers,
    )

    # Try to add item to sent budget - should fail
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cannot_accept_draft_budget(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test that draft budgets cannot be directly accepted."""
    # Create budget without sending
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Try to accept draft budget - should fail
    response = await client.post(
        f"/api/v1/budget/budgets/{budget_id}/accept",
        json={
            "signature": {
                "signed_by_name": "Test Patient",
                "relationship_to_patient": "patient",
            }
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


# ============================================================================
# History and Versions Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_budget_history(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test getting budget history."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Get history
    response = await client.get(
        f"/api/v1/budget/budgets/{budget_id}/history",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    # Should have at least 'created' entry
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_budget_versions(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test getting budget versions."""
    # Create budget and duplicate
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Duplicate to create version 2
    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/duplicate",
        json={},
        headers=auth_headers,
    )

    # Get versions
    response = await client.get(
        f"/api/v1/budget/budgets/{budget_id}/versions",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "budget_number" in data
    assert "versions" in data
    assert len(data["versions"]) >= 2


# ============================================================================
# Authentication Tests
# ============================================================================


@pytest.mark.asyncio
async def test_budget_requires_authentication(client: AsyncClient):
    """Test that budget endpoints require authentication."""
    response = await client.get("/api/v1/budget/budgets")
    assert response.status_code == 401


# ============================================================================
# Totals Calculation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_budget_totals_updated(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test that budget totals are updated when items change."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Add first item
    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )

    # Check totals
    budget = await client.get(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
    )
    assert float(budget.json()["data"]["total"]) == 100.00

    # Add second item
    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 2,
        },
        headers=auth_headers,
    )

    # Check updated totals
    budget = await client.get(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
    )
    assert float(budget.json()["data"]["total"]) == 300.00  # 100 + 200


@pytest.mark.asyncio
async def test_global_discount_applied(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """Test that global discount is applied correctly."""
    # Create budget
    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
            "global_discount_type": "percentage",
            "global_discount_value": 10,
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]

    # Add item
    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
        },
        headers=auth_headers,
    )

    # Check totals with global discount
    budget = await client.get(
        f"/api/v1/budget/budgets/{budget_id}",
        headers=auth_headers,
    )
    data = budget.json()["data"]
    assert float(data["subtotal"]) == 100.00
    assert float(data["total_discount"]) == 10.00  # 10% of 100
    assert float(data["total"]) == 90.00
    # Per-line share of the global discount, ex-tax (issue #167)
    assert float(data["items"][0]["global_discount_share"]) == 10.00


# ---------------------------------------------------------------------------
# Issue #167 — global discount proration (pure) + budget.accepted line snapshot
# ---------------------------------------------------------------------------


def _line(subtotal: str, discount: str, vat: float) -> SimpleNamespace:
    sub, disc = Decimal(subtotal), Decimal(discount)
    taxable = sub - disc
    tax = taxable * Decimal(str(vat)) / 100
    return SimpleNamespace(
        line_subtotal=sub, line_discount=disc, line_tax=tax, line_total=taxable + tax, vat_rate=vat
    )


def test_allocate_global_discount_percentage() -> None:
    items = [_line("100", "20", 0), _line("50", "0", 21)]
    assert allocate_global_discount("percentage", Decimal("10"), items) == [
        Decimal("8.00"),
        Decimal("5.00"),
    ]


def test_allocate_global_discount_absolute_matches_gross() -> None:
    """Σ share_i * (1 + vat_i) == D, so the invoice gross equals the quote gross."""
    items = [_line("100", "0", 0), _line("100", "0", 21)]
    shares = allocate_global_discount("absolute", Decimal("30"), items)
    gross = sum(
        (s * (1 + Decimal(str(i.vat_rate)) / 100) for s, i in zip(shares, items, strict=True)),
        Decimal("0"),
    )
    assert gross.quantize(Decimal("0.01")) == Decimal("30.00")
    assert all(s > 0 for s in shares)


def test_allocate_global_discount_absolute_clamped_and_zero_cases() -> None:
    items = [_line("40", "0", 0), _line("60", "0", 0)]
    assert allocate_global_discount("absolute", Decimal("500"), items) == [
        Decimal("40.00"),
        Decimal("60.00"),
    ]
    assert allocate_global_discount(None, None, items) == [Decimal("0.00"), Decimal("0.00")]
    assert allocate_global_discount("percentage", Decimal("10"), []) == []
    assert net_line_amount(items[0], Decimal("10")) == Decimal("30.00")


@pytest.mark.asyncio
async def test_budget_accepted_payload_carries_net_line_amounts(
    client: AsyncClient, auth_headers: dict, budget_clinic_setup: dict
):
    """budget.accepted snapshots each line's ex-tax net amount (line + global discount)."""
    from app.core.events import event_bus

    create_response = await client.post(
        "/api/v1/budget/budgets",
        json={
            "patient_id": budget_clinic_setup["patient_id"],
            "valid_from": "2024-01-01",
            "global_discount_type": "percentage",
            "global_discount_value": 10,
        },
        headers=auth_headers,
    )
    budget_id = create_response.json()["data"]["id"]
    await client.post(
        f"/api/v1/budget/budgets/{budget_id}/items",
        json={
            "catalog_item_id": budget_clinic_setup["catalog_item_id"],
            "quantity": 1,
            "discount_type": "percentage",
            "discount_value": 20,
        },
        headers=auth_headers,
    )

    captured: list[dict] = []
    event_bus.subscribe("budget.accepted", captured.append)
    try:
        r = await client.post(
            f"/api/v1/budget/budgets/{budget_id}/accept",
            headers=auth_headers,
            json={"signature": {"signed_by_name": "Test", "relationship_to_patient": "patient"}},
        )
        assert r.status_code == 200, r.text
    finally:
        event_bus.unsubscribe("budget.accepted", captured.append)

    assert len(captured) == 1
    items = captured[0]["items"]
    assert len(items) == 1
    assert items[0]["net_amount"] == "72.00"  # 100 → 80 (line 20%) → 72 (global 10%)
    assert items[0]["quantity"] == 1
