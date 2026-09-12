"""ADR 0023 (#353): HttpOnly session cookies, refresh rotation, CSRF."""

from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import RefreshToken
from app.core.auth.service import decode_token

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"

_SETUP_PAYLOAD = {
    "admin_first_name": "Ana",
    "admin_last_name": "Admin",
    "admin_email": "admin@example.com",
    "admin_password": "SecurePass1234",
    "clinic_name": "Clinic",
    "clinic_tax_id": "B12345678",
}


async def _bootstrap(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/setup", json=_SETUP_PAYLOAD)
    assert resp.status_code in (200, 201), resp.text
    client.cookies.clear()


async def _login(client: AsyncClient):
    return await client.post(
        LOGIN, data={"username": "admin@example.com", "password": "SecurePass1234"}
    )


def _cookie_flags(resp, name: str) -> str:
    for header in resp.headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return header
    raise AssertionError(f"cookie {name} not set: {resp.headers.get_list('set-cookie')}")


@pytest.mark.asyncio
async def test_login_sets_httponly_session_cookies_and_keeps_body(client: AsyncClient) -> None:
    await _bootstrap(client)
    resp = await _login(client)
    assert resp.status_code == 200, resp.text

    access = _cookie_flags(resp, "dp_access")
    refresh = _cookie_flags(resp, "dp_refresh")
    csrf = _cookie_flags(resp, "dp_csrf")
    assert "HttpOnly" in access and "HttpOnly" in refresh
    assert "HttpOnly" not in csrf  # the readable double-submit half
    # All three on path=/ so a page request carries dp_refresh and SSR can
    # refresh an expired access cookie in place (review of #394).
    assert "Path=/" in refresh and "Path=/api" not in refresh
    assert "Domain=" not in refresh  # host-only unless COOKIE_DOMAIN is set
    assert "SameSite=lax" in access.lower().replace("samesite=lax", "SameSite=lax")

    # Transition release: bearer clients still get the pair in the body.
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]


