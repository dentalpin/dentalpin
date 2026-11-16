"""Exercise direct and legacy catalog links on imported invoice lines."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.billing.models import Invoice, InvoiceItem
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory
from app.modules.migration_import.mappers.base import MapperContext, MappingResolver
from app.modules.migration_import.mappers.fiscal_document_line import FiscalDocumentLineMapper
from app.modules.migration_import.models import ImportJob, ImportWarning
from app.modules.odontogram.models import Treatment
from app.modules.patients.models import Patient
from app.modules.treatment_plan.models import PlannedTreatmentItem, TreatmentPlan


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("references", "expected_catalog", "unmapped_field"),
    [
        ({"treatment_variant_uuid": "variant"}, "variant", None),
        (
            {"treatment_variant_uuid": "variant", "applied_treatment_uuid": "applied"},
            "variant",
            None,
        ),
        (
            {"treatment_uuid": "parent", "treatment_variant_uuid": "variant"},
            "parent",
            None,
        ),
        ({"applied_treatment_uuid": "applied"}, "applied", None),
        (
            {"treatment_variant_uuid": "missing", "applied_treatment_uuid": "applied"},
            "applied",
            "treatment_variant_uuid",
        ),
        ({"treatment_variant_uuid": "missing"}, None, "treatment_variant_uuid"),
        (
            {"treatment_uuid": "missing", "treatment_variant_uuid": "variant"},
            "variant",
            "treatment_uuid",
        ),
        ({}, None, None),
    ],
    ids=[
        "variant-without-act",
        "variant-before-act",
        "parent-before-variant",
        "legacy-act",
        "missing-variant-with-act",
        "missing-variant-without-act",
        "missing-parent-with-variant",
        "no-links",
    ],
)
async def test_resolve_catalog_link(
    db_session: AsyncSession,
    references: dict[str, str],
    expected_catalog: str | None,
    unmapped_field: str | None,
) -> None:
    """Persist the resolved catalog link and preserve the billed snapshot."""
    clinic = Clinic(id=uuid4(), name="Test Clinic", tax_id="B12345678")
    user = User(
        id=uuid4(),
        email="importer@example.test",
        password_hash="unused",
        first_name="Test",
        last_name="Importer",
    )
    patient = Patient(id=uuid4(), clinic_id=clinic.id, first_name="Test", last_name="Patient")
    invoice = Invoice(id=uuid4(), clinic_id=clinic.id, patient_id=patient.id, created_by=user.id)
    category = TreatmentCategory(id=uuid4(), clinic_id=clinic.id, key="test")
    catalog = {
        key: TreatmentCatalogItem(
            id=uuid4(),
            clinic_id=clinic.id,
            category_id=category.id,
            internal_code=key,
            default_price=Decimal("500.00"),
        )
        for key in ("parent", "variant", "applied")
    }
    treatment = Treatment(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        catalog_item_id=catalog["applied"].id,
        clinical_type="crown",
        status="performed",
        recorded_at=datetime.now(UTC),
    )
    plan = TreatmentPlan(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        plan_number="TEST-001",
        created_by=user.id,
    )
    plan_item = PlannedTreatmentItem(
        id=uuid4(), clinic_id=clinic.id, treatment_plan_id=plan.id, treatment_id=treatment.id
    )
    job = ImportJob(
        id=uuid4(),
        clinic_id=clinic.id,
        created_by=user.id,
        status="executing",
        original_filename="test.dpm",
        file_path="/tmp/test.dpm",
        file_size=0,
    )
    db_session.add_all(
        [
            clinic,
            user,
            patient,
            invoice,
            category,
            *catalog.values(),
            treatment,
            plan,
            plan_item,
            job,
        ]
    )
    await db_session.flush()

    resolver = MappingResolver(db_session, clinic.id, job.id)
    canonical = {
        key: str(uuid4()) for key in ("invoice", "parent", "variant", "applied", "missing")
    }
    for key, entity_type, table, row_id in (
        ("invoice", "fiscal_document", "invoices", invoice.id),
        ("parent", "treatment_catalog_item", "treatment_catalog_items", catalog["parent"].id),
        ("variant", "treatment_catalog_variant", "treatment_catalog_items", catalog["variant"].id),
        ("applied", "applied_treatment", "planned_treatment_items", plan_item.id),
    ):
        await resolver.set(
            entity_type=entity_type,
            canonical_uuid=canonical[key],
            source_system="test",
            dentalpin_table=table,
            dentalpin_id=row_id,
        )
    ctx = MapperContext(db_session, clinic.id, job.id, resolver, False, user.id)

    item_id = await FiscalDocumentLineMapper().apply(
        ctx,
        entity_type="fiscal_document_line",
        payload={
            "document_uuid": canonical["invoice"],
            "concept": "Imported concept",
            "amount": "125.00",
            **{field: canonical[key] for field, key in references.items()},
        },
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="42",
        source_system="test",
    )

    assert item_id is not None
    item = await db_session.get(InvoiceItem, item_id)
    assert item is not None
    assert item.invoice_id == invoice.id
    assert item.catalog_item_id == (catalog[expected_catalog].id if expected_catalog else None)
    assert item.description == "Imported concept"
    assert item.line_total == Decimal("125.00")
    warnings = (
        await db_session.scalars(select(ImportWarning).where(ImportWarning.job_id == job.id))
    ).all()
    if unmapped_field:
        assert len(warnings) == 1
        warning = warnings[0]
        assert warning.code == "fiscal_document_line.unmapped_catalog_reference"
        assert warning.source_id == "42"
        assert unmapped_field in warning.message
    else:
        assert not warnings
