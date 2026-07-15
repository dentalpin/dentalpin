"""Authentication router with rate limiting."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.plugins import module_registry
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .dependencies import ClinicContext, get_clinic_context, get_current_user, require_permission
from .models import Clinic, ClinicMembership, User
from .permissions import CORE_PERMISSIONS, ROLES, expand_permissions, get_role_permissions
from .schemas import (
    AuthResponse,
    ClinicMetadataResponse,
    ClinicMetadataUpdate,
    ClinicResponse,
    MeResponse,
    ProfessionalResponse,
    SetupStatusResponse,
    SystemSetup,
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
    UserWithRoleResponse,
)
from .service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
# Rate limiting guards production. Dev + test disable it so local flows
# (manual clicking, Playwright E2E, pytest) don't run into 5/minute
# caps after a handful of reloads.
_limiter_enabled = settings.ENVIRONMENT == "production" and not settings.TESTING
limiter = Limiter(key_func=get_remote_address, enabled=_limiter_enabled)


async def _refresh_rate_key(request: Request) -> str:
    """Key the refresh limiter by user, not IP.

    A shared edge proxy (Cloudflare → Nuxt SSR → backend) collapses every
    real client to the same socket peer, so an IP-keyed limiter caps the
    whole tenant after a handful of refreshes. Decoding the refresh token
    here gives a per-user bucket; we fall back to the proxy-aware client
    IP if the body is missing or unreadable.
    """
    try:
        body = await request.json()
        token = body.get("refresh_token") if isinstance(body, dict) else None
        if token:
            payload = decode_token(token)
            sub = payload.get("sub")
            if sub:
                return f"refresh:{sub}"
    except Exception:
        pass
    return get_remote_address(request)


@router.get("/setup/status", response_model=ApiResponse[SetupStatusResponse])
async def setup_status(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[SetupStatusResponse]:
    """Whether the system already has an account (drives the first-run wizard)."""
    count = await db.scalar(select(func.count()).select_from(User))
    return ApiResponse(data=SetupStatusResponse(initialized=bool(count)))


@router.post("/setup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def setup(
    request: Request,
    data: SystemSetup,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """First-run: create the first admin account and its clinic, then log them in.

    Self-closing: once any user exists the system is initialized and this
    endpoint returns 409.
    """
    # ponytail: guard por count==0; una carrera entre dos setups simultáneos es
    # despreciable en un arranque de operador único. Subir a constraint/lock solo
    # si esto se vuelve multi-tenant self-serve.
    existing = await db.scalar(select(func.count()).select_from(User))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="System already initialized",
        )

    is_valid, error_msg = validate_password_strength(data.admin_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )

    clinic = Clinic(
        name=data.clinic_name,
        tax_id=data.clinic_tax_id,
        timezone=data.timezone or "Europe/Madrid",
        currency=data.currency or "EUR",
    )
    db.add(clinic)
    await db.flush()

    user = User(
        email=data.admin_email,
        password_hash=hash_password(data.admin_password),
        first_name=data.admin_first_name,
        last_name=data.admin_last_name,
    )
    db.add(user)
    await db.flush()

    db.add(ClinicMembership(user_id=user.id, clinic_id=clinic.id, role="admin"))
    await db.commit()

    access_token = create_access_token(
        user.id, clinic_id=clinic.id, token_version=user.token_version
    )
    refresh_token = create_refresh_token(user.id, token_version=user.token_version)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Login and get access tokens."""
    # Find user by email
    result = await db.execute(
        select(User).options(selectinload(User.memberships)).where(User.email == form_data.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Get first clinic ID if user has any membership
    clinic_id = None
    if user.memberships:
        clinic_id = user.memberships[0].clinic_id

    # Generate tokens
    access_token = create_access_token(
        user.id,
        clinic_id=clinic_id,
        token_version=user.token_version,
    )
    refresh_token = create_refresh_token(user.id, token_version=user.token_version)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=AuthResponse)
@limiter.limit("10/minute", key_func=_refresh_rate_key)
async def refresh_token(
    request: Request,
    data: TokenRefresh,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthResponse:
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(data.refresh_token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        token_version = payload.get("token_version", 0)

        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Fetch user with memberships and clinics
    result = await db.execute(
        select(User).options(selectinload(User.memberships)).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Check token version for revocation
    if user.token_version != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    # Fetch memberships with clinics for response
    memberships_result = await db.execute(
        select(ClinicMembership)
        .options(selectinload(ClinicMembership.clinic))
        .where(ClinicMembership.user_id == user.id)
    )
    memberships = memberships_result.scalars().all()

    clinics = [
        ClinicResponse(
            id=m.clinic.id,
            name=m.clinic.name,
            role=m.role,
        )
        for m in memberships
    ]

    # Get first clinic ID for token
    clinic_id = None
    if memberships:
        clinic_id = memberships[0].clinic_id

    # Generate new tokens
    access_token = create_access_token(
        user.id,
        clinic_id=clinic_id,
        token_version=user.token_version,
    )
    new_refresh_token = create_refresh_token(user.id, token_version=user.token_version)

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserResponse.model_validate(user),
        clinics=clinics,
    )


@router.get("/me", response_model=ApiResponse[MeResponse])
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[MeResponse]:
    """Get current user info, clinics, and permissions."""
    # Fetch memberships with clinics
    result = await db.execute(
        select(ClinicMembership)
        .options(selectinload(ClinicMembership.clinic))
        .where(ClinicMembership.user_id == current_user.id)
    )
    memberships = result.scalars().all()

    clinics = [
        ClinicResponse(
            id=m.clinic.id,
            name=m.clinic.name,
            role=m.role,
        )
        for m in memberships
    ]

    # Compute effective permissions (use first clinic's role for MVP)
    permissions: list[str] = []
    if memberships:
        role = memberships[0].role
        role_perms = get_role_permissions(role)
        # Combine module permissions with core permissions
        all_perms = module_registry.get_all_permissions() + CORE_PERMISSIONS
        permissions = expand_permissions(role_perms, all_perms)

    return ApiResponse(
        data=MeResponse(
            user=UserResponse.model_validate(current_user),
            clinics=clinics,
            permissions=permissions,
        )
    )


@router.get("/users", response_model=PaginatedApiResponse[UserWithRoleResponse])
async def list_users(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.users.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaginatedApiResponse[UserWithRoleResponse]:
    """List all users in the current clinic (admin only)."""
    # Fetch all memberships for this clinic with user data
    result = await db.execute(
        select(ClinicMembership)
        .options(selectinload(ClinicMembership.user))
        .where(ClinicMembership.clinic_id == ctx.clinic_id)
    )
    memberships = result.scalars().all()

    users = [
        UserWithRoleResponse(
            id=m.user.id,
            email=m.user.email,
            first_name=m.user.first_name,
            last_name=m.user.last_name,
            is_active=m.user.is_active,
            role=m.role,
            created_at=m.user.created_at.isoformat(),
        )
        for m in memberships
    ]

    return PaginatedApiResponse(
        data=users,
        total=len(users),
        page=1,
        page_size=len(users),
    )


@router.post(
    "/users", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED
)
async def create_user(
    data: UserCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.users.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[UserResponse]:
    """Create a new user (admin only)."""
    # Validate role
    if data.role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role. Must be one of: {', '.join(ROLES)}",
        )

    # Validate password strength
    is_valid, error_msg = validate_password_strength(data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_msg,
        )

    # Resolve the target clinic. A caller may only create a membership in
    # a clinic they administer themselves — otherwise an admin of clinic A
    # could mint an admin membership in clinic B by passing its id.
    clinic_id = data.clinic_id if data.clinic_id else ctx.clinic_id
    if clinic_id != ctx.clinic_id:
        caller_is_admin = await db.execute(
            select(ClinicMembership.id).where(
                ClinicMembership.user_id == ctx.user_id,
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.role == "admin",
            )
        )
        if caller_is_admin.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not administer the target clinic",
            )

    # Check if email already exists
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
    )
    db.add(user)
    await db.flush()

    # Create clinic membership
    membership = ClinicMembership(
        user_id=user.id,
        clinic_id=clinic_id,
        role=data.role,
    )
    db.add(membership)
    await db.commit()

    return ApiResponse(data=UserResponse.model_validate(user))


@router.put("/users/{user_id}", response_model=ApiResponse[UserWithRoleResponse])
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.users.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[UserWithRoleResponse]:
    """Update a user in the current clinic (admin only)."""
    # Verify user belongs to this clinic
    result = await db.execute(
        select(ClinicMembership)
        .options(selectinload(ClinicMembership.user))
        .where(ClinicMembership.user_id == user_id)
        .where(ClinicMembership.clinic_id == ctx.clinic_id)
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this clinic",
        )

    user = membership.user

    # Prevent admin from deactivating themselves
    if data.is_active is False and user.id == ctx.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    # Validate role if provided
    if data.role is not None and data.role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role. Must be one of: {', '.join(ROLES)}",
        )

    # Check email uniqueness if changing email
    if data.email is not None and data.email != user.email:
        email_check = await db.execute(select(User).where(User.email == data.email))
        if email_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        user.email = data.email

    # Update user fields
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.is_active is not None:
        user.is_active = data.is_active
        # Increment token version to invalidate existing tokens when deactivating
        if not data.is_active:
            user.token_version += 1

    # Update role in membership
    if data.role is not None:
        membership.role = data.role

    await db.commit()
    await db.refresh(user)
    await db.refresh(membership)

    return ApiResponse(
        data=UserWithRoleResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            role=membership.role,
            created_at=user.created_at.isoformat(),
        )
    )