@pytest.mark.asyncio
async def test_cookie_alone_authenticates_and_csrf_gates_unsafe_methods(
    client: AsyncClient,
) -> None:
    await _bootstrap(client)
    await _login(client)
    csrf = client.cookies.get("dp_csrf")
    assert csrf

    # GET with only the cookies (httpx keeps the jar) → authenticated.
    me = await client.get(ME)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["user"]["email"] == "admin@example.com"

    # Cookie-authenticated unsafe method without the CSRF header → 403;
    # with the double-submit header → accepted. (Logout itself is
    # deliberately lenient: forcing a sign-out is not worth protecting.)
    target = "/api/v1/auth/clinic/settings/communications"
    denied = await client.patch(target, json={"language": "en"})
    assert denied.status_code == 403, denied.text
    assert "CSRF" in denied.text
    ok = await client.patch(target, json={"language": "en"}, headers={"X-CSRF-Token": csrf})
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_bearer_header_path_is_unchanged_and_csrf_exempt(
    client: AsyncClient, auth_headers: dict
) -> None:
    me = await client.get(ME, headers=auth_headers)
    assert me.status_code == 200
    # Bearer clients never carry the session cookie → no CSRF requirement.
    resp = await client.post(LOGOUT, headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_refresh_rotates_and_reuse_burns_the_family(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "REFRESH_REUSE_GRACE_SECONDS", 0)
    await _bootstrap(client)
    first = (await _login(client)).json()
    old_refresh = first["refresh_token"]

    # Bearer-style rotation via the body.
    client.cookies.clear()
    rotated = await client.post(REFRESH, json={"refresh_token": old_refresh})
    assert rotated.status_code == 200, rotated.text
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != old_refresh

    # The old token is revoked: presenting it again is reuse → family burned.
    client.cookies.clear()
    reuse = await client.post(REFRESH, json={"refresh_token": old_refresh})
    assert reuse.status_code == 401
    assert "reuse" in reuse.text.lower()

    # …so the *new* token is dead too.
    client.cookies.clear()
    dead = await client.post(REFRESH, json={"refresh_token": new_refresh})
    assert dead.status_code == 401

    rows = await _family_rows(db_session, old_refresh)
    assert rows and all(r.revoked_at is not None for r in rows)


async def _family_rows(db: AsyncSession, refresh_jwt: str) -> list[RefreshToken]:
    """Rows of the family a refresh token belongs to (setup starts its own
    family for the admin, which these tests never touch)."""
    from uuid import UUID

    fam = UUID(decode_token(refresh_jwt)["fam"])
    return list(
        (await db.execute(select(RefreshToken).where(RefreshToken.family_id == fam)))
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_refresh_via_cookie_only(client: AsyncClient) -> None:
    await _bootstrap(client)
    await _login(client)
    csrf = client.cookies.get("dp_csrf")
    # No body: the dp_refresh cookie is the credential.
    resp = await client.post(REFRESH, headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200, resp.text
    assert _cookie_flags(resp, "dp_refresh")
    # The CSRF token is per family: unchanged by rotation, so a tab that
    # captured it before another tab refreshed keeps passing the gate.
    assert _cookie_flags(resp, "dp_csrf").startswith(f"dp_csrf={csrf};")
    # The rotated session keeps working.
    me = await client.get(ME)
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_logout_revokes_family_and_clears_cookies(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _bootstrap(client)
    login = (await _login(client)).json()
    csrf = client.cookies.get("dp_csrf")

    resp = await client.post(LOGOUT, headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 204
    cleared = [
        h for h in resp.headers.get_list("set-cookie") if "Max-Age=0" in h or "expires" in h.lower()
    ]
    assert any(h.startswith("dp_access=") for h in cleared)
    assert any(h.startswith("dp_refresh=") for h in cleared)

    # The family is revoked: the refresh token from login is dead.
    client.cookies.clear()
    dead = await client.post(REFRESH, json={"refresh_token": login["refresh_token"]})
    assert dead.status_code == 401
    rows = await _family_rows(db_session, login["refresh_token"])
    assert rows and all(r.revoked_at is not None for r in rows)


@pytest.mark.asyncio
async def test_legacy_stateless_refresh_token_is_migrated(client: AsyncClient) -> None:
    """Tokens issued before ADR 0023 (no jti) still refresh during the
    transition and get migrated into a tracked family. They are not
    single-use (nothing marks them consumed); they expire with their own
    ``exp``."""
    from app.core.auth.service import create_refresh_token

    await _bootstrap(client)
    me = await _login(client)
    user_id = me.json() and (await client.get(ME)).json()["data"]["user"]["id"]
    client.cookies.clear()
    from uuid import UUID

    legacy = create_refresh_token(UUID(user_id), token_version=0)
    resp = await client.post(REFRESH, json={"refresh_token": legacy})
    assert resp.status_code == 200, resp.text
    assert resp.json()["refresh_token"] != legacy


@pytest.mark.asyncio
async def test_cookie_domain_setting_widens_cookies_for_split_hosts(
    client: AsyncClient, monkeypatch
) -> None:
    """Split-host deployments (app and API on sibling hosts) set COOKIE_DOMAIN
    so the browser sends the cookies to both and the app can read dp_csrf."""
    from app.config import settings

    await _bootstrap(client)
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".example.com")
    resp = await _login(client)
    assert resp.status_code == 200, resp.text
    for name in ("dp_access", "dp_refresh", "dp_csrf"):
        assert "Domain=.example.com" in _cookie_flags(resp, name)
    # httpx's jar ignores a cookie for a foreign domain, as a browser on
    # another host would; read the token from the header instead.
    csrf = _cookie_flags(resp, "dp_csrf").split(";")[0].split("=", 1)[1]
    out = await client.post(LOGOUT, headers={"X-CSRF-Token": csrf})
    assert out.status_code == 204
    # Clearing must target the same domain or the browser keeps the cookies.
    assert all("Domain=.example.com" in h for h in out.headers.get_list("set-cookie"))


@pytest.mark.asyncio
async def test_refresh_rate_key_reads_cookie_when_body_is_empty() -> None:
    """The browser refresh has no body; the limiter must still key by user."""
    from uuid import uuid4

    from starlette.requests import Request

    from app.core.auth.router import _refresh_rate_key
    from app.core.auth.service import create_refresh_token

    user_id = uuid4()
    token = create_refresh_token(user_id, token_version=0)
    scope = {
        "type": "http",
        "method": "POST",
        "path": REFRESH,
        "headers": [(b"cookie", f"dp_refresh={token}".encode())],
        "client": ("10.0.0.1", 1234),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    assert await _refresh_rate_key(Request(scope, receive)) == f"refresh:{user_id}"


@pytest.mark.asyncio
async def test_logout_after_access_cookie_expired_still_revokes_family(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Once the browser has dropped the expired ``dp_access`` (max-age),
    logout must still find the family through ``dp_refresh``."""
    await _bootstrap(client)
    login = (await _login(client)).json()
    client.cookies.delete("dp_access")
    resp = await client.post(LOGOUT)
    assert resp.status_code == 204
    rows = await _family_rows(db_session, login["refresh_token"])
    assert rows and all(r.revoked_at is not None for r in rows)


@pytest.mark.asyncio
async def test_reuse_inside_grace_window_returns_live_successor(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Two tabs refreshing with the same token (#421): the second one gets
    the successor instead of burning the family; the family stays alive."""
    await _bootstrap(client)
    old_refresh = (await _login(client)).json()["refresh_token"]
    client.cookies.clear()
    first = await client.post(REFRESH, json={"refresh_token": old_refresh})
    assert first.status_code == 200
    client.cookies.clear()
    second = await client.post(REFRESH, json={"refresh_token": old_refresh})
    assert second.status_code == 200, second.text
    live = second.json()["refresh_token"]
    assert decode_token(live)["jti"] == decode_token(first.json()["refresh_token"])["jti"]
    # The successor still rotates normally afterwards.
    client.cookies.clear()
    third = await client.post(REFRESH, json={"refresh_token": live})
    assert third.status_code == 200, third.text
    rows = await _family_rows(db_session, old_refresh)
    assert any(r.revoked_at is None for r in rows)


@pytest.mark.asyncio
async def test_split_host_login_warns_with_the_cookie_domain_to_set(
    client: AsyncClient, monkeypatch, caplog
) -> None:
    """#444: host-only cookies never reach a separately hosted app, and the
    only symptom is that every page reload lands on /login. Say it once, at
    login, with the value to set."""
    from app.config import settings
    from app.core.auth import cookies

    await _bootstrap(client)
    monkeypatch.setattr(cookies, "_HOST_ONLY_WARNED", False)
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", "")
    with caplog.at_level(logging.WARNING, logger="app.core.auth.cookies"):
        resp = await client.post(
            LOGIN,
            data={"username": "admin@example.com", "password": "SecurePass1234"},
            headers={"Host": "api-demo.example.com", "Origin": "https://demo.example.com"},
        )
    assert resp.status_code == 200, resp.text
    assert "COOKIE_DOMAIN=.example.com" in caplog.text


@pytest.mark.asyncio
async def test_no_warning_for_one_host_or_when_cookie_domain_is_set(
    client: AsyncClient, monkeypatch, caplog
) -> None:
    from app.config import settings
    from app.core.auth import cookies

    await _bootstrap(client)
    creds = {"username": "admin@example.com", "password": "SecurePass1234"}

    # Same host for app and API: nothing to warn about.
    monkeypatch.setattr(cookies, "_HOST_ONLY_WARNED", False)
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", "")
    with caplog.at_level(logging.WARNING, logger="app.core.auth.cookies"):
        resp = await client.post(
            LOGIN,
            data=creds,
            headers={"Host": "app.example.com", "Origin": "https://app.example.com"},
        )
    assert resp.status_code == 200, resp.text
    assert "COOKIE_DOMAIN" not in caplog.text

    # Split hosts, but the deployment already widened the cookies.
    caplog.clear()
    monkeypatch.setattr(cookies, "_HOST_ONLY_WARNED", False)
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".example.com")
    with caplog.at_level(logging.WARNING, logger="app.core.auth.cookies"):
        resp = await client.post(
            LOGIN,
            data=creds,
            headers={"Host": "api.example.com", "Origin": "https://app.example.com"},
        )
    assert resp.status_code == 200, resp.text
    assert "COOKIE_DOMAIN" not in caplog.text


def test_shared_parent_needs_two_common_labels() -> None:
    from app.core.auth.cookies import _shared_parent

    assert _shared_parent("demo.dentalpin.com", "api-demo.dentalpin.com") == ".dentalpin.com"
    assert (
        _shared_parent("app.clinic.example.org", "api.clinic.example.org") == ".clinic.example.org"
    )
    assert _shared_parent("app.example.com", "api.example.net") is None
    assert _shared_parent("app.com", "api.com") is None  # a public suffix is not a parent
