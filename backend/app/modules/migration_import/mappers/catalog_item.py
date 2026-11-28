"""Generic ``catalog_item`` dispatcher — Gesdén lookup tables.

DPMF carries dozens of small reference tables (countries, provinces,
specialties, payment methods, chairs/cabinets, …) as
``CanonicalCatalogItem`` rows tagged with a ``kind``. Treatment
templates have their own dedicated entity (``treatment_catalog_item``)
and mapper; everything else flows through here.

For now only ``kind=chair`` produces real DentalPin rows: Gesdén's
``TBoxes`` rows land as :class:`agenda.Cabinet` entries on the clinic
so imported appointments can resolve their ``chair_uuid``. Other kinds
fall through to :class:`RawEntity` for forward-compat — when DentalPin
grows a payment-methods or specialties master, the importer just adds
another branch here.

Idempotency is via ``EntityMapping`` keyed on the canonical UUID; the
``catalog_item`` kind=chair upsert is also guarded by the
``(clinic_id, name)`` unique index on ``cabinets``.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.modules.agenda.models import Cabinet

from ..models import ImportWarning
from .base import MapperContext
from .raw import RawEntityMapper

logger = logging.getLogger(__name__)


# Default cabinet color when Gesdén doesn't carry one. Picked from
# DentalPin's seeded palette so the migrated cabinets blend in with
# the rest of the agenda board.
_DEFAULT_CABINET_COLOR = "#3B82F6"

# Cabinet.name is String(50); Gesdén ``TBoxes.Descripcion`` can run
# longer (clinic-named "Quirófano implantes – Dra. García") so we trim
# with an ellipsis and surface the original in a warning.
_CABINET_NAME_MAX = 50


class CatalogItemMapper:
    def __init__(self) -> None:
        self._raw = RawEntityMapper()

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
        # Idempotency — re-run on the same DPMF short-circuits.
        existing = await ctx.resolver.get("catalog_item", canonical_uuid)
        if existing is not None:
            return existing

        kind = payload.get("kind")
        if kind == "chair":
            return await self._handle_chair(
                ctx,
                payload=payload,
                canonical_uuid=canonical_uuid,
                source_id=source_id,
                source_system=source_system,
            )

        # Everything else is archived for forward-compat — RawEntityMapper
        # writes a ``migration_import_raw_entities`` row so future
        # consumers can rehydrate without re-uploading the file.
        return await self._raw.apply(
            ctx,
            entity_type=entity_type,
            payload=payload,
            raw=raw,
            canonical_uuid=canonical_uuid,
            source_id=source_id,
            source_system=source_system,
        )

    @staticmethod
    async def _handle_chair(
        ctx: MapperContext,
        *,
        payload: dict[str, Any],
        canonical_uuid: str,
        source_id: str,
        source_system: str,
    ) -> UUID | None:
        """Materialise Gesdén ``TBoxes`` → :class:`agenda.Cabinet`.

        Reuses an existing cabinet when its case-insensitive name
        matches the source label (e.g. clinic already had "Box 1" set
        up by demo seed). New labels become new cabinets with the
        default color; the operator can re-style them in the agenda
        settings page later.
        """
        name = (payload.get("name") or payload.get("code") or "").strip()
        if not name:
            ctx.db.add(
                ImportWarning(
                    job_id=ctx.job_id,
                    entity_type="catalog_item",
                    source_id=source_id,
                    severity="warn",
                    code="catalog_item.chair_unnamed",
                    message=(
                        f"Gabinete sin nombre (canonical={canonical_uuid}); "
                        "saltado. Re-asignar manualmente si las citas pierden cabinet_id."
                    ),
                )
            )
            await ctx.resolver.mark_skipped("catalog_item", canonical_uuid, source_system)
            return None

        if len(name) > _CABINET_NAME_MAX:
            ctx.db.add(
                ImportWarning(
                    job_id=ctx.job_id,
                    entity_type="catalog_item",
                    source_id=source_id,
                    severity="info",
                    code="catalog_item.chair_name_truncated",
                    message=f"Nombre de gabinete recortado: {name!r}",
                )
            )
            name = name[: _CABINET_NAME_MAX - 1] + "…"

        # Match by case-insensitive name within the clinic so a
        # re-import doesn't duplicate a cabinet the operator already
        # has under the same label. An equality, not ``ilike``: a ``_``
        # or ``%`` in a source label is a character, not a wildcard.
        result = await ctx.db.execute(
            select(Cabinet).where(
                Cabinet.clinic_id == ctx.clinic_id,
                func.lower(Cabinet.name) == func.lower(name),
            )
        )
        cabinet = result.scalars().first()
        if cabinet is None:
            # Sort imported cabinets after any clinic-managed ones so
            # they don't reshuffle the existing UI on first import.
            order_q = await ctx.db.execute(
                select(Cabinet.display_order)
                .where(Cabinet.clinic_id == ctx.clinic_id)
                .order_by(Cabinet.display_order.desc())
                .limit(1)
            )
            highest = order_q.scalar_one_or_none() or 0
            cabinet = Cabinet(
                clinic_id=ctx.clinic_id,
                name=name,
                color=_DEFAULT_CABINET_COLOR,
                display_order=highest + 1,
                is_active=True,
            )
            ctx.db.add(cabinet)
            await ctx.db.flush()

        await ctx.resolver.set(
            entity_type="catalog_item",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="cabinets",
            dentalpin_id=cabinet.id,
        )
        return cabinet.id
