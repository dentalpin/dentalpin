"""API tests for the clinic-hours endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_clinic_hours_returns_default(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    response = await client.get("/api/v1/schedules/clinic-hours", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["clinic_id"] == str(test_clinic.id)
    assert data["timezone"] == "Europe/Madrid"
    assert len(data["days"]) == 7


@pytest.mark.asyncio
async def test_put_clinic_hours_replaces_shifts(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    payload = {
        "timezone": "Europe/Madrid",
        "days": [
            {
                "weekday": 0,
                "shifts": [
                    {"start_time": "09:00:00", "end_time": "14:00:00"},
                    {"start_time": "16:00:00", "end_time": "20:00:00"},
                ],
            },
            {"weekday": 5, "shifts": []},
            {"weekday": 6, "shifts": []},
        ],
    }
    response = await client.put(
        "/api/v1/schedules/clinic-hours", json=payload, headers=auth_headers
    )
    assert response.status_code == 200
    days = response.json()["data"]["days"]
    monday = next(d for d in days if d["weekday"] == 0)
    assert len(monday["shifts"]) == 2


@pytest.mark.asyncio
async def test_clinic_override_lifecycle(client: AsyncClient, auth_headers: dict, test_clinic):
    # Create
    create_res = await client.post(
        "/api/v1/schedules/clinic-overrides",
        json={
            "start_date": "2026-12-25",
            "end_date": "2026-12-26",
            "kind": "closed",
            "reason": "Navidad",
            "shifts": [],
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    override_id = create_res.json()["data"]["id"]

    # List
    list_res = await client.get("/api/v1/schedules/clinic-overrides", headers=auth_headers)
    assert list_res.status_code == 200
    assert any(o["id"] == override_id for o in list_res.json()["data"])

    # Delete
    del_res = await client.delete(
        f"/api/v1/schedules/clinic-overrides/{override_id}", headers=auth_headers
    )
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_clinic_override_closed_rejects_shifts(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    res = await client.post(
        "/api/v1/schedules/clinic-overrides",
        json={
            "start_date": "2026-12-25",
            "end_date": "2026-12-25",
            "kind": "closed",
            "shifts": [{"start_time": "09:00:00", "end_time": "14:00:00"}],
        },
        headers=auth_headers,
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_put_clinic_hours_rejects_overlapping_shifts(
    client: AsyncClient, auth_headers: dict, test_clinic
):
    """Overlapping shifts on one day are a 422 (#991); touching ones are fine."""
    overlapping = {
        "days": [
            {
                "weekday": 0,
                "shifts": [
                    {"start_time": "09:00:00", "end_time": "18:00:00"},
                    {"start_time": "10:00:00", "end_time": "12:00:00"},
                ],
            }
        ]
    }
    response = await client.put(
        "/api/v1/schedules/clinic-hours", json=overlapping, headers=auth_headers
    )
    assert response.status_code == 422, response.text

    touching = {
        "days": [
            {
                "weekday": 0,
                "shifts": [
                    {"start_time": "14:00:00", "end_time": "18:00:00"},
                    {"start_time": "09:00:00", "end_time": "14:00:00"},
                ],
            }
        ]
    }
    response = await client.put(
        "/api/v1/schedules/clinic-hours", json=touching, headers=auth_headers
    )
    assert response.status_code == 200, response.text