@router.get("/professionals", response_model=PaginatedApiResponse[ProfessionalResponse])
async def list_professionals(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaginatedApiResponse[ProfessionalResponse]:
    """List professionals (dentists and hygienists) in the current clinic."""
    # Fetch memberships with dentist/hygienist role and active users
    result = await db.execute(
        select(ClinicMembership)
        .options(selectinload(ClinicMembership.user))
        .where(
            ClinicMembership.clinic_id == ctx.clinic_id,
            ClinicMembership.role.in_(["dentist", "hygienist"]),
        )
    )
    memberships = result.scalars().all()

    professionals = [
        ProfessionalResponse(
            id=m.user.id,
            email=m.user.email,
            first_name=m.user.first_name,
            last_name=m.user.last_name,
            role=m.role,
        )
        for m in memberships
        if m.user.is_active
    ]

    return PaginatedApiResponse(
        data=professionals,
        total=len(professionals),
        page=1,
        page_size=len(professionals),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.users.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Remove a user from the current clinic (admin only).

    This removes the clinic membership but does not delete the user account.
    """
    # Prevent admin from removing themselves
    if user_id == ctx.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself from the clinic",
        )

    # Verify user belongs to this clinic
    result = await db.execute(
        select(ClinicMembership)
        .where(ClinicMembership.user_id == user_id)
        .where(ClinicMembership.clinic_id == ctx.clinic_id)
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this clinic",
        )

    await db.delete(membership)
    await db.commit()


# --- Clinic metadata (B.5: moved from clinical module) ------------------


@router.get("/clinics", response_model=PaginatedApiResponse[ClinicMetadataResponse])
async def list_user_clinics(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
) -> PaginatedApiResponse[ClinicMetadataResponse]:
    """List the caller's active clinic with full metadata + cabinets."""
    clinics = [ClinicMetadataResponse.model_validate(ctx.clinic)]
    return PaginatedApiResponse(
        data=clinics,
        total=len(clinics),
        page=1,
        page_size=len(clinics),
    )


@router.get("/clinics/{clinic_id}", response_model=ApiResponse[ClinicMetadataResponse])
async def get_clinic_metadata(
    clinic_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
) -> ApiResponse[ClinicMetadataResponse]:
    """Get clinic details."""
    if ctx.clinic_id != clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic",
        )
    return ApiResponse(data=ClinicMetadataResponse.model_validate(ctx.clinic))


@router.put("/clinics", response_model=ApiResponse[ClinicMetadataResponse])
async def update_clinic_metadata(
    data: ClinicMetadataUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ClinicMetadataResponse]:
    """Update clinic info (admin only)."""
    clinic = ctx.clinic

    if data.name is not None:
        clinic.name = data.name
    if data.tax_id is not None:
        clinic.tax_id = data.tax_id
    if data.legal_name is not None:
        clinic.legal_name = data.legal_name or None
    if data.phone is not None:
        clinic.phone = data.phone
    if data.email is not None:
        clinic.email = data.email
    if data.address is not None:
        existing_address = clinic.address or {}
        new_address = data.address.model_dump(exclude_unset=True)
        clinic.address = {**existing_address, **new_address}
    if data.timezone is not None:
        clinic.timezone = data.timezone
    if data.currency is not None:
        clinic.currency = data.currency

    await db.commit()
    # Re-query with cabinets eagerly loaded so ClinicMetadataResponse
    # serialization doesn't trigger an async lazy load. The response
    # always returns the full metadata shape including cabinets.
    result = await db.execute(
        select(Clinic).where(Clinic.id == clinic.id).options(selectinload(Clinic.cabinets))
    )
    clinic = result.scalar_one()

    return ApiResponse(data=ClinicMetadataResponse.model_validate(clinic))


# ---------------------------------------------------------------------------
# Per-clinic settings (JSONB ``clinic.settings``).
#
# Module-specific settings live under namespaced keys so each module
# can read its own subset without colliding. The settings PATCH
# endpoint lives in core because ``Clinic`` is a core entity, but the
# accepted keys are validated against per-module schemas.
# ---------------------------------------------------------------------------


from pydantic import BaseModel, Field  # noqa: E402


class _BudgetSettingsPatch(BaseModel):
    """Subset of clinic.settings keys owned by the budget module."""

    budget_expiry_days: int | None = Field(default=None, ge=7, le=180)
    plan_auto_close_days_after_expiry: int | None = Field(default=None, ge=7, le=180)
    budget_reminders_enabled: bool | None = None
    budget_public_auth_disabled: bool | None = None


class _BudgetSettingsResponse(BaseModel):
    budget_expiry_days: int = 30
    plan_auto_close_days_after_expiry: int = 30
    budget_reminders_enabled: bool = False
    budget_public_auth_disabled: bool = False


def _read_budget_settings(raw: dict | None) -> _BudgetSettingsResponse:
    raw = raw or {}
    return _BudgetSettingsResponse(
        budget_expiry_days=int(raw.get("budget_expiry_days", 30)),
        plan_auto_close_days_after_expiry=int(raw.get("plan_auto_close_days_after_expiry", 30)),
        budget_reminders_enabled=bool(raw.get("budget_reminders_enabled", False)),
        budget_public_auth_disabled=bool(raw.get("budget_public_auth_disabled", False)),
    )


@router.get(
    "/clinic/settings/budget",
    response_model=ApiResponse[_BudgetSettingsResponse],
)
async def get_budget_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.read"))],
) -> ApiResponse[_BudgetSettingsResponse]:
    """Read the budget-related toggles from the clinic settings."""
    return ApiResponse(data=_read_budget_settings(ctx.clinic.settings))


