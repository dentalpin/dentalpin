"""Storage and validation for declared clinic settings (ADR 0041)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.plugins.registry import module_registry
from app.core.settings.spec import SettingSpec, SettingValueError, validate_value


class UnknownSettingsModuleError(LookupError):
    """The module is not discovered, not active or declares no settings."""


class UnknownSettingError(ValueError):
    """The payload names a key the module does not declare."""


class SettingsClinicNotFoundError(LookupError):
    """The clinic row does not exist."""


class ClinicSettingsService:
    """Read and write declared settings for one clinic."""

    @staticmethod
    def declarations(module_name: str) -> list[SettingSpec]:
        module = module_registry.get(module_name)
        if module is None or not module_registry.is_active(module_name):
            raise UnknownSettingsModuleError(module_name)
        specs = list(module.get_settings())
        if not specs:
            raise UnknownSettingsModuleError(module_name)
        return specs

    @staticmethod
    def _effective(specs: list[SettingSpec], stored: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for spec in specs:
            if spec.key in stored:
                try:
                    values[spec.key] = validate_value(spec, stored[spec.key])
                    continue
                except SettingValueError:
                    pass
            values[spec.key] = spec.default
        return values

    @staticmethod
    async def get_values(db: AsyncSession, clinic_id: UUID, module_name: str) -> dict[str, Any]:
        specs = ClinicSettingsService.declarations(module_name)
        clinic = await db.get(Clinic, clinic_id)
        if clinic is None:
            raise SettingsClinicNotFoundError(str(clinic_id))
        stored = (clinic.settings or {}).get(module_name)
        return ClinicSettingsService._effective(specs, stored if isinstance(stored, dict) else {})

    @staticmethod
    async def update(
        db: AsyncSession,
        clinic_id: UUID,
        module_name: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        specs = ClinicSettingsService.declarations(module_name)
        by_key = {spec.key: spec for spec in specs}
        unknown = sorted(set(values) - set(by_key))
        if unknown:
            raise UnknownSettingError(
                f"Unknown setting(s) for '{module_name}': {', '.join(unknown)}"
            )
        validated = {key: validate_value(by_key[key], value) for key, value in values.items()}

        result = await db.execute(
            select(Clinic)
            .where(Clinic.id == clinic_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        clinic = result.scalar_one_or_none()
        if clinic is None:
            raise SettingsClinicNotFoundError(str(clinic_id))

        settings = dict(clinic.settings or {})
        namespace = settings.get(module_name)
        namespace = dict(namespace) if isinstance(namespace, dict) else {}
        namespace.update(validated)
        settings[module_name] = namespace
        clinic.settings = settings
        await db.commit()

        return ClinicSettingsService._effective(specs, namespace)
