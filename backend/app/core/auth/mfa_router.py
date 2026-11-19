"""Routes for staff TOTP enrollment, login verification and recovery."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import ApiResponse
from app.database import get_db

from . import mfa
from .dependencies import (
    ClinicContext,
    block_in_demo,
    get_clinic_context,
    get_current_user,
    require_permission,
)
from .mfa import MfaChallengeResponse, MfaDisable, MfaPassword, MfaPolicy, MfaProof, MfaStatus
from .models import Clinic, ClinicMembership, User, UserMfaTotp
from .router import _role_is_valid_for_clinic, limiter
from .schemas import TokenResponse
from .service import verify_password
from .sessions import start_session

router = APIRouter(prefix="/auth", tags=["auth"])
Db = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Context = Annotated[ClinicContext, Depends(get_clinic_context)]


class MfaSessionResponse(TokenResponse):
    recovery_codes: list[str] | None = None


async def _locked_current_user(db: AsyncSession, current: User) -> User:
    version = current.token_version
    user = await mfa.lock_user(db, current.id)
    if user is None or not user.is_active or user.token_version != version:
        raise HTTPException(401, "mfa_expired")
    return user


async def _session(
    request: Request,
    response: Response,
    db: AsyncSession,
    user: User,
    recovery_codes: list[str] | None = None,
) -> MfaSessionResponse:
    mfa.no_store(response)
    clinic_id = user.memberships[0].clinic_id if user.memberships else None
    tokens = await start_session(request, response, db, user, clinic_id)
    return MfaSessionResponse(**tokens.model_dump(), recovery_codes=recovery_codes)


@router.get("/mfa/status", response_model=ApiResponse[MfaStatus])
async def status(response: Response, user: CurrentUser, db: Db) -> ApiResponse[MfaStatus]:
    mfa.no_store(response)
    return ApiResponse(data=await mfa.mfa_status(db, user))


@router.post("/mfa/totp/enroll", response_model=MfaChallengeResponse)
@limiter.limit("5/minute")
async def begin_enrollment(
    request: Request,
    response: Response,
    data: MfaPassword,
    current: CurrentUser,
    db: Db,
    _: Annotated[None, Depends(block_in_demo)],
) -> MfaChallengeResponse:
    user = await _locked_current_user(db, current)
    state = await mfa.mfa_status(db, user)
    if state.enabled:
        raise HTTPException(409, "mfa_already_enabled")
    if not state.allowed:
        raise HTTPException(403, "mfa_policy_off")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "mfa_invalid_password")
    challenge = await mfa.new_challenge(db, user, "self")
    await db.commit()
    mfa.no_store(response)
    return challenge


@router.post("/mfa/totp/confirm", response_model=MfaSessionResponse)
@limiter.limit("10/minute")
async def confirm_enrollment(
    request: Request,
    response: Response,
    data: MfaProof,
    current: CurrentUser,
    db: Db,
    _: Annotated[None, Depends(block_in_demo)],
) -> MfaSessionResponse:
    user, challenge = await mfa.locked_challenge(
        db, data.mfa_token, ("self",), expected_user=current
    )
    if not (await mfa.mfa_status(db, user)).allowed:
        raise HTTPException(403, "mfa_policy_off")
    codes = await mfa.enroll(db, user, challenge, data.code)
    return await _session(request, response, db, user, codes)


@router.post("/mfa/verify", response_model=MfaSessionResponse)
@limiter.limit("10/minute")
async def complete_login(
    request: Request, response: Response, data: MfaProof, db: Db
) -> MfaSessionResponse:
    user, challenge = await mfa.locked_challenge(db, data.mfa_token, ("verify", "required"))
    if challenge.purpose == "required":
        codes = await mfa.enroll(db, user, challenge, data.code)
        return await _session(request, response, db, user, codes)
    credential = await db.get(UserMfaTotp, user.id)
    if credential is None:
        raise HTTPException(401, "mfa_expired")
    await mfa.verify_code(db, user, credential, data.code)
    await db.delete(challenge)
    return await _session(request, response, db, user)


@router.post("/mfa/disable", response_model=MfaSessionResponse)
@limiter.limit("5/minute")
async def disable(
    request: Request,
    response: Response,
    data: MfaDisable,
    current: CurrentUser,
    db: Db,
    _: Annotated[None, Depends(block_in_demo)],
) -> MfaSessionResponse:
    user = await _locked_current_user(db, current)
    if (await mfa.mfa_status(db, user)).required:
        raise HTTPException(409, "mfa_required_by_policy")
    credential = await db.get(UserMfaTotp, user.id)
    if credential is None:
        raise HTTPException(409, "mfa_not_enabled")
    mfa.check_lockout(user)
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "mfa_invalid_password")
    await mfa.verify_code(db, user, credential, data.code)
    await mfa.clear_enrollment(db, user, actor_id=user.id)
    return await _session(request, response, db, user)


@router.delete("/mfa/users/{user_id}", status_code=204)
async def reset(
    user_id: UUID,
    ctx: Context,
    db: Db,
    _: Annotated[None, Depends(require_permission("admin.users.write"))],
    __: Annotated[None, Depends(block_in_demo)],
) -> None:
    if ctx.role != "admin" or user_id == ctx.user_id:
        raise HTTPException(403, "mfa_reset_forbidden")
    member = await db.scalar(
        select(ClinicMembership.id).where(
            ClinicMembership.user_id == user_id, ClinicMembership.clinic_id == ctx.clinic_id
        )
    )
    if member is None:
        raise HTTPException(404, "mfa_user_not_found")
    target = await mfa.lock_user(db, user_id)
    if target is None:
        raise HTTPException(404, "mfa_user_not_found")
    target_clinics = {m.clinic_id for m in target.memberships}
    admin_clinics = set(
        await db.scalars(
            select(ClinicMembership.clinic_id).where(
                ClinicMembership.user_id == ctx.user_id,
                ClinicMembership.role == "admin",
                ClinicMembership.clinic_id.in_(target_clinics),
            )
        )
    )
    if ctx.clinic_id not in target_clinics or target_clinics - admin_clinics:
        raise HTTPException(403, "mfa_reset_forbidden")
    if await db.get(UserMfaTotp, target.id) is None:
        raise HTTPException(409, "mfa_not_enabled")
    await mfa.clear_enrollment(db, target, actor_id=ctx.user_id, reset_clinic=ctx.clinic_id)
    await db.commit()


@router.get("/clinic/settings/mfa", response_model=ApiResponse[MfaPolicy])
async def get_policy(
    ctx: Context, _: Annotated[None, Depends(require_permission("admin.clinic.read"))]
) -> ApiResponse[MfaPolicy]:
    return ApiResponse(data=MfaPolicy.model_validate(ctx.clinic.mfa_policy))


@router.put("/clinic/settings/mfa", response_model=ApiResponse[MfaPolicy])
async def update_policy(
    data: MfaPolicy,
    ctx: Context,
    db: Db,
    _: Annotated[None, Depends(require_permission("admin.clinic.write"))],
    __: Annotated[None, Depends(block_in_demo)],
) -> ApiResponse[MfaPolicy]:
    if ctx.role != "admin":
        raise HTTPException(403, "mfa_policy_forbidden")
    if data.mode != "off":
        mfa.cipher()
    for role in data.roles:
        if not await _role_is_valid_for_clinic(db, ctx.clinic_id, role):
            raise HTTPException(422, "mfa_invalid_role")
    clinic = await db.get(Clinic, ctx.clinic_id)
    if clinic is None:
        raise HTTPException(404, "mfa_clinic_not_found")
    clinic.mfa_policy = data.model_dump()
    await db.commit()
    return ApiResponse(data=data)
