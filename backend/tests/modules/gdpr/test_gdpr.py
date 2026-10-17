"""gdpr: DSR lifecycle, consents, erasure, breaches and tenant isolation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.gdpr.schemas import (
    ConsentCreate,
    DataBreachCreate,
    DataBreachUpdate,
    GdprRequestCreate,
    GdprRequestUpdate,
    RetentionPolicyCreate,
)
from app.modules.gdpr.service import (
    ConsentService,
    DataBreachService,
    ErasureService,
    ExportService,
    GdprService,
    RetentionService,
    SlaCalculator,
)
from app.modules.gdpr.tools import _record_consent
from app.modules.patients.models import Patient


@pytest.fixture
def erasure_contributors():
    """Mirror boot: collect the real contributors into the global registry.

    The loader only runs in app boot, so tests register explicitly. Always
    cleared afterwards so contributor state never leaks between tests.
    """
    from app.core.erasure.registry import erasure_registry
    from app.modules.billing import BillingModule
    from app.modules.budget import BudgetModule
    from app.modules.clinical_notes import ClinicalNotesModule
    from app.modules.documents import DocumentsModule
    from app.modules.media import MediaModule
    from app.modules.notifications import NotificationsModule
    from app.modules.patient_timeline import PatientTimelineModule
    from app.modules.recalls import RecallsModule

    erasure_registry.clear()
    for module in (
        BillingModule(),
        BudgetModule(),
        ClinicalNotesModule(),
        DocumentsModule(),
        MediaModule(),
        NotificationsModule(),
        PatientTimelineModule(),
        RecallsModule(),
    ):
        erasure_registry.register_from(module)
    yield
    erasure_registry.clear()


def _make_patient(db, clinic_id, **kw) -> Patient:
    p = Patient(
        clinic_id=clinic_id,
        first_name=kw.pop("first_name", "Test"),
        last_name=kw.pop("last_name", "Patient"),
        email=kw.pop("email", "patient@test.com"),
        phone=kw.pop("phone", "+34666123456"),
        national_id=kw.pop("national_id", "12345678A"),
        **kw,
    )
    db.add(p)
    return p


@pytest.mark.asyncio
async def test_dsr_create_sets_30_day_sla(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    row = await GdprService.create_request(
        db_session,
        test_clinic.id,
        GdprRequestCreate(
            patient_id=test_patient.id,
            requester_name="Test Patient",
            requester_email="patient@test.com",
            request_type="access",
        ),
    )
    assert row.status == "received"
    assert row.request_type == "access"
    assert (row.deadline_at - row.received_at).days == 30

    sla = SlaCalculator.deadline_from(row.received_at)
    assert row.deadline_at == sla

    fetched = await GdprService.get_request(db_session, test_clinic.id, row.id)
    assert fetched is not None
    assert fetched.id == row.id


@pytest.mark.asyncio
async def test_dsr_status_transition_completes(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    row = await GdprService.create_request(
        db_session,
        test_clinic.id,
        GdprRequestCreate(
            requester_name="Test Patient",
            requester_email="patient@test.com",
            request_type="erasure",
        ),
    )
    assert row.resolved_at is None

    updated = await GdprService.update_request(
        db_session, row, GdprRequestUpdate(status="completed")
    )
    assert updated.status == "completed"
    assert updated.resolved_at is not None


@pytest.mark.asyncio
async def test_consent_grant_withdraw_regrant_keeps_full_trail(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id)
    from app.modules.gdpr.tools import RecordConsentArgs

    out = await _record_consent(
        ctx,
        RecordConsentArgs(
            patient_id=str(test_patient.id),
            purpose="sms",
            granted=True,
            provided_text="I accept receiving SMS.",
        ),
    )
    assert "error" not in out
    assert out["granted"] is True
    assert out["withdrawn_at"] is None

    items, total = await ConsentService.list_consents(
        db_session, test_clinic.id, patient_id=test_patient.id
    )
    assert total == 1
    assert items[0].granted is True
    assert items[0].purpose == "sms"

    # Withdraw appends a row; re-grant appends another — the withdrawal
    # event is never lost (append-only trail, latest first).
    await ConsentService.grant_or_withdraw(
        db_session,
        test_clinic.id,
        ConsentCreate(patient_id=test_patient.id, purpose="sms", granted=False),
    )
    await ConsentService.grant_or_withdraw(
        db_session,
        test_clinic.id,
        ConsentCreate(
            patient_id=test_patient.id,
            purpose="sms",
            granted=True,
            provided_text="I accept receiving SMS.",
        ),
    )
    items, total = await ConsentService.list_consents(
        db_session, test_clinic.id, patient_id=test_patient.id
    )
    assert total == 3
    assert items[0].granted is True
    assert items[0].withdrawn_at is None
    withdrawals = [c for c in items if not c.granted]
    assert len(withdrawals) == 1
    assert withdrawals[0].withdrawn_at is not None


@pytest.mark.asyncio
async def test_partial_erasure_blanks_identity_and_never_hard_deletes(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    erasure_contributors: None,
):
    # No retention policy → conservative default retains everything.
    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )

    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=test_patient.id,
        categories=["email"],
        rationale="Art.17 erasure request",
    )
    assert result.erased_categories == ["email"]
    assert result.retained_categories == []
    # The result records a per-scope coverage report (#546): a completed
    # run must never read as full DSR coverage.
    coverage = {c.scope: c.status for c in result.coverage}
    assert coverage["patient_record"] == "erased"
    assert coverage["notifications"] == "erased"
    assert coverage["recalls"] == "erased"
    # Retention scopes: every one of these holds an email copy, so an
    # email run reports what each of them keeps (#657).
    assert coverage["patient_timeline"] == "retained"
    assert coverage["budget"] == "retained"
    assert coverage["billing"] == "retained"
    assert coverage["clinical_notes"] == "retained"
    assert coverage["documents"] == "retained"
    assert coverage["media"] == "retained"
    assert set(coverage) == {
        "patient_record",
        "notifications",
        "recalls",
        "patient_timeline",
        "budget",
        "billing",
        "clinical_notes",
        "documents",
        "media",
    }

    # Row still exists (never hard-deleted).
    from sqlalchemy import select as sel

    patient = (
        await db_session.execute(
            sel(Patient).where(Patient.id == test_patient.id, Patient.clinic_id == test_clinic.id)
        )
    ).scalar_one_or_none()
    assert patient is not None
    assert patient.email is None  # identity blanked
    assert patient.first_name == "Test"  # retained: name is not a mapped erasure field

    # Audit log written.
    logs, _ = await ErasureService.list_audit(db_session, test_clinic.id)
    assert logs[0].erased_categories == ["email"]
    assert logs[0].patient_id == test_patient.id


@pytest.mark.asyncio
async def test_erasure_retained_when_retention_holds(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    erasure_contributors: None,
):
    # "clinical" has no field mapping, so it always retains (nothing to
    # blank) — the closed erasure vocabulary is email|phone|identity.
    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="clinical", retention_years=5),
    )
    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=test_patient.id,
        categories=["clinical"],
        rationale="Art.17",
    )
    assert result.erased_categories == []
    assert result.retained_categories == ["clinical"]
    # Nothing was erased, so every scope reports what it kept (#546).
    coverage = {c.scope: c.status for c in result.coverage}
    assert coverage["patient_record"] == "retained"
    # "clinical" is outside the closed vocabulary, so no scope holds a copy
    # of it: every contributor reports not_applicable rather than claiming
    # to retain something this run never looked at (#657).
    assert coverage["notifications"] == "not_applicable"
    assert coverage["patient_timeline"] == "not_applicable"
    assert coverage["budget"] == "not_applicable"
    assert coverage["billing"] == "not_applicable"
    assert coverage["clinical_notes"] == "not_applicable"
    assert coverage["documents"] == "not_applicable"
    assert coverage["media"] == "not_applicable"

    patient = (
        await db_session.execute(
            select(Patient).where(
                Patient.id == test_patient.id, Patient.clinic_id == test_clinic.id
            )
        )
    ).scalar_one_or_none()
    assert patient.email is not None  # not blanked


@pytest.mark.asyncio
async def test_erasure_omits_scope_without_contributor(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    # ADR 0038 honesty: a scope with no registered contributor produces no
    # row. Uninstall recalls and the DSR must NOT report recalls: erased.
    from app.core.erasure.registry import erasure_registry
    from app.modules.notifications import NotificationsModule

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    erasure_registry.clear()
    try:
        erasure_registry.register_from(NotificationsModule())
        result = await ErasureService.execute(
            db_session,
            test_clinic.id,
            patient_id=test_patient.id,
            categories=["email"],
            rationale="Art.17 erasure request",
        )
        coverage = {c.scope: c.status for c in result.coverage}
        assert coverage["notifications"] == "erased"
        assert "recalls" not in coverage
    finally:
        erasure_registry.clear()


@pytest.mark.asyncio
async def test_announcement_failure_does_not_fail_erasure(
    db_session: AsyncSession,
    test_clinic: Clinic,
    test_patient: Patient,
    erasure_contributors: None,
):
    # The post-commit announcement must not fail the committed erasure:
    # a subscriber declaring db raises inside publish (bus rule), after
    # the audit log is already durable.
    from app.core.events import EventType, event_bus

    async def _db_subscriber(data, *, db):
        raise AssertionError("announcement must not run in-transaction")

    announced: list[dict] = []

    async def _recorder(data):
        announced.append(data)

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    # Subscribe the recorder first: the bus aborts the loop on the
    # db-subscriber's RuntimeError, so ordering decides what is recorded.
    event_bus.subscribe(EventType.GDPR_ERASURE_EXECUTED, _recorder)
    event_bus.subscribe(EventType.GDPR_ERASURE_EXECUTED, _db_subscriber)
    try:
        result = await ErasureService.execute(
            db_session,
            test_clinic.id,
            patient_id=test_patient.id,
            categories=["email"],
            rationale="Art.17 erasure request",
        )
    finally:
        event_bus.unsubscribe(EventType.GDPR_ERASURE_EXECUTED, _db_subscriber)
        event_bus.unsubscribe(EventType.GDPR_ERASURE_EXECUTED, _recorder)
    assert result is not None
    assert result.erased_categories == ["email"]
    coverage = {c.scope: c.status for c in result.coverage}
    assert coverage["notifications"] == "erased"
    # The announcement still went out (to the non-transactional subscriber)
    # even though the db-subscriber raised.
    assert [a["patient_id"] for a in announced] == [str(test_patient.id)]


@pytest.mark.asyncio
async def test_receptionist_cannot_write_breaches(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    # `receptionist` holds consents.write but NOT breaches.write: one role
    # proves both gates instead of assuming them (#562 advisory F2).
    # Pinned to the static role map: under RBAC_FROM_DB the same role can
    # resolve differently, so the flag is saved and restored.
    from uuid import uuid4

    from app.config import settings
    from app.core.auth.models import ClinicMembership, User
    from app.core.auth.service import create_access_token, hash_password

    desk = User(
        email="desk@example.com",
        password_hash=hash_password("DeskPass1234"),
        first_name="Front",
        last_name="Desk",
    )
    db_session.add(desk)
    await db_session.flush()
    db_session.add(
        ClinicMembership(id=uuid4(), user_id=desk.id, clinic_id=test_clinic.id, role="receptionist")
    )
    await db_session.commit()
    desk_headers = {
        "Authorization": f"Bearer {create_access_token(desk.id, token_version=desk.token_version)}"
    }
    original_flag = settings.RBAC_FROM_DB
    settings.RBAC_FROM_DB = False
    try:
        # Allowed: the gate passes, so the unknown patient 404s (not 403s).
        ok = await client.post(
            "/api/v1/gdpr/consents",
            json={
                "patient_id": str(uuid4()),
                "purpose": "sms",
                "granted": True,
                "provided_text": "I accept receiving SMS.",
            },
            headers=desk_headers,
        )
        assert ok.status_code == 404

        # Denied: no breaches.write for receptionist.
        denied = await client.patch(
            f"/api/v1/gdpr/breaches/{uuid4()}",
            json={"description": "x"},
            headers=desk_headers,
        )
        assert denied.status_code == 403
        assert denied.json()["message"] == "Permission denied: gdpr.breaches.write"
    finally:
        settings.RBAC_FROM_DB = original_flag


@pytest.mark.asyncio
async def test_tool_erasure_rejects_unknown_category():
    from app.modules.gdpr.tools import ExecuteErasureArgs

    # The closed vocabulary on the DESTRUCTIVE tool boundary: widening
    # categories to list[str] must fail here first.
    with pytest.raises(ValidationError):
        ExecuteErasureArgs(
            patient_id="12345678-1234-5678-1234-567812345678",
            categories=["clinical"],
            rationale=None,
        )


@pytest.mark.asyncio
async def test_breach_create_and_report(db_session: AsyncSession, test_clinic: Clinic):
    row = await DataBreachService.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Backup exposed",
            data_involved=["patients", "billing"],
            affected_people=10,
        ),
    )
    assert row.status == "under_review"
    assert row.reported is False

    updated = await DataBreachService.update(
        db_session,
        row,
        DataBreachUpdate(status="reported"),
    )
    assert updated.status == "reported"
    assert updated.reported is True
    assert updated.notified_authority_at is not None


@pytest.mark.asyncio
async def test_consent_unknown_patient_returns_none(db_session: AsyncSession, test_clinic: Clinic):
    from uuid import uuid4

    # Unknown ids return None (404 upstream) instead of a raw 500 from the
    # audit-table FK (#562 CONS-03).
    result = await ConsentService.grant_or_withdraw(
        db_session,
        test_clinic.id,
        ConsentCreate(patient_id=uuid4(), purpose="sms", granted=True, provided_text="I accept."),
    )
    assert result is None


@pytest.mark.asyncio
async def test_consent_other_clinic_patient_returns_none(
    db_session: AsyncSession, test_clinic: Clinic
):
    from uuid import uuid4

    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()
    p_other = _make_patient(db_session, other.id)
    db_session.add(p_other)
    await db_session.flush()

    # A consent row must never reference a patient the clinic cannot see
    # (#562 CONS-01).
    result = await ConsentService.grant_or_withdraw(
        db_session,
        test_clinic.id,
        ConsentCreate(
            patient_id=p_other.id, purpose="sms", granted=True, provided_text="I accept."
        ),
    )
    assert result is None
    items, total = await ConsentService.list_consents(
        db_session, test_clinic.id, patient_id=p_other.id
    )
    assert total == 0


@pytest.mark.asyncio
async def test_consent_tool_reports_missing_patient(db_session: AsyncSession, test_clinic: Clinic):
    from uuid import uuid4

    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id)
    from app.modules.gdpr.tools import RecordConsentArgs

    out = await _record_consent(
        ctx,
        RecordConsentArgs(
            patient_id=str(uuid4()),
            purpose="sms",
            granted=True,
            provided_text="I accept receiving SMS.",
        ),
    )
    assert out == {"error": "patient not found"}


@pytest.mark.asyncio
async def test_retention_create_supersedes_same_category(
    db_session: AsyncSession, test_clinic: Clinic
):
    # At most one policy per (clinic, category) is active: creating a new
    # one deactivates its predecessors (history preserved), so erasure
    # eligibility can never collapse duplicates nondeterministically
    # (#562 RET-01).
    first = await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=5),
    )
    second = await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    assert second.is_active is True
    await db_session.refresh(first)
    assert first.is_active is False

    active = await RetentionService.list_active(db_session, test_clinic.id)
    assert [p.id for p in active if p.data_category == "email"] == [second.id]


@pytest.mark.asyncio
async def test_retention_update_ignores_reactivate(db_session: AsyncSession, test_clinic: Clinic):
    from app.modules.gdpr.schemas import RetentionPolicyUpdate

    first = await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=5),
    )
    second = await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0),
    )
    # Reactivation is not a path: pass the INACTIVE row and assert the
    # guard holds it inactive while the live sibling is untouched. (Passing
    # the already-active row would assert nothing.) (#562 ADV-A2.)
    await db_session.refresh(first)
    assert first.is_active is False
    still = await RetentionService.update(db_session, first, RetentionPolicyUpdate(is_active=True))
    assert still.is_active is False
    await db_session.refresh(second)
    assert second.is_active is True


@pytest.mark.asyncio
async def test_breach_illegal_transition_raises(db_session: AsyncSession, test_clinic: Clinic):
    from app.modules.gdpr.schemas import DataBreachUpdate

    row = await DataBreachService.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Backup exposed",
            data_involved=["patients"],
            affected_people=1,
        ),
    )
    updated = await DataBreachService.update(db_session, row, DataBreachUpdate(status="reported"))
    assert updated.reported is True
    # Terminal and backwards moves are rejected: reported -> under_review
    # would leave a stale reported latch (#562 SEC-03).
    from app.modules.gdpr.service import BreachTransitionError

    with pytest.raises(BreachTransitionError, match="illegal breach transition"):
        await DataBreachService.update(db_session, updated, DataBreachUpdate(status="under_review"))


@pytest.mark.asyncio
async def test_breach_notified_authority_at_ignored(db_session: AsyncSession, test_clinic: Clinic):
    from datetime import datetime

    from app.modules.gdpr.schemas import DataBreachUpdate

    row = await DataBreachService.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Backup exposed",
            data_involved=["patients"],
            affected_people=1,
        ),
    )
    forged = datetime(2020, 1, 1)
    # An explicit timestamp decoupled from status is ignored: the stamp
    # is owned by the reported transition (#562 SEC-04).
    updated = await DataBreachService.update(
        db_session,
        row,
        DataBreachUpdate(status="reported", notified_authority_at=forged),
    )
    assert updated.notified_authority_at is not None
    assert updated.notified_authority_at.replace(tzinfo=None) != forged


@pytest.mark.asyncio
async def test_breach_create_rejects_empty_data_involved(
    db_session: AsyncSession, test_clinic: Clinic
):
    # An Art. 33 register entry with zero data categories is rejected
    # (#562 SEC-05).
    with pytest.raises(ValidationError):
        DataBreachCreate(description="Backup exposed", data_involved=[])


@pytest.mark.asyncio
async def test_partial_unique_index_rejects_twin_actives(
    db_session: AsyncSession, test_clinic: Clinic
):
    from sqlalchemy.exc import IntegrityError

    from app.modules.gdpr.models import RetentionPolicy

    # Bypass the service supersede: two committed active rows for one
    # (clinic, category) must fail at the backstop, proving gdpr_0002
    # fires (#562 ADV-S1-01). The service 409 handler is reviewed, not
    # runnable deterministically (it needs a true concurrent twin).
    db_session.add(
        RetentionPolicy(clinic_id=test_clinic.id, data_category="email", retention_years=0)
    )
    await db_session.commit()
    db_session.add(
        RetentionPolicy(clinic_id=test_clinic.id, data_category="email", retention_years=5)
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_breach_update_rejects_empty_data_involved(
    db_session: AsyncSession, test_clinic: Clinic
):
    from app.modules.gdpr.schemas import DataBreachUpdate

    row = await DataBreachService.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Backup exposed",
            data_involved=["patients"],
            affected_people=1,
        ),
    )
    # The create-side min_length must also hold on update: PATCH [] would
    # otherwise wipe the Art. 33(3) nature-of-data from the register.
    with pytest.raises(ValidationError):
        DataBreachUpdate(data_involved=[])
    updated = await DataBreachService.update(
        db_session, row, DataBreachUpdate(data_involved=["patients", "billing"])
    )
    assert updated.data_involved == ["patients", "billing"]


@pytest.mark.asyncio
async def test_consent_http_unknown_patient_404(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    from uuid import uuid4

    # The 404 surface, end to end: router maps the service None (#562 CONS-03).
    response = await client.post(
        "/api/v1/gdpr/consents",
        json={
            "patient_id": str(uuid4()),
            "purpose": "sms",
            "granted": True,
            "provided_text": "I accept receiving SMS.",
        },
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert response.json()["message"] == "Patient not found"


@pytest.mark.asyncio
async def test_breach_http_illegal_transition_422(
    db_session: AsyncSession,
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
):
    row = await DataBreachService.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Backup exposed",
            data_involved=["patients"],
            affected_people=1,
        ),
    )
    reported = await DataBreachService.update(db_session, row, DataBreachUpdate(status="reported"))
    # The 422 surface, end to end: router maps the transition error (#562 SEC-03).
    response = await client.patch(
        f"/api/v1/gdpr/breaches/{reported.id}",
        json={"status": "under_review"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "illegal breach transition" in response.json()["message"]


@pytest.mark.asyncio
async def test_breach_record_fields_correctable(db_session: AsyncSession, test_clinic: Clinic):
    from app.modules.gdpr.schemas import DataBreachUpdate

    # The documented remedy for a wrong report is correcting the record
    # fields (rewinding the lifecycle stays blocked).
    row = await DataBreachService.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Backup exposed",
            data_involved=["patients"],
            affected_people=1,
        ),
    )
    updated = await DataBreachService.update(
        db_session,
        row,
        DataBreachUpdate(description="Backup exposed (revised)", affected_people=5),
    )
    assert updated.description == "Backup exposed (revised)"
    assert updated.affected_people == 5
    assert updated.status == "under_review"


@pytest.mark.asyncio
async def test_breach_explicit_null_on_required_fields_is_noop(
    db_session: AsyncSession, test_clinic: Clinic
):
    from app.modules.gdpr.schemas import DataBreachUpdate

    # Explicit nulls on non-nullable columns are ignored, not 500s (#562 S1-04).
    # (Nullable affected_people genuinely clears on null.)
    row = await DataBreachService.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Backup exposed",
            data_involved=["patients"],
            affected_people=1,
        ),
    )
    updated = await DataBreachService.update(
        db_session,
        row,
        DataBreachUpdate(description=None, data_involved=None, affected_people=None),
    )
    assert updated.description == "Backup exposed"
    assert updated.data_involved == ["patients"]
    assert updated.affected_people is None


@pytest.mark.asyncio
async def test_export_returns_patient_data(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    await GdprService.create_request(
        db_session,
        test_clinic.id,
        GdprRequestCreate(requester_name="P", requester_email="p@test.com", request_type="access"),
    )
    data = await ExportService.export(db_session, test_clinic.id, test_patient.id)
    assert data["identity"]["email"] == "patient@test.com"
    assert data["identity"]["first_name"] == "Test"
    assert isinstance(data["consents"], list)


@pytest.mark.asyncio
async def test_cross_clinic_isolation(db_session: AsyncSession, test_clinic: Clinic):
    from uuid import uuid4

    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999991",
        address={"street": "Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()

    p_other = _make_patient(db_session, other.id)
    db_session.add(p_other)
    await db_session.flush()

    await GdprService.create_request(
        db_session,
        other.id,
        GdprRequestCreate(
            requester_name="Other", requester_email="o@test.com", request_type="access"
        ),
    )

    # A request created in clinic A must not be listable in clinic B.
    items, total = await GdprService.list_requests(db_session, test_clinic.id)
    assert total == 0

    # Export for a patient of clinic B queried under clinic A returns empty.
    data = await ExportService.export(db_session, test_clinic.id, p_other.id)
    assert data == {}


@pytest.mark.asyncio
async def test_erasure_unknown_patient_returns_none_and_writes_no_audit(
    db_session: AsyncSession, test_clinic: Clinic
):
    from uuid import uuid4

    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=uuid4(),
        categories=["email"],
        rationale="Art.17",
    )
    assert result is None
    logs, total = await ErasureService.list_audit(db_session, test_clinic.id)
    assert total == 0


@pytest.mark.asyncio
async def test_erasure_other_clinic_patient_returns_none(
    db_session: AsyncSession, test_clinic: Clinic
):
    from uuid import uuid4

    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B99999992",
        address={"street": "Otra", "city": "Madrid"},
        settings={"slot_duration_min": 15},
    )
    db_session.add(other)
    await db_session.commit()
    p_other = _make_patient(db_session, other.id)
    await db_session.flush()

    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=p_other.id,
        categories=["email"],
        rationale="Art.17",
    )
    assert result is None


@pytest.mark.asyncio
async def test_erasure_rejects_unknown_category():
    from app.modules.gdpr.schemas import ErasureRequest

    with pytest.raises(ValidationError):
        ErasureRequest(patient_id="12345678-1234-5678-1234-567812345678", categories=["clinical"])


@pytest.mark.asyncio
async def test_erasure_retention_window_uses_patient_updated_at_anchor(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update as sa_update

    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="phone", retention_years=1),
    )
    # Fresh patient → 1-year window not passed → retained.
    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=test_patient.id,
        categories=["phone"],
        rationale="Art.17",
    )
    assert result is not None
    assert result.erased_categories == []
    assert result.retained_categories == ["phone"]

    # Backdate updated_at past the window (direct SQL skips the onupdate
    # bump) → erasable.
    old = datetime.now(UTC) - timedelta(days=400)
    await db_session.execute(
        sa_update(Patient).where(Patient.id == test_patient.id).values(updated_at=old)
    )
    await db_session.commit()
    result = await ErasureService.execute(
        db_session,
        test_clinic.id,
        patient_id=test_patient.id,
        categories=["phone"],
        rationale="Art.17",
    )
    assert result is not None
    assert result.erased_categories == ["phone"]


@pytest.mark.asyncio
async def test_execute_erasure_tool_reports_missing_patient(
    db_session: AsyncSession, test_clinic: Clinic
):
    from uuid import uuid4

    from app.modules.gdpr.tools import _execute_erasure

    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id, agent_id=uuid4())
    from app.modules.gdpr.tools import ExecuteErasureArgs

    out = await _execute_erasure(
        ctx,
        ExecuteErasureArgs(patient_id=str(uuid4()), categories=["email"], rationale=None),
    )
    assert out == {"error": "patient not found"}


@pytest.mark.asyncio
async def test_consent_purpose_case_variants_collapse(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """CONS-05: "SMS", "sms" and "sms " are one purpose, not three."""
    for purpose in ("SMS", "sms", "sms "):
        await ConsentService.grant_or_withdraw(
            db_session,
            test_clinic.id,
            ConsentCreate(
                patient_id=test_patient.id,
                purpose=purpose,
                granted=True,
                provided_text="I accept.",
            ),
        )
    items, total = await ConsentService.list_consents(
        db_session, test_clinic.id, patient_id=test_patient.id
    )
    assert total == 3
    assert {i.purpose for i in items} == {"sms"}
    current = await ConsentService.current(db_session, test_clinic.id, test_patient.id, "SMS")
    assert current is not None and current.purpose == "sms"


@pytest.mark.asyncio
async def test_consent_current_endpoint_returns_latest(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    test_patient: Patient,
    db_session: AsyncSession,
):
    """CONS-04/08: the current endpoint agrees with the ledger, over HTTP."""
    from uuid import uuid4

    from app.modules.gdpr.service import ConsentService as _Svc

    await _Svc.grant_or_withdraw(
        db_session,
        test_clinic.id,
        ConsentCreate(
            patient_id=test_patient.id,
            purpose="email",
            granted=True,
            provided_text="Yes.",
        ),
    )
    await _Svc.grant_or_withdraw(
        db_session,
        test_clinic.id,
        ConsentCreate(patient_id=test_patient.id, purpose="email", granted=False),
    )
    got = await client.get(
        f"/api/v1/gdpr/consents/current?patient_id={test_patient.id}&purpose=email",
        headers=auth_headers,
    )
    assert got.status_code == 200
    assert got.json()["data"]["granted"] is False
    missing = await client.get(
        f"/api/v1/gdpr/consents/current?patient_id={uuid4()}&purpose=email",
        headers=auth_headers,
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_consent_grant_without_text_is_422(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """CONS-07/08: a grant with no shown text is not informed consent."""
    from uuid import uuid4

    blank = await client.post(
        "/api/v1/gdpr/consents",
        json={"patient_id": str(uuid4()), "purpose": "sms", "granted": True},
        headers=auth_headers,
    )
    assert blank.status_code == 422
    empty = await client.post(
        "/api/v1/gdpr/consents",
        json={"patient_id": str(uuid4()), "purpose": "sms", "granted": True, "provided_text": "  "},
        headers=auth_headers,
    )
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_consent_blank_purpose_is_422(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """CONS-05: a blank purpose passes ``min_length=1`` but normalizes to
    ``""``; the schema rejects it, so an empty key never enters the ledger."""
    from uuid import uuid4

    blank = await client.post(
        "/api/v1/gdpr/consents",
        json={"patient_id": str(uuid4()), "purpose": "   ", "granted": False},
        headers=auth_headers,
    )
    assert blank.status_code == 422


@pytest.mark.asyncio
async def test_consent_event_publishes_canonical_purpose(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """CONS-05: the grant event carries the canonical purpose - the same key
    that is stored and looked up - not the raw client string."""
    from app.core.events import EventType, event_bus

    seen: list[dict] = []

    async def _recorder(data):
        seen.append(data)

    event_bus.subscribe(EventType.GDPR_CONSENT_GRANTED, _recorder)
    try:
        await ConsentService.grant_or_withdraw(
            db_session,
            test_clinic.id,
            ConsentCreate(
                patient_id=test_patient.id,
                purpose="SMS ",
                granted=True,
                provided_text="Yes.",
            ),
        )
    finally:
        event_bus.unsubscribe(EventType.GDPR_CONSENT_GRANTED, _recorder)
    assert [s["purpose"] for s in seen] == ["sms"]


@pytest.mark.asyncio
async def test_consent_http_grant_withdraw_list_roundtrip(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
):
    """CONS-08: consent endpoints over HTTP, not just the service layer."""
    grant = await client.post(
        "/api/v1/gdpr/consents",
        json={
            "patient_id": str(test_patient.id),
            "purpose": "research",
            "granted": True,
            "provided_text": "I consent to research use.",
        },
        headers=auth_headers,
    )
    assert grant.status_code == 201
    assert grant.json()["data"]["purpose"] == "research"
    withdraw = await client.post(
        "/api/v1/gdpr/consents",
        json={"patient_id": str(test_patient.id), "purpose": "research", "granted": False},
        headers=auth_headers,
    )
    assert withdraw.status_code == 201
    listed = await client.get(
        f"/api/v1/gdpr/consents?patient_id={test_patient.id}", headers=auth_headers
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert listed.json()["data"][0]["granted"] is False


@pytest.mark.asyncio
async def test_request_status_filter_rejects_garbage(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
):
    """QUAL-11: status/type filters are closed vocabularies, not free text."""
    assert (
        await client.get("/api/v1/gdpr/requests?status=bogus", headers=auth_headers)
    ).status_code == 422
    assert (
        await client.get("/api/v1/gdpr/requests?request_type=bogus", headers=auth_headers)
    ).status_code == 422
    assert (
        await client.get("/api/v1/gdpr/breaches?status=bogus", headers=auth_headers)
    ).status_code == 422


@pytest.mark.asyncio
async def test_breach_resolved_flow_and_not_reportable_branch(
    db_session: AsyncSession, test_clinic: Clinic
):
    """SEC-07: beyond the happy path — full reported run + closed branch."""
    from app.modules.gdpr.schemas import DataBreachCreate, DataBreachUpdate
    from app.modules.gdpr.service import BreachTransitionError
    from app.modules.gdpr.service import DataBreachService as _Svc

    row = await _Svc.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(description="Lost drive", data_involved=["email"], affected_people=3),
    )
    row = await _Svc.update(
        db_session, row, DataBreachUpdate(status="reported", description="Lost encrypted drive")
    )
    assert row.status == "reported" and row.reported is True
    assert row.notified_authority_at is not None
    row = await _Svc.update(db_session, row, DataBreachUpdate(status="resolved"))
    assert row.status == "resolved"

    other = await _Svc.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(description="False alarm", data_involved=["email"]),
    )
    other = await _Svc.update(db_session, other, DataBreachUpdate(status="not_reportable"))
    assert other.status == "not_reportable" and other.reported is False
    # Closed branch: resolved is unreachable from here, retry path stays open.
    with pytest.raises(BreachTransitionError):
        await _Svc.update(db_session, other, DataBreachUpdate(status="resolved"))
    other = await _Svc.update(db_session, other, DataBreachUpdate(status="under_review"))
    assert other.status == "under_review"


@pytest.mark.asyncio
async def test_reported_to_not_reportable_keeps_the_latches(
    db_session: AsyncSession, test_clinic: Clinic
):
    """The edge agreed in the #664 review round: the authority ruled the
    report below the threshold after notification, so the record moves -
    but the latches stay, because the notification really happened."""
    from app.modules.gdpr.schemas import DataBreachCreate, DataBreachUpdate
    from app.modules.gdpr.service import DataBreachService as _Svc

    row = await _Svc.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(description="Misdirected letter", data_involved=["email"]),
    )
    row = await _Svc.update(db_session, row, DataBreachUpdate(status="reported"))
    assert row.reported is True and row.notified_authority_at is not None

    row = await _Svc.update(db_session, row, DataBreachUpdate(status="not_reportable"))
    assert row.status == "not_reportable"
    assert row.reported is True, "the authority notification happened; it stays on the record"
    assert row.notified_authority_at is not None


@pytest.mark.asyncio
async def test_breach_subject_notification_fields_persist(
    db_session: AsyncSession, test_clinic: Clinic
):
    """SEC-02: Art. 34 subject-notification record (gdpr_0003 columns)."""
    from datetime import UTC, datetime

    from app.modules.gdpr.schemas import DataBreachCreate, DataBreachUpdate
    from app.modules.gdpr.service import DataBreachService as _Svc

    row = await _Svc.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(description="Mail misfire", data_involved=["email"], affected_people=12),
    )
    assert row.notified_subjects_at is None
    row = await _Svc.update(
        db_session,
        row,
        DataBreachUpdate(
            status="reported",
            notified_subjects_at=datetime(2026, 10, 1, tzinfo=UTC),
            notified_subjects_count=12,
        ),
    )
    assert row.notified_subjects_count == 12
    assert row.notified_subjects_at is not None

    # A late-discovered incident may already have been communicated, so the
    # record has to be settable at creation too (L4: a persistable field
    # belongs on both schemas).
    late = await _Svc.create(
        db_session,
        test_clinic.id,
        DataBreachCreate(
            description="Discovered in audit",
            data_involved=["national_id"],
            notified_subjects_at=datetime(2026, 9, 1, tzinfo=UTC),
            notified_subjects_count=4,
        ),
    )
    assert late.notified_subjects_count == 4
    assert late.notified_subjects_at is not None


@pytest.mark.asyncio
async def test_breach_tools_report_and_list(db_session: AsyncSession, test_clinic: Clinic):
    """SEC-06: breach register reachable from agents, clinic-scoped."""
    from uuid import uuid4

    from app.modules.gdpr.tools import (
        ListBreachesArgs,
        ReportBreachArgs,
        _list_breaches,
        _report_breach,
    )

    ctx = SimpleNamespace(db=db_session, clinic_id=test_clinic.id, agent_id=uuid4())
    out = await _report_breach(
        ctx,
        ReportBreachArgs(description="Phish", data_involved=["email"], affected_people=2),
    )
    assert out["status"] == "under_review"
    listed = await _list_breaches(ctx, ListBreachesArgs(status=None, limit=20))
    assert listed["total"] >= 1
    filtered = await _list_breaches(ctx, ListBreachesArgs(status="reported", limit=20))
    assert filtered["total"] == 0


@pytest.mark.asyncio
async def test_hold_boundary_today_holds_yesterday_releases(
    db_session: AsyncSession, test_clinic: Clinic, test_patient: Patient
):
    """RET-03: a hold through today still holds; yesterday's hold released."""
    from datetime import UTC, datetime, timedelta

    from app.modules.gdpr.schemas import RetentionPolicyCreate
    from app.modules.gdpr.service import ErasureService, RetentionService

    # The service measures "today" as the UTC date, so the test must build
    # its boundary from the same clock. `date.today()` is host-local and
    # drifts a day in the east-of-utc CI job, which then reads a hold set
    # for "yesterday" as still in force.
    today = datetime.now(UTC).date()
    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(data_category="email", retention_years=0, legal_hold_until=today),
    )
    erasable, retained = await ErasureService.erasure_eligible(
        db_session, test_clinic.id, ["email"], today
    )
    assert retained == ["email"] and erasable == []
    await RetentionService.create(
        db_session,
        test_clinic.id,
        RetentionPolicyCreate(
            data_category="email", retention_years=0, legal_hold_until=today - timedelta(days=1)
        ),
    )
    erasable, retained = await ErasureService.erasure_eligible(
        db_session, test_clinic.id, ["email"], today
    )
    assert erasable == ["email"] and retained == []
