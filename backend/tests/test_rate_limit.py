"""Rate-limit posture pins (#530).

The limiter is on everywhere except the pytest suite; ENVIRONMENT is a
closed enum so a typo cannot silently degrade to development behavior.
"""

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.config import Settings


def test_environment_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError, match="ENVIRONMENT"):
        Settings(ENVIRONMENT="staging-typo")


@pytest.mark.parametrize("value", ["development", "test", "production"])
def test_environment_accepts_known_values(value: str) -> None:
    # Explicit long secrets: ambient CI secrets are short, and the
    # production SECRET_KEY / public-key floors must not mask the enum
    # check.
    settings = Settings(
        ENVIRONMENT=value,
        SECRET_KEY="x" * 32,
        BUDGET_PUBLIC_SECRET_KEY="x" * 32,
        AGENDA_PUBLIC_SECRET_KEY="x" * 32,
    )
    assert settings.ENVIRONMENT == value


@pytest.mark.asyncio
async def test_login_is_rate_limited_when_limiter_enabled(client: AsyncClient) -> None:
    """Six rapid logins: the sixth answers 429 while the limiter is on."""
    from app.core.auth.router import limiter

    limiter.enabled = True
    try:
        statuses = []
        for _ in range(6):
            response = await client.post(
                "/api/v1/auth/login",
                data={"username": "nobody@example.com", "password": "wrongpass1234"},
            )
            statuses.append(response.status_code)
        assert statuses[:5] == [401] * 5, statuses
        assert statuses[5] == 429, statuses
    finally:
        limiter.enabled = False
