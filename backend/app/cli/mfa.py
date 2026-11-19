"""Rotate keys and recover staff TOTP accounts from the backend CLI."""

from argparse import ArgumentParser, Namespace
from uuid import UUID

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import mfa
from app.core.auth.models import ClinicMembership, User, UserMfaTotp
from app.core.plugins.loader import register_discovered
from app.database import async_session_maker


async def rotate_keys(_args) -> int:
    register_discovered()
    try:
        keyring = mfa.cipher()
        async with async_session_maker.begin() as db:
            credentials = await db.scalars(
                select(UserMfaTotp).with_for_update().execution_options(populate_existing=True)
            )
            count = 0
            for credential in credentials:
                credential.secret_encrypted = keyring.rotate(
                    credential.secret_encrypted.encode()
                ).decode()
                count += 1
    except (InvalidToken, HTTPException):
        print("MFA key rotation failed. Check the configured keys. No changes were committed.")
        return 1
    print(f"Rotated {count} MFA credentials.")
    return 0


async def _targets(db: AsyncSession, email: str, clinic_id: UUID | None) -> list[UUID]:
    query = select(User.id).where(func.lower(User.email) == email)
    if clinic_id is not None:
        membership = select(ClinicMembership.user_id).where(
            ClinicMembership.user_id == User.id,
            ClinicMembership.clinic_id == clinic_id,
        )
        query = query.where(membership.exists())
    return list(await db.scalars(query.limit(2)))


async def reset(args: Namespace) -> int:
    register_discovered()
    email = args.email.strip().lower()
    async with async_session_maker() as db:
        targets = await _targets(db, email, args.clinic)
    if not targets:
        print("No user matches the email and clinic.")
        return 1
    if len(targets) != 1:
        print("More than one user matches. Specify --clinic with the clinic UUID.")
        return 1

    if not args.yes:
        try:
            answer = input(f"Reset MFA and revoke all sessions for {email}? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() not in {"y", "yes"}:
            print("MFA reset cancelled.")
            return 1

    async with async_session_maker.begin() as db:
        user = await mfa.lock_user(db, targets[0])
        if user is None or await _targets(db, email, args.clinic) != targets:
            print("The matching account changed. Run the command again.")
            return 1
        if await db.get(UserMfaTotp, user.id) is None:
            print("The user has no enrolled MFA factor.")
            return 1
        requires_mfa = mfa.policy_requires_mfa(await mfa.membership_policies(db, user.id))
        await mfa.clear_enrollment(
            db,
            user,
            actor_id=None,
            reset_clinic=args.clinic,
            require_reenrollment=requires_mfa,
        )

    print("MFA reset. All sessions were revoked.")
    if requires_mfa:
        print("MFA enrollment is required at the next sign-in.")
    return 0


def register(subparsers) -> None:
    parser: ArgumentParser = subparsers.add_parser("mfa", help="Manage staff MFA encryption")
    actions = parser.add_subparsers(dest="mfa_command", required=True)
    rotate = actions.add_parser("rotate-keys", help="Re-encrypt TOTP secrets with the primary key")
    rotate.set_defaults(func=rotate_keys)

    recovery = actions.add_parser("reset", help="Reset a staff member's TOTP and revoke sessions")
    recovery.add_argument("--email", required=True, help="Staff account email address")
    recovery.add_argument(
        "--clinic", type=UUID, help="Clinic UUID used to constrain account lookup"
    )
    recovery.add_argument("--yes", action="store_true", help="Confirm the reset noninteractively")
    recovery.set_defaults(func=reset)
