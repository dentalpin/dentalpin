"""Use a synthetic clinic to exercise staging, review and delivery controls."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.auth.models import ClinicMembership
from app.core.patient_access import PatientAccessLog
from app.modules.gdpr.models import PatientConsent
from app.modules.notifications.channels import Channel
from app.modules.notifications.gateway import NotificationGateway
from app.modules.notifications.models import CommunicationMessage
from app.modules.notifications.service import NotificationService
from app.modules.patient_intake import service
from app.modules.patient_intake.models import ConsentProvenance
from app.modules.patient_intake.schemas import (
    AdministrativeReview,
    ClinicalReview,
    FormDefinition,
    Representative,
    SignedAnswers,
)
from app.modules.patients_clinical.service import PatientsClinicalService as Clinical

BASE = "/api/v1/patient_intake"
CONTACT = {"phone": "+12025550101", "email": "intake@example.com"}
TEXTS = {purpose: f"Approved text for {purpose}" for purpose in service.PURPOSES}


def definition(**kwargs):
    options = {
        "version": 1,
        "locale": "en",
        "questionnaire_intro": "Please tell us about your medical history",
        "privacy_notice": "Clinic test privacy notice",
        "consent_texts": TEXTS,
        **kwargs,
    }
    return FormDefinition.model_validate(options)


def signed_answers(**grants):
    return SignedAnswers.model_validate(
        {
            "contact": {**CONTACT, "first_name": "Signed", "last_name": "Example"},
            "health": {
                "context": {"is_pregnant": "unknown", "is_on_anticoagulants": True},
                "allergies": [{"name": "Synthetic allergen", "reaction": "Test reaction"}],
                "medications": [{"name": "Synthetic medication"}],
                "diseases": [{"name": "Synthetic condition"}],
                "surgeries": [{"procedure": "Synthetic procedure"}],
            },
            "acknowledged_notice": True,
            "choices": dict.fromkeys(service.PURPOSES, False) | grants,
        }
    )


@pytest.fixture
async def desk(db_session, test_clinic):
    member = await db_session.scalar(
        select(ClinicMembership).where(ClinicMembership.clinic_id == test_clinic.id)
    )
    return member


async def issue(db, clinic, patient, user_id):
    form = await service.publish_form(db, clinic.id, user_id, definition())
    return await service.issue(db, clinic, patient.id, form.id, user_id, None)


async def signed(db, clinic, patient, user_id, **grants):
    intake = await issue(db, clinic, patient, user_id)
    await service.record_signed_submission(
        db, clinic.id, intake.id, signed_answers(**grants), datetime.now(UTC)
    )
    return intake


def message(clinic_id, patient_id, channel, template_key, status):
    address = CONTACT["email" if channel == "email" else "phone"]
    return CommunicationMessage(
        clinic_id=clinic_id,
        patient_id=patient_id,
        channel=channel,
        template_key=template_key,
        status=status,
        to_address=address,
        direction="outbound",
        message_kind="template",
    )


async def test_sign_stages_and_each_section_applies_selectively(
    db_session, test_clinic, test_patient, desk
):
    db = db_session
    clinic_id, patient_id, user_id = test_clinic.id, test_patient.id, desk.user_id
    initial_name = test_patient.first_name
    await Clinical.create_allergy(db, clinic_id, patient_id, {"name": "Existing"})
    intake = await signed(
        db, test_clinic, test_patient, user_id, email=True, appointment_reminder=True
    )

    assert test_patient.first_name == initial_name
    assert await Clinical.get_medical_context(db, clinic_id, patient_id) is None
    prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
    assert prefs.verified_consents == {}
    assert not prefs.email_enabled and not prefs.sms_enabled and not prefs.whatsapp_enabled
    assert await db.scalar(select(func.count()).select_from(PatientConsent)) == 0

    await service.review_admin(
        db,
        clinic_id,
        intake.id,
        user_id,
        AdministrativeReview(fields={"email"}, apply_choices=True, verified_channels={"email"}),
    )
    assert test_patient.email == CONTACT["email"]
    assert test_patient.first_name == initial_name
    assert intake.clinical_review is None
    prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
    assert prefs.verified_consents.keys() == {"email", "appointment_reminder"}
    assert CONTACT["email"] not in prefs.verified_consents.values()
    consent = await db.scalar(
        select(PatientConsent).where(PatientConsent.purpose == "patient_intake:email")
    )
    assert consent.granted_at == intake.signed_at
    assert consent.provided_text == TEXTS["email"]
    assert (await db.get(ConsentProvenance, consent.id)).recorded_by == user_id

    await service.review_clinical(
        db,
        clinic_id,
        intake.id,
        user_id,
        ClinicalReview(fields={"is_on_anticoagulants"}, allergies={0: "high"}),
    )
    context = await Clinical.get_medical_context(db, clinic_id, patient_id)
    assert context.is_on_anticoagulants
    assert context.last_updated_by == user_id
    allergen_names = [row.name for row in await Clinical.list_allergies(db, clinic_id, patient_id)]
    assert allergen_names == ["Existing", "Synthetic allergen"]
    assert await Clinical.list_medications(db, clinic_id, patient_id) == []
    assert {
        alert["type"] for alert in await Clinical.compute_alerts(db, clinic_id, patient_id)
    } == {
        "allergy",
        "anticoagulant",
    }
    with pytest.raises(HTTPException, match="already been reviewed"):
        await service.review_clinical(db, clinic_id, intake.id, user_id, ClinicalReview())


async def test_versions_minor_representative_disabled_sms_and_one_submission(
    db_session, test_clinic, test_patient, desk
):
    db = db_session
    first = await service.publish_form(db, test_clinic.id, desk.user_id, definition())
    second = await service.publish_form(db, test_clinic.id, desk.user_id, definition(version=2))
    with pytest.raises(HTTPException, match="higher version"):
        await service.publish_form(db, test_clinic.id, desk.user_id, definition())
    with pytest.raises(HTTPException, match="latest form"):
        await service.issue(db, test_clinic, test_patient.id, first.id, desk.user_id, None)

    test_patient.date_of_birth = date.today() - timedelta(days=3650)
    await db.flush()
    with pytest.raises(HTTPException, match="representative"):
        await service.issue(db, test_clinic, test_patient.id, second.id, desk.user_id, None)
    intake = await service.issue(
        db,
        test_clinic,
        test_patient.id,
        second.id,
        desk.user_id,
        Representative(name="Verified Example", relationship="guardian"),
    )
    assert intake.representative == {"name": "Verified Example", "relationship": "guardian"}
    assert intake.issued_by == desk.user_id
    with pytest.raises(HTTPException, match="disabled channel"):
        await service.record_signed_submission(
            db, test_clinic.id, intake.id, signed_answers(sms=True), datetime.now(UTC)
        )
    await service.record_signed_submission(
        db, test_clinic.id, intake.id, signed_answers(), datetime.now(UTC)
    )
    with pytest.raises(HTTPException, match="no longer available"):
        await service.record_signed_submission(
            db, test_clinic.id, intake.id, signed_answers(), datetime.now(UTC)
        )


async def test_reception_reads_only_admin_and_can_withdraw(
    client, db_session, auth_headers, test_clinic, test_patient, desk
):
    intake = await signed(db_session, test_clinic, test_patient, desk.user_id, email=True)
    desk.role = "receptionist"
    await db_session.commit()
    headers = {**auth_headers, "X-Clinic-Id": str(test_clinic.id)}
    read = await client.get(f"{BASE}/intakes/{intake.id}/admin", headers=headers)
    assert read.status_code == 200, read.text
    assert "health" not in read.json()["data"]
    assert "Synthetic allergen" not in read.text
    assert (
        await client.get(f"{BASE}/intakes/{intake.id}/clinical", headers=headers)
    ).status_code == 403
    assert (
        await client.post(f"{BASE}/intakes/{intake.id}/clinical", headers=headers, json={})
    ).status_code == 403
    assert await db_session.scalar(select(PatientAccessLog.resource)) == "patient_intake_admin"
    response = await client.post(
        f"{BASE}/patients/{test_patient.id}/consents/email/withdraw",
        headers=headers,
    )
    assert response.status_code == 204, response.text
    withdrawal = await db_session.scalar(select(PatientConsent))
    assert withdrawal.withdrawn_at is not None
    assert (await db_session.get(ConsentProvenance, withdrawal.id)).recorded_by == desk.user_id
    wrong_clinic = await client.get(f"{BASE}/intakes/{uuid4()}/admin", headers=headers)
    assert wrong_clinic.status_code == 404


async def test_withdrawal_cancels_pending_by_purpose_and_old_review_cannot_regrant(
    db_session, test_clinic, test_patient, desk
):
    db = db_session
    clinic_id, patient_id, user_id = test_clinic.id, test_patient.id, desk.user_id
    intake = await signed(
        db, test_clinic, test_patient, user_id, whatsapp=True, email=True, appointment_reminder=True
    )
    review = AdministrativeReview(
        fields={"email", "phone"}, apply_choices=True, verified_channels={"email", "whatsapp"}
    )
    await service.review_admin(db, clinic_id, intake.id, user_id, review)
    form = await service.get_form(db, clinic_id, intake.form_id)
    older = await service.issue(db, test_clinic, patient_id, form.id, user_id, None)
    await service.record_signed_submission(
        db, clinic_id, older.id, signed_answers(whatsapp=True, email=True), datetime.now(UTC)
    )
    pending = [
        message(clinic_id, patient_id, "email", "appointment_reminder", "queued"),
        message(clinic_id, patient_id, "whatsapp", "appointment_reminder", "awaiting_manual"),
        message(clinic_id, patient_id, "sms", "appointment_reminder", "failed"),
    ]
    unaffected = [
        message(clinic_id, patient_id, "email", "budget_sent", "queued"),
        message(clinic_id, patient_id, "email", "appointment_reminder", "sent"),
    ]
    db.add_all(pending + unaffected)
    await db.flush()
    await service.withdraw(db, clinic_id, patient_id, user_id, "appointment_reminder")
    assert [row.status for row in pending] == ["skipped"] * 3
    assert [row.status for row in unaffected] == ["queued", "sent"]
    assert await NotificationGateway.has_whatsapp_consent(
        db, clinic_id, test_patient, "budget_sent"
    )
    assert not await NotificationGateway.has_whatsapp_consent(
        db, clinic_id, test_patient, "appointment_reminder"
    )

    await db.commit()
    with pytest.raises(HTTPException, match="newer consent decision"):
        async with db.begin_nested():
            await service.review_admin(db, clinic_id, older.id, user_id, review)
    await db.refresh(older)
    assert older.administrative_review is None
    await service.withdraw(db, clinic_id, patient_id, user_id, "email")
    assert unaffected[0].status == "skipped"
    assert unaffected[1].status == "sent"


async def test_failed_withdrawal_rolls_back_ledger_projection_and_manual_draft(
    db_session, test_clinic, test_patient, desk, monkeypatch
):
    db = db_session
    clinic_id, patient_id, user_id = test_clinic.id, test_patient.id, desk.user_id
    intake = await signed(db, test_clinic, test_patient, user_id, whatsapp=True)
    await service.review_admin(
        db,
        clinic_id,
        intake.id,
        user_id,
        AdministrativeReview(fields={"phone"}, apply_choices=True, verified_channels={"whatsapp"}),
    )
    draft = message(clinic_id, patient_id, "whatsapp", "budget_sent", "awaiting_manual")
    db.add(draft)
    await db.flush()
    draft_id = draft.id
    await db.commit()
    set_verified_consents = NotificationService.set_verified_consents

    async def fail_after_cancellation(*args, **kwargs):
        await set_verified_consents(*args, **kwargs)
        assert draft.status == "skipped"
        raise RuntimeError("synthetic failure after draft cancellation")

    monkeypatch.setattr(NotificationService, "set_verified_consents", fail_after_cancellation)
    with pytest.raises(RuntimeError, match="synthetic failure after draft cancellation"):
        async with db.begin():
            await service.withdraw(db, clinic_id, patient_id, user_id, "whatsapp")

    ledger = (await db.scalars(select(PatientConsent))).all()
    assert len(ledger) == 1 and ledger[0].granted
    assert await db.scalar(select(func.count()).select_from(ConsentProvenance)) == 1
    prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
    assert prefs.whatsapp_enabled and prefs.whatsapp_opt_in_at is not None
    assert "whatsapp" in prefs.verified_consents
    saved_draft = await db.get(CommunicationMessage, draft_id)
    assert saved_draft.status == "awaiting_manual" and saved_draft.error_message is None


async def test_review_rolls_back_chart_ledger_and_preference_together(
    db_session, test_clinic, test_patient, desk, monkeypatch
):
    db = db_session
    clinic_id, patient_id, user_id = test_clinic.id, test_patient.id, desk.user_id
    intake = await signed(db, test_clinic, test_patient, user_id, email=True)
    initial_email = test_patient.email
    await db.commit()

    original = NotificationService.set_verified_consents

    async def fail_after_projection(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError("synthetic write failure")

    monkeypatch.setattr(NotificationService, "set_verified_consents", fail_after_projection)
    with pytest.raises(RuntimeError, match="synthetic write failure"):
        async with db.begin_nested():
            await service.review_admin(
                db,
                clinic_id,
                intake.id,
                user_id,
                AdministrativeReview(
                    fields={"email"}, apply_choices=True, verified_channels={"email"}
                ),
            )
    await db.refresh(test_patient)
    await db.refresh(intake)
    assert test_patient.email == initial_email
    assert intake.administrative_review is None
    assert await db.scalar(select(func.count()).select_from(PatientConsent)) == 0
    assert (
        await NotificationService.get_patient_preferences(db, clinic_id, patient_id)
    ).verified_consents == {}


async def test_verified_contact_is_rechecked_at_resolution_and_dispatch(
    db_session, test_clinic, test_patient, desk, monkeypatch
):
    db = db_session
    clinic_id, patient_id, user_id = test_clinic.id, test_patient.id, desk.user_id
    intake = await signed(
        db, test_clinic, test_patient, user_id, email=True, appointment_reminder=True
    )
    await service.review_admin(
        db,
        clinic_id,
        intake.id,
        user_id,
        AdministrativeReview(fields={"email"}, apply_choices=True, verified_channels={"email"}),
    )

    class SyntheticEmailAdapter:
        async def send(self, *_args):
            raise AssertionError("Unverified address must not reach the transport")

    async def get_adapter(_db, _clinic, channel):
        if channel == Channel.EMAIL:
            return SyntheticEmailAdapter()
        raise AssertionError("Unconsented fallback channel was considered")

    monkeypatch.setattr(NotificationGateway, "_supporting_adapter", get_adapter)
    queued = await NotificationGateway.enqueue(
        db,
        clinic_id,
        "appointment_reminder",
        context={},
        patient_id=patient_id,
        channels=["push", "whatsapp", "email"],
        force_send=True,
    )
    assert queued.channel == "email"
    test_patient.email = "different@example.com"
    await db.commit()
    blocked = await NotificationGateway.enqueue(
        db,
        clinic_id,
        "appointment_reminder",
        context={},
        patient_id=patient_id,
        channels=["push", "whatsapp", "email"],
        force_send=True,
    )
    assert blocked.status == "skipped"
    await NotificationGateway.dispatch_outbox(db)
    await db.refresh(queued)
    assert queued.status == "skipped"
    assert queued.error_message == "verified_consent_required"


async def test_staging_retention_keeps_live_and_pending_signed_rows(
    db_session, test_clinic, test_patient, desk
):
    db = db_session
    clinic_id, patient_id, user_id = test_clinic.id, test_patient.id, desk.user_id
    discarded = await signed(db, test_clinic, test_patient, user_id)
    form = await service.get_form(db, clinic_id, discarded.form_id)
    expired = await service.issue(db, test_clinic, patient_id, form.id, user_id, None)
    live = await service.issue(db, test_clinic, patient_id, form.id, user_id, None)
    pending = await service.issue(db, test_clinic, patient_id, form.id, user_id, None)
    await service.record_signed_submission(
        db, clinic_id, pending.id, signed_answers(), datetime.now(UTC)
    )
    now = datetime.now(UTC)
    expired.created_at = now - timedelta(hours=25)
    expired.expires_at = now - timedelta(hours=24)
    pending.created_at = now - timedelta(days=45)
    pending.expires_at = now - timedelta(days=44)
    await service.discard(db, clinic_id, discarded.id)
    discarded.discarded_at = now - timedelta(days=31)
    await db.commit()

    await service.purge_expired_intakes()
    for row in (discarded, expired):
        with pytest.raises(HTTPException, match="Intake not found"):
            await service.get_intake(db, clinic_id, row.id)
    for row in (live, pending):
        assert await service.get_intake(db, clinic_id, row.id) is not None
