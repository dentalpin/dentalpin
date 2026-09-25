"""Copilot morning digest (proactivity v1).

Covers the settings opt-in (PATCH validation + recipient defaulting)
and the task itself: disabled clinics are skipped, enabled clinics get
one digest built through the tool registry with the recipient's role
permissions, and ``copilot.digest.sent`` is published.

The task opens its own sessions via ``async_session_maker``, so test
fixtures must be committed before invoking it.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core.events import event_bus
from app.core.events.types import EventType
from app.core.llm.factory import ANTHROPIC_SPEC
from app.core.llm.registry import llm_provider_registry
from app.database import engine
from app.modules.copilot.service import CopilotSettingsService
from app.modules.copilot.tasks import send_morning_digests


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_pool():
    """Drop the global engine's pool around every test.

    ``send_morning_digests`` opens sessions through the global
    ``async_session_maker``; lingering pool connections from a previous
    test's event loop trigger "attached to a different loop" (same
    pattern as ``test_patient_timeline.py``).
    """
    await engine.dispose()
    yield
    await engine.dispose()


async def _set_clinic_tz(db: AsyncSession, clinic_id, tz: str) -> None:
    await db.execute(
        text("UPDATE clinics SET timezone = :tz WHERE id = :id"), {"tz": tz, "id": clinic_id}
    )
    await db.commit()


@pytest.mark.asyncio
async def test_settings_patch_enables_digest_and_defaults_recipient(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    res = await client.patch(
        "/api/v1/copilot/settings",
        json={"digest_enabled": True, "digest_hour": 7},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["digest_enabled"] is True
    assert data["digest_hour"] == 7
    # Recipient defaults to the user who flipped the switch.
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert data["digest_recipient_user_ids"] == [me.json()["data"]["user"]["id"]]


@pytest.mark.asyncio
async def test_settings_patch_digest_only_does_not_require_openai_key(
    client: AsyncClient, auth_headers: dict, test_clinic, monkeypatch
) -> None:
    """Digest opt-in is no-LLM: must work even when OPENAI_API_KEY is unset."""
    monkeypatch.setattr(app_settings, "OPENAI_API_KEY", "")
    res = await client.patch(
        "/api/v1/copilot/settings",
        json={"digest_enabled": True},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_settings_patch_provider_change_requires_openai_key(
    client: AsyncClient, auth_headers: dict, test_clinic, monkeypatch
) -> None:
    monkeypatch.setattr(app_settings, "OPENAI_API_KEY", "")
    res = await client.patch(
        "/api/v1/copilot/settings",
        json={"provider": "openai"},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "OPENAI_API_KEY" in res.text


@pytest.mark.asyncio
async def test_settings_patch_provider_change_requires_anthropic_key(
    client: AsyncClient, auth_headers: dict, test_clinic, monkeypatch
) -> None:
    monkeypatch.setattr(app_settings, "ANTHROPIC_API_KEY", "")
    res = await client.patch(
        "/api/v1/copilot/settings",
        json={"provider": "anthropic"},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "ANTHROPIC_API_KEY" in res.text


@pytest.mark.asyncio
async def test_settings_patch_provider_switch_defaults_model(
    client: AsyncClient, auth_headers: dict, test_clinic, monkeypatch
) -> None:
    """Switching provider without naming a model must not keep the other vendor's model id."""
    monkeypatch.setattr(app_settings, "ANTHROPIC_API_KEY", "test-key")
    res = await client.patch(
        "/api/v1/copilot/settings",
        json={"provider": "anthropic"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["provider"] == "anthropic"
    assert body["model"] == app_settings.COPILOT_MODEL_CHAT_ANTHROPIC


@pytest.mark.asyncio
async def test_settings_patch_uses_registered_provider_metadata(
    client: AsyncClient, auth_headers: dict, test_clinic, monkeypatch
) -> None:
    spec = replace(
        ANTHROPIC_SPEC,
        name="registry-test",
        label="Registry Test",
        default_model="registry-default-model",
    )
    llm_provider_registry.register(spec)
    monkeypatch.setattr(app_settings, "ANTHROPIC_API_KEY", "")

    try:
        response = await client.patch(
            "/api/v1/copilot/settings",
            json={"provider": spec.name},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert spec.api_key_setting is not None
        assert spec.api_key_setting in response.text

        monkeypatch.setattr(app_settings, "ANTHROPIC_API_KEY", "test-key")
        response = await client.patch(
            "/api/v1/copilot/settings",
            json={"provider": spec.name},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["model"] == spec.default_model
    finally:
        llm_provider_registry.unregister(spec.name)


@pytest.mark.asyncio
async def test_settings_patch_rejects_bad_hour(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    res = await client.patch(
        "/api/v1/copilot/settings",
        json={"digest_hour": 25},
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_digest_skips_disabled_clinics(db_session: AsyncSession, test_clinic) -> None:
    await CopilotSettingsService.get_or_create(db_session, test_clinic.id)
    await db_session.commit()

    seen: list[dict] = []
    event_bus.subscribe(EventType.COPILOT_DIGEST_SENT, lambda data: seen.append(data))
    await send_morning_digests(datetime(2032, 1, 5, 8, 0))
    assert seen == []


@pytest.mark.asyncio
async def test_digest_sends_for_enabled_clinic(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    # The /me user is admin of test_clinic (conftest fixture).
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]

    from uuid import UUID

    # Pin the clinic to UTC so the hour gate is unambiguous (the digest
    # hour is interpreted in the clinic's timezone, v2).
    await _set_clinic_tz(db_session, test_clinic.id, "UTC")
    row = await CopilotSettingsService.update(
        db_session,
        test_clinic.id,
        {"digest_enabled": True, "digest_hour": 8},
        acting_user_id=UUID(user_id),
    )
    assert row.digest_recipient_user_ids == [user_id]
    await db_session.commit()

    seen: list[dict] = []
    event_bus.subscribe(EventType.COPILOT_DIGEST_SENT, lambda data: seen.append(data))

    # Hour mismatch → nothing.
    await send_morning_digests(datetime(2032, 1, 5, 9, 0, tzinfo=UTC))
    assert seen == []

    # Hour match → one digest, event published.
    await send_morning_digests(datetime(2032, 1, 5, 8, 0, tzinfo=UTC))
    assert len(seen) == 1
    assert seen[0]["clinic_id"] == str(test_clinic.id)
    assert seen[0]["recipient_user_id"] == user_id
    assert seen[0]["date"] == "2032-01-05"


@pytest.mark.asyncio
async def test_digest_audit_trail_lands_in_agent_logs(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    """Digest tool calls go through the registry → audit rows exist."""
    from uuid import UUID

    from app.core.agents.models import AgentAuditLog

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    await _set_clinic_tz(db_session, test_clinic.id, "UTC")
    await CopilotSettingsService.update(
        db_session,
        test_clinic.id,
        {"digest_enabled": True, "digest_hour": 6},
        acting_user_id=UUID(me.json()["data"]["user"]["id"]),
    )
    await db_session.commit()

    await send_morning_digests(datetime(2032, 1, 6, 6, 0, tzinfo=UTC))

    names = list(
        await db_session.scalars(
            select(AgentAuditLog.tool_name).where(AgentAuditLog.clinic_id == test_clinic.id)
        )
    )
    assert "agenda.get_day_overview" in names
    assert "recalls.list_due_recalls" in names
    assert "budget.list_budgets" in names


@pytest.mark.asyncio
async def test_digest_hour_is_clinic_timezone(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    """The hour gate compares against the clinic's local hour, not UTC."""
    from uuid import UUID

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me.json()["data"]["user"]["id"]
    # Fixed UTC+5 offset (no DST) → 06:00 UTC is 11:00 local.
    await _set_clinic_tz(db_session, test_clinic.id, "Etc/GMT-5")
    await CopilotSettingsService.update(
        db_session,
        test_clinic.id,
        {"digest_enabled": True, "digest_hour": 11},
        acting_user_id=UUID(user_id),
    )
    await db_session.commit()

    seen: list[dict] = []
    event_bus.subscribe(EventType.COPILOT_DIGEST_SENT, lambda data: seen.append(data))

    # 11:00 UTC would match a naive server-local gate but is 16:00 local.
    await send_morning_digests(datetime(2032, 1, 6, 11, 0, tzinfo=UTC))
    assert seen == []

    # 06:00 UTC == 11:00 in the clinic's timezone → fires.
    await send_morning_digests(datetime(2032, 1, 6, 6, 0, tzinfo=UTC))
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_digest_sends_one_email_per_recipient(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    """Two recipients → two digests, each scoped to its own user."""
    from uuid import UUID, uuid4

    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import hash_password

    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    admin_id = me.json()["data"]["user"]["id"]

    # A second clinic member.
    other = User(
        id=uuid4(),
        email="recall.staff@demo.clinic",
        password_hash=hash_password("TestPass1234"),
        first_name="Reca",
        last_name="Staff",
        is_active=True,
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        ClinicMembership(
            id=uuid4(), user_id=other.id, clinic_id=test_clinic.id, role="receptionist"
        )
    )
    await _set_clinic_tz(db_session, test_clinic.id, "UTC")
    await CopilotSettingsService.update(
        db_session,
        test_clinic.id,
        {
            "digest_enabled": True,
            "digest_hour": 8,
            "digest_recipient_user_ids": [admin_id, str(other.id)],
        },
        acting_user_id=UUID(admin_id),
    )
    await db_session.commit()

    seen: list[dict] = []
    event_bus.subscribe(EventType.COPILOT_DIGEST_SENT, lambda data: seen.append(data))
    await send_morning_digests(datetime(2032, 1, 5, 8, 0, tzinfo=UTC))
    recipients = {e["recipient_user_id"] for e in seen}
    assert recipients == {admin_id, str(other.id)}


@pytest.mark.asyncio
async def test_settings_patch_rejects_non_member_recipient(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    from uuid import uuid4

    res = await client.patch(
        "/api/v1/copilot/settings",
        json={"digest_enabled": True, "digest_recipient_user_ids": [str(uuid4())]},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "clinic members" in res.text.lower()
