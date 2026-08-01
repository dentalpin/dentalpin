"""Business logic service for odontogram module."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.events import event_bus
from app.core.events.types import EventType
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentOdontogramMapping
from app.modules.catalog.pricing import (
    PricingTooth,
    compute_duration_snapshot,
    compute_price_snapshot,
)

from .constants import (
    ATOMIC_MULTI_TOOTH_TYPES,
    ToothCondition,
    TreatmentStatus,
    get_tooth_type,
)
from .models import OdontogramHistory, ToothRecord, Treatment, TreatmentTooth


def build_treatment_response(treatment: Treatment) -> dict:
    """Produce a dict matching TreatmentResponse from a loaded Treatment.

    Requires `treatment.performer`, `treatment.teeth`, `treatment.catalog_item` to be
    eager-loaded. The dict is passed through Pydantic in the router.
    """
    performer_name = None
    if treatment.performed_by is not None and treatment.performer is not None:
        performer_name = f"{treatment.performer.first_name} {treatment.performer.last_name}"

    catalog_brief = None
    if treatment.catalog_item is not None:
        catalog_brief = {
            "id": treatment.catalog_item.id,
            "internal_code": treatment.catalog_item.internal_code,
            "names": treatment.catalog_item.names,
            "default_price": treatment.catalog_item.default_price,
        }

    return {
        "id": treatment.id,
        "patient_id": treatment.patient_id,
        "clinical_type": treatment.clinical_type,
        "scope": treatment.scope,
        "arch": treatment.arch,
        "status": treatment.status,
        "catalog_item_id": treatment.catalog_item_id,
        "catalog_item": catalog_brief,
        "teeth": [
            {
                "id": t.id,
                "tooth_record_id": t.tooth_record_id,
                "tooth_number": t.tooth_number,
                "role": t.role,
                "surfaces": t.surfaces,
            }
            for t in treatment.teeth
        ],
        "recorded_at": treatment.recorded_at,
        "performed_at": treatment.performed_at,
        "performed_by": treatment.performed_by,
        "performed_by_name": performer_name,
        "price_snapshot": treatment.price_snapshot,
        "duration_snapshot": treatment.duration_snapshot,
        "vat_rate_snapshot": treatment.vat_rate_snapshot,
        "budget_item_id": treatment.budget_item_id,
        "notes": treatment.notes,
        "source_module": treatment.source_module,
        "created_at": treatment.created_at,
        "updated_at": treatment.updated_at,
    }


class OdontogramEventType:
    """Legacy event types kept for surface/tooth updates."""

    SURFACE_UPDATED = "odontogram.surface.updated"
    TOOTH_UPDATED = "odontogram.tooth.updated"
    CONDITION_CHANGED = "odontogram.condition.changed"


class OdontogramService:
    """Service for tooth state (ToothRecord) operations."""

    @staticmethod
    def _default_surfaces() -> dict[str, str]:
        return {s: ToothCondition.HEALTHY.value for s in ("M", "D", "O", "V", "L")}

    @staticmethod
    async def get_patient_odontogram(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID
    ) -> list[ToothRecord]:
        result = await db.execute(
            select(ToothRecord)
            .where(ToothRecord.clinic_id == clinic_id, ToothRecord.patient_id == patient_id)
            .order_by(ToothRecord.tooth_number)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_tooth_record(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, tooth_number: int
    ) -> ToothRecord | None:
        result = await db.execute(
            select(ToothRecord).where(
                ToothRecord.clinic_id == clinic_id,
                ToothRecord.patient_id == patient_id,
                ToothRecord.tooth_number == tooth_number,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_tooth_record(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        tooth_number: int,
        user_id: UUID,
    ) -> ToothRecord:
        existing = await OdontogramService.get_tooth_record(db, clinic_id, patient_id, tooth_number)
        if existing:
            return existing
        return await OdontogramService.create_or_update_tooth(
            db, clinic_id, patient_id, tooth_number, user_id
        )

    @staticmethod
    async def create_or_update_tooth(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        tooth_number: int,
        user_id: UUID,
        general_condition: str | None = None,
        surface_updates: list[dict] | None = None,
        notes: str | None = None,
        is_displaced: bool | None = None,
        is_rotated: bool | None = None,
        displacement_notes: str | None = None,
    ) -> ToothRecord:
        """Create or update a tooth record with history tracking."""
        existing = await OdontogramService.get_tooth_record(db, clinic_id, patient_id, tooth_number)
        tooth_type = get_tooth_type(tooth_number)
        now = datetime.now(UTC)

        if existing:
            record = existing
            if general_condition is not None and general_condition != record.general_condition:
                old = record.general_condition
                record.general_condition = general_condition
                db.add(
                    OdontogramHistory(
                        clinic_id=clinic_id,
                        patient_id=patient_id,
                        tooth_number=tooth_number,
                        change_type="general_condition",
                        surface=None,
                        old_condition=old,
                        new_condition=general_condition,
                        changed_by=user_id,
                        changed_at=now,
                    )
                )
                await event_bus.publish(
                    OdontogramEventType.CONDITION_CHANGED,
                    {
                        "clinic_id": str(clinic_id),
                        "patient_id": str(patient_id),
                        "tooth_number": tooth_number,
                        "surface": None,
                        "old_condition": old,
                        "new_condition": general_condition,
                        "changed_by": str(user_id),
                    },
                )

            if surface_updates:
                current = dict(record.surfaces)
                for upd in surface_updates:
                    surface = upd["surface"]
                    new_cond = upd["condition"]
                    old_cond = current.get(surface, ToothCondition.HEALTHY.value)
                    if new_cond != old_cond:
                        current[surface] = new_cond
                        db.add(
                            OdontogramHistory(
                                clinic_id=clinic_id,
                                patient_id=patient_id,
                                tooth_number=tooth_number,
                                change_type="surface_update",
                                surface=surface,
                                old_condition=old_cond,
                                new_condition=new_cond,
                                changed_by=user_id,
                                changed_at=now,
                            )
                        )
                        await event_bus.publish(
                            OdontogramEventType.SURFACE_UPDATED,
                            {
                                "clinic_id": str(clinic_id),
                                "patient_id": str(patient_id),
                                "tooth_number": tooth_number,
                                "surface": surface,
                                "old_condition": old_cond,
                                "new_condition": new_cond,
                                "changed_by": str(user_id),
                            },
                        )
                record.surfaces = current

            if notes is not None and notes != record.notes:
                record.notes = notes
                db.add(
                    OdontogramHistory(
                        clinic_id=clinic_id,
                        patient_id=patient_id,
                        tooth_number=tooth_number,
                        change_type="note",
                        surface=None,
                        old_condition=None,
                        new_condition=None,
                        notes=notes,
                        changed_by=user_id,
                        changed_at=now,
                    )
                )

            if is_displaced is not None:
                record.is_displaced = is_displaced
            if is_rotated is not None:
                record.is_rotated = is_rotated
            if displacement_notes is not None:
                record.displacement_notes = displacement_notes
        else:
            default = OdontogramService._default_surfaces()
            if surface_updates:
                for upd in surface_updates:
                    default[upd["surface"]] = upd["condition"]
            record = ToothRecord(
                clinic_id=clinic_id,
                patient_id=patient_id,
                tooth_number=tooth_number,
                tooth_type=tooth_type.value,
                general_condition=general_condition or ToothCondition.HEALTHY.value,
                surfaces=default,
                notes=notes,
                is_displaced=is_displaced or False,
                is_rotated=is_rotated or False,
                displacement_notes=displacement_notes,
            )
            db.add(record)
            db.add(
                OdontogramHistory(
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    tooth_number=tooth_number,
                    change_type="created",
                    surface=None,
                    old_condition=None,
                    new_condition=general_condition or ToothCondition.HEALTHY.value,
                    changed_by=user_id,
                    changed_at=now,
                )
            )
            await event_bus.publish(
                OdontogramEventType.TOOTH_UPDATED,
                {
                    "clinic_id": str(clinic_id),
                    "patient_id": str(patient_id),
                    "tooth_number": tooth_number,
                    "changed_by": str(user_id),
                },
            )

        await db.flush()
        await db.refresh(record)
        return record

    @staticmethod
    async def bulk_update_teeth(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        user_id: UUID,
        updates: list[dict],
    ) -> list[ToothRecord]:
        return [
            await OdontogramService.create_or_update_tooth(
                db=db,
                clinic_id=clinic_id,
                patient_id=patient_id,
                tooth_number=upd["tooth_number"],
                user_id=user_id,
                general_condition=upd.get("general_condition"),
                surface_updates=upd.get("surface_updates"),
                notes=upd.get("notes"),
            )
            for upd in updates
        ]

    @staticmethod
    async def get_tooth_history(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        tooth_number: int,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[OdontogramHistory], int]:
        offset = (page - 1) * page_size
        base = select(OdontogramHistory).where(
            OdontogramHistory.clinic_id == clinic_id,
            OdontogramHistory.patient_id == patient_id,
            OdontogramHistory.tooth_number == tooth_number,
        )
        count_result = await db.execute(base)
        total = len(count_result.scalars().all())
        result = await db.execute(
            base.options(selectinload(OdontogramHistory.user))
            .order_by(OdontogramHistory.changed_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def get_patient_history(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[OdontogramHistory], int]:
        offset = (page - 1) * page_size
        base = select(OdontogramHistory).where(
            OdontogramHistory.clinic_id == clinic_id,
            OdontogramHistory.patient_id == patient_id,
        )
        count_result = await db.execute(base)
        total = len(count_result.scalars().all())
        result = await db.execute(
            base.options(selectinload(OdontogramHistory.user))
            .order_by(OdontogramHistory.changed_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def get_tooth_with_treatments(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, tooth_number: int
    ) -> tuple[ToothRecord | None, list[Treatment]]:
        """Return tooth record + all treatments whose teeth include this tooth."""
        record = await OdontogramService.get_tooth_record(db, clinic_id, patient_id, tooth_number)
        if not record:
            return None, []
        result = await db.execute(
            select(Treatment)
            .join(TreatmentTooth, TreatmentTooth.treatment_id == Treatment.id)
            .where(
                Treatment.clinic_id == clinic_id,
                Treatment.patient_id == patient_id,
                TreatmentTooth.tooth_number == tooth_number,
                Treatment.deleted_at.is_(None),
            )
            .options(
                selectinload(Treatment.teeth),
                selectinload(Treatment.performer),
                selectinload(Treatment.catalog_item),
            )
        )
        treatments = list(result.scalars().unique().all())
        return record, treatments

    @staticmethod
    async def get_timeline_dates(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> list[dict]:
        history_dates = await db.execute(
            select(
                func.date(OdontogramHistory.changed_at).label("change_date"),
                func.count().label("count"),
            )
            .where(
                OdontogramHistory.clinic_id == clinic_id,
                OdontogramHistory.patient_id == patient_id,
            )
            .group_by(func.date(OdontogramHistory.changed_at))
        )
        history_results = {row.change_date: row.count for row in history_dates.all()}

        treatment_dates = await db.execute(
            select(
                func.date(Treatment.recorded_at).label("recorded_date"),
                func.count().label("count"),
            )
            .where(Treatment.clinic_id == clinic_id, Treatment.patient_id == patient_id)
            .group_by(func.date(Treatment.recorded_at))
        )
        treatment_results = {row.recorded_date: row.count for row in treatment_dates.all()}

        all_dates: dict[date, int] = {}
        for d, c in history_results.items():
            all_dates[d] = all_dates.get(d, 0) + c
        for d, c in treatment_results.items():
            all_dates[d] = all_dates.get(d, 0) + c
        return [
            {"date": d.isoformat(), "change_count": c}
            for d, c in sorted(all_dates.items(), key=lambda x: x[0])
        ]

    @staticmethod
    async def get_odontogram_at_date(
        db: AsyncSession, clinic_id: UUID, patient_id: UUID, target_date: date
    ) -> dict:
        target_dt = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=UTC)

        history_result = await db.execute(
            select(OdontogramHistory)
            .where(
                OdontogramHistory.clinic_id == clinic_id,
                OdontogramHistory.patient_id == patient_id,
                OdontogramHistory.changed_at <= target_dt,
            )
            .order_by(OdontogramHistory.changed_at.asc())
        )
        history_entries = list(history_result.scalars().all())

        treatment_result = await db.execute(
            select(Treatment)
            .options(
                selectinload(Treatment.teeth),
                selectinload(Treatment.performer),
                selectinload(Treatment.catalog_item),
            )
            .where(
                Treatment.clinic_id == clinic_id,
                Treatment.patient_id == patient_id,
                Treatment.recorded_at <= target_dt,
                or_(Treatment.deleted_at.is_(None), Treatment.deleted_at > target_dt),
            )
        )
        treatments = list(treatment_result.scalars().unique().all())

        teeth_state: dict[int, dict] = {}
        for entry in history_entries:
            n = entry.tooth_number
            if n not in teeth_state:
                teeth_state[n] = {
                    "tooth_number": n,
                    "tooth_type": "permanent" if n < 50 else "deciduous",
                    "general_condition": ToothCondition.HEALTHY.value,
                    "surfaces": OdontogramService._default_surfaces(),
                    "notes": None,
                    "is_displaced": False,
                    "is_rotated": False,
                }
            tooth = teeth_state[n]
            if entry.change_type == "created" and entry.new_condition:
                tooth["general_condition"] = entry.new_condition
            elif entry.change_type == "general_condition" and entry.new_condition:
                tooth["general_condition"] = entry.new_condition
            elif entry.change_type == "surface_update" and entry.surface and entry.new_condition:
                tooth["surfaces"][entry.surface] = entry.new_condition
            elif entry.change_type == "note" and entry.notes:
                tooth["notes"] = entry.notes

        return {
            "teeth": list(teeth_state.values()),
            "treatments": [build_treatment_response(t) for t in treatments],
        }


class TreatmentService:
    """Service for Treatment (clinical act) operations."""

    # ----- read helpers -----

    @staticmethod
    def _select_with_relations():
        return select(Treatment).options(
            selectinload(Treatment.teeth),
            selectinload(Treatment.performer),
            selectinload(Treatment.catalog_item),
        )

    @staticmethod
    async def get_treatment(
        db: AsyncSession, clinic_id: UUID, treatment_id: UUID, include_deleted: bool = False
    ) -> Treatment | None:
        conditions = [Treatment.clinic_id == clinic_id, Treatment.id == treatment_id]
        if not include_deleted:
            conditions.append(Treatment.deleted_at.is_(None))
        result = await db.execute(TreatmentService._select_with_relations().where(*conditions))
        return result.scalars().unique().one_or_none()

    @staticmethod
    async def list_patient_treatments(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        status: str | None = None,
        clinical_type: str | None = None,
        tooth_number: int | None = None,
        catalog_item_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
        include_deleted: bool = False,
    ) -> tuple[list[Treatment], int]:
        offset = (page - 1) * page_size
        base = TreatmentService._select_with_relations()
        conditions = [Treatment.clinic_id == clinic_id, Treatment.patient_id == patient_id]
        if not include_deleted:
            conditions.append(Treatment.deleted_at.is_(None))
        if status:
            conditions.append(Treatment.status == status)
        if clinical_type:
            conditions.append(Treatment.clinical_type == clinical_type)
        if catalog_item_id:
            conditions.append(Treatment.catalog_item_id == catalog_item_id)
        if tooth_number is not None:
            base = base.join(TreatmentTooth, TreatmentTooth.treatment_id == Treatment.id)
            conditions.append(TreatmentTooth.tooth_number == tooth_number)

        count_q = select(func.count(func.distinct(Treatment.id)))
        if tooth_number is not None:
            count_q = count_q.join(TreatmentTooth, TreatmentTooth.treatment_id == Treatment.id)
        count_q = count_q.where(*conditions)
        total = (await db.execute(count_q)).scalar() or 0

        result = await db.execute(
            base.where(*conditions)
            .order_by(Treatment.recorded_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().unique().all()), total

    # ----- catalog resolution & role assignment -----

    @staticmethod
    async def _load_catalog_item(
        db: AsyncSession, clinic_id: UUID, catalog_item_id: UUID
    ) -> TreatmentCatalogItem:
        result = await db.execute(
            select(TreatmentCatalogItem)
            .options(
                selectinload(TreatmentCatalogItem.odontogram_mapping),
                selectinload(TreatmentCatalogItem.vat_type_rel),
            )
            .where(
                TreatmentCatalogItem.clinic_id == clinic_id,
                TreatmentCatalogItem.id == catalog_item_id,
                TreatmentCatalogItem.deleted_at.is_(None),
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError("Catalog item not found")
        return item

    @staticmethod
    def _resolve_clinical_type(
        explicit: str | None, catalog_item: TreatmentCatalogItem | None
    ) -> str:
        if catalog_item is not None and catalog_item.odontogram_mapping is not None:
            mapping: TreatmentOdontogramMapping = catalog_item.odontogram_mapping
            if explicit and explicit != mapping.odontogram_treatment_type:
                raise ValueError(
                    f"clinical_type={explicit!r} conflicts with catalog mapping "
                    f"{mapping.odontogram_treatment_type!r}"
                )
            return mapping.odontogram_treatment_type
        if explicit is None:
            raise ValueError(
                "clinical_type is required when catalog item has no odontogram mapping"
            )
        return explicit

    @staticmethod
    def _build_teeth_inputs(
        tooth_numbers: list[int],
        teeth: list | None,
        common_surfaces: list[str] | None,
    ) -> list[dict]:
        """Normalize caller input into a list of dicts: [{tooth_number, role, surfaces}]."""
        if teeth:
            return [
                {
                    "tooth_number": t.tooth_number,
                    "role": t.role,
                    "surfaces": t.surfaces if t.surfaces is not None else common_surfaces,
                }
                for t in teeth
            ]
        return [
            {"tooth_number": n, "role": None, "surfaces": common_surfaces} for n in tooth_numbers
        ]

    @staticmethod
    def _assign_roles(teeth_inputs: list[dict], clinical_type: str) -> list[dict]:
        """For bridges, honor caller-supplied roles; auto-assign only when none set.

        Auto rule (fallback): sorted first+last = pillar, middle = pontic.
        Valid bridges allow cantilevers (1 pillar) and mid-span pillars —
        only enforce ≥1 pillar and reject all-pontic.
        """
        if clinical_type != "bridge":
            return teeth_inputs
        sorted_teeth = sorted(teeth_inputs, key=lambda x: x["tooth_number"])
        has_explicit = any(t.get("role") in ("pillar", "pontic") for t in sorted_teeth)
        if has_explicit:
            for t in sorted_teeth:
                if t.get("role") not in ("pillar", "pontic"):
                    t["role"] = "pontic"
        else:
            first_n = sorted_teeth[0]["tooth_number"]
            last_n = sorted_teeth[-1]["tooth_number"]
            for t in sorted_teeth:
                t["role"] = "pillar" if t["tooth_number"] in (first_n, last_n) else "pontic"
        if not any(t["role"] == "pillar" for t in sorted_teeth):
            raise ValueError("bridge requires at least one pillar tooth")
        return sorted_teeth

    # ----- write operations -----

    @staticmethod
    async def create(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        user_id: UUID,
        catalog_item_id: UUID | None,
        clinical_type: str | None,
        tooth_numbers: list[int],
        teeth: list | None,
        common_surfaces: list[str] | None,
        status: str,
        notes: str | None,
        budget_item_id: UUID | None,
        source_module: str,
        scope: str,
        arch: str | None = None,
    ) -> Treatment:
        """Create a Treatment with its TreatmentTooth children."""
        now = datetime.now(UTC)

        # 1. Resolve catalog + clinical type.
        catalog_item = None
        if catalog_item_id is not None:
            catalog_item = await TreatmentService._load_catalog_item(db, clinic_id, catalog_item_id)
        resolved_clinical_type = TreatmentService._resolve_clinical_type(
            clinical_type, catalog_item
        )

        # 2. Normalize teeth input + assign roles for bridges.
        teeth_inputs = TreatmentService._build_teeth_inputs(tooth_numbers, teeth, common_surfaces)
        teeth_inputs = TreatmentService._assign_roles(teeth_inputs, resolved_clinical_type)

        # 3. Validate atomic multi-tooth minimums (only for tooth-level scopes).
        if scope in ("tooth", "multi_tooth") and (
            resolved_clinical_type in ATOMIC_MULTI_TOOTH_TYPES and len(teeth_inputs) < 2
        ):
            raise ValueError(f"clinical_type={resolved_clinical_type} requires at least 2 teeth")

        # 4. Compute snapshots.
        price_snapshot = None
        duration_snapshot = None
        vat_rate_snapshot = None
        if catalog_item is not None:
            pricing_teeth = [
                PricingTooth(role=t["role"], surfaces=t["surfaces"]) for t in teeth_inputs
            ]
            price_snapshot = compute_price_snapshot(catalog_item, pricing_teeth)
            duration_snapshot = compute_duration_snapshot(catalog_item, len(teeth_inputs))
            if catalog_item.vat_type_rel is not None:
                vat_rate_snapshot = catalog_item.vat_type_rel.rate

        # 5. Create Treatment header.
        is_performed = status == TreatmentStatus.PERFORMED.value
        treatment = Treatment(
            clinic_id=clinic_id,
            patient_id=patient_id,
            clinical_type=resolved_clinical_type,
            scope=scope,
            arch=arch,
            catalog_item_id=catalog_item.id if catalog_item else None,
            status=status,
            recorded_at=now,
            performed_at=now if is_performed else None,
            performed_by=user_id if is_performed else None,
            price_snapshot=price_snapshot,
            duration_snapshot=duration_snapshot,
            vat_rate_snapshot=vat_rate_snapshot,
            budget_item_id=budget_item_id,
            notes=notes,
            source_module=source_module,
        )
        db.add(treatment)
        await db.flush()

        # 6. Create TreatmentTooth rows.
        for t in teeth_inputs:
            tooth_record = await OdontogramService.get_or_create_tooth_record(
                db, clinic_id, patient_id, t["tooth_number"], user_id
            )
            db.add(
                TreatmentTooth(
                    treatment_id=treatment.id,
                    tooth_record_id=tooth_record.id,
                    tooth_number=t["tooth_number"],
                    role=t["role"],
                    surfaces=t["surfaces"],
                )
            )
        await db.flush()

        # 7. Emit single event for the Treatment.
        await event_bus.publish(
            EventType.ODONTOGRAM_TREATMENT_ADDED,
            {
                "clinic_id": str(clinic_id),
                "patient_id": str(patient_id),
                "treatment_id": str(treatment.id),
                "clinical_type": treatment.clinical_type,
                "catalog_item_id": str(treatment.catalog_item_id)
                if treatment.catalog_item_id
                else None,
                "status": treatment.status,
                "tooth_numbers": [t["tooth_number"] for t in teeth_inputs],
                "budget_item_id": str(budget_item_id) if budget_item_id else None,
                "source_module": source_module,
                "created_by": str(user_id),
                "created_at": now.isoformat(),
            },
        )

        reloaded = await TreatmentService.get_treatment(db, clinic_id, treatment.id)
        assert reloaded is not None
        return reloaded

    @staticmethod
    async def update(
        db: AsyncSession,
        clinic_id: UUID,
        treatment_id: UUID,
        user_id: UUID,
        status: str | None = None,
        notes: str | None = None,
        surfaces: list[str] | None = None,
    ) -> Treatment | None:
        treatment = await TreatmentService.get_treatment(db, clinic_id, treatment_id)
        if not treatment:
            return None
        old_status = treatment.status
        now = datetime.now(UTC)

        if status is not None and status != old_status:
            treatment.status = status
            if status == TreatmentStatus.PERFORMED.value:
                treatment.performed_at = now
                treatment.performed_by = user_id
            await event_bus.publish(
                EventType.ODONTOGRAM_TREATMENT_STATUS_CHANGED,
                {
                    "clinic_id": str(clinic_id),
                    "patient_id": str(treatment.patient_id),
                    "treatment_id": str(treatment_id),
                    "clinical_type": treatment.clinical_type,
                    "old_status": old_status,
                    "new_status": status,
                    "budget_item_id": str(treatment.budget_item_id)
                    if treatment.budget_item_id
                    else None,
                    "changed_by": str(user_id),
                },
            )

        if notes is not None:
            treatment.notes = notes

        if surfaces is not None:
            for tooth in treatment.teeth:
                tooth.surfaces = list(surfaces)
            if treatment.catalog_item is not None:
                pricing_teeth = [
                    PricingTooth(role=t.role, surfaces=t.surfaces) for t in treatment.teeth
                ]
                treatment.price_snapshot = compute_price_snapshot(
                    treatment.catalog_item, pricing_teeth
                )
                treatment.duration_snapshot = compute_duration_snapshot(
                    treatment.catalog_item, len(treatment.teeth)
                )

        await db.flush()
        return treatment

    @staticmethod
    async def perform(
        db: AsyncSession,
        clinic_id: UUID,
        treatment_id: UUID,
        user_id: UUID,
        notes: str | None = None,
        publish_price: bool = True,
    ) -> Treatment | None:
        treatment = await TreatmentService.get_treatment(db, clinic_id, treatment_id)
        if not treatment:
            return None
        old_status = treatment.status
        now = datetime.now(UTC)
        treatment.status = TreatmentStatus.PERFORMED.value
        treatment.performed_at = now
        treatment.performed_by = user_id
        if notes:
            treatment.notes = notes
        await db.flush()

        await event_bus.publish(
            EventType.ODONTOGRAM_TREATMENT_PERFORMED,
            {
                "clinic_id": str(clinic_id),
                "patient_id": str(treatment.patient_id),
                "treatment_id": str(treatment_id),
                "clinical_type": treatment.clinical_type,
                "treatment_name": (
                    (treatment.catalog_item.names or {}).get("es")
                    or (treatment.catalog_item.names or {}).get("en")
                    if treatment.catalog_item
                    else None
                ),
                "catalog_item_id": str(treatment.catalog_item_id)
                if treatment.catalog_item_id
                else None,
                "tooth_numbers": [t.tooth_number for t in treatment.teeth],
                "budget_item_id": str(treatment.budget_item_id)
                if treatment.budget_item_id
                else None,
                "performed_by": str(user_id),
                "performed_at": now.isoformat(),
                "previous_status": old_status,
                # Snapshot price so subscribers (e.g. payments earned
                # ledger) can attribute revenue without importing
                # odontogram models. `Treatment.price_snapshot` is the
                # frozen catalog price captured at treatment creation;
                # multiply by tooth count for multi-tooth headers.
                # ``None`` means "revenue already attributed elsewhere"
                # (``publish_price=False``): treatment_plan finalizes a
                # sessioned item whose amounts were booked per-session.
                "unit_price": str(
                    (treatment.price_snapshot or Decimal("0")) * (len(treatment.teeth) or 1)
                )
                if publish_price and treatment.price_snapshot is not None
                else None,
            },
        )
        return treatment

    @staticmethod
    async def delete(db: AsyncSession, clinic_id: UUID, treatment_id: UUID, user_id: UUID) -> bool:
        treatment = await TreatmentService.get_treatment(db, clinic_id, treatment_id)
        if not treatment:
            return False
        event_data = {
            "clinic_id": str(clinic_id),
            "patient_id": str(treatment.patient_id),
            "treatment_id": str(treatment_id),
            "clinical_type": treatment.clinical_type,
            "catalog_item_id": str(treatment.catalog_item_id)
            if treatment.catalog_item_id
            else None,
            "tooth_numbers": [t.tooth_number for t in treatment.teeth],
            "budget_item_id": str(treatment.budget_item_id) if treatment.budget_item_id else None,
            "deleted_by": str(user_id),
        }
        treatment.deleted_at = datetime.now(UTC)
        await db.flush()
        await event_bus.publish(EventType.ODONTOGRAM_TREATMENT_DELETED, event_data)
        return True
