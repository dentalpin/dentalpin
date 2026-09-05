"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Test health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


_SETUP_PAYLOAD = {
    "admin_first_name": "Admin",
    "admin_last_name": "User",
    "admin_email": "admin@example.com",
    "admin_password": "SecurePass123",
    "clinic_name": "My Clinic",
    "clinic_tax_id": "B12345678",
}


@pytest.mark.asyncio
async def test_setup_status(client: AsyncClient) -> None:
    """setup/status flips to initialized once the first account exists."""
    before = await client.get("/api/v1/auth/setup/status")
    assert before.status_code == 200
    assert before.json()["data"]["initialized"] is False

    response = await client.post("/api/v1/auth/setup", json=_SETUP_PAYLOAD)
    assert response.status_code == 201

    after = await client.get("/api/v1/auth/setup/status")
    assert after.json()["data"]["initialized"] is True


@pytest.mark.asyncio
async def test_setup_creates_admin_and_clinic(client: AsyncClient) -> None:
    """First-run setup returns a working admin token tied to a new clinic."""
    response = await client.post("/api/v1/auth/setup", json=_SETUP_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    body = me.json()["data"]
    assert body["user"]["email"] == "admin@example.com"
    assert body["clinics"][0]["name"] == "My Clinic"
    assert body["clinics"][0]["role"] == "admin"


@pytest.mark.asyncio
async def test_setup_rejected_when_initialized(client: AsyncClient) -> None:
    """Once the system has an account, setup is closed (409)."""
    first = await client.post("/api/v1/auth/setup", json=_SETUP_PAYLOAD)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/setup",
        json={**_SETUP_PAYLOAD, "admin_email": "other@example.com"},
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_password_floor_is_12(client: AsyncClient) -> None:
    """#354: length beats composition — 11 characters is rejected even with
    letters and digits; 12 passes the length gate."""
    resp = await client.post(
        "/api/v1/auth/setup", json={**_SETUP_PAYLOAD, "admin_password": "Abcdefghij1"}
    )
    assert resp.status_code in (400, 422), resp.text
    assert "12" in resp.text


@pytest.mark.asyncio
async def test_setup_weak_password(client: AsyncClient) -> None:
    """Weak admin passwords are rejected."""
    response = await client.post(
        "/api/v1/auth/setup",
        json={**_SETUP_PAYLOAD, "admin_password": "weak"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login(client: AsyncClient) -> None:
    """Test user login after first-run setup."""
    await client.post("/api/v1/auth/setup", json=_SETUP_PAYLOAD)

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin@example.com", "password": "SecurePass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    """Test login with invalid credentials."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "nonexistent@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """Test /me endpoint returns current user wrapped in ApiResponse."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    # Response is wrapped in ApiResponse: {data: {user, clinics, permissions}, message}
    assert data["data"]["user"]["email"] == "test@example.com"
    assert data["data"]["user"]["first_name"] == "Test"
    assert "message" in data  # message field is present (may be null)


@pytest.mark.asyncio
async def test_me_without_auth(client: AsyncClient) -> None:
    """Test /me endpoint requires authentication."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
