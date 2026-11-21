"""A rejected SDI record is regenerated once.

``requeue`` checked only that the record it was given was ``rejected``, and
the rejected record keeps that state after the regeneration (it stays as
history). A second click on "Reinvia" — or a requeue of an older scarto
after a newer file existed — built yet another file for the same invoice
number: two pending records, two files with one number and date for the
admin to upload to the SDI.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.sdi_it.models import SdiItRecord

from .test_router import NS, _queued_record


def _scarto(file_name: str) -> str:
    return (
        f'<ns3:NotificaScarto xmlns:ns3="{NS}"><IdentificativoSdI>556</IdentificativoSdI>'
        f"<NomeFile>{file_name}</NomeFile><ListaErrori><Errore><Codice>00423</Codice>"
        "<Descrizione>Prezzo totale</Descrizione></Errore></ListaErrori></ns3:NotificaScarto>"
    )


@pytest.mark.asyncio
async def test_requeueing_the_same_scarto_twice_builds_one_file(
    client: AsyncClient, auth_headers, test_clinic, test_patient, db_session
):
    rec = await _queued_record(db_session, test_clinic, test_patient)
    res = await client.post(
        "/api/v1/sdi_it/receipts", json={"xml": _scarto(rec.file_name)}, headers=auth_headers
    )
    assert res.json()["data"]["state"] == "rejected"

    first = await client.post(f"/api/v1/sdi_it/records/{rec.id}/requeue", headers=auth_headers)
    second = await client.post(f"/api/v1/sdi_it/records/{rec.id}/requeue", headers=auth_headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 409
    states = (
        await db_session.scalars(
            select(SdiItRecord.state)
            .where(SdiItRecord.invoice_id == rec.invoice_id)
            .order_by(SdiItRecord.created_at)
        )
    ).all()
    assert states == ["rejected", "pending"]


@pytest.mark.asyncio
async def test_an_older_scarto_cannot_be_requeued_after_a_newer_file(
    client: AsyncClient, auth_headers, test_clinic, test_patient, db_session
):
    rec = await _queued_record(db_session, test_clinic, test_patient)
    await client.post(
        "/api/v1/sdi_it/receipts", json={"xml": _scarto(rec.file_name)}, headers=auth_headers
    )
    newer = (
        await client.post(f"/api/v1/sdi_it/records/{rec.id}/requeue", headers=auth_headers)
    ).json()["data"]
    # The newer file is rejected too; only *it* may be regenerated now.
    await client.post(
        "/api/v1/sdi_it/receipts",
        json={"xml": _scarto(newer["file_name"])},
        headers=auth_headers,
    )

    stale = await client.post(f"/api/v1/sdi_it/records/{rec.id}/requeue", headers=auth_headers)
    latest = await client.post(
        f"/api/v1/sdi_it/records/{newer['id']}/requeue", headers=auth_headers
    )

    assert stale.status_code == 409
    assert latest.status_code == 200, latest.text
