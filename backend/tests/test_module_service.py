"""Tests for ModuleService reconciliation and query methods."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugins.alembic_paths import module_branch_is_isolated
from app.core.plugins.db_models import ModuleRecord
from app.core.plugins.loader import discover_modules
from app.core.plugins.service import ModuleService
from app.core.plugins.state import ModuleState


@pytest.mark.asyncio
async def test_reconcile_empty_db_inserts_all_modules(db_session: AsyncSession) -> None:
    svc = ModuleService(db_session)
    await svc.reconcile_with_db()

    records = (await db_session.execute(select(ModuleRecord))).scalars().all()
    names = {r.name for r in records}

    # All modules declared as entry points in pyproject.toml should land.
    expected = {
        "patients",
        "patients_clinical",
        "agenda",
        "patient_timeline",
        "catalog",
        "budget",
        "billing",
        "odontogram",
        "treatment_plan",
        "media",
        "notifications",
        "reports",
    }
    assert expected.issubset(names)

    for record in records:
        if record.name in expected:
            assert record.state == ModuleState.INSTALLED.value
            assert record.manifest_snapshot["name"] == record.name


@pytest.mark.asyncio
async def test_list_modules_combines_disk_and_db(db_session: AsyncSession) -> None:
    svc = ModuleService(db_session)
    await svc.reconcile_with_db()

    infos = await svc.list_modules()
    by_name = {i.name: i for i in infos}

    assert "patients" in by_name
    assert by_name["patients"].in_disk is True
    assert by_name["patients"].state == ModuleState.INSTALLED


@pytest.mark.asyncio
async def test_doctor_flags_orphans(db_session: AsyncSession) -> None:
    svc = ModuleService(db_session)
    await svc.reconcile_with_db()

    # Simulate an orphan: a module row whose code disappeared from disk.
    db_session.add(
        ModuleRecord(
            name="ghost",
            version="0.0.1",
            state=ModuleState.INSTALLED.value,
            category="community",
            removable=True,
            auto_install=False,
            manifest_snapshot={"name": "ghost", "version": "0.0.1"},
        )
    )
    await db_session.commit()

    report = await svc.doctor()
    assert "ghost" in report.orphans
    assert report.ok is False


@pytest.mark.asyncio
async def test_orphan_command_resets_state(db_session: AsyncSession) -> None:
    svc = ModuleService(db_session)
    await svc.reconcile_with_db()

    db_session.add(
        ModuleRecord(
            name="ghost",
            version="0.0.1",
            state=ModuleState.INSTALLED.value,
            category="community",
            removable=True,
            auto_install=False,
            manifest_snapshot={"name": "ghost", "version": "0.0.1"},
        )
    )
    await db_session.commit()

    updated = await svc.orphan("ghost")
    assert updated is True

    record = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "ghost"))
    ).scalar_one()
    assert record.state == ModuleState.UNINSTALLED.value


@pytest.mark.asyncio
async def test_status_reports_counts(db_session: AsyncSession) -> None:
    svc = ModuleService(db_session)
    await svc.reconcile_with_db()

    status = await svc.status()
    assert status["total"] >= 9
    assert status["by_state"].get("installed", 0) >= 9
    assert status["pending"] == []


# --- Branch isolation + reconcile enforcement (issue #56) ------------------


def _module(name: str):
    for m in discover_modules():
        if m.name == name:
            return m
    raise LookupError(name)


def test_branch_isolated_helper_accepts_schedules() -> None:
    """schedules owns sch_0001 with no foreign descendants → isolated."""
    assert module_branch_is_isolated(_module("schedules")) is True


def test_branch_isolated_helper_rejects_non_tip_module() -> None:
    """patient_timeline's pt_0001 has billing/notifications above it on
    the main linear chain, so the branch is not isolated."""
    assert module_branch_is_isolated(_module("patient_timeline")) is False


def test_validator_rejects_removable_true_on_non_isolated_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The branch-isolation invariant for ``removable=True`` is enforced
    by ``manifest_validator`` — the silent reconcile-time override was
    moved here so CI rejects the manifest before merge."""
    from app.core.plugins.manifest_validator import validate_module

    pt = _module("patient_timeline")
    patched = {**pt.manifest, "removable": True}
    monkeypatch.setattr(type(pt), "manifest", patched)

    issues = validate_module(pt)
    assert any(i.code == "REMOVABLE_BRANCH_NOT_ISOLATED" for i in issues), issues


@pytest.mark.asyncio
async def test_reconcile_keeps_removable_true_for_branch_isolated_module(
    db_session: AsyncSession,
) -> None:
    """schedules is the one module that genuinely satisfies the contract."""
    svc = ModuleService(db_session)
    await svc.reconcile_with_db()

    record = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "schedules"))
    ).scalar_one()
    assert record.removable is True
