"""An imported chair reuses a cabinet only on a same-name match.

The lookup used ``Cabinet.name.ilike(name)``, so a ``_`` or ``%`` in a
Gesdén ``TBoxes`` label acted as a LIKE wildcard: ``Box_1`` reused the
clinic's ``Box 1`` and ``Box%`` reused whichever ``Box…`` came first, so
two source chairs collapsed into one cabinet. Same-name reuse ignoring
case (the reason for the lookup) still works.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.agenda.models import Cabinet
from app.modules.migration_import.mappers.catalog_item import CatalogItemMapper
from tests.modules.migration_import.test_appointment_notes_routing import _bootstrap, _ctx


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "reuses"),
    [("Box_1", False), ("Box%", False), ("box 1", True), ("BOX 1", True)],
)
async def test_chair_reuses_a_cabinet_only_on_a_same_name_match(
    db_session, label: str, reuses: bool
) -> None:
    clinic, admin, _, _ = await _bootstrap(db_session)
    existing = Cabinet(id=uuid4(), clinic_id=clinic.id, name="Box 1", color="#000", display_order=0)
    db_session.add(existing)
    await db_session.flush()
    ctx = await _ctx(db_session, clinic.id, admin.id)

    cabinet_id = await CatalogItemMapper().apply(
        ctx,
        entity_type="catalog_item",
        payload={"kind": "chair", "name": label},
        raw={},
        canonical_uuid=str(uuid4()),
        source_id="1",
        source_system="gesden",
    )

    assert (cabinet_id == existing.id) is reuses
