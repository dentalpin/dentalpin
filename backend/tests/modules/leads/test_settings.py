"""The module settings page's backend (D13) + the tool-surface guard."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.plugins.registry import module_registry
from app.modules.leads.models import LEAD_STATUSES, LeadIntakeKey, LeadSettings
from app.modules.leads.service import LeadIntakeKeyService

from .conftest import STAFF_ROLE, make_clinic, make_headers

SETTINGS = "/api/v1/leads/settings"
KEY = "/api/v1/leads/settings/intake-key"
ROTATE = "/api/v1/leads/settings/intake-key/rotate"
INTAKE = "/api/v1/leads/public/intake"

PAYLOAD = {
    "full_name": "Marta Ruiz",
    "phone": "+34 699 888 777",
    "email": "marta@example.com",
    "motive": "Presupuesto",
    "availability_days": ["tue"],
    "availability_slot": "morning",
}


async def _usage(db: AsyncSession, clinic_id) -> LeadSettings:
    return (
        await db.execute(select(LeadSettings).where(LeadSettings.clinic_id == clinic_id))
    ).scalar_one()


@pytest.mark.asyncio
async def test_get_settings_lazily_creates_the_row_but_never_a_key(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    assert (
        await db_session.execute(
            select(LeadSettings).where(LeadSettings.clinic_id == test_clinic.id)
        )
    ).scalar_one_or_none() is None

    response = await client.get(SETTINGS, headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    assert data["daily_cap"] == 200  # the column default IS the default
    assert data["day_count"] == 0
    assert data["day_count_date"] is None
    assert data["intake_url"] == "/api/v1/leads/public/intake"
    assert data["key"] == {
        "configured": False,
        "key_prefix": None,
        "is_active": False,
        "last_used_at": None,
    }
    # The row now exists (lazy create)…
    assert await _usage(db_session, test_clinic.id) is not None
    # …but a read never mints a key.
    assert (
        await db_session.execute(
            select(LeadIntakeKey).where(LeadIntakeKey.clinic_id == test_clinic.id)
        )
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cap_bounds_are_enforced(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    unlimited = await client.patch(SETTINGS, json={"daily_cap": 0}, headers=auth_headers)
    assert unlimited.status_code == 200
    assert unlimited.json()["data"]["daily_cap"] == 0

    too_big = await client.patch(SETTINGS, json={"daily_cap": 5001}, headers=auth_headers)
    assert too_big.status_code == 422

    negative = await client.patch(SETTINGS, json={"daily_cap": -1}, headers=auth_headers)
    assert negative.status_code == 422


@pytest.mark.asyncio
async def test_settings_are_admin_only_while_leads_stay_visible(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic
):
    """The intake key is a secret: front-desk roles must not read or
    rotate it, and must still be able to work the queue."""
    headers = await make_headers(db_session, test_clinic.id, role=STAFF_ROLE)

    assert (await client.get("/api/v1/leads/", headers=headers)).status_code == 200

    assert (await client.get(SETTINGS, headers=headers)).status_code == 403
    assert (
        await client.patch(SETTINGS, json={"daily_cap": 10}, headers=headers)
    ).status_code == 403
    assert (await client.post(ROTATE, headers=headers)).status_code == 403
    assert (await client.patch(KEY, json={"is_active": False}, headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_rotation_replaces_the_key_without_resetting_the_counter(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    first = await client.post(ROTATE, headers=auth_headers)
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["key"].startswith("lk_")
    assert first_data["key_prefix"] == first_data["key"][:12]

    # One accepted enquiry, so the gauge has something to protect.
    used = await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": first_data["key"]})
    assert used.status_code == 201
    assert (await _usage(db_session, test_clinic.id)).day_count == 1

    second = await client.post(ROTATE, headers=auth_headers)
    second_data = second.json()["data"]
    assert second_data["key_prefix"] != first_data["key_prefix"]

    # The old key stops working immediately…
    stale = await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": first_data["key"]})
    assert stale.status_code == 401
    # …the new one works…
    fresh = await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": second_data["key"]})
    assert fresh.status_code == 201
    # …and rotation handed back no fresh daily budget.
    assert (await _usage(db_session, test_clinic.id)).day_count == 2

    # Once is enough: the plaintext is never returned again.
    status = await client.get(SETTINGS, headers=auth_headers)
    key_status = status.json()["data"]["key"]
    assert key_status["configured"] is True
    assert key_status["key_prefix"] == second_data["key_prefix"]
    assert key_status["is_active"] is True
    assert second_data["key"] not in status.text


@pytest.mark.asyncio
async def test_deactivating_the_key_is_the_kill_switch(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    plaintext = (await client.post(ROTATE, headers=auth_headers)).json()["data"]["key"]

    off = await client.patch(KEY, json={"is_active": False}, headers=auth_headers)
    assert off.status_code == 200
    assert off.json()["data"]["is_active"] is False
    assert (
        await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": plaintext})
    ).status_code == 401

    on = await client.patch(KEY, json={"is_active": True}, headers=auth_headers)
    assert on.status_code == 200
    assert (
        await client.post(INTAKE, json=PAYLOAD, headers={"X-Lead-Key": plaintext})
    ).status_code == 201


@pytest.mark.asyncio
async def test_toggle_without_a_key_is_404(
    client: AsyncClient, test_clinic: Clinic, auth_headers: dict
):
    response = await client.patch(KEY, json={"is_active": False}, headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_settings_are_clinic_scoped(
    client: AsyncClient, db_session: AsyncSession, test_clinic: Clinic, auth_headers: dict
):
    other = await make_clinic(db_session, "Second Clinic")
    other_headers = await make_headers(db_session, other.id, role="admin")

    await client.patch(SETTINGS, json={"daily_cap": 7}, headers=auth_headers)
    await client.post(ROTATE, headers=auth_headers)

    other_settings = await client.get(SETTINGS, headers=other_headers)
    assert other_settings.json()["data"]["daily_cap"] == 200
    assert other_settings.json()["data"]["key"]["configured"] is False
    assert (
        await db_session.execute(select(LeadIntakeKey).where(LeadIntakeKey.clinic_id == other.id))
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_intake_key_rotation_is_not_exposed_as_an_agent_tool():
    """The deliberate exception in the module's tool set: an LLM that
    rotates the key breaks the clinic's website with no undo."""
    module = module_registry.get("leads")
    assert module is not None
    names = {tool.name for tool in module.get_tools()}

    assert names == {
        "list_leads",
        "get_lead",
        "create_lead",
        "update_lead",
        "convert_lead_to_patient",
        "update_intake_settings",
    }
    forbidden = [name for name in names if "key" in name or "rotate" in name]
    assert forbidden == []


@pytest.mark.asyncio
async def test_key_service_never_returns_the_plaintext_twice(
    db_session: AsyncSession, test_clinic: Clinic
):
    key, plaintext = await LeadIntakeKeyService.rotate(db_session, test_clinic.id)
    await db_session.commit()

    assert key.key_hash != plaintext
    assert len(key.key_hash) == 64
    # Only the hash is stored.
    stored = (
        await db_session.execute(
            select(LeadIntakeKey).where(LeadIntakeKey.clinic_id == test_clinic.id)
        )
    ).scalar_one()
    assert stored.key_hash == key.key_hash
    assert plaintext not in (stored.key_hash, stored.key_prefix)


def test_lead_statuses_are_the_four_the_ui_offers():
    assert LEAD_STATUSES == ("new", "contacted", "converted", "discarded")
