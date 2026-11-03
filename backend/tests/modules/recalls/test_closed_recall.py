"""A done or cancelled recall is final (#804)."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from httpx import AsyncClient

from app.database import async_session_maker
from app.modules.patients.models import Patient
from app.modules.recalls.service import RecallClosedError, RecallService

ACTIONS = [
    ("attempts", {"channel": "phone", "outcome": "scheduled"}),
    ("attempts", {"channel": "phone", "outcome": "declined"}),
    ("attempts", {"channel": "phone", "outcome": "no_answer"}),
    ("done", None),
    ("cancel", {}),
    ("snooze", {"months": 3}),
]


async def _new_recall(client: AsyncClient, headers: dict, patient: Patient) -> str:
    res = await client.post(
        "/api/v1/recalls/",
        json={
            "patient_id": str(patient.id),
            "due_month": "2026-08-01",
            "reason": "hygiene",
            "priority": "normal",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("closing", ["done", "cancel"])
@pytest.mark.parametrize(("path", "body"), ACTIONS)
async def test_closed_recall_refuses_every_action(
    client: AsyncClient, auth_headers: dict, test_patient: Patient, closing, path, body
):
    recall_id = await _new_recall(client, auth_headers, test_patient)
    url = f"/api/v1/recalls/{recall_id}"
    closed = await client.post(
        f"{url}/{closing}", json={} if closing == "cancel" else None, headers=auth_headers
    )
    assert closed.status_code == 200, closed.text
    before = (await client.get(url, headers=auth_headers)).json()["data"]

    res = await client.post(f"{url}/{path}", json=body, headers=auth_headers)

    assert res.status_code == 409, res.text
    after = (await client.get(url, headers=auth_headers)).json()["data"]
    assert after == before


@pytest.mark.asyncio
async def test_open_recall_can_still_be_worked_and_closed(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
):
    recall_id = await _new_recall(client, auth_headers, test_patient)
    url = f"/api/v1/recalls/{recall_id}"

    attempt = await client.post(
        f"{url}/attempts", json={"channel": "phone", "outcome": "no_answer"}, headers=auth_headers
    )
    assert attempt.status_code == 201, attempt.text
    snoozed = await client.post(f"{url}/snooze", json={"months": 3}, headers=auth_headers)
    assert snoozed.status_code == 200, snoozed.text
    assert snoozed.json()["data"]["status"] == "pending"
    done = await client.post(f"{url}/done", headers=auth_headers)
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "done"


@pytest.mark.asyncio
async def test_concurrent_done_runs_once(
    client: AsyncClient, auth_headers: dict, test_patient: Patient
):
    recall_id = UUID(await _new_recall(client, auth_headers, test_patient))
    clinic_id = test_patient.clinic_id

    async def complete() -> bool:
        async with async_session_maker() as db:
            try:
                await RecallService.mark_done(db, clinic_id, recall_id, by_user=None)
            except RecallClosedError:
                return False
            await db.commit()
            return True

    results = await asyncio.gather(complete(), complete())

    assert sorted(results) == [False, True]
