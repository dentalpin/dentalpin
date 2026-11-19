"""Issuance of normal authenticated staff sessions."""

from uuid import UUID

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from .cookies import new_csrf_token, set_session_cookies
from .models import User
from .schemas import TokenResponse
from .service import create_access_token, issue_refresh_token


def client_ip(request: Request) -> str | None:
    """The peer as uvicorn resolved it — never the raw header (#623).

    This used to read ``X-Forwarded-For`` itself and take the leftmost
    entry, which is the one the client writes, so the ``client_ip``
    stored on a refresh family could be set to anything the caller
    liked. ``request.client.host`` is what uvicorn's proxy-headers
    middleware already settled using FORWARDED_ALLOW_IPS, and it is the
    same value the login rate limit keys on (``get_remote_address``), so
    the audit trail and the limiter can no longer disagree.
    """
    return request.client.host if request.client else None


async def start_session(
    request: Request, response: Response, db: AsyncSession, user: User, clinic_id: UUID | None
) -> TokenResponse:
    """Issue a tracked refresh family + access token and set the session
    cookies (ADR 0023). The body still carries the pair for one release so
    bearer clients and the e2e API context keep working unchanged."""
    refresh_token, family_id = await issue_refresh_token(
        db, user, user_agent=request.headers.get("user-agent"), client_ip=client_ip(request)
    )
    access_token = create_access_token(
        user.id, clinic_id=clinic_id, token_version=user.token_version, family_id=family_id
    )
    await db.commit()
    set_session_cookies(
        response,
        access_token=access_token,
        refresh_token=refresh_token,
        csrf_token=new_csrf_token(),
        request=request,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
