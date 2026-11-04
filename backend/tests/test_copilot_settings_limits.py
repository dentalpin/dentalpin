"""The monthly limits: an admin can remove one, and a negative one is refused.

A negative token limit is worse than a typo: ``used < limit`` is then never
true, so the copilot stops for the whole clinic.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.modules.copilot.schemas import SettingsUpdate
from app.modules.copilot.service import ClinicBudgetGuard, CopilotSettingsService


async def _update(db, clinic, **body):
    data = SettingsUpdate(**body).model_dump(exclude_unset=True)
    return await CopilotSettingsService.update(db, clinic.id, data)


@pytest.mark.asyncio
async def test_null_removes_a_limit_and_unsent_keeps_it(db_session, test_clinic):
    row = await _update(
        db_session, test_clinic, monthly_token_limit=1000, monthly_cost_limit_cents=500
    )
    assert (row.monthly_token_limit, row.monthly_cost_limit_cents) == (1000, 500)

    row = await _update(db_session, test_clinic, digest_hour=8)
    assert (row.monthly_token_limit, row.monthly_cost_limit_cents) == (1000, 500)

    row = await _update(
        db_session, test_clinic, monthly_token_limit=None, monthly_cost_limit_cents=None
    )
    assert (row.monthly_token_limit, row.monthly_cost_limit_cents) == (None, None)
    assert ClinicBudgetGuard(row, SimpleNamespace()).check() is True


@pytest.mark.parametrize("field", ["monthly_token_limit", "monthly_cost_limit_cents"])
def test_negative_limit_is_refused(field):
    with pytest.raises(ValidationError):
        SettingsUpdate(**{field: -1})


def test_zero_limit_is_accepted():
    """Zero stops the copilot without removing the limit, as it does today."""
    assert SettingsUpdate(monthly_token_limit=0).monthly_token_limit == 0
