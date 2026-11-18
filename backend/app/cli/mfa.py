"""Rotate staff TOTP credentials without exposing their plaintext."""

from argparse import ArgumentParser

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import select

from app.core.auth.mfa import cipher
from app.core.auth.models import UserMfaTotp
from app.core.plugins.loader import register_discovered
from app.database import async_session_maker


async def rotate_keys(_args) -> int:
    register_discovered()
    try:
        keyring = cipher()
        async with async_session_maker.begin() as db:
            credentials = await db.scalars(select(UserMfaTotp).with_for_update())
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


def register(subparsers) -> None:
    parser: ArgumentParser = subparsers.add_parser("mfa", help="Manage staff MFA encryption")
    actions = parser.add_subparsers(dest="mfa_command", required=True)
    rotate = actions.add_parser("rotate-keys", help="Re-encrypt TOTP secrets with the primary key")
    rotate.set_defaults(func=rotate_keys)
