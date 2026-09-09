"""Authentication dependencies for FastAPI."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.log_context import set_request_context
from app.database import get_db

from .models import Clinic, ClinicMembership, User
from .permissions import has_permission
from .rbac import has_permission_in_clinic
from .service import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class ClinicContext:
    """Context object containing current user and clinic."""

    def __init__(self, user: User, clinic: Clinic, role: str):
        self.user = user
        self.clinic = clinic
        self.role = role
        self.clinic_id = clinic.id
        self.user_id = user.id


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        token_version = payload.get("token_version", 0)

        if user_id is None or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Fetch user from database
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Check token version for revocation
    if user.token_version != token_version:
        raise credentials_exception

    return user


async def get_clinic_context(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    clinic_id: UUID | None = None,
) -> ClinicContext:
    """Get clinic context for the current user.

    If clinic_id is not provided, uses the user's first clinic.
    Raises 403 if user doesn't have access to the clinic.
    """
    # Get user's clinic memberships; eager-load cabinets so downstream
    # ClinicResponse.model_validate doesn't trigger async lazy loads.
    from app.core.auth.models import Clinic as ClinicModel

    result = await db.execute(
        select(ClinicMembership)
        .options(selectinload(ClinicMembership.clinic).selectinload(ClinicModel.cabinets))
        .where(ClinicMembership.user_id == current_user.id)
    )
    memberships = result.scalars().all()

    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of any clinic",
        )

    # Find the requested clinic or use the first one
    if clinic_id:
        membership = next(
            (m for m in memberships if m.clinic_id == clinic_id),
            None,
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to this clinic",
            )
    else:
        membership = memberships[0]

    # Bind clinic_id + user_id onto the per-request logging context so
    # every log line and event emitted inside this handler carries
    # them automatically (request_id was set by the middleware). Not
    # reset — the middleware drops the whole context at request end.
    set_request_context(clinic_id=membership.clinic.id, user_id=current_user.id)

    return ClinicContext(
        user=current_user,
        clinic=membership.clinic,
        role=membership.role,
    )


async def block_in_demo() -> None:
    """Reject the request on the public demo instance (DEMO_MODE=true).

    Guards operations that would lock out or break the shared demo for
    other visitors; the rest of the app stays fully interactive.
    """
    if settings.DEMO_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action is disabled on the public demo.",
        )


def require_permission(permission: str) -> Callable:
    """FastAPI dependency factory that requires a specific permission.

    Usage:
        @router.get("/patients")
        async def list_patients(
            ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
            _: Annotated[None, Depends(require_permission("clinical.patients.read"))],
        ):
            ...
    """

    async def permission_checker(
        ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> None:
        if settings.RBAC_FROM_DB:
            allowed = await has_permission_in_clinic(db, ctx.clinic_id, ctx.role, permission)
        else:
            allowed = has_permission(ctx.role, permission)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )

    return permission_checker
