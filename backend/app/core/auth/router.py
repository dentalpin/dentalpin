"""Authentication router with rate limiting."""

import secrets
from datetime import UTC, datetime
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
from app.core.events import EventType, event_bus
from app.core.plugins import module_registry
from app.core.schemas import ApiResponse, PaginatedApiResponse
from app.database import get_db

from .country_presets import COUNTRY_PRESETS, GENERIC, get_preset, tax_id_matches
from .dependencies import (
    ClinicContext,
    block_in_demo,
    get_clinic_context,
    get_current_user,
    require_permission,
)
from .models import Clinic, ClinicMembership, User
from .permissions import (
    CORE_PERMISSIONS,
    PROFESSIONAL_ROLES,
    ROLES,
    expand_permissions,
    get_role_permissions,
)
from .schemas import (
    AuthResponse,
    ClinicMetadataResponse,
    ClinicMetadataUpdate,
    ClinicResponse,
    InviteLinkResponse,
    MeResponse,
    ProfessionalResponse,
    SetPasswordRequest,
    SetupPresetsResponse,
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
    create_invite_token,
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


@router.get("/setup/presets", response_model=ApiResponse[SetupPresetsResponse])
async def setup_presets() -> ApiResponse[SetupPresetsResponse]:
    """Country presets for the first-run wizard (public — the wizard runs pre-auth)."""
    return ApiResponse(
        data=SetupPresetsResponse(
            countries=[p.to_dict() for p in COUNTRY_PRESETS.values()],
            fallback=GENERIC.to_dict(),
        )
    )


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

    preset = get_preset(data.country)
    if data.country and not tax_id_matches(preset, data.clinic_tax_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid tax id format for {data.country} ({preset.tax_id_label})",
        )

    # No country → keep the historical defaults; an unknown country → GENERIC
    # (currency/timezone come from the client, which lets the user pick them).
    timezone = data.timezone or (preset.timezone if data.country else "Europe/Madrid")
    currency = data.currency or (preset.currency if data.country else "EUR")
    language = data.language or preset.language
    clinic_settings: dict = {"communication_language": language}
    if data.country:
        clinic_settings["country"] = data.country

    address = {
        key: value
        for key, value in {
            "country": data.country,
            "street": data.clinic_street,
            "city": data.clinic_city,
            "postal_code": data.clinic_postal_code,
        }.items()
        if value
    }
    clinic = Clinic(
        name=data.clinic_name,
        tax_id=data.clinic_tax_id,
        timezone=timezone,
        currency=currency,
        address=address,
        settings=clinic_settings,
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

    db.add(
        ClinicMembership(
            user_id=user.id,
            clinic_id=clinic.id,
            role="admin",
            is_professional=data.admin_is_professional,
        )
    )
    await db.commit()

    # Modules seed their defaults (catalog + VAT preset, invoice series,
    # cabinet, weekly hours) in their own sessions. Awaited so the clinic is
    # ready on first login; handler failures are logged, never raised.
    await event_bus.publish(
        EventType.CLINIC_CREATED,
        {
            "clinic_id": str(clinic.id),
            "country": data.country,
            "currency": currency,
            "timezone": timezone,
            "language": language,
            "vat_preset": preset.vat_preset,
            "created_by": str(user.id),
            "source": "setup",
        },
    )

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
            is_professional=m.is_professional,
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

    # Validate password strength (when given). Without a password the
    # account gets an unusable random hash until an invite link is consumed.
    if data.password is not None:
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
        password_hash=hash_password(data.password or secrets.token_urlsafe(32)),
        first_name=data.first_name,
        last_name=data.last_name,
    )
    db.add(user)
    await db.flush()

    # Create clinic membership. Professional-ness defaults from the
    # role but is an independent axis — an admin can also practise.
    membership = ClinicMembership(
        user_id=user.id,
        clinic_id=clinic_id,
        role=data.role,
        is_professional=(
            data.is_professional
            if data.is_professional is not None
            else data.role in PROFESSIONAL_ROLES
        ),
    )
    db.add(membership)
    await db.commit()

    return ApiResponse(data=UserResponse.model_validate(user))


@router.post("/users/{user_id}/invite-link", response_model=ApiResponse[InviteLinkResponse])
async def create_user_invite_link(
    user_id: UUID,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.users.write"))],
    __: Annotated[None, Depends(block_in_demo)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[InviteLinkResponse]:
    """Mint a one-time set-password token for a member of this clinic.

    Works for brand-new accounts (created without a password) and as an
    admin-driven password reset for existing ones. The link is a bearer
    secret: the client shows it once for the admin to copy / share.
    """
    result = await db.execute(
        select(User)
        .join(ClinicMembership, ClinicMembership.user_id == User.id)
        .where(User.id == user_id, ClinicMembership.clinic_id == ctx.clinic_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is inactive")

    token, expires_at = create_invite_token(user.id, token_version=user.token_version)
    return ApiResponse(data=InviteLinkResponse(token=token, expires_at=expires_at))


@router.post("/set-password", response_model=TokenResponse)
@limiter.limit("10/hour")
async def set_password_from_invite(
    request: Request,
    data: SetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Consume an invite token: set the password and log the user in.

    Single use — bumping ``token_version`` invalidates the token (and any
    older session). Public endpoint, rate limited.
    """
    try:
        payload = decode_token(data.token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired link"
        ) from None
    if payload.get("type") != "invite" or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid link")

    result = await db.execute(
        select(User).options(selectinload(User.memberships)).where(User.id == UUID(payload["sub"]))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or payload.get("token_version", 0) != user.token_version:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or used link")

    is_valid, error_msg = validate_password_strength(data.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)

    user.password_hash = hash_password(data.password)
    user.token_version += 1
    await db.commit()

    clinic_id = user.memberships[0].clinic_id if user.memberships else None
    return TokenResponse(
        access_token=create_access_token(
            user.id, clinic_id=clinic_id, token_version=user.token_version
        ),
        refresh_token=create_refresh_token(user.id, token_version=user.token_version),
    )


@router.put("/users/{user_id}", response_model=ApiResponse[UserWithRoleResponse])
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.users.write"))],
    __: Annotated[None, Depends(block_in_demo)],
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

    # Explicit flag wins; a role-only change re-derives it so switching
    # someone to dentist keeps them schedulable without a second click.
    if data.is_professional is not None:
        membership.is_professional = data.is_professional
    elif data.role is not None:
        membership.is_professional = data.role in PROFESSIONAL_ROLES

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
            is_professional=membership.is_professional,
            created_at=user.created_at.isoformat(),
        )
    )


@router.get("/professionals", response_model=PaginatedApiResponse[ProfessionalResponse])
async def list_professionals(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("agenda.appointments.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaginatedApiResponse[ProfessionalResponse]:
    """List professionals (members with ``is_professional``) in the current clinic."""
    # Professional-ness is a membership flag, not a role — an admin who
    # also practises shows up here too (defaults to true for
    # dentist/hygienist).
    result = await db.execute(
        select(ClinicMembership)
        .options(selectinload(ClinicMembership.user))
        .where(
            ClinicMembership.clinic_id == ctx.clinic_id,
            ClinicMembership.is_professional.is_(True),
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
    __: Annotated[None, Depends(block_in_demo)],
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
        # ``settings.country`` (ISO2) is what billing hooks / verifactu read;
        # keep it in sync with the address country when it is a valid code.
        country = (new_address.get("country") or "").upper()
        if len(country) == 2 and country.isalpha():
            clinic.settings = {**(clinic.settings or {}), "country": country}
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
    language: str | None = Field(default=None, pattern="^(es|en|fr|pt|ta)$")


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


# ---------------------------------------------------------------------------
# Onboarding state (clinic-wide). Step completion is *derived* client-side
# from real data (getting-started rules); only skip / dismiss / completion
# markers are stored, under ``clinic.settings.onboarding``.
# ---------------------------------------------------------------------------


class _OnboardingPatch(BaseModel):
    dismissed: bool | None = None
    completed: bool | None = None
    skip: list[str] | None = Field(default=None, max_length=50)
    unskip: list[str] | None = Field(default=None, max_length=50)
    reset: bool = False


class _OnboardingState(BaseModel):
    dismissed_at: datetime | None = None
    completed_at: datetime | None = None
    skipped: dict[str, datetime] = Field(default_factory=dict)


def _read_onboarding(raw: dict | None) -> _OnboardingState:
    return _OnboardingState.model_validate((raw or {}).get("onboarding") or {})


@router.patch("/clinic/settings/onboarding", response_model=ApiResponse[_OnboardingState])
async def update_onboarding_state(
    data: _OnboardingPatch,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[_OnboardingState]:
    """Merge skip / dismiss / completion markers into ``settings.onboarding``."""
    clinic = ctx.clinic
    current = dict(clinic.settings or {})
    state = {} if data.reset else dict(current.get("onboarding") or {})
    now = datetime.now(UTC).isoformat()
    if data.dismissed is not None:
        state["dismissed_at"] = now if data.dismissed else None
    if data.completed is not None:
        state["completed_at"] = now if data.completed else None
    skipped = dict(state.get("skipped") or {})
    for rule_id in data.skip or []:
        skipped[rule_id] = now
    for rule_id in data.unskip or []:
        skipped.pop(rule_id, None)
    state["skipped"] = skipped
    current["onboarding"] = state
    clinic.settings = current
    await db.commit()
    await db.refresh(clinic)
    return ApiResponse(data=_read_onboarding(clinic.settings))
