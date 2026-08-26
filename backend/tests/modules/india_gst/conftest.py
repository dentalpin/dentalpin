"""Shared fixtures for india_gst tests."""

from __future__ import annotations

from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.modules.billing.models import InvoiceSeries
from app.modules.india_gst.models import IndiaGstSettings


@pytest_asyncio.fixture
async def india_gst_clinic(db_session: AsyncSession, test_clinic: Clinic) -> Clinic:
    """``test_clinic`` flipped to ``country=IN`` so the india_gst hook
    picks it up via ``BillingHookRegistry.get_for_clinic``, with default
    invoice/credit-note series so ``POST .../issue`` and ``.../credit-note``
    work through the real API (``test_clinic`` bypasses the
    ``clinic.created`` seed handler that normally provisions these).
    """
    test_clinic.settings = {**(test_clinic.settings or {}), "country": "IN"}
    db_session.add(test_clinic)
    db_session.add_all(
        [
            InvoiceSeries(
                id=uuid4(),
                clinic_id=test_clinic.id,
                prefix="GST",
                series_type="invoice",
                is_default=True,
            ),
            InvoiceSeries(
                id=uuid4(),
                clinic_id=test_clinic.id,
                prefix="CN",
                series_type="credit_note",
                is_default=True,
            ),
        ]
    )
    await db_session.commit()
    await db_session.refresh(test_clinic)
    return test_clinic


@pytest_asyncio.fixture
async def india_gst_settings(
    db_session: AsyncSession, india_gst_clinic: Clinic
) -> IndiaGstSettings:
    """A ``regular``-registrant clinic based in Tamil Nadu (state code 33)."""
    settings = IndiaGstSettings(
        clinic_id=india_gst_clinic.id,
        trade_name="SmileCare Dental Clinic",
        gstin="33ABCDE1234F1Z7",
        registration_type="regular",
        clinic_state="33",
    )
    db_session.add(settings)
    await db_session.commit()
    await db_session.refresh(settings)
    return settings
