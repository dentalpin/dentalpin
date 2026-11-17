"""DebtMapper gating rules + happy path.

Stub-driven coverage of the early-exit branches (no DB needed) and
DB-backed checks for signed amounts, ledger labels and idempotent imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.auth.models import Clinic, User
from app.modules.migration_import.mappers.base import MapperContext, MappingResolver
from app.modules.migration_import.mappers.debt import DebtMapper
from app.modules.migration_import.models import ImportJob, ImportWarning
from app.modules.patients.models import Patient
from app.modules.payments.models import PatientEarnedEntry
from app.modules.payments.service import LedgerService

CLINIC_ID = uuid4()


@dataclass
class _StubResolver:
    """Minimal MappingResolver stand-in for the mapper's lookups."""

    _store: dict[tuple[str, str], Any] = field(default_factory=dict)
    _skipped: set[tuple[str, str]] = field(default_factory=set)

    async def get(self, entity_type: str, canonical_uuid: str):
        return self._store.get((entity_type, canonical_uuid))

    async def set(
        self,
        entity_type: str,
        canonical_uuid: str,
        source_system: str,
        dentalpin_table: str,
        dentalpin_id: Any,
    ) -> None:
        self._store[(entity_type, canonical_uuid)] = dentalpin_id

    async def mark_skipped(self, entity_type: str, canonical_uuid: str, source_system: str) -> None:
        self._skipped.add((entity_type, canonical_uuid))

    async def was_skipped(self, entity_type: str, canonical_uuid: str) -> bool:
        return (entity_type, canonical_uuid) in self._skipped


