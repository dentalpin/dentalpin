"""bcrypt hashes at most 72 bytes: a longer password is a 422, not a 500 (#1051)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.auth.models import Clinic


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("a1" * 36, 201),  # 72 bytes
        ("a1" * 37, 422),
        ("jelszó1" + "ő" * 33, 422),  # 40 characters, 74 bytes
    ],
)
async def test_create_user_password_byte_limit(
    client: AsyncClient,
    auth_headers: dict[str, str],
    test_clinic: Clinic,
    password: str,
    expected: int,
) -> None:
    r = await client.post(
        "/api/v1/auth/users",
        json={
            "email": f"new-{uuid4().hex[:8]}@example.com",
            "password": password,
            "first_name": "New",
            "last_name": "Staff",
            "role": "receptionist",
        },
        headers=auth_headers,
    )
    assert r.status_code == expected, r.text
