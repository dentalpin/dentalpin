"""Map ``applied_treatment`` → :class:`treatment_plan.PlannedTreatmentItem`.

DPMF's ``applied_treatment`` row is the clinical event: a patient
underwent (or is scheduled to undergo) a specific catalog entry. In
DentalPin this requires three rows in cooperation:

1. **One ``TreatmentPlan`` per (patient, source budget)**. Gesdén
   organises clinical activity around budgets; piling 100+ items
   into a single per-patient plan makes the UI unreadable. The
   mapper resolves ``applied_treatment.budget_line_uuid`` → its
   ``BudgetItem.budget_id`` and creates a plan titled after the
   source budget number ("Migrado — PRES-2024-0007"). Applied
   treatments without a budget link land in a "Migrado — sin
   presupuesto" catch-all per patient.
2. **One ``odontogram.Treatment``** for the actual tooth treatment
   record. ``clinical_type`` is derived from the raw Gesdén
   ``IdTipoOdg`` code via :func:`clinical_type_for_tipo_odg` so the UI
   shows real names ("filling_composite", "implant", "crown" …)
   instead of every row landing as the catch-all "migrated". The
   catalog item is also linked so the imported budget/treatment
   inherits the destination catalog's pricing strategy and labels.
3. **One ``PlannedTreatmentItem``** linking the plan and the
   treatment.

The ``applied_treatment_phase`` mapper attaches sessions to the
``PlannedTreatmentItem`` produced here.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.modules.budget.models import Budget, BudgetItem
from app.modules.clinical_notes.models import ClinicalNote
from app.modules.odontogram.models import ToothRecord, Treatment, TreatmentTooth
from app.modules.treatment_plan.models import PlannedTreatmentItem, TreatmentPlan

from ..models import ImportWarning
from ._gesden_catalog import clinical_type_for_tipo_odg
from .base import MapperContext

# Gesdén ``TtosMed.StaTto`` codes that mean "treatment was performed".
# 5 dominates (~99 % of finished work) and 6 is a low-volume variant
# also carrying ``FecFin``. The remaining codes (3 = in active plan
# but not yet done, 1/2/4/8 = legacy/unclear) all leave ``FecFin``
# null in the source and stay as ``pending`` items.
_REALISED_CODES: set[int] = {5, 6}

# Threshold for the "notes longer than catalog name → likely
# performed" heuristic. Field validation against ``SOURCE_DB`` shows
# StaTto=3 averages 25 chars of notes (essentially just the catalog
# entry name), while StaTto=5 averages 91 chars (catalog name +
# clinical detail: implant lot, surfaces, dose, etc.). 40 chars sits
# above the noise floor and still catches the bulk of legitimately
# performed entries the clinic forgot to flag.
_NOTES_LIKELY_PERFORMED_MIN_CHARS = 40

# Heuristic age thresholds applied to ``FecIni`` for the
# "data-hygiene rescue" pass on StaTto=3 entries:
# - older than ``_OLD_TREATMENT_AGE_DAYS`` (5 years) → assume done
#   regardless of notes. A treatment planned but never done that long
#   ago is statistically negligible.
# - older than ``_MID_TREATMENT_AGE_DAYS`` (2 years) AND with notes
#   that exceed the catalog-name floor → assume done. The notes
#   length acts as the second corroborating signal.
_OLD_TREATMENT_AGE_DAYS = 365 * 5
_MID_TREATMENT_AGE_DAYS = 365 * 2

# Maximum gap (days) between a planned line and its performed twin
# before we stop treating them as the same intervention. Presupuestos
# typically execute within 3-18 months; 24 months is conservative
# enough to catch slow clinics while rejecting the case where a
# treatment is genuinely repeated years later on the same tooth.
_SHADOW_WINDOW_DAYS = 365 * 2

# Plan status to write for every migrated plan. Gesdén plans are by
# definition already-accepted historical records — leaving them in
# ``draft`` would force the operator to confirm each one manually
# before any consumer (budget, payments, reports) treats them as
# real. ``active`` is the post-acceptance state in DentalPin's plan
# machine and is the right migration target.
_MIGRATED_PLAN_STATUS = "active"

# Catch-all clinical_type for source rows whose ``IdTipoOdg`` doesn't
# map to a known DentalPin treatment vocabulary entry. Visible in
# warnings so the operator can backfill the mapping.
_FALLBACK_CLINICAL_TYPE = "migrated"

# Gesdén ``IdTipoOdg`` → DentalPin ``TreatmentType`` resolution lives
# in :mod:`._gesden_catalog` and is shared with the catalog template
# mapper so the two stay in sync over the 46-value ``TTipoOdg`` master.
# Use :func:`clinical_type_for_tipo_odg` — returns ``None`` for
# non-clinical entries (Higiene, Panorámica, Anotación, …) which this
# mapper treats as the catch-all ``"migrated"``.

# Once a treatment is realised, its DentalPin ``clinical_type`` often
# implies an observable artefact on the tooth (missing, crown,
# implant…). Without this mapping the imported odontogram looks
# uniformly ``healthy`` even for patients with decades of restorative
# history, because we only created the per-event ``Treatment`` rows
# and never touched ``ToothRecord.general_condition``. The chart reads
# that column, so the migrated mouth appeared empty.
#
# Values intentionally mirror the ``ToothCondition`` enum in
# ``odontogram/constants.py`` (importing it here would push that
# module into the import graph and isn't worth the coupling).
_CLINICAL_TYPE_TO_TOOTH_CONDITION: dict[str, str] = {
    "extraction": "missing",
    "implant": "implant",
    "crown": "crown",
    "bridge": "crown",  # bridges show as crowned on each abutment/pontic
    "veneer": "crown",
    "post": "crown",  # post-and-core; visible artefact is the crown
    "filling_composite": "filling",
    "filling_amalgam": "filling",
    "filling_temporary": "filling",
    "inlay": "filling",
    "overlay": "filling",
    "sealant": "sealant",
    "root_canal_full": "root_canal",
    "root_canal_two_thirds": "root_canal",
    "root_canal_half": "root_canal",
    "root_canal_overfill": "root_canal",
}

# Precedence used to break ties when two treatments on the same tooth
# carry the same effective date. Higher wins. Implant beats missing
# (a tooth was extracted and later implanted — final state is
# implant). Restorations beat the "treated" hints (root canal). The
# tie-breaker only kicks in when chronology is genuinely identical;
# normally we compare on ``effective_date`` and keep the latest.
_CONDITION_PRECEDENCE: dict[str, int] = {
    "healthy": 0,
    "missing": 1,
    "sealant": 2,
    "filling": 3,
    "root_canal": 4,
    "crown": 5,
    "implant": 6,
}


# Gesdén ``IdTipoOdg`` codes that aren't tooth-level clinical
# treatments — they're audit / non-clinical entries Gesdén lets the
# clinic park on the treatment timeline. Importing them as
# ``odontogram.Treatment`` rows pollutes the plan with line items
# that have no clinical meaning, so the mapper drops them on the
# floor (with an info warning + the canonical row still landing in
# ``RawEntity`` for audit).
_NON_CLINICAL_TIPO_ODG: set[int] = {
    1,  # Piezas Iniciales (tooth state)
    2,  # Posición Diente (orthodontic position state)
    3,  # Rotación Diente (orthodontic rotation state)
    4,  # Pieza Niño (deciduous presence)
    5,  # Pieza Adulto (permanent presence)
    6,  # SuperNumeraria (extra tooth)
    9,  # Nuevo Paciente
    10,  # Visita No Atendida
    11,  # Anotación
    12,  # Nota Económica
    13,  # Primera Visita
    14,  # Bonos
    38,  # Higiene (whole-mouth, not tooth-specific)
    39,  # Panorámicas (radiograph)
    40,  # Teleradio (radiograph)
    41,  # Fluorización (not tooth-specific)
    42,  # Genérico (meta)
}


def _routes_to_note(payload: dict[str, Any], raw: dict[str, Any]) -> bool:
    """True when the row becomes an administrative ClinicalNote, not a Treatment.

    Either ``IdTipoOdg`` is a known non-clinical code, or the row carries
    no clinical signal at all (no catalog variant and no IdTipoOdg that
    resolves to a ``clinical_type``).
    """
    id_tipo_odg = _coerce_int(raw.get("IdTipoOdg"))
    if id_tipo_odg in _NON_CLINICAL_TIPO_ODG:
        return True
    return not payload.get("treatment_variant_uuid") and (
        clinical_type_for_tipo_odg(id_tipo_odg) is None
    )


class AppliedTreatmentMapper:
    def __init__(self) -> None:
        # (clinic_id, patient_id, budget_id_or_year) -> plan_id. One
        # plan per source budget keeps each plan to a manageable size;
        # the year slot is the per-patient catch-all for treatments
        # imported without a budget link, so 20 years of history fans
        # out into "Migrado — 2018", "Migrado — 2019", … rather than
        # one mega-plan.
        self._plan_cache: dict[tuple[UUID, UUID, UUID | int | None], UUID] = {}
        # plan_id -> next sequence_order to assign. Avoids a SELECT per item.
        self._next_sequence: dict[UUID, int] = {}
        # (clinic_id, patient_id, tooth_number) -> tooth_record_id. Lazy
        # creation of per-tooth state so TreatmentTooth has a valid FK
        # without us scanning the full odontogram up-front.
        self._tooth_cache: dict[tuple[UUID, UUID, int], UUID] = {}
        # budget_item_id -> budget_id. Resolved on first need; the
        # source can attach hundreds of applied_treatments to the same
        # budget so the cache pays for itself quickly.
        self._budget_for_item: dict[UUID, UUID] = {}
        # (clinic_id, patient_id, tooth_number) ->
        #   (current_condition, effective_date). We process applied
        # treatments in DPMF iteration order (not strictly
        # chronological), so a chronologically-later treatment can
        # arrive before an earlier one. Keep the chosen state in
        # memory and only overwrite the ToothRecord row when the new
        # treatment's effective date is later (or equal date but
        # higher precedence).
        self._tooth_state: dict[tuple[UUID, UUID, int], tuple[str, datetime]] = {}
        # Shadow-pairing index. Gesdén creates a *new* TtosMed row at
        # StaTto=5 when a budgeted line (StaTto=3) is performed, leaving
        # the original planned row untouched. We detect those shadow
        # pairs in a single DPMF pre-pass and drop the planned twin so
        # the odontogram doesn't display obvious duplicates.
        #   planned_canonical_uuid -> performed_canonical_uuid
        self._shadow_index: dict[str, str] | None = None
        #   performed_canonical_uuid -> PlannedTreatmentItem.id
        # Filled by apply() as performed rows are processed.
        self._performed_item_id: dict[str, UUID] = {}
        #   performed_canonical_uuid -> [planned_canonical_uuid, ...]
        # Shadows whose performed twin hasn't been seen yet — we'll
        # redirect their resolver mapping once the twin lands.
        self._pending_shadow_links: dict[str, list[str]] = defaultdict(list)
        #   performed_canonical_uuid -> Treatment.id
        # Sidecar so the same redirection happens for the
        # ``applied_treatment_record`` resolver entry — the DebtMapper
        # reads that side car to recover the destination Treatment row.
        self._performed_treatment_id: dict[str, UUID] = {}

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
        existing = await ctx.resolver.get("applied_treatment", canonical_uuid)
        if existing is not None:
            return existing

        patient_uuid = payload.get("patient_uuid")
        if not patient_uuid:
            await _warn(
                ctx, source_id, "applied_treatment.no_patient", "Tratamiento omitido: sin paciente."
            )
            return None
        patient_id = await ctx.resolver.get("patient", str(patient_uuid))
        if patient_id is None:
            await _warn(
                ctx,
                source_id,
                "applied_treatment.unmapped_patient",
                "Tratamiento omitido: paciente no mapeado previamente.",
            )
            return None

        # Budget-shadow check. If this row was identified as the
        # planned twin of a performed sibling during the pre-pass,
        # drop it and let any FK references resolve to the performed
        # counterpart instead.
        shadow_index = self._ensure_shadow_index(ctx)
        twin_uuid = shadow_index.get(canonical_uuid)
        if twin_uuid is not None:
            await _warn(
                ctx,
                source_id,
                "applied_treatment.shadow_planned",
                f"Línea presupuesto omitida: existe acto realizado coincidente "
                f"(canonical_uuid={twin_uuid}).",
            )
            twin_item_id = self._performed_item_id.get(twin_uuid)
            twin_treatment_id = self._performed_treatment_id.get(twin_uuid)
            if twin_item_id is not None and twin_treatment_id is not None:
                await ctx.resolver.set(
                    entity_type="applied_treatment",
                    canonical_uuid=canonical_uuid,
                    source_system=source_system,
                    dentalpin_table="planned_treatment_items",
                    dentalpin_id=twin_item_id,
                )
                await ctx.resolver.set(
                    entity_type="applied_treatment_record",
                    canonical_uuid=canonical_uuid,
                    source_system=source_system,
                    dentalpin_table="treatments",
                    dentalpin_id=twin_treatment_id,
                )
            else:
                self._pending_shadow_links[twin_uuid].append(canonical_uuid)
            return None

        # Route non-clinical Gesdén entries (notes, payment memos,
        # panoramic X-rays, hygiene visits, generic services…) to a
        # patient-level administrative ClinicalNote instead of a
        # synthetic Treatment. Two source signals qualify:
        #
        # - ``IdTipoOdg`` in :data:`_NON_CLINICAL_TIPO_ODG`
        #   (Anotación, Nota Económica, Higiene, Panorámica, …).
        # - The row carries *no* recognisable clinical signal:
        #   ``IdTto`` is null **and** ``IdTipoOdg`` doesn't resolve to a
        #   DentalPin ``clinical_type``. These are the free-text rows
        #   that would otherwise land as ``clinical_type='migrated'``
        #   (the catch-all) with a blank label. Rows with a known
        #   clinical IdTipoOdg (filling, crown, extraction…) but no
        #   catalog link stay as Treatments — we don't lose the
        #   clinical typing just because the source skipped catalog
        #   selection.
        #
        # The canonical row still lands in RawEntity via the catch-all
        # so the audit trail isn't lost. The patient ledger is driven
        # separately by ``DebtMapper`` reading ``DeudaCli`` — this code
        # path never touches earned entries.
        id_tipo_odg = _coerce_int(raw.get("IdTipoOdg"))
        has_no_catalog_variant = not payload.get("treatment_variant_uuid")
        if _routes_to_note(payload, raw):
            # Short-circuit re-runs.
            if await ctx.resolver.was_skipped("applied_treatment", canonical_uuid):
                return None
            await _warn(
                ctx,
                source_id,
                "applied_treatment.non_clinical_entry",
                (
                    "Entrada no clínica registrada como nota administrativa "
                    f"(IdTipoOdg={id_tipo_odg}, IdTto={'null' if has_no_catalog_variant else 'set'})."
                ),
            )
            note_id = await self._record_non_clinical_note(
                ctx,
                patient_id=patient_id,
                payload=payload,
                source_id=source_id,
                id_tipo_odg=id_tipo_odg,
            )
            if note_id is not None:
                # Register against ``applied_treatment`` so downstream
                # references (phases, fiscal lines) resolve to a real
                # row. No sidecar ``applied_treatment_record``: there's
                # no Treatment to recover. ``DebtMapper`` tolerates the
                # miss and skips the PatientEarnedEntry — these aren't
                # billable services.
                await ctx.resolver.set(
                    entity_type="applied_treatment",
                    canonical_uuid=canonical_uuid,
                    source_system=source_system,
                    dentalpin_table="clinical_notes",
                    dentalpin_id=note_id,
                )
            else:
                # Empty notes + no catalog → nothing worth keeping in
                # patient-facing surfaces. Sentinel suppresses re-warns.
                await ctx.resolver.mark_skipped("applied_treatment", canonical_uuid, source_system)
            return None

        professional_id: UUID | None = None
        prof_uuid = payload.get("professional_uuid")
        if prof_uuid:
            professional_id = await ctx.resolver.get("professional", str(prof_uuid))

        catalog_item_id: UUID | None = None
        variant_uuid = payload.get("treatment_variant_uuid")
        if variant_uuid:
            catalog_item_id = await ctx.resolver.get("treatment_catalog_variant", str(variant_uuid))
            if catalog_item_id is None:
                await _warn(
                    ctx,
                    source_id,
                    "applied_treatment.unmapped_variant",
                    f"Variante de catálogo {variant_uuid} no encontrada en mappings "
                    "previos; se importa el tratamiento sin enlace de catálogo.",
                )

        # Resolve clinical_type from Gesdén's ``IdTipoOdg`` so the UI
        # surfaces real labels ("filling_composite", "implant", "crown"
        # …) instead of every row reading "migrated".
        clinical_type, was_resolved = _resolve_clinical_type(id_tipo_odg)
        if not was_resolved and id_tipo_odg not in (None, 0):
            await _warn(
                ctx,
                source_id,
                "applied_treatment.unmapped_tipo_odg",
                f"IdTipoOdg={id_tipo_odg} sin equivalente clínico en DentalPin; "
                f"se ha registrado como '{_FALLBACK_CLINICAL_TYPE}'.",
            )

        # Status & timestamps. ``StaTto`` 5/6 and ``FecFin`` presence
        # are the only formal Gesdén signals for "done", but this
        # specific export's data hygiene is poor — implants planned
        # 13 years ago that were obviously performed still sit at
        # StaTto=3 because the clinic never updated the flag. Apply
        # the corroborating heuristics decided in #ops:
        #
        #   1) StaTto ∈ {5, 6}                 → done (formal)
        #   2) FecFin set                       → done (formal)
        #   3) FecIni older than 5 years        → done (age alone)
        #   4) FecIni older than 2 years AND
        #      notes longer than the catalog
        #      name floor (40 chars)            → done (age + clinical detail)
        #
        # Every heuristic-triggered hit emits an audit warning so the
        # operator can spot-check the reclassification.
        status_code = _coerce_int(payload.get("status_code"))
        start_dt = _parse_datetime(payload.get("start_date")) or datetime.now(UTC)
        end_dt = _parse_datetime(payload.get("end_date"))
        amount = _decimal_or_none(payload.get("amount"))

        formal_done = status_code in _REALISED_CODES or end_dt is not None
        is_realised = formal_done
        if not is_realised:
            notes_value = payload.get("notes") or ""
            notes_chars = len(notes_value)
            age_days = (datetime.now(UTC) - start_dt).days
            if age_days >= _OLD_TREATMENT_AGE_DAYS:
                is_realised = True
                await _warn(
                    ctx,
                    source_id,
                    "applied_treatment.completed_by_age",
                    f"Tratamiento marcado como realizado por antigüedad "
                    f"({age_days // 365} años desde FecIni); Gesdén lo "
                    "deja en StaTto=3.",
                )
            elif (
                age_days >= _MID_TREATMENT_AGE_DAYS
                and notes_chars > _NOTES_LIKELY_PERFORMED_MIN_CHARS
            ):
                is_realised = True
                await _warn(
                    ctx,
                    source_id,
                    "applied_treatment.completed_by_notes",
                    f"Tratamiento marcado como realizado por notas "
                    f"clínicas ({notes_chars} chars) sobre tratamiento "
                    f"antiguo ({age_days // 365} años); StaTto=3 en "
                    "Gesdén.",
                )

        # When the heuristic says "done" but Gesdén has no end date,
        # use FecIni as an approximation so DentalPin's reports have
        # a date to anchor on.
        if is_realised and end_dt is None and not formal_done:
            end_dt = start_dt

        # Plan grouping: prefer the source budget link (one plan per
        # source presupuesto). When the source has no budget for this
        # treatment, fall back to a per-year bucket so a patient with
        # 20 years of history doesn't end up with one mega-plan.
        budget_id, budget_item_id = await self._budget_for_applied_treatment(ctx, payload)
        year_for_grouping = start_dt.year if budget_id is None and start_dt else None
        plan_id = await self._get_or_create_plan(ctx, patient_id, budget_id, year=year_for_grouping)

        # 1) odontogram.Treatment header — clinical record.
        treatment = Treatment(
            clinic_id=ctx.clinic_id,
            patient_id=patient_id,
            clinical_type=clinical_type,
            scope="tooth",
            catalog_item_id=catalog_item_id,
            status="performed" if is_realised else "planned",
            recorded_at=start_dt,
            performed_at=end_dt if is_realised else None,
            performed_by=professional_id if is_realised else None,
            price_snapshot=amount,
            notes=payload.get("notes"),
            source_module="migration_import",
            budget_item_id=budget_item_id,
        )
        ctx.db.add(treatment)
        await ctx.db.flush()

        # 1a) Back-fill the symmetric link on the budget side so the
        # Presupuesto UI shows each accepted line connected to its
        # imported Treatment. ``BudgetItem.treatment_id`` is nullable
        # and stays so for lines whose source had no
        # ``applied_treatment_uuid`` (planned-only quotes).
        if budget_item_id is not None:
            await ctx.db.execute(
                BudgetItem.__table__.update()
                .where(
                    BudgetItem.id == budget_item_id,
                    BudgetItem.clinic_id == ctx.clinic_id,
                )
                .values(treatment_id=treatment.id)
            )

        # 1b) TreatmentTooth children — populate from the decoded teeth
        # the dental-bridge transformer emits (PiezasAdu + PiezasLec
        # bit-mask decode). Surfaces remain ``None`` until the
        # ``ZonasPieza`` encoding is field-validated.
        teeth = payload.get("teeth") or []
        artefact_condition = (
            _CLINICAL_TYPE_TO_TOOTH_CONDITION.get(clinical_type) if is_realised else None
        )
        effective_state_date = end_dt or start_dt
        for tooth_number in teeth:
            tn = int(tooth_number)
            tooth_record_id = await self._tooth_record_id(
                ctx, patient_id=patient_id, tooth_number=tn
            )
            ctx.db.add(
                TreatmentTooth(
                    treatment_id=treatment.id,
                    tooth_record_id=tooth_record_id,
                    tooth_number=tn,
                )
            )
            if artefact_condition is not None:
                await self._update_tooth_condition(
                    ctx,
                    patient_id=patient_id,
                    tooth_number=tn,
                    tooth_record_id=tooth_record_id,
                    new_condition=artefact_condition,
                    effective_date=effective_state_date,
                )
        if teeth:
            await ctx.db.flush()

        # 2) PlannedTreatmentItem — links the plan to the Treatment.
        sequence = self._next_sequence.get(plan_id, 0) + 1
        self._next_sequence[plan_id] = sequence
        item = PlannedTreatmentItem(
            clinic_id=ctx.clinic_id,
            treatment_plan_id=plan_id,
            treatment_id=treatment.id,
            sequence_order=sequence,
            status="completed" if is_realised else "pending",
            completed_at=end_dt if is_realised else None,
            completed_by=professional_id if is_realised else None,
            assigned_professional_id=professional_id,
            notes=payload.get("notes"),
        )
        ctx.db.add(item)
        await ctx.db.flush()

        # The patient ledger is populated by ``DebtMapper`` from
        # ``DeudaCli`` (the only Gesdén source of truth for "this work
        # was billed"). Booking earned from ``TtosMed.Importe`` would
        # over-book — ~76% of realised treatments in real Gesdén
        # exports have no ``DeudaCli``: staff/family/courtesy work,
        # "incluido" bundle lines, pre-billing-system historicals.
        # The clinical record below still lands so the odontogram and
        # plan view show the work.

        # 4) ClinicalNote — Gesdén stores per-treatment narrative
        # (composite shade, implant lot, anaesthetic, surfaces,
        # outcome…) in ``TtosMed.Notas``. We mirror it on
        # ``Treatment.notes`` but the UI's clinical-notes feed reads
        # from the polymorphic ``clinical_notes`` table, so a copy of
        # the body needs to land there as a ``note_type='treatment'``
        # row owned by the Treatment. Without this the timeline /
        # sidebar look empty for migrated patients even though the
        # original PMS had decades of clinical narrative.
        note_body = (payload.get("notes") or "").strip()
        if note_body:
            note_at = end_dt or start_dt
            ctx.db.add(
                ClinicalNote(
                    clinic_id=ctx.clinic_id,
                    note_type="treatment",
                    owner_type="treatment",
                    owner_id=treatment.id,
                    tooth_number=None,
                    body=note_body,
                    author_id=professional_id or ctx.created_by,
                    created_at=note_at,
                    updated_at=note_at,
                )
            )
            await ctx.db.flush()

        await ctx.resolver.set(
            entity_type="applied_treatment",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="planned_treatment_items",
            dentalpin_id=item.id,
        )
        # Sidecar mapping for ``DebtMapper``: it needs ``Treatment.id``
        # to enrich earned entries (catalog_item_id, professional_id,
        # performed_at) and to honour the ledger's
        # ``(treatment_id, source_session_id)`` constraint. The
        # primary ``applied_treatment`` entry resolves to the
        # PlannedTreatmentItem so downstream phase/budget mappers keep
        # working; this second entry resolves to the Treatment row.
        await ctx.resolver.set(
            entity_type="applied_treatment_record",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="treatments",
            dentalpin_id=treatment.id,
        )

        # Drain shadows that arrived before this performed twin: now
        # that the performed has a ``PlannedTreatmentItem``, redirect
        # each pending planned canonical_uuid at it so any
        # ``applied_treatment_phase`` / ``budget_line`` / ``debt``
        # still resolves cleanly.
        self._performed_item_id[canonical_uuid] = item.id
        self._performed_treatment_id[canonical_uuid] = treatment.id
        pending = self._pending_shadow_links.pop(canonical_uuid, None)
        if pending:
            for planned_uuid in pending:
                await ctx.resolver.set(
                    entity_type="applied_treatment",
                    canonical_uuid=planned_uuid,
                    source_system=source_system,
                    dentalpin_table="planned_treatment_items",
                    dentalpin_id=item.id,
                )
                await ctx.resolver.set(
                    entity_type="applied_treatment_record",
                    canonical_uuid=planned_uuid,
                    source_system=source_system,
                    dentalpin_table="treatments",
                    dentalpin_id=treatment.id,
                )

        return item.id

    def _ensure_shadow_index(self, ctx: MapperContext) -> dict[str, str]:
        """One-pass scan over every ``applied_treatment`` row in the
        DPMF, building the planned→performed shadow map.

        Pairing key — preferred: ``(patient_uuid, IdPresuTto)``.
        Gesdén explicitly links a planned (StaTto=3) line and its
        realised twin via shared ``IdPresuTto`` (the budget-line FK,
        ``PresuTto.Ident``), so two TtosMed rows sharing that FK are
        the same clinical event even when ``IdTto`` differs (which
        happens when the tariff was edited between plan-creation and
        execution).

        Fallback key — when ``IdPresuTto`` is null on either side:
        ``(patient_uuid, IdTto, IdTipoOdg, sorted_teeth)``. Rows with
        no budget link can still pair against same-tariff, same-type,
        same-teeth siblings within the 24-month window.

        Within a group we match each performed row with the closest
        earlier planned that no other performed has claimed yet,
        within ``_SHADOW_WINDOW_DAYS``.

        Lazy: built on first call, returns ``{}`` when the DPMF
        handle isn't available (test paths, programmatic use).
        """
        if self._shadow_index is not None:
            return self._shadow_index
        if ctx.handle is None:
            self._shadow_index = {}
            return self._shadow_index

        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in ctx.handle.entity_iter("applied_treatment"):
            cu, _src_id, _src_sys, payload_json, raw_json, _ts = row
            try:
                payload = json.loads(payload_json)
                raw = json.loads(raw_json)
            except json.JSONDecodeError:
                continue
            patient_uuid = payload.get("patient_uuid")
            if not patient_uuid:
                continue
            # Rows routed to an administrative note are not treatments:
            # pairing them would drop free-text notes as "planned
            # twins" (they all share the legacy key (patient, None,
            # None, ())). Same predicate as apply() (#872).
            if _routes_to_note(payload, raw):
                continue
            start_dt = _parse_datetime(payload.get("start_date"))
            end_dt = _parse_datetime(payload.get("end_date"))
            status_code = _coerce_int(payload.get("status_code"))
            performed = status_code in _REALISED_CODES or end_dt is not None

            budget_line_uuid = payload.get("budget_line_uuid")
            if budget_line_uuid:
                key: tuple[Any, ...] = (
                    "budget_line",
                    str(patient_uuid),
                    str(budget_line_uuid),
                )
            else:
                id_tto = _coerce_int(raw.get("IdTto"))
                id_tipo_odg = _coerce_int(raw.get("IdTipoOdg"))
                teeth = payload.get("teeth") or []
                teeth_key = tuple(sorted(int(t) for t in teeth))
                key = ("legacy", str(patient_uuid), id_tto, id_tipo_odg, teeth_key)
            groups[key].append(
                {
                    "canonical_uuid": cu,
                    "performed": performed,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                }
            )

        window = _SHADOW_WINDOW_DAYS
        shadow: dict[str, str] = {}
        for rows in groups.values():
            if len(rows) < 2:
                continue
            performed_rows = [r for r in rows if r["performed"] and (r["end_dt"] or r["start_dt"])]
            planned_rows = [r for r in rows if not r["performed"] and r["start_dt"]]
            if not performed_rows or not planned_rows:
                continue
            # Sort performed by effective date (ascending) so the
            # earliest performed claims the earliest matching planned.
            performed_rows.sort(key=lambda r: r["end_dt"] or r["start_dt"])
            planned_rows.sort(key=lambda r: r["start_dt"])
            claimed: set[int] = set()
            for perf in performed_rows:
                perf_dt = perf["end_dt"] or perf["start_dt"]
                best_idx: int | None = None
                for idx, plan in enumerate(planned_rows):
                    if idx in claimed:
                        continue
                    plan_dt = plan["start_dt"]
                    if plan_dt is None or plan_dt > perf_dt:
                        continue
                    if (perf_dt - plan_dt).days > window:
                        continue
                    # Closest-but-earlier wins: prefer the planned
                    # with the largest start_dt still <= perf_dt.
                    if best_idx is None or plan_dt > planned_rows[best_idx]["start_dt"]:
                        best_idx = idx
                if best_idx is not None:
                    claimed.add(best_idx)
                    shadow[planned_rows[best_idx]["canonical_uuid"]] = perf["canonical_uuid"]

        self._shadow_index = shadow
        return shadow

    async def _record_non_clinical_note(
        self,
        ctx: MapperContext,
        *,
        patient_id: UUID,
        payload: dict[str, Any],
        source_id: str,
        id_tipo_odg: int | None,
    ) -> UUID | None:
        """Persist a Gesdén non-clinical TtosMed row as a patient-level
        :class:`ClinicalNote` instead of a synthetic ``Treatment``.

        Covers two source shapes:

        - ``IdTipoOdg`` in the non-clinical taxonomy (Anotación, Nota
          Económica, Bonos, Higiene, Panorámica…). These never represent
          per-tooth interventions; some are administrative memos
          ("Pago a cuenta de Tratamientos"), others are whole-mouth
          services. Both belong on the patient summary feed, not in the
          odontogram chart or plan list.
        - ``IdTto`` null (no catalog variant). The receptionist typed
          free text without picking a service from the catalog. In our
          field exports these are the bulk of the noise (≈4 k rows on
          a 500-patient subset).

        Resulting :class:`ClinicalNote` is ``note_type='administrative'``
        and ``owner_type='patient'``. The note body is the source
        ``Notas`` field verbatim. ``author_id`` defaults to the admin
        who launched the import; if the source row has a resolvable
        ``professional_uuid`` we attribute the note to that clinician
        instead. ``created_at`` is backdated to the source ``FecFin``
        (or ``FecIni`` when no end date) so the patient timeline keeps
        chronological order.

        Returns the new ``ClinicalNote.id`` or ``None`` when the source
        row has no usable text (caller marks the canonical skipped so
        re-runs don't re-warn).
        """
        body = (payload.get("notes") or "").strip()
        if not body:
            return None
        start_dt = _parse_datetime(payload.get("start_date")) or datetime.now(UTC)
        end_dt = _parse_datetime(payload.get("end_date")) or start_dt
        author_id = ctx.created_by
        prof_uuid = payload.get("professional_uuid")
        if prof_uuid:
            resolved = await ctx.resolver.get("professional", str(prof_uuid))
            if resolved is not None:
                author_id = resolved
        note = ClinicalNote(
            clinic_id=ctx.clinic_id,
            note_type="administrative",
            owner_type="patient",
            owner_id=patient_id,
            tooth_number=None,
            body=body,
            author_id=author_id,
            created_at=end_dt,
            updated_at=end_dt,
        )
        ctx.db.add(note)
        await ctx.db.flush()
        return note.id

    async def _update_tooth_condition(
        self,
        ctx: MapperContext,
        *,
        patient_id: UUID,
        tooth_number: int,
        tooth_record_id: UUID,
        new_condition: str,
        effective_date: datetime,
    ) -> None:
        """Last-write-wins by effective_date; precedence breaks ties.

        We do not overwrite a state that came from a chronologically
        later treatment, which can happen because the DPMF rows are
        not sorted by date. When the dates match exactly, the higher
        precedence wins (e.g. an implant placed the same day a tooth
        was extracted keeps the implant as final state).
        """
        key = (ctx.clinic_id, patient_id, tooth_number)
        current = self._tooth_state.get(key)
        if current is not None:
            current_condition, current_date = current
            if effective_date < current_date:
                return
            if effective_date == current_date and (
                _CONDITION_PRECEDENCE.get(new_condition, 0)
                <= _CONDITION_PRECEDENCE.get(current_condition, 0)
            ):
                return
        self._tooth_state[key] = (new_condition, effective_date)
        await ctx.db.execute(
            ToothRecord.__table__.update()
            .where(ToothRecord.id == tooth_record_id)
            .values(general_condition=new_condition)
        )

    async def _tooth_record_id(
        self, ctx: MapperContext, *, patient_id: UUID, tooth_number: int
    ) -> UUID:
        """Resolve (or lazily create) the ``ToothRecord`` for a patient/tooth pair.

        Re-runs are safe — an existing row is reused. New rows land
        with ``general_condition='healthy'`` and an empty ``surfaces``
        map; subsequent clinical activity in DentalPin overlays state
        on top.
        """
        key = (ctx.clinic_id, patient_id, tooth_number)
        if key in self._tooth_cache:
            return self._tooth_cache[key]

        result = await ctx.db.execute(
            select(ToothRecord.id).where(
                ToothRecord.clinic_id == ctx.clinic_id,
                ToothRecord.patient_id == patient_id,
                ToothRecord.tooth_number == tooth_number,
            )
        )
        tooth_id = result.scalar_one_or_none()
        if tooth_id is None:
            tooth_type = "permanent" if 11 <= tooth_number <= 48 else "deciduous"
            record = ToothRecord(
                clinic_id=ctx.clinic_id,
                patient_id=patient_id,
                tooth_number=tooth_number,
                tooth_type=tooth_type,
                general_condition="healthy",
                surfaces={},
            )
            ctx.db.add(record)
            await ctx.db.flush()
            tooth_id = record.id

        self._tooth_cache[key] = tooth_id
        return tooth_id

    async def _budget_for_applied_treatment(
        self, ctx: MapperContext, payload: dict[str, Any]
    ) -> tuple[UUID | None, UUID | None]:
        """Walk ``applied_treatment.budget_line_uuid`` → (budget_id, budget_item_id).

        Both ids are returned because the caller needs the item to
        back-fill ``BudgetItem.treatment_id`` once it has created the
        ``Treatment`` row.
        """
        budget_line_uuid = payload.get("budget_line_uuid")
        if not budget_line_uuid:
            return None, None
        budget_item_id = await ctx.resolver.get("budget_line", str(budget_line_uuid))
        if budget_item_id is None:
            return None, None
        if budget_item_id in self._budget_for_item:
            return self._budget_for_item[budget_item_id], budget_item_id
        result = await ctx.db.execute(
            select(BudgetItem.budget_id).where(BudgetItem.id == budget_item_id)
        )
        budget_id = result.scalar_one_or_none()
        if budget_id is not None:
            self._budget_for_item[budget_item_id] = budget_id
        return budget_id, budget_item_id

    async def _get_or_create_plan(
        self,
        ctx: MapperContext,
        patient_id: UUID,
        budget_id: UUID | None,
        year: int | None = None,
    ) -> UUID:
        cache_key = (ctx.clinic_id, patient_id, budget_id if budget_id else year)
        if cache_key in self._plan_cache:
            return self._plan_cache[cache_key]

        # Per-budget plan title carries the source budget number for
        # human navigation; the per-year fallback keeps catch-all
        # plans tractable when the source carries no budget link.
        if budget_id is not None:
            result = await ctx.db.execute(
                select(Budget.budget_number).where(Budget.id == budget_id)
            )
            budget_number = result.scalar_one_or_none() or str(budget_id)[:8]
            title = f"Migrado — {budget_number}"
            plan_number = f"MIG-{budget_number}"
            notes = (
                f"Plan generado por dental-bridge para tratamientos del "
                f"presupuesto {budget_number}."
            )
        elif year is not None:
            title = f"Migrado — {year}"
            plan_number = f"MIG-{str(patient_id)[:8]}-{year}"
            notes = (
                f"Plan generado por dental-bridge para tratamientos "
                f"realizados en {year} sin presupuesto de origen."
            )
        else:
            title = "Migrado — sin fecha"
            plan_number = f"MIG-{str(patient_id)[:8]}-ND"
            notes = (
                "Plan generado por dental-bridge para tratamientos sin "
                "presupuesto ni fecha de origen."
            )

        # Idempotent lookup so re-imports don't multiply plans.
        result = await ctx.db.execute(
            select(TreatmentPlan.id).where(
                TreatmentPlan.clinic_id == ctx.clinic_id,
                TreatmentPlan.patient_id == patient_id,
                TreatmentPlan.plan_number == plan_number,
            )
        )
        plan_id = result.scalar_one_or_none()
        if plan_id is None:
            # Bypass ``TreatmentPlanService.create`` — its
            # ``count(*)``-based plan-number generator collides after
            # any historic delete leaves gaps, and re-importing under
            # gap conditions throws ``uq_treatment_plan_number``. The
            # synthetic ``MIG-<budget_number>`` / ``MIG-<patient>-NB``
            # is deterministic, unique per (clinic, patient,
            # budget_or_none) and immediately re-runnable.
            plan = TreatmentPlan(
                clinic_id=ctx.clinic_id,
                patient_id=patient_id,
                plan_number=plan_number,
                title=title,
                status=_MIGRATED_PLAN_STATUS,
                internal_notes=notes,
                budget_id=budget_id,
                created_by=ctx.created_by,
            )
            ctx.db.add(plan)
            await ctx.db.flush()
            plan_id = plan.id

        self._plan_cache[cache_key] = plan_id
        return plan_id


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_clinical_type(id_tipo_odg: int | None) -> tuple[str, bool]:
    """Return ``(clinical_type, was_resolved)`` for a Gesdén ``IdTipoOdg``.

    Backed by the shared :mod:`._gesden_catalog` table. ``None`` from
    the shared lookup (non-clinical Gesdén row like Higiene/Panorámica
    or a value we genuinely don't know) maps to the catch-all
    ``_FALLBACK_CLINICAL_TYPE`` so the operator sees a warning.
    """
    mapped = clinical_type_for_tipo_odg(id_tipo_odg)
    if mapped is None:
        return _FALLBACK_CLINICAL_TYPE, False
    return mapped, True


async def _warn(ctx: MapperContext, source_id: str, code: str, message: str) -> None:
    ctx.db.add(
        ImportWarning(
            job_id=ctx.job_id,
            entity_type="applied_treatment",
            source_id=source_id,
            severity="warn",
            code=code,
            message=message,
        )
    )


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
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
