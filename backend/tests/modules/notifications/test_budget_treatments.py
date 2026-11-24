"""The ``treatments`` block every locale's ``budget_sent.html`` renders (#527).

Two copies of this logic existed. #287 fixed the handler's
``catalog_item.name`` — the model has no such attribute, only a per-locale
``names`` dict — and left the router's alone, so a manual ``budget_sent``
send raised ``AttributeError`` for any budget with items. These guard the
single implementation both now call.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, ClinicMembership
from app.modules.budget.models import Budget, BudgetItem
from app.modules.catalog.models import TreatmentCatalogItem, TreatmentCategory
from app.modules.notifications.service import budget_treatments_context, money_formatter
from app.modules.patients.models import Patient

# es + EUR, the formatter every caller builds from the clinic (#1133).
MONEY = money_formatter(None, "es")


async def _budget_with_items(db: AsyncSession, clinic: Clinic, count: int) -> UUID:
    """A budget carrying ``count`` lines, each on its own catalog item."""
    patient = Patient(
        id=uuid4(), clinic_id=clinic.id, first_name="Ana", last_name="Test", status="active"
    )
    category = TreatmentCategory(
        id=uuid4(),
        clinic_id=clinic.id,
        key=f"cat-{uuid4().hex[:8]}",
        names={"es": "Cat", "en": "Cat"},
        is_system=False,
    )
    db.add_all([patient, category])
    await db.flush()

    # ``created_by`` is a FK to users; test_clinic already seeded a membership.
    created_by = (
        await db.execute(
            select(ClinicMembership.user_id).where(ClinicMembership.clinic_id == clinic.id)
        )
    ).scalar_one()

    budget = Budget(
        id=uuid4(),
        clinic_id=clinic.id,
        patient_id=patient.id,
        budget_number=f"PRES-{uuid4().hex[:8]}",
        valid_from=date(2026, 9, 1),
        created_by=created_by,
    )
    db.add(budget)
    await db.flush()

    for index in range(count):
        catalog_item = TreatmentCatalogItem(
            id=uuid4(),
            clinic_id=clinic.id,
            category_id=category.id,
            internal_code=f"T-{index}-{uuid4().hex[:6]}",
            names={"es": f"Corona {index}", "en": f"Crown {index}"},
            default_price=Decimal("100.00"),
            is_active=True,
            is_system=False,
        )
        db.add(catalog_item)
        await db.flush()
        db.add(
            BudgetItem(
                id=uuid4(),
                clinic_id=clinic.id,
                budget_id=budget.id,
                catalog_item_id=catalog_item.id,
                unit_price=Decimal("100.00"),
                quantity=1,
                line_total=Decimal("100.00"),
                tooth_number=11 + index,
            )
        )

    await db.commit()
    return budget.id


def _count_statements(db: AsyncSession) -> tuple[list[str], callable]:
    """Record every SQL statement the session issues until the returned stop()."""
    engine = db.get_bind().sync_engine if hasattr(db.get_bind(), "sync_engine") else db.get_bind()
    seen: list[str] = []

    def before(conn, cursor, statement, params, context, executemany):  # noqa: ANN001
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    return seen, lambda: event.remove(engine, "before_cursor_execute", before)


@pytest.mark.asyncio
async def test_names_come_from_the_locale_dict(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    """The regression: the model has ``names``, never ``name``."""
    assert not hasattr(TreatmentCatalogItem, "name")

    budget_id = await _budget_with_items(db_session, test_clinic, 3)
    treatments = await budget_treatments_context(db_session, budget_id, MONEY)

    assert len(treatments) == 3
    assert sorted(t["name"] for t in treatments) == ["Corona 0", "Corona 1", "Corona 2"]
    assert all(t["price"] == "100,00\xa0€" for t in treatments)
    assert sorted(t["tooth"] for t in treatments) == [11, 12, 13]


@pytest.mark.asyncio
async def test_a_line_cannot_point_at_a_missing_catalog_item(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    """Why the old expression was always fatal, not merely flaky.

    ``catalog_item.name if catalog_item else "Tratamiento"`` only ever
    worked in its ``else``. That branch needs a line whose catalog item is
    absent — and ``budget_items.catalog_item_id`` is a non-nullable FK with
    no ``ON DELETE``, so Postgres refuses to create one and refuses to
    delete a catalog item a line still references. The working branch was
    unreachable, so every budget with items hit the ``AttributeError``.

    The helper keeps the fallback anyway; it costs nothing and covers a
    future ``ON DELETE SET NULL``. This pins the reason it is dead today.
    """
    budget_id = await _budget_with_items(db_session, test_clinic, 1)
    # Read it out now: the rollback below expires the instance, and touching
    # an expired attribute afterwards is IO outside the greenlet.
    existing_catalog_id = (
        await db_session.execute(
            select(BudgetItem.catalog_item_id).where(BudgetItem.budget_id == budget_id)
        )
    ).scalar_one()
    assert existing_catalog_id is not None

    with pytest.raises(IntegrityError):
        db_session.add(
            BudgetItem(
                id=uuid4(),
                clinic_id=test_clinic.id,
                budget_id=budget_id,
                catalog_item_id=uuid4(),  # nothing behind it
                unit_price=Decimal("50.00"),
                quantity=1,
                line_total=Decimal("50.00"),
                tooth_number=48,
            )
        )
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_query_count_does_not_grow_with_the_number_of_lines(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    """Both copies used to fetch one catalog row per line (#527)."""
    small = await _budget_with_items(db_session, test_clinic, 2)
    large = await _budget_with_items(db_session, test_clinic, 12)

    seen, stop = _count_statements(db_session)
    try:
        await budget_treatments_context(db_session, small, MONEY)
        after_small = len(seen)
        await budget_treatments_context(db_session, large, MONEY)
        after_large = len(seen) - after_small
    finally:
        stop()

    assert after_small == after_large, (
        f"{after_small} statements for 2 lines vs {after_large} for 12 — still N+1"
    )
    assert after_large <= 2, f"expected items + names, got {after_large} statements"


@pytest.mark.asyncio
async def test_empty_budget_issues_no_name_lookup(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    budget_id = await _budget_with_items(db_session, test_clinic, 0)

    seen, stop = _count_statements(db_session)
    try:
        assert await budget_treatments_context(db_session, budget_id, MONEY) == []
    finally:
        stop()

    assert len(seen) == 1, f"expected only the items query, got {len(seen)}"
