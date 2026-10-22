"""Module settings registry (ADR 0041)."""

from uuid import uuid4

import pytest
from fastapi import APIRouter
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.models import Clinic
from app.core.plugins import BaseModule
from app.core.plugins.registry import module_registry
from app.core.settings import router as settings_router
from app.core.settings.service import ClinicSettingsService
from app.core.settings.spec import (
    SettingDeclarationError,
    SettingSpec,
    validate_declarations,
    validate_value,
)
from app.modules.billing.schemas import BillingSettingsResponse, BillingSettingsUpdate

BILLING_KEYS = ["default_payment_term_days", "invoice_footer_text", "bank_account_info"]


def _spec(**overrides) -> SettingSpec:
    payload = {
        "key": "enabled",
        "type": "boolean",
        "default": False,
        "permission": "billing.read",
        "label_key": "billingSettings.fields.enabled.label",
    }
    payload.update(overrides)
    return SettingSpec(**payload)


async def _stored_settings(db_session: AsyncSession, clinic_id) -> dict:
    result = await db_session.execute(select(Clinic.settings).where(Clinic.id == clinic_id))
    return result.scalar_one() or {}


async def test_get_declarations_and_defaults(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    response = await client.get("/api/v1/settings/billing", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["module"] == "billing"
    assert [setting["key"] for setting in data["settings"]] == BILLING_KEYS
    assert data["values"] == {
        "default_payment_term_days": 30,
        "invoice_footer_text": None,
        "bank_account_info": None,
    }
    assert all(setting["writable"] for setting in data["settings"])
    term = data["settings"][0]
    assert term["min_value"] == 0
    assert term["max_value"] == 365
    assert data["settings"][1]["multiline"] is True


async def test_patch_persists_only_declared_keys(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
) -> None:
    response = await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"default_payment_term_days": 45, "invoice_footer_text": "Gracias"}},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["values"]["default_payment_term_days"] == 45

    stored = await _stored_settings(db_session, test_clinic.id)
    assert stored["billing"]["default_payment_term_days"] == 45
    assert stored["billing"]["invoice_footer_text"] == "Gracias"
    assert stored["slot_duration_min"] == 15


async def test_patch_unknown_key_is_rejected_without_writing(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, db_session: AsyncSession
) -> None:
    before = await _stored_settings(db_session, test_clinic.id)

    response = await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"nope": 1}},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert await _stored_settings(db_session, test_clinic.id) == before


@pytest.mark.parametrize(
    "value",
    ["45", 366, -1, True, 1.5],
)
async def test_patch_invalid_integer_is_rejected(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic, value: object
) -> None:
    response = await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"default_payment_term_days": value}},
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_patch_invalid_integer_does_not_write(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    before = await _stored_settings(db_session, test_clinic.id)

    response = await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"default_payment_term_days": 366}},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert await _stored_settings(db_session, test_clinic.id) == before


async def test_patch_wrong_type_string_is_rejected(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    response = await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"invoice_footer_text": 5}},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_validate_value_enforces_max_length() -> None:
    spec = _spec(type="string", default="", max_length=5)

    with pytest.raises(ValueError, match="at most 5 characters"):
        validate_value(spec, "x" * 6)


async def test_legacy_put_accepts_long_string(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    footer = "x" * 600

    update = await client.put(
        "/api/v1/billing/settings",
        json={"invoice_footer_text": footer},
        headers=auth_headers,
    )

    assert update.status_code == 200
    assert update.json()["data"]["invoice_footer_text"] == footer

    legacy = await client.get("/api/v1/billing/settings", headers=auth_headers)
    assert legacy.json()["data"]["invoice_footer_text"] == footer

    registry = await client.get("/api/v1/settings/billing", headers=auth_headers)
    assert registry.json()["data"]["values"]["invoice_footer_text"] == footer


async def test_patch_can_clear_nullable_string(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"bank_account_info": "ES00 0000"}},
        headers=auth_headers,
    )

    response = await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"bank_account_info": None}},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["values"]["bank_account_info"] is None


async def test_legacy_billing_endpoints_delegate(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    update = await client.put(
        "/api/v1/billing/settings",
        json={"default_payment_term_days": 15, "invoice_footer_text": "Pie"},
        headers=auth_headers,
    )
    assert update.status_code == 200
    assert update.json()["data"]["default_payment_term_days"] == 15

    legacy = await client.get("/api/v1/billing/settings", headers=auth_headers)
    assert legacy.status_code == 200
    assert legacy.json()["data"]["invoice_footer_text"] == "Pie"

    registry = await client.get("/api/v1/settings/billing", headers=auth_headers)
    assert registry.json()["data"]["values"]["default_payment_term_days"] == 15


async def test_unknown_module_returns_404(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    response = await client.get("/api/v1/settings/not_a_module", headers=auth_headers)

    assert response.status_code == 404


async def test_values_are_clinic_scoped(db_session: AsyncSession, test_clinic: Clinic) -> None:
    await ClinicSettingsService.update(
        db_session, test_clinic.id, "billing", {"default_payment_term_days": 60}
    )
    other = Clinic(
        id=uuid4(),
        name="Other Clinic",
        tax_id="B87654321",
        address={},
        settings={},
    )
    db_session.add(other)
    await db_session.commit()

    values = await ClinicSettingsService.get_values(db_session, other.id, "billing")

    assert values["default_payment_term_days"] == 30


async def test_permissions_filter_reads_and_block_writes(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    async def read_only(db, clinic_id, role, permission):
        return permission == "billing.read"

    monkeypatch.setattr(settings_router, "has_permission_for", read_only)

    response = await client.get("/api/v1/settings/billing", headers=auth_headers)
    data = response.json()["data"]
    assert all(setting["writable"] is False for setting in data["settings"])

    before = await _stored_settings(db_session, test_clinic.id)
    patch = await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"default_payment_term_days": 5}},
        headers=auth_headers,
    )
    assert patch.status_code == 403
    assert await _stored_settings(db_session, test_clinic.id) == before

    async def deny_all(db, clinic_id, role, permission):
        return False

    monkeypatch.setattr(settings_router, "has_permission_for", deny_all)
    hidden = await client.get("/api/v1/settings/billing", headers=auth_headers)
    assert hidden.status_code == 200
    assert hidden.json()["data"]["settings"] == []
    assert hidden.json()["data"]["values"] == {}


