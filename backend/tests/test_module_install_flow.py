"""Tests for ModuleService state transitions (install/uninstall/upgrade)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugins.db_models import ModuleRecord
from app.core.plugins.loader import register_discovered
from app.core.plugins.service import ModuleOperationError, ModuleService
from app.core.plugins.state import ModuleState


async def _reconcile(db_session: AsyncSession) -> None:
    register_discovered()
    await ModuleService(db_session).reconcile_with_db()


@pytest.mark.asyncio
async def test_uninstall_blocked_for_non_removable_module(db_session: AsyncSession) -> None:
    """Non-removable modules must reject uninstall even when they ship an
    Alembic branch — ``billing`` has its own ``bil_0001`` branch that the
    service auto-resolves during reconcile."""
    await _reconcile(db_session)

    svc = ModuleService(db_session)
    with pytest.raises(ModuleOperationError, match="removable=False"):
        await svc.uninstall("billing")


@pytest.mark.asyncio
async def test_uninstall_blocked_for_legacy_module_without_branch(
    db_session: AsyncSession,
) -> None:
    """Modules whose migrations live in the main linear chain (no
    per-module ``migrations/versions`` dir) have ``base_revision=None``
    even after reconcile, so uninstall falls back to the legacy guard."""
    await _reconcile(db_session)

    # Force a pristine state by wiping base_revision and marking removable.
    from app.core.plugins.db_models import ModuleRecord

    billing = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "billing"))
    ).scalar_one()
    billing.base_revision = None
    billing.removable = True
    await db_session.commit()

    svc = ModuleService(db_session)
    with pytest.raises(ModuleOperationError, match="no Alembic branch"):
        await svc.uninstall("billing")


@pytest.mark.asyncio
async def test_uninstall_blocked_by_reverse_dependency(
    db_session: AsyncSession,
) -> None:
    await _reconcile(db_session)

    # Fake a branch revision + removable=True so the only block is the
    # reverse dep from notifications.
    budget = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "budget"))
    ).scalar_one()
    budget.base_revision = "fake_base"
    budget.removable = True
    await db_session.commit()

    svc = ModuleService(db_session)
    with pytest.raises(ModuleOperationError, match="required by"):
        await svc.uninstall("budget")


@pytest.mark.asyncio
async def test_install_already_installed_is_noop(
    db_session: AsyncSession,
) -> None:
    await _reconcile(db_session)

    svc = ModuleService(db_session)
    scheduled = await svc.install("patients")
    assert scheduled == []


@pytest.mark.asyncio
async def test_install_schedules_dependency_chain(
    db_session: AsyncSession,
) -> None:
    await _reconcile(db_session)

    # Mark billing as uninstalled to simulate a fresh install of it and
    # its chain.
    billing = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "billing"))
    ).scalar_one()
    budget = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "budget"))
    ).scalar_one()
    catalog = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "catalog"))
    ).scalar_one()
    billing.state = ModuleState.UNINSTALLED.value
    budget.state = ModuleState.UNINSTALLED.value
    catalog.state = ModuleState.UNINSTALLED.value
    await db_session.commit()

    svc = ModuleService(db_session)
    scheduled = await svc.install("billing")

    assert "billing" in scheduled
    assert "budget" in scheduled
    assert "catalog" in scheduled
    # Dependency-first order.
    assert scheduled.index("catalog") < scheduled.index("budget") < scheduled.index("billing")

    # All three now marked to_install.
    for name in ("billing", "budget", "catalog"):
        row = (
            await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == name))
        ).scalar_one()
        assert row.state == ModuleState.TO_INSTALL.value


@pytest.mark.asyncio
async def test_upgrade_noop_when_versions_match(
    db_session: AsyncSession,
) -> None:
    await _reconcile(db_session)

    svc = ModuleService(db_session)
    assert await svc.upgrade("billing") is False


@pytest.mark.asyncio
async def test_upgrade_marks_to_upgrade_when_version_diverges(
    db_session: AsyncSession,
) -> None:
    await _reconcile(db_session)

    billing = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "billing"))
    ).scalar_one()
    billing.version = "0.0.0"
    await db_session.commit()

    svc = ModuleService(db_session)
    assert await svc.upgrade("billing") is True

    refreshed = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "billing"))
    ).scalar_one()
    assert refreshed.state == ModuleState.TO_UPGRADE.value
    assert refreshed.version == "0.0.0"  # version advances only on finalize


@pytest.mark.asyncio
async def test_reconcile_keeps_installed_version_on_drift(
    db_session: AsyncSession,
) -> None:
    """Reconcile must NOT absorb a disk version bump into ``record.version``.

    The stored version is the last-applied version — the upgrade signal.
    A second reconcile with drift keeps the old version and the installed
    state, so the upgrade path stays reachable (issue #47)."""
    await _reconcile(db_session)

    billing = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "billing"))
    ).scalar_one()
    billing.version = "0.0.0"
    await db_session.commit()

    await _reconcile(db_session)

    refreshed = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "billing"))
    ).scalar_one()
    assert refreshed.version == "0.0.0"
    assert refreshed.state == ModuleState.INSTALLED.value


@pytest.mark.asyncio
async def test_list_signals_upgrade_available_on_drift(
    db_session: AsyncSession,
) -> None:
    await _reconcile(db_session)

    billing = (
        await db_session.execute(select(ModuleRecord).where(ModuleRecord.name == "billing"))
    ).scalar_one()
    billing.version = "0.0.0"
    await db_session.commit()

    svc = ModuleService(db_session)
    info = await svc.get_info("billing")
    assert info is not None
    assert info.upgrade_available is True
    assert info.installable is True
    assert info.installed_version == "0.0.0"
    assert info.version != "0.0.0"
    payload = info.to_dict()
    assert payload["upgrade_available"] is True
    assert payload["installable"] is True
    assert payload["installed_version"] == "0.0.0"


@pytest.mark.asyncio
async def test_no_upgrade_signal_when_in_sync(
    db_session: AsyncSession,
) -> None:
    await _reconcile(db_session)

    svc = ModuleService(db_session)
    info = await svc.get_info("billing")
    assert info is not None
    assert info.upgrade_available is False
