"""Per-conversation redaction salt persistence (#586)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic, User
from app.modules.copilot.bridge import _ensure_redaction_salt
from app.modules.copilot.models import CopilotConversation


@pytest.mark.asyncio
async def test_ensure_redaction_salt_generates_once(
    db_session: AsyncSession, test_clinic: Clinic
) -> None:
    """First build mints a salt and persists it; later builds reuse it,
    so tokens stay stable across turns."""
    user = (
        await db_session.execute(select(User).where(User.email == "test@example.com"))
    ).scalar_one()
    conv = CopilotConversation(clinic_id=test_clinic.id, user_id=user.id, model="test")
    db_session.add(conv)
    first = await _ensure_redaction_salt(db_session, conv)
    assert first and len(first) == 32
    second = await _ensure_redaction_salt(db_session, conv)
    assert second == first
