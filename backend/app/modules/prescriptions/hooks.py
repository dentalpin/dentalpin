"""Country compliance hooks for prescriptions (issue #269).

Mirrors ``billing/hooks.py``: the base module owns the ABC + registry
and never imports country modules. A localization module (e.g.
``prescriptions_mx``) implements ``PrescriptionComplianceHook`` and
registers it in ``on_activate()`` (re-attached every boot — #91).
The clinic's ``settings["country"]`` selects the hook.
"""

from __future__ import annotations

from abc import ABC
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class PrescriptionComplianceHook(ABC):
    """Interface for country-specific prescription compliance modules."""

    @property
    def country_code(self) -> str:
        """ISO country code (MX, ES, ...). Registry key."""
        raise NotImplementedError

    def get_required_fields(self) -> list[str]:
        """Prescriber/profile fields the country mandates (e.g. MX makes
        ``license_number`` mandatory). Empty by default."""
        return []

    def label_overrides(self) -> dict[str, str]:
        """UI label overrides, e.g. license field caption
        ("Cédula Profesional" MX, "Nº de colegiado" ES)."""
        return {}

    async def validate_before_issue(
        self, prescription: Any, db: AsyncSession
    ) -> tuple[bool, str | None]:
        """Country gate before issuing (e.g. antibiotic rules).
        Returns (is_valid, error_message). Default: no validation."""
        return True, None

    async def on_prescription_issued(self, prescription: Any, db: AsyncSession) -> dict[str, Any]:
        """Hook called after issuing. Return value is stored under
        ``compliance_data[country_code]``. Default: nothing."""
        return {}

    def enhance_pdf_data(self, pdf_data: dict[str, Any], prescription: Any) -> dict[str, Any]:
        """Add structured rows only (``compliance_section``,
        ``legal_notices``, ``label_overrides``, optional QR data).
        Hooks never return HTML — the base renderer escapes (PR #210
        rule)."""
        return pdf_data


class PrescriptionHookRegistry:
    """Registry for country hooks. Country modules register here."""

    _hooks: dict[str, PrescriptionComplianceHook] = {}

    @classmethod
    def register(cls, hook: PrescriptionComplianceHook) -> None:
        cls._hooks[hook.country_code.upper()] = hook

    @classmethod
    def for_country(cls, country_code: str | None) -> PrescriptionComplianceHook | None:
        if not country_code:
            return None
        return cls._hooks.get(country_code.upper())

    @classmethod
    def for_clinic_settings(
        cls, settings: dict[str, Any] | None, db: AsyncSession | None = None
    ) -> PrescriptionComplianceHook | None:
        del db  # reserved for hooks that need a lookup later
        if not isinstance(settings, dict):
            return None
        return cls.for_country(settings.get("country"))


async def resolve_hook_for_clinic(
    db: AsyncSession, clinic_id: UUID
) -> PrescriptionComplianceHook | None:
    """Load the clinic row and return its country hook (or None)."""
    from sqlalchemy import select

    from app.core.auth.models import Clinic

    clinic = (await db.execute(select(Clinic).where(Clinic.id == clinic_id))).scalars().first()
    if clinic is None:
        return None
    return PrescriptionHookRegistry.for_clinic_settings(clinic.settings)