class _RecordingDB:
    """Captures ``add()`` calls so we can inspect what the mapper writes
    without a real session.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None: ...
    async def execute(self, _stmt: Any):
        class _Empty:
            def first(self) -> None:
                return None

        return _Empty()


@dataclass
class _StubCtx:
    """MapperContext stand-in for the early-exit branches."""

    job_id: Any = field(default_factory=uuid4)
    clinic_id: Any = field(default=CLINIC_ID)
    resolver: _StubResolver = field(default_factory=_StubResolver)
    handle: Any = None
    db: _RecordingDB = field(default_factory=_RecordingDB)


def _payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "patient_uuid": str(uuid4()),
        "applied_treatment_uuid": None,
        "owed_amount": "100.00",
        "due_date": "2024-06-15",
        "cancelled_by_uuid": None,
        "uncollectible": False,
        "treatment_number": "1",
        "phase_number": 1,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_skip_when_anulado() -> None:
    ctx = _StubCtx()
    result = await DebtMapper().apply(
        ctx,  # type: ignore[arg-type]
        entity_type="debt",
        payload=_payload(cancelled_by_uuid=str(uuid4())),
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="42",
        source_system="gesden",
    )
    assert result is None
    assert not [a for a in ctx.db.added if isinstance(a, PatientEarnedEntry)]
    assert any(
        isinstance(a, ImportWarning) and a.code == "debt.skipped_anulado" for a in ctx.db.added
    )


@pytest.mark.asyncio
async def test_skip_when_uncollectible() -> None:
    ctx = _StubCtx()
    result = await DebtMapper().apply(
        ctx,  # type: ignore[arg-type]
        entity_type="debt",
        payload=_payload(uncollectible=True, uncollectible_description="No localizado"),
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="42",
        source_system="gesden",
    )
    assert result is None
    assert any(
        isinstance(a, ImportWarning) and a.code == "debt.skipped_uncollectible"
        for a in ctx.db.added
    )


@pytest.mark.asyncio
async def test_skip_when_zero_owed() -> None:
    ctx = _StubCtx()
    result = await DebtMapper().apply(
        ctx,  # type: ignore[arg-type]
        entity_type="debt",
        payload=_payload(owed_amount="0"),
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="42",
        source_system="gesden",
    )
    assert result is None
    assert not [a for a in ctx.db.added if isinstance(a, PatientEarnedEntry)]


@pytest.mark.asyncio
async def test_skip_when_patient_unmapped() -> None:
    ctx = _StubCtx()
    result = await DebtMapper().apply(
        ctx,  # type: ignore[arg-type]
        entity_type="debt",
        payload=_payload(owed_amount="100", patient_uuid=str(uuid4())),
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="42",
        source_system="gesden",
    )
    assert result is None
    assert any(
        isinstance(a, ImportWarning) and a.code == "debt.unmapped_patient" for a in ctx.db.added
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "expected_event", "expected_description"),
    [
        ({}, "migration_import:debt", "Adeudo migrado · NumTto 1 · fase 1"),
        (
            {"description": "x" * 161},
            "migration_import:debt",
            "x" * 160,
        ),
        (
            {"opening_balance": True, "description": "Saldo inicial vTiger"},
            "migration_import:opening_balance",
            "Saldo inicial vTiger",
        ),
        (
            {"opening_balance": True, "description": "Crédito vTiger", "owed_amount": "-80.50"},
            "migration_import:opening_balance",
            "Crédito vTiger",
        ),
        (
            {"opening_balance": True, "description": " "},
            "migration_import:opening_balance",
            "Saldo de apertura",
        ),
    ],
)
async def test_books_earned_when_billed(
    db_session,
    overrides: dict[str, Any],
    expected_event: str,
    expected_description: str,
) -> None:
    """Book the signed amount once and expose it on the patient ledger."""
    clinic, admin = await _bootstrap(db_session)
    patient = Patient(
        clinic_id=clinic.id,
        first_name="Test",
        last_name="Debt",
    )
    db_session.add(patient)
    await db_session.flush()

    canonical_patient = str(uuid4())
    canonical_debt = str(uuid4())
    ctx = await _ctx(db_session, clinic.id, admin.id)
    await ctx.resolver.set(
        entity_type="patient",
        canonical_uuid=canonical_patient,
        source_system="gesden",
        dentalpin_table="patients",
        dentalpin_id=patient.id,
    )

    payload = _payload(patient_uuid=canonical_patient, **overrides)
    amount = Decimal(payload["owed_amount"])
    result = await DebtMapper().apply(
        ctx,
        entity_type="debt",
        payload=payload,
        raw={},
        canonical_uuid=canonical_debt,
        source_id="99",
        source_system="gesden",
    )
    assert result is not None

    rows = await db_session.execute(
        select(PatientEarnedEntry).where(PatientEarnedEntry.patient_id == patient.id)
    )
    earned = rows.scalars().all()
    assert len(earned) == 1
    assert earned[0].amount == amount
    assert earned[0].source_event == expected_event
    assert earned[0].description == expected_description

    ledger = await LedgerService.get_patient_ledger(db_session, clinic.id, patient.id, "EUR")
    assert ledger.clinic_receivable == max(Decimal("0"), amount)
    assert ledger.patient_credit == max(Decimal("0"), -amount)
    assert ledger.total_paid == ledger.on_account_balance == Decimal("0")
    assert [entry.description for entry in ledger.timeline] == [expected_description]

    # A new import job resolves the same canonical UUID from persistent mappings.
    await db_session.commit()
    retry_ctx = await _ctx(db_session, clinic.id, admin.id)
    again = await DebtMapper().apply(
        retry_ctx,
        entity_type="debt",
        payload=payload,
        raw={},
        canonical_uuid=canonical_debt,
        source_id="99",
        source_system="gesden",
    )
    assert again == result
    rows = await db_session.execute(
        select(PatientEarnedEntry).where(PatientEarnedEntry.patient_id == patient.id)
    )
    assert len(rows.scalars().all()) == 1


async def _bootstrap(db_session) -> tuple[Clinic, User]:
    clinic = Clinic(id=uuid4(), name="C", tax_id=f"B-{uuid4().hex[:8]}")
    admin = User(
        id=uuid4(),
        email=f"admin-{uuid4().hex[:8]}@test.local",
        password_hash="x",
        first_name="A",
        last_name="A",
    )
    db_session.add_all([clinic, admin])
    await db_session.flush()
    return clinic, admin


async def _ctx(db_session, clinic_id, admin_id) -> MapperContext:
    job = ImportJob(
        clinic_id=clinic_id,
        created_by=admin_id,
        status="executing",
        original_filename="t.dpm",
        file_path="/tmp/t.dpm",
        file_size=0,
    )
    db_session.add(job)
    await db_session.flush()
    return MapperContext(
        db=db_session,
        clinic_id=clinic_id,
        job_id=job.id,
        resolver=MappingResolver(db=db_session, clinic_id=clinic_id, job_id=job.id),
        import_fiscal_compliance=False,
        created_by=admin_id,
    )
