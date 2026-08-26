"""India GST seed data: clinic settings and seed_india_gst function."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import TreatmentCatalogItem, VatType
from app.modules.india_gst.models import IndiaGstCatalogItem, IndiaGstSettings
from app.seeds.demo_data import get_clinic_data, set_country, set_language


def test_clinic_settings_include_country_in_for_tamil():
    """When LANG=ta, the clinic settings must include country=IN so
    the IndiaGstHook activates."""
    set_language("ta")
    try:
        data = get_clinic_data()
        assert data["settings"].get("country") == "IN"
    finally:
        set_language("en")


def test_clinic_settings_exclude_country_for_non_tamil():
    """When LANG is not ta and COUNTRY is the default "generic", the
    clinic settings must NOT include country=IN — the India GST hook
    should not activate."""
    for lang in ("en", "es", "fr"):
        set_language(lang)
        try:
            data = get_clinic_data()
            assert "country" not in data["settings"]
        finally:
            set_language("en")


def test_clinic_settings_include_country_in_for_english_india_variant():
    """--lang en --country in must also activate the IndiaGstHook, with
    the India physical details overlaid in English (not Tamil script)."""
    set_language("en")
    set_country("in")
    try:
        data = get_clinic_data()
        assert data["settings"].get("country") == "IN"
        assert data["address"]["city"] == "Chennai"
        assert data["address"]["country"] == "India"
        assert data["currency"] == "INR"
        assert data["timezone"] == "Asia/Kolkata"
    finally:
        set_country("generic")
        set_language("en")


def test_clinic_settings_country_in_ignored_for_unsupported_languages():
    """--country in is only wired for en/ta in seed_demo.py's main() guard,
    but get_clinic_data() itself must stay well-defined for es/fr too —
    India GST activates, using the English-literal overlay (no es/fr
    translation exists yet, so it must not silently fall back to Tamil)."""
    set_language("es")
    set_country("in")
    try:
        data = get_clinic_data()
        assert data["settings"].get("country") == "IN"
        assert data["address"]["city"] == "Chennai"
    finally:
        set_country("generic")
        set_language("en")


async def test_seed_india_gst_creates_settings_vat_type_and_sac_defaults(
    db_session: AsyncSession,
    india_gst_clinic,
):
    """seed_india_gst must create IndiaGstSettings, GST 18% VAT type,
    SAC defaults on all catalog items, and reassign items to 18%."""
    from app.modules.catalog.seed import seed_catalog

    # Seed the catalog first so there are items to configure.
    await seed_catalog(db_session, india_gst_clinic.id)

    # Verify no GST 18% VAT type exists yet.
    count_q = await db_session.execute(
        select(VatType).where(
            VatType.clinic_id == india_gst_clinic.id,
            VatType.names.op("->>")("en") == "GST 18%",
        )
    )
    assert count_q.scalar_one_or_none() is None

    # Run seed_india_gst.
    # seed_india_gst uses the module-level CLINIC_ID, so we need to
    # patch it to our test clinic.
    import scripts.seed_demo as seed_mod
    from scripts.seed_demo import seed_india_gst

    original_clinic_id = seed_mod.CLINIC_ID
    seed_mod.CLINIC_ID = india_gst_clinic.id
    try:
        stats = await seed_india_gst(db_session)
    finally:
        seed_mod.CLINIC_ID = original_clinic_id

    assert stats["settings_created"] is True
    assert stats["sac_configured"] > 0
    assert stats["items_reassigned"] > 0

    # Verify IndiaGstSettings.
    settings_q = await db_session.execute(
        select(IndiaGstSettings).where(IndiaGstSettings.clinic_id == india_gst_clinic.id)
    )
    settings = settings_q.scalar_one()
    assert settings.gstin == "33ABCDE1234F1Z7"
    assert settings.clinic_state == "33"
    assert settings.registration_type == "regular"

    # Verify GST 18% VAT type exists.
    vat_q = await db_session.execute(
        select(VatType).where(
            VatType.clinic_id == india_gst_clinic.id,
            VatType.names.op("->>")("en") == "GST 18%",
        )
    )
    gst_vat = vat_q.scalar_one()
    assert float(gst_vat.rate) == 18.0

    # Verify all active catalog items are assigned to GST 18%.
    items_q = await db_session.execute(
        select(TreatmentCatalogItem).where(
            TreatmentCatalogItem.clinic_id == india_gst_clinic.id,
            TreatmentCatalogItem.is_active.is_(True),
            TreatmentCatalogItem.deleted_at.is_(None),
        )
    )
    for item in items_q.scalars():
        assert item.vat_type_id == gst_vat.id

    # Verify SAC defaults exist for all active catalog items.
    sac_q = await db_session.execute(
        select(IndiaGstCatalogItem).where(IndiaGstCatalogItem.clinic_id == india_gst_clinic.id)
    )
    sac_rows = sac_q.scalars().all()
    assert len(sac_rows) > 0
    for row in sac_rows:
        assert row.sac_code == "999312"