async def test_patch_requires_read_permission_to_write(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    async def write_only(db, clinic_id, role, permission):
        return permission == "billing.admin"

    monkeypatch.setattr(settings_router, "has_permission_for", write_only)
    before = await _stored_settings(db_session, test_clinic.id)

    response = await client.patch(
        "/api/v1/settings/billing",
        json={"values": {"default_payment_term_days": 5}},
        headers=auth_headers,
    )

    assert response.status_code == 403
    assert await _stored_settings(db_session, test_clinic.id) == before


async def test_empty_patch_is_a_noop(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    clinic_id = test_clinic.id
    before = await _stored_settings(db_session, clinic_id)

    response = await client.patch(
        "/api/v1/settings/billing", json={"values": {}}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["values"]["default_payment_term_days"] == 30
    assert await _stored_settings(db_session, clinic_id) == before


async def test_stored_value_outside_declaration_falls_back_to_default(
    client: AsyncClient,
    auth_headers: dict,
    test_clinic: Clinic,
    db_session: AsyncSession,
) -> None:
    test_clinic.settings = {
        **(test_clinic.settings or {}),
        "billing": {"default_payment_term_days": 999},
    }
    await db_session.commit()

    response = await client.get("/api/v1/settings/billing", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"]["values"]["default_payment_term_days"] == 30
    stored = await _stored_settings(db_session, test_clinic.id)
    assert stored["billing"]["default_payment_term_days"] == 999


def test_declarations_reject_duplicate_keys() -> None:
    with pytest.raises(SettingDeclarationError):
        validate_declarations("billing", [_spec(), _spec()])


def test_declarations_reject_foreign_permission() -> None:
    with pytest.raises(SettingDeclarationError):
        validate_declarations("billing", [_spec(permission="patients.read")])


def test_declarations_reject_undeclared_permission() -> None:
    with pytest.raises(SettingDeclarationError, match="not one of the module"):
        validate_declarations(
            "billing",
            [_spec(permission="billing.raed")],
            known_permissions={"billing.read", "billing.admin"},
        )


def test_declarations_reject_device_scope() -> None:
    with pytest.raises(SettingDeclarationError):
        validate_declarations("billing", [_spec(scope="device")])


def test_declarations_reject_bad_default() -> None:
    with pytest.raises(SettingDeclarationError):
        validate_declarations("billing", [_spec(default="no")])


def test_declarations_reject_enum_default_outside_choices() -> None:
    with pytest.raises(SettingDeclarationError):
        validate_declarations(
            "billing",
            [_spec(type="enum", default="b", choices=("a", "c"))],
        )


def test_declarations_accept_valid_spec() -> None:
    validate_declarations("billing", [_spec()])


class _StubSettingsModule(BaseModule):
    manifest = {"name": "settings_stub", "version": "0.1.0"}

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_permissions(self) -> list[str]:
        return ["read"]

    def get_settings(self) -> list[SettingSpec]:
        return [_spec(permission="settings_stub.raed")]


def test_registry_rejects_undeclared_setting_permission() -> None:
    module = _StubSettingsModule()
    try:
        with pytest.raises(SettingDeclarationError, match="not one of the module"):
            module_registry.register(module)
    finally:
        module_registry.unregister("settings_stub")


class _InactiveSettingsModule(BaseModule):
    manifest = {"name": "settings_inactive_stub", "version": "0.1.0"}

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_permissions(self) -> list[str]:
        return ["read"]

    def get_settings(self) -> list[SettingSpec]:
        return [_spec(permission="settings_inactive_stub.read")]


class _EmptySettingsModule(BaseModule):
    manifest = {"name": "settings_empty_stub", "version": "0.1.0"}

    def get_models(self) -> list:
        return []

    def get_router(self) -> APIRouter:
        return APIRouter()

    def get_permissions(self) -> list[str]:
        return ["read"]

    def get_settings(self) -> list[SettingSpec]:
        return []


async def test_discovered_but_inactive_module_returns_404(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    module_registry.register(_InactiveSettingsModule())
    try:
        response = await client.get("/api/v1/settings/settings_inactive_stub", headers=auth_headers)
    finally:
        module_registry.unregister("settings_inactive_stub")

    assert response.status_code == 404


async def test_active_module_without_declarations_returns_404(
    client: AsyncClient, auth_headers: dict, test_clinic: Clinic
) -> None:
    module_registry.register(_EmptySettingsModule())
    module_registry.activate("settings_empty_stub")
    try:
        response = await client.get("/api/v1/settings/settings_empty_stub", headers=auth_headers)
    finally:
        module_registry.unregister("settings_empty_stub")

    assert response.status_code == 404


async def test_legacy_billing_payload_covers_every_declared_key(
    client: AsyncClient,
) -> None:
    declared = {spec.key for spec in ClinicSettingsService.declarations("billing")}

    assert declared == set(BillingSettingsResponse.model_fields)
    assert declared == set(BillingSettingsUpdate.model_fields)
