"""Storage and validation for declared clinic settings (ADR 0042)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.plugins.registry import module_registry
from app.core.settings.spec import SettingSpec, SettingValueError, validate_value

logger = logging.getLogger(__name__)


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
    def _effective(
        specs: list[SettingSpec], stored: dict[str, Any], module_name: str
    ) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for spec in specs:
            if spec.key in stored:
                try:
                    values[spec.key] = validate_value(spec, stored[spec.key])
                    continue
                except SettingValueError as exc:
                    logger.warning(
                        "Settings fallback: module %s key %s %s",
                        module_name,
                        spec.key,
                        exc,
                    )
            values[spec.key] = spec.default
        return values

    @staticmethod
    async def get_values(db: AsyncSession, clinic_id: UUID, module_name: str) -> dict[str, Any]:
        specs = ClinicSettingsService.declarations(module_name)
        clinic = await db.get(Clinic, clinic_id)
        if clinic is None:
            raise SettingsClinicNotFoundError(str(clinic_id))
        stored = (clinic.settings or {}).get(module_name)
        if not isinstance(stored, dict) and stored is not None:
            logger.warning(
                "Settings fallback: module %s stores a non-dict namespace; using defaults",
                module_name,
            )
            stored = {}
        return ClinicSettingsService._effective(specs, stored or {}, module_name)

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

        return ClinicSettingsService._effective(specs, namespace, module_name)
