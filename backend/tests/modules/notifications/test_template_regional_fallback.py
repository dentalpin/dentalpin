"""DB template lookup falls back from a regional locale to its base (#1136)."""

import pytest
import pytest_asyncio

from app.modules.notifications.models import NotificationTemplate
from app.modules.notifications.service import NotificationService


@pytest_asyncio.fixture
async def seeded(db_session):
    """System booking templates seeded the way ob_0003 does (pt, no pt-BR)."""
    from app.modules.online_booking.migrations.versions import ob_0003_seed_email_templates as seed

    for row in seed._rows():
        await db_session.execute(seed._INSERT, row)
    await db_session.commit()


@pytest.mark.asyncio
async def test_pt_br_falls_back_to_the_system_pt_row(db_session, test_clinic, seeded):
    template = await NotificationService.get_template(
        db_session, test_clinic.id, "booking_confirmation", "pt-BR"
    )
    assert template is not None
    assert template.clinic_id is None and template.locale == "pt"


@pytest.mark.asyncio
async def test_clinic_pt_br_row_beats_the_system_pt_row(db_session, test_clinic, seeded):
    db_session.add(
        NotificationTemplate(
            clinic_id=test_clinic.id,
            template_key="booking_confirmation",
            locale="pt-BR",
            channel="email",
            subject="Custom",
            body_html="<p>custom</p>",
            is_system=False,
            is_active=True,
        )
    )
    await db_session.commit()
    template = await NotificationService.get_template(
        db_session, test_clinic.id, "booking_confirmation", "pt-BR"
    )
    assert template.clinic_id == test_clinic.id and template.locale == "pt-BR"


@pytest.mark.asyncio
async def test_clinic_pt_row_beats_the_system_pt_row_for_pt_br(db_session, test_clinic, seeded):
    db_session.add(
        NotificationTemplate(
            clinic_id=test_clinic.id,
            template_key="booking_confirmation",
            locale="pt",
            channel="email",
            subject="Custom pt",
            is_system=False,
            is_active=True,
        )
    )
    await db_session.commit()
    template = await NotificationService.get_template(
        db_session, test_clinic.id, "booking_confirmation", "pt-BR"
    )
    assert template.clinic_id == test_clinic.id and template.locale == "pt"


@pytest.mark.asyncio
async def test_es_lookup_is_unchanged(db_session, test_clinic, seeded):
    template = await NotificationService.get_template(
        db_session, test_clinic.id, "booking_confirmation", "es"
    )
    assert template.clinic_id is None and template.locale == "es"
    # A base locale never borrows another one, and exact callers stay exact.
    assert (
        await NotificationService.get_template(
            db_session, test_clinic.id, "booking_confirmation", "pt-BR", exact_locale=True
        )
        is None
    )
    assert (
        await NotificationService.get_template(
            db_session, test_clinic.id, "booking_confirmation", "xx"
        )
        is None
    )


@pytest.mark.asyncio
async def test_a_clinic_pt_override_does_not_block_creating_a_pt_br_one(
    client, auth_headers, test_clinic
):
    """The duplicate check on create stays exact: pt and pt-BR are separate rows."""
    body = {"template_key": "booking_confirmation", "subject": "S", "body_html": "<p>x</p>"}
    url = "/api/v1/notifications/templates"
    assert (
        await client.post(url, json={**body, "locale": "pt"}, headers=auth_headers)
    ).status_code == 201
    response = await client.post(url, json={**body, "locale": "pt-BR"}, headers=auth_headers)
    assert response.status_code == 201, response.text
    again = await client.post(url, json={**body, "locale": "pt-BR"}, headers=auth_headers)
    assert again.status_code == 409
