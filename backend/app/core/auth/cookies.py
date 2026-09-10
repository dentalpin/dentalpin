"""Session cookies (ADR 0023, issue #353).

The backend sets the tokens as ``HttpOnly; Secure; SameSite=Lax`` cookies
so JS never sees them. A third, JS-readable ``dp_csrf`` cookie is the
double-submit token: cookie-authenticated unsafe requests must echo it in
``X-CSRF-Token`` (``dependencies.get_auth_token``); it is minted per
refresh-token family and survives rotation, so an already-mounted tab
keeps a valid token after another tab refreshed.

All three share ``path=/`` so a server-rendered page request carries the
refresh cookie too and SSR can refresh an expired access cookie in place
(a path-scoped refresh cookie never reached Nuxt, so every reload after
expiry bounced through ``/login``). ``COOKIE_DOMAIN`` widens them to a
parent domain for split-host deployments.
"""

from __future__ import annotations

import secrets

from fastapi import Response

from app.config import settings

ACCESS_COOKIE = "dp_access"
REFRESH_COOKIE = "dp_refresh"
CSRF_COOKIE = "dp_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _secure() -> bool:
    # Plain http://localhost in dev/e2e can't carry Secure cookies.
    return settings.ENVIRONMENT == "production"


def _domain() -> str | None:
    return settings.COOKIE_DOMAIN.strip() or None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_session_cookies(
    response: Response, *, access_token: str, refresh_token: str, csrf_token: str
) -> None:
    access_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=access_ttl,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/",
        domain=_domain(),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_ttl,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/",
        domain=_domain(),
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_ttl,
        httponly=False,  # the double-submit half JS must read
        secure=_secure(),
        samesite="lax",
        path="/",
        domain=_domain(),
    )


def clear_session_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", domain=_domain())
