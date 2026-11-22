"""Consent managed by verified evidence, exercised without any managing module."""

from datetime import UTC, datetime

import pytest

from app.config import settings
from app.modules.notifications.service import ManagedConsentError, NotificationService


async def _enroll(db, patient, **projection):
    await NotificationService.set_verified_consents(
        db, patient.clinic_id, patient.id, projection, at=datetime.now(UTC)
    )
    await db.commit()
    return await NotificationService.get_patient_preferences(db, patient.clinic_id, patient.id)


@pytest.mark.asyncio
async def test_contact_binding_survives_secret_rotation_but_not_an_address_change(
    db_session, test_patient, monkeypatch
):
    binding = NotificationService.contact_binding(test_patient, test_patient.email)
    prefs = await _enroll(db_session, test_patient, email=binding, appointment_reminder=True)
    assert NotificationService.verified_consent_allows(
        prefs, test_patient, "email", "appointment_reminder"
    )

    monkeypatch.setattr(settings, "SECRET_KEY", "a-different-secret-key-after-rotation-0123456789")
    assert NotificationService.contact_binding(test_patient, test_patient.email) == binding
    assert NotificationService.verified_consent_allows(
        prefs, test_patient, "email", "appointment_reminder"
    )

    # Spelling variants of the same address keep matching; another address does not.
    assert NotificationService.contact_binding(test_patient, " Patient@TEST.com ") == binding
    test_patient.email = "other@test.com"
    assert not NotificationService.verified_consent_allows(
        prefs, test_patient, "email", "appointment_reminder"
    )


@pytest.mark.asyncio
async def test_contact_binding_is_scoped_to_the_patient(db_session, test_patient):
    from types import SimpleNamespace
    from uuid import uuid4

    stranger = SimpleNamespace(id=uuid4())
    assert NotificationService.contact_binding(
        test_patient, "same@test.com"
    ) != NotificationService.contact_binding(stranger, "same@test.com")


@pytest.mark.asyncio
async def test_managed_patient_rejects_a_manual_whatsapp_consent_change(
    client, db_session, auth_headers, test_patient
):
    await _enroll(db_session, test_patient)

    with pytest.raises(ManagedConsentError):
        await NotificationService.update_patient_preferences(
            db_session, test_patient.clinic_id, test_patient.id, {"whatsapp_consent": True}
        )
    response = await client.put(
        f"/api/v1/notifications/preferences/patient/{test_patient.id}",
        json={"whatsapp_consent": True},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["message"] == "Consent for this patient is managed by verified evidence"


@pytest.mark.asyncio
async def test_unmanaged_patient_keeps_the_legacy_preference_behaviour(
    client, auth_headers, test_patient
):
    response = await client.put(
        f"/api/v1/notifications/preferences/patient/{test_patient.id}",
        json={"whatsapp_enabled": True, "whatsapp_consent": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
