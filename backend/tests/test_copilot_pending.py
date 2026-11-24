"""Copilot "Pendientes" feed (IA redesign Fase 2, ADR 0015).

Aggregates open work (overdue recalls, budgets awaiting response) via the
tool registry with the caller's role permissions — read-only, deep-links
to the owning module. Here we just assert the endpoint runs and shapes
results; the underlying tools have their own tests.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.models import AgentSession
from app.core.auth.models import User
from app.database import engine
from app.modules.budget.models import Budget
from app.modules.copilot.service import PENDING_SECTION_LIMIT
from app.modules.recalls.models import Recall


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_pool():
    await engine.dispose()
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_pending_runs_and_returns_list(
    client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    res = await client.get("/api/v1/copilot/pending", headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert isinstance(data["items"], list)
    # Every item carries a kind + a deep-link.
    for item in data["items"]:
        assert item["kind"] in ("recall", "budget")
        assert item["link"]
    for sec in data["sections"]:
        assert sec["kind"] in ("recall", "budget")
        assert sec["link"]


@pytest.mark.asyncio
async def test_pending_reports_real_totals_beyond_the_bounded_list(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, test_clinic, test_patient
) -> None:
    """35 overdue recalls and 25 sent budgets must not read as 30 / 20 (#1137).

    The list stays bounded, but each section carries the tool's real total
    and a link to the full list, so the drawer can say "and N more".
    """
    user = await db_session.scalar(select(User).where(User.email == "test@example.com"))
    for i in range(35):
        db_session.add(
            Recall(
                id=uuid4(),
                clinic_id=test_clinic.id,
                patient_id=test_patient.id,
                due_month=date(2020, 1 + i % 12, 1),
                reason="checkup",
                status="pending",
            )
        )
    for i in range(25):
        db_session.add(
            Budget(
                clinic_id=test_clinic.id,
                patient_id=test_patient.id,
                budget_number=f"PRES-2026-{i:04d}",
                status="sent",
                valid_from=date(2026, 1, 1),
                created_by=user.id,
            )
        )
    await db_session.commit()

    res = await client.get("/api/v1/copilot/pending", headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]

    shown = {k: sum(1 for i in data["items"] if i["kind"] == k) for k in ("recall", "budget")}
    assert shown == {"recall": PENDING_SECTION_LIMIT, "budget": PENDING_SECTION_LIMIT}

    sections = {s["kind"]: s for s in data["sections"]}
    assert sections["recall"]["total"] == 35
    assert sections["budget"]["total"] == 25
    assert sections["recall"]["link"].startswith("/recalls?overdue=true")
    assert sections["budget"]["link"] == "/budgets?status=sent"


@pytest.mark.asyncio
async def test_pending_reuses_single_session(
    db_session: AsyncSession, client: AsyncClient, auth_headers: dict, test_clinic
) -> None:
    """Repeated drawer opens must not insert a session row each time."""
    await client.get("/api/v1/copilot/pending", headers=auth_headers)
    await client.get("/api/v1/copilot/pending", headers=auth_headers)
    await client.get("/api/v1/copilot/pending", headers=auth_headers)

    sessions = list(
        await db_session.scalars(
            select(AgentSession).where(AgentSession.clinic_id == test_clinic.id)
        )
    )
    pending = [
        s for s in sessions if (s.session_metadata or {}).get("surface") == "copilot_pending"
    ]
    assert len(pending) == 1
