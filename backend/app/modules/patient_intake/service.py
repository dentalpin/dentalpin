"""Intake operations run in the caller's transaction."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.utils.dates import clinic_today_for
from app.database import async_session_maker
from app.modules.gdpr.service import ConsentService
from app.modules.notifications.service import NotificationService
from app.modules.patients.models import Patient
from app.modules.patients.service import PatientService
from app.modules.patients_clinical.service import PatientsClinicalService as Clinical

from .models import ConsentProvenance, FormVersion, Intake
from .schemas import (
    PURPOSES,
    AdministrativeReview,
    ClinicalReview,
    FormDefinition,
    Purpose,
    Representative,
    RetentionConfig,
    SignedAnswers,
)


def purpose_key(purpose: Purpose) -> str:
    return f"patient_intake:{purpose}"


async def locked_patient(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID, *, active_only: bool = True
) -> Patient:
    patient = await NotificationService.lock_whatsapp_patient(db, clinic_id, patient_id)
    if patient is None or (active_only and patient.status != "active"):
        raise HTTPException(404, "Patient not found")
    return patient


async def publish_form(
    db: AsyncSession, clinic_id: UUID, user_id: UUID, definition: FormDefinition
) -> FormVersion:
    await db.scalar(select(Clinic.id).where(Clinic.id == clinic_id).with_for_update())
    latest = await db.scalar(
        select(FormVersion.version)
        .where(FormVersion.clinic_id == clinic_id, FormVersion.locale == definition.locale)
        .order_by(FormVersion.version.desc())
        .limit(1)
    )
    if latest is not None and definition.version <= latest:
        raise HTTPException(409, "Publish a higher version for this language")
    form = FormVersion(
        clinic_id=clinic_id,
        published_by=user_id,
        version=definition.version,
        locale=definition.locale,
        definition=definition.model_dump(mode="json"),
    )
    db.add(form)
    await db.flush()
    return form


async def get_form(db: AsyncSession, clinic_id: UUID, form_id: UUID) -> FormVersion:
    row = await db.scalar(
        select(FormVersion).where(FormVersion.clinic_id == clinic_id, FormVersion.id == form_id)
    )
    if row is None:
        raise HTTPException(404, "Intake form not found")
    return row


async def issue(
    db: AsyncSession,
    clinic: Clinic,
    patient_id: UUID,
    form_id: UUID,
    issued_by: UUID,
    representative: Representative | None,
) -> Intake:
    patient = await locked_patient(db, clinic.id, patient_id)
    form = await get_form(db, clinic.id, form_id)
    newer = await db.scalar(
        select(FormVersion.id)
        .where(
            FormVersion.clinic_id == clinic.id,
            FormVersion.locale == form.locale,
            FormVersion.version > form.version,
        )
        .limit(1)
    )
    if newer is not None:
        raise HTTPException(409, "Issue the latest form for this language")
    birthday = patient.date_of_birth
    today = await clinic_today_for(db, clinic.id)
    if birthday and representative is None:
        age = (
            today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
        )
        if age < 18:
            raise HTTPException(422, "Reception must verify a representative for a minor")
    now = datetime.now(UTC)
    await NotificationService.require_verified_consent(db, clinic.id, patient.id)
    intake = Intake(
        clinic_id=clinic.id,
        patient_id=patient.id,
        form_id=form_id,
        issued_by=issued_by,
        representative=representative.model_dump() if representative else None,
        expires_at=now + timedelta(minutes=30),
    )
    db.add(intake)
    await db.flush()
    return intake


async def get_intake(
    db: AsyncSession, clinic_id: UUID, intake_id: UUID, *, lock: bool = False
) -> Intake:
    stmt = select(Intake).where(Intake.clinic_id == clinic_id, Intake.id == intake_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    row = await db.scalar(stmt)
    if row is None:
        raise HTTPException(404, "Intake not found")
    return row


async def record_signed_submission(
    db: AsyncSession,
    clinic_id: UUID,
    intake_id: UUID,
    answers: SignedAnswers,
    signed_at: datetime,
) -> Intake:
    """Internal handoff after verified signing. The signing caller owns the transaction."""
    intake = await get_intake(db, clinic_id, intake_id, lock=True)
    now = datetime.now(UTC)
    if intake.signed_at or intake.discarded_at or now >= intake.expires_at:
        raise HTTPException(409, "Intake session is no longer available")
    if signed_at.tzinfo is None or signed_at < intake.created_at or signed_at > now:
        raise HTTPException(422, "Invalid signing time")
    form = await get_form(db, clinic_id, intake.form_id)
    definition = FormDefinition.model_validate(form.definition)
    if any(
        answers.choices[channel] and channel not in definition.enabled_channels
        for channel in ("whatsapp", "sms", "email")
    ):
        raise HTTPException(422, "A disabled channel cannot be authorized")
    intake.answers = answers.model_dump(mode="json")
    intake.signed_at = signed_at
    await db.flush()
    return intake


def pending_answers(intake: Intake, section: str) -> SignedAnswers:
    if intake.signed_at is None or intake.answers is None or intake.discarded_at is not None:
        raise HTTPException(409, "Intake is not pending review")
    if getattr(intake, section) is not None:
        raise HTTPException(409, "Section has already been reviewed")
    return SignedAnswers.model_validate(intake.answers)


async def _record_consent(
    db: AsyncSession,
    patient: Patient,
    purpose: Purpose,
    user_id: UUID,
    *,
    granted: bool,
    at: datetime,
    text: str | None = None,
    intake_id: UUID | None = None,
) -> None:
    row = await ConsentService.append_event(
        db,
        patient.clinic_id,
        patient.id,
        purpose_key(purpose),
        granted=granted,
        provided_text=text,
        effective_at=at,
    )
    db.add(
        ConsentProvenance(
            consent_id=row.id, clinic_id=patient.clinic_id, intake_id=intake_id, recorded_by=user_id
        )
    )
    await ConsentService.publish_event(db, row)


async def _apply_choices(
    db: AsyncSession,
    patient: Patient,
    intake: Intake,
    answers: SignedAnswers,
    verified_channels: set[str],
    user_id: UUID,
) -> None:
    assert intake.signed_at is not None
    form = await get_form(db, patient.clinic_id, intake.form_id)
    definition = FormDefinition.model_validate(form.definition)
    projection: dict[str, str | bool] = {}
    for purpose in PURPOSES:
        current = await ConsentService.current(
            db, patient.clinic_id, patient.id, purpose_key(purpose)
        )
        if current is not None and current.created_at > intake.signed_at:
            raise HTTPException(409, "A newer consent decision exists")
        granted = answers.choices[purpose]
        if granted and purpose == "appointment_reminder":
            projection[purpose] = True
        elif granted:
            field = "email" if purpose == "email" else "phone"
            address = getattr(answers.contact, field)
            if (
                purpose not in verified_channels
                or not address
                or address != getattr(patient, field)
            ):
                raise HTTPException(422, f"Verify the signed {purpose} destination first")
            projection[purpose] = NotificationService.contact_binding(patient, address)
        if granted or (current is not None and current.granted):
            await _record_consent(
                db,
                patient,
                purpose,
                user_id,
                granted=granted,
                at=intake.signed_at,
                text=definition.consent_texts[purpose],
                intake_id=intake.id,
            )
    await NotificationService.set_verified_consents(
        db, patient.clinic_id, patient.id, projection, at=intake.signed_at, apply_all=True
    )


async def review_admin(
    db: AsyncSession,
    clinic_id: UUID,
    intake_id: UUID,
    user_id: UUID,
    review: AdministrativeReview,
) -> None:
    intake = await get_intake(db, clinic_id, intake_id)
    patient = await locked_patient(db, clinic_id, intake.patient_id)
    intake = await get_intake(db, clinic_id, intake_id, lock=True)
    answers = pending_answers(intake, "administrative_review")
    proposed = answers.contact.model_dump(exclude_none=True)
    if not review.fields <= proposed.keys():
        raise HTTPException(422, "Select only answered contact fields")
    changes = {
        field: proposed[field]
        for field in review.fields
        if proposed[field] != getattr(patient, field)
    }
    if changes and patient.updated_at > intake.signed_at:
        raise HTTPException(409, "Patient contact details have changed since signing")
    if changes:
        await PatientService.update_patient(db, patient, changes)
    if review.apply_choices:
        await _apply_choices(db, patient, intake, answers, review.verified_channels, user_id)
    intake.administrative_review = {
        "user_id": str(user_id),
        "at": datetime.now(UTC).isoformat(),
        "fields": sorted(review.fields),
        "applied_choices": review.apply_choices,
    }
    await db.flush()


async def withdraw(
    db: AsyncSession, clinic_id: UUID, patient_id: UUID, user_id: UUID, purpose: Purpose
) -> None:
    patient = await locked_patient(db, clinic_id, patient_id, active_only=False)
    prefs = await NotificationService.get_patient_preferences(db, clinic_id, patient.id)
    if prefs is None or prefs.verified_consents is None:
        raise HTTPException(409, "Patient is not enrolled in intake consent")
    now = datetime.now(UTC)
    await _record_consent(db, patient, purpose, user_id, granted=False, at=now)
    projection = {key: value for key, value in prefs.verified_consents.items() if key != purpose}
    await NotificationService.set_verified_consents(db, clinic_id, patient.id, projection, at=now)


async def review_clinical(
    db: AsyncSession, clinic_id: UUID, intake_id: UUID, user_id: UUID, review: ClinicalReview
) -> UUID | None:
    intake = await get_intake(db, clinic_id, intake_id)
    patient = await locked_patient(db, clinic_id, intake.patient_id)
    intake = await get_intake(db, clinic_id, intake_id, lock=True)
    health = pending_answers(intake, "clinical_review").health
    proposed = {
        key: value
        for key, value in health.context.model_dump(exclude_none=True).items()
        if value not in ("unknown", "prefer_not_to_answer")
    }
    if not review.fields <= proposed.keys():
        raise HTTPException(422, "Select only confirmed clinical answers")
    fields = {key: proposed[key] for key in review.fields}
    context = await Clinical.get_medical_context(db, clinic_id, patient.id)
    if (
        fields
        and context
        and context.last_updated_at
        and context.last_updated_at > intake.signed_at
    ):
        raise HTTPException(409, "Medical context has changed since signing")
    if fields:
        await Clinical.upsert_medical_context(db, clinic_id, patient.id, fields, user_id)

    groups = (
        (
            health.allergies,
            review.allergies,
            Clinical.list_allergies,
            Clinical.create_allergy,
            "name",
        ),
        (
            health.medications,
            review.medications,
            Clinical.list_medications,
            Clinical.create_medication,
            "name",
        ),
        (
            health.diseases,
            review.diseases,
            Clinical.list_systemic_diseases,
            Clinical.create_systemic_disease,
            "name",
        ),
        (
            health.surgeries,
            review.surgeries,
            Clinical.list_surgical_history,
            Clinical.create_surgical_history,
            "procedure",
        ),
    )
    for proposals, selected, list_rows, create_row, label in groups:
        if not selected:
            continue
        existing = await list_rows(db, clinic_id, patient.id)
        seen = {getattr(row, label).strip().casefold() for row in existing}
        for index in sorted(selected):
            if index >= len(proposals):
                raise HTTPException(422, "Selected entry was not submitted")
            payload = proposals[index].model_dump(exclude_none=True)
            identifier = payload[label].strip().casefold()
            if identifier in seen:
                raise HTTPException(409, f"An active {label} already matches a selected entry")
            seen.add(identifier)
            if proposals is health.allergies:
                payload["severity"] = review.allergies[index]
            elif proposals is health.diseases:
                payload.update(review.diseases[index].model_dump())
            await create_row(db, clinic_id, patient.id, payload)

    intake.clinical_review = {
        "user_id": str(user_id),
        "at": datetime.now(UTC).isoformat(),
        "selection": review.model_dump(mode="json"),
    }
    await db.flush()
    changed = fields or any(
        (review.allergies, review.medications, review.diseases, review.surgeries)
    )
    return patient.id if changed else None


async def discard(db: AsyncSession, clinic_id: UUID, intake_id: UUID) -> None:
    intake = await get_intake(db, clinic_id, intake_id, lock=True)
    if intake.administrative_review is not None or intake.clinical_review is not None:
        raise HTTPException(409, "A section has already been reviewed")
    if intake.discarded_at is None:
        intake.discarded_at = datetime.now(UTC)


async def purge_expired_intakes() -> None:
    """Apply limits only to unsigned and discarded staging rows."""
    async with async_session_maker.begin() as db:
        clinics = (
            await db.execute(
                select(Clinic.id, Clinic.settings)
                .join(Intake, Intake.clinic_id == Clinic.id)
                .distinct()
            )
        ).all()
        now = datetime.now(UTC)
        for clinic_id, settings in clinics:
            retention = RetentionConfig.model_validate(
                (settings or {}).get("patient_intake_retention", {})
            )
            await db.execute(
                delete(Intake).where(
                    Intake.clinic_id == clinic_id,
                    Intake.signed_at.is_(None),
                    Intake.expires_at <= now,
                    Intake.created_at <= now - timedelta(hours=retention.unsigned_hours),
                )
            )
            await db.execute(
                delete(Intake).where(
                    Intake.clinic_id == clinic_id,
                    Intake.discarded_at <= now - timedelta(days=retention.discarded_days),
                )
            )