@router.patch(
    "/clinic/settings/budget",
    response_model=ApiResponse[_BudgetSettingsResponse],
)
async def update_budget_settings(
    data: _BudgetSettingsPatch,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[_BudgetSettingsResponse]:
    """Update budget-related clinic settings (admin only)."""
    clinic = ctx.clinic
    current = dict(clinic.settings or {})
    payload = data.model_dump(exclude_unset=True)
    current.update(payload)
    clinic.settings = current
    await db.commit()
    await db.refresh(clinic)
    return ApiResponse(data=_read_budget_settings(clinic.settings))


# ---------------------------------------------------------------------------
# Communications settings (clinic-wide). Drives the language used for
# patient-facing pages (public budget link), email templates, and
# future SMS / WhatsApp messages.
# ---------------------------------------------------------------------------


class _CommunicationsSettingsPatch(BaseModel):
    language: str | None = Field(default=None, pattern="^(es|en|fr)$")


class _CommunicationsSettingsResponse(BaseModel):
    language: str = "es"


def _read_communications_settings(raw: dict | None) -> _CommunicationsSettingsResponse:
    raw = raw or {}
    return _CommunicationsSettingsResponse(
        language=str(raw.get("communication_language", "es")),
    )


@router.get(
    "/clinic/settings/communications",
    response_model=ApiResponse[_CommunicationsSettingsResponse],
)
async def get_communications_settings(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.read"))],
) -> ApiResponse[_CommunicationsSettingsResponse]:
    """Read the clinic-wide communications language."""
    return ApiResponse(data=_read_communications_settings(ctx.clinic.settings))


@router.patch(
    "/clinic/settings/communications",
    response_model=ApiResponse[_CommunicationsSettingsResponse],
)
async def update_communications_settings(
    data: _CommunicationsSettingsPatch,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[_CommunicationsSettingsResponse]:
    """Update the clinic-wide communications language.

    Persists under ``clinic.settings.communication_language``.
    """
    clinic = ctx.clinic
    current = dict(clinic.settings or {})
    if data.language is not None:
        current["communication_language"] = data.language
    clinic.settings = current
    await db.commit()
    await db.refresh(clinic)
    return ApiResponse(data=_read_communications_settings(clinic.settings))
