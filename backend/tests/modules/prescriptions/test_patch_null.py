"""An explicit ``null`` on a NOT NULL template field is a 422 (#1134).

``items`` is a JSONB NOT NULL column: SQLAlchemy stores Python ``None`` as
JSON ``'null'``, so a null used to commit and then break the response model
and every later list of the clinic's templates (500). ``name`` null hit the
NOT NULL constraint and came back as the duplicate-name 409.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["items", "name"])
async def test_null_on_template_field_is_422_and_row_untouched(
    client, auth_headers, test_clinic, field
):
    line = {"medication_name": "Amoxicilina", "dosage": "500 mg"}
    created = await client.post(
        "/api/v1/prescriptions/templates",
        json={"name": "keep-me", "items": [line]},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    tpl_id = created.json()["data"]["id"]

    patched = await client.patch(
        f"/api/v1/prescriptions/templates/{tpl_id}",
        json={field: None},
        headers=auth_headers,
    )
    assert patched.status_code == 422, patched.text
    assert field in patched.text

    listed = await client.get("/api/v1/prescriptions/templates", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    (row,) = [t for t in listed.json()["data"] if t["id"] == tpl_id]
    assert row["name"] == "keep-me"
    assert row["items"][0]["medication_name"] == "Amoxicilina"
