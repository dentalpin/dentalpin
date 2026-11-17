"""Map ``debt`` → :class:`payments.PatientEarnedEntry`.

Gesdén's ``DeudaCli`` is the authoritative billing ledger. A row exists
iff the clinic actually billed a treatment (or treatment phase) — a
realised treatment without a corresponding ``DeudaCli`` was performed
off-books (staff/family/courtesy/old pre-billing-system records). This
mapper translates one ``DeudaCli`` row into one ``PatientEarnedEntry``
with ``amount = Adeudo`` so the patient ledger reflects what Gesdén
actually charged, not the catalog reference price stamped on
``TtosMed.Importe``.

The clinical history is preserved upstream: ``Treatment``,
``PlannedTreatmentItem``, ``TreatmentTooth``, ``ToothRecord``
all come from ``AppliedTreatmentMapper`` and run regardless of whether
a debt exists. A patient with realised treatments but no debt still
sees their odontogram + plan; their balance is just zero.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

from sqlalchemy import select

from app.modules.odontogram.models import Treatment
from app.modules.payments.models import PatientEarnedEntry

from ..models import ImportWarning
from .base import MapperContext


class DebtMapper:
    async def apply(
        self,
        ctx: MapperContext,
        *,
        entity_type: str,
        payload: dict[str, Any],
        raw: dict[str, Any],
        canonical_uuid: str,
        source_id: str,
        source_system: str,
    ) -> UUID | None:
        existing = await ctx.resolver.get("debt", canonical_uuid)
        if existing is not None:
            return existing
        if await ctx.resolver.was_skipped("debt", canonical_uuid):
            return None

        # 1) Cancellation chain — IdAnulado set means the source PMS
        # already voided this debt row. Don't book.
        if payload.get("cancelled_by_uuid"):
            await _warn(
                ctx,
                source_id,
                "debt.skipped_anulado",
                "Deuda omitida: cancelada en origen (IdAnulado).",
            )
            await ctx.resolver.mark_skipped("debt", canonical_uuid, source_system)
            return None

        # 2) Bad debt — Incobrable=True. Per ops decision the clinic
        # already wrote off the receivable; we don't surface it on the
        # patient ledger. The raw row stays in RawEntity for audit.
        if payload.get("uncollectible"):
            reason = payload.get("uncollectible_description") or "sin motivo"
            await _warn(
                ctx,
                source_id,
                "debt.skipped_uncollectible",
                f"Deuda omitida: marcada Incobrable en origen ({reason}).",
            )
            await ctx.resolver.mark_skipped("debt", canonical_uuid, source_system)
            return None

        # 3) Zero / null Adeudo — placeholder rows the source carries
        # for historical settled debts. Nothing to book.
        owed = _decimal_or_none(payload.get("owed_amount"))
        if owed is None or owed == 0:
            await ctx.resolver.mark_skipped("debt", canonical_uuid, source_system)
            return None

        # 4) Patient resolution. Without a patient the entry can't land
        # on any ledger; warn and drop.
        patient_uuid = payload.get("patient_uuid")
        if not patient_uuid:
            await _warn(
                ctx,
                source_id,
                "debt.no_patient",
                "Deuda omitida: sin paciente origen.",
            )
            return None
        patient_id = await ctx.resolver.get("patient", str(patient_uuid))
        if patient_id is None:
            await _warn(
                ctx,
                source_id,
                "debt.unmapped_patient",
                "Deuda omitida: paciente no mapeado previamente.",
            )
            return None

        # 5) Best-effort enrichment from the linked Treatment. The
        # applied_treatment mapper registers a sidecar
        # ``applied_treatment_record`` → ``treatments.id`` resolver entry
        # so debts can recover catalog/professional/performed_at without
        # rejoining via the PlannedTreatmentItem hop. When the source
        # row pointed at a TtosMed we never imported (orphan), book the
        # ledger entry anyway — ``PatientEarnedEntry.treatment_id`` has
        # no FK on purpose.
        treatment_id: UUID | None = None
        applied_treatment_uuid = payload.get("applied_treatment_uuid")
        if applied_treatment_uuid:
            treatment_id = await ctx.resolver.get(
                "applied_treatment_record", str(applied_treatment_uuid)
            )
            if treatment_id is None:
                # The sidecar is missing when the applied_treatment
                # mapper routed the canonical to an administrative
                # ClinicalNote instead of a Treatment (non-clinical
                # entries: payment-on-account memos, anotaciones,
                # generic services with no catalog link). Those are
                # never billable services — skip the earned entry so
                # the patient ledger doesn't double-count payments as
                # phantom income.
                applied_target = await ctx.resolver.mapping_table(
                    "applied_treatment", str(applied_treatment_uuid)
                )
                if applied_target == "clinical_notes":
                    await _warn(
                        ctx,
                        source_id,
                        "debt.no_clinical_target",
                        f"Deuda apunta a anotación administrativa migrada "
                        f"(canonical={applied_treatment_uuid}); no se registra en el ledger.",
                    )
                    await ctx.resolver.mark_skipped("debt", canonical_uuid, source_system)
                    return None
                await _warn(
                    ctx,
                    source_id,
                    "debt.orphan_treatment",
                    f"Deuda sin Treatment vinculado (canonical={applied_treatment_uuid}); "
                    "se registra en el ledger sin enlace clínico.",
                )

        catalog_item_id: UUID | None = None
        professional_id: UUID | None = None
        performed_at: datetime | None = None
        clinical_type: str | None = None
        if treatment_id is not None:
            row = await ctx.db.execute(
                select(
                    Treatment.catalog_item_id,
                    Treatment.performed_by,
                    Treatment.performed_at,
                    Treatment.recorded_at,
                    Treatment.clinical_type,
                ).where(Treatment.id == treatment_id)
            )
            result = row.first()
            if result is not None:
                catalog_item_id = result.catalog_item_id
                professional_id = result.performed_by
                performed_at = result.performed_at or result.recorded_at
                clinical_type = result.clinical_type

        # 6) Performed timestamp. Prefer (a) the source ``FecPlazo``
        # (due date — usually when the line was billed), (b) the
        # treatment's performed_at, (c) recorded_at, (d) now. The
        # patient ledger orders rows by ``performed_at``; getting this
        # close to reality keeps the patient timeline coherent.
        when = _parse_date(payload.get("due_date")) or performed_at or datetime.now(UTC)

        # 7) Snapshot label so the UI timeline can render without
        # rejoining the source. The payments service ledger query
        # prefers the joined catalog name, falls back to this
        # ``description`` field, then to ``source_event`` — so a
        # human label here saves the row from showing the raw
        # ``migration_import:debt`` tag when the treatment has no
        # destination catalog link. Format: friendly clinical type +
        # source identifiers for traceability. 160 chars is the cap.
        treatment_number = payload.get("treatment_number")
        phase_number = payload.get("phase_number")
        head = _CLINICAL_TYPE_LABELS.get(clinical_type, "Tratamiento migrado")
        bits = [head]
        if treatment_number:
            bits.append(f"NumTto {treatment_number}")
        if phase_number is not None:
            bits.append(f"fase {phase_number}")
        is_opening_balance = payload.get("opening_balance") is True
        description = payload.get("description")
        if not isinstance(description, str) or not description.strip():
            description = "Saldo de apertura" if is_opening_balance else " · ".join(bits)

        # The earned-entries table enforces ``(treatment_id,
        # source_session_id)`` uniqueness. One treatment commonly
        # has multiple ``DeudaCli`` (per-phase billing), so we mint a
        # deterministic ``source_session_id`` from the debt's
        # canonical_uuid: distinct per debt, stable across re-runs.
        # Orphan debts (no resolved Treatment) share a sentinel
        # ``treatment_id`` and rely on the same session-id bucketing
        # for uniqueness.
        session_id = uuid5(NAMESPACE_DNS, f"migration_import:debt:{canonical_uuid}")
        entry = PatientEarnedEntry(
            clinic_id=ctx.clinic_id,
            patient_id=patient_id,
            treatment_id=treatment_id or _ORPHAN_TREATMENT_ID,
            catalog_item_id=catalog_item_id,
            source_session_id=session_id,
            amount=owed,
            performed_at=when,
            professional_id=professional_id,
            source_event=(
                "migration_import:opening_balance"
                if is_opening_balance
                else "migration_import:debt"
            ),
            description=description[:160],
        )
        ctx.db.add(entry)
        await ctx.db.flush()

        await ctx.resolver.set(
            entity_type="debt",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="patient_earned_entries",
            dentalpin_id=entry.id,
        )
        return entry.id


# Human-readable Spanish labels for the destination ``clinical_type``
# values written by ``AppliedTreatmentMapper``. Used as the leading
# bit of ``PatientEarnedEntry.description`` so the patient Pagos
# timeline shows "Implante · NumTto 12 · fase 1" instead of the raw
# ``migration_import:debt`` source_event tag when the underlying
# Treatment lacks a destination ``TreatmentCatalogItem`` link (very
# common: only ~33% of migrated treatments match a seed catalog
# entry). Keys mirror the enum in ``odontogram.constants``.
_CLINICAL_TYPE_LABELS: dict[str | None, str] = {
    "band": "Banda ortodóncica",
    "bracket": "Bracket",
    "root_canal_full": "Endodoncia",
    "root_canal_two_thirds": "Endodoncia parcial",
    "root_canal_half": "Endodoncia parcial",
    "root_canal_overfill": "Endodoncia",
    "filling_composite": "Obturación composite",
    "filling_amalgam": "Obturación amalgama",
    "filling_temporary": "Obturación temporal",
    "apicoectomy": "Apicectomía",
    "implant": "Implante",
    "post": "Perno",
    "crown": "Corona",
    "bridge": "Puente",
    "sealant": "Sellado",
    "veneer": "Carilla",
    "extraction": "Extracción",
    "inlay": "Incrustación",
    "overlay": "Recubrimiento",
    "crown_on_implant": "Corona sobre implante",
    "provisional_crown_on_implant": "Corona provisional sobre implante",
    "splint": "Férula",
    "retainer": "Retenedor",
    "attachment": "Attachment",
    "migrated": "Tratamiento migrado",
    None: "Adeudo migrado",
}


# Sentinel ``treatment_id`` for orphan debts whose source
# ``IdentTM`` points at a TtosMed we never imported (the source row
# was skipped as non-clinical, deduped as a shadow planned twin, or
# never made it into the subset). Every orphan still gets a unique
# ``source_session_id`` derived from the debt's canonical_uuid, so
# the ``(treatment_id, source_session_id)`` constraint holds.
_ORPHAN_TREATMENT_ID = UUID("00000000-0000-0000-0000-000000000000")


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_date(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        try:
            d = date.fromisoformat(str(value)[:10])
            return datetime(d.year, d.month, d.day, tzinfo=UTC)
        except (TypeError, ValueError):
            return None


async def _warn(ctx: MapperContext, source_id: str, code: str, message: str) -> None:
    ctx.db.add(
        ImportWarning(
            job_id=ctx.job_id,
            entity_type="debt",
            source_id=source_id,
            severity="warn",
            code=code,
            message=message,
        )
    )
