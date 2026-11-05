# 0042 — Module settings registry

- **Status:** proposed
- **Date:** 2026-10-20
- **Deciders:** maintainers
- **Tags:** modules, settings, api, frontend

## Context

Clinic-scoped settings are implemented three different ways in the tree.
A few namespaces live in the `clinics.settings` JSONB column and are served
by hand-written endpoints (`billing` in `backend/app/modules/billing/router.py`,
`budget`/`communications`/`onboarding` in `backend/app/core/auth/router.py`).
Most modules instead create their own `<module>_settings` table plus a
bespoke router and service (copilot, india_gst, leads, nav_online,
notifications, razorpay, recalls, sdi_it, sistema_ts, sms_gateway, telephony,
whatsapp_kapso, whatsapp_webhook). Each new simple setting therefore costs a
migration, a table, a router, schemas, permission checks and a frontend page,
and each implementation re-derives clinic scoping and RBAC independently.

There is also no discovery surface: the frontend cannot ask "which settings
exist for this module, with which types, defaults and permissions", so every
settings screen is hand-built. At the same time `clinics.settings` is already
returned to every member of the clinic (`ClinicMetadataResponse.settings` in
`backend/app/core/auth/schemas.py:127`, served by `GET /api/v1/auth/clinics`),
so anything stored there is member-visible and must never hold credentials.

## Decision

A module declares its simple, non-secret, clinic-scoped settings through an
optional `get_settings()` hook on `BaseModule`; the core validates and serves
them through one generic API backed by `clinics.settings[<module>][<key>]`.

Clarifications:

- A setting is declared once, by the module that owns it, as a `SettingSpec`
  (`key`, `type`, `default`, `permission`, optional `write_permission`,
  optional `nullable`, labels, bounds). Keys are module-local because the
  namespace is the
  module's `manifest["name"]`; a module cannot declare into another module's
  namespace.
- Storage is the existing JSONB column. No new table, no migration, no data
  backfill. Existing namespaces and endpoints keep working; a module migrates
  by delegating its router to the core settings service.
- `GET /api/v1/settings/{module}` returns the declarations (filtered to
  readable ones) together with the effective values; `PATCH` validates every
  key against the declaration, enforces the read and write permissions per
  field, locks the clinic row and writes only the declared keys.
- v1 supports clinic scope only. `SettingSpec.scope` exists so the contract
  can grow, but declaring `"device"` fails fast until a device identity
  exists in the auth model.
- Secrets (API keys, tokens, SMTP passwords) are out of scope. They stay in
  bespoke `<module>_settings` tables (or encrypted storage) and are never
  declared, because `clinics.settings` is client-visible.
- The frontend gets one generic form component driven by the declarations;
  modules add a settings page by registering an entry that mounts it.

## Consequences

### Good

- A new simple setting costs one `SettingSpec` line plus a translate key,
  not a migration and a router.
- Validation, defaults, clinic scoping and RBAC live in one place and are
  tested once.
- Settings become discoverable and renderable without bespoke UI code.
- Existing hand-rolled settings keep working; migration is incremental and
  behaviour-preserving (billing is the pilot).

### Bad / accepted trade-offs

- JSONB values have no database-level constraints; validation is
  application-level and old values written outside the registry are only
  defended by read-time fallback to the default.
- Per-field permissions mean the generic PATCH can reject one key without
  writing the rest; callers must send only what they may write.
- `clinics.settings` remains returned to every member of the clinic, so the
  registry cannot
  ever be used for credentials. Modules that need secrets keep two surfaces.

## Alternatives considered

- **A generic `clinic_settings` table (clinic_id, module, key, value JSONB)**
  - new table, new migration path, and it duplicates what the existing
  `clinics.settings` column already provides.
- **Declarations in the manifest dict instead of a Python hook** - the
  manifest is data-only and validated by `manifest_validator`; typed specs
  with defaults and bounds would become untyped dictionaries.
- **Keep hand-rolled endpoints and only share helpers** - does not remove the
  duplication that motivates this work, and leaves no discovery surface.
- **Declare secrets in the registry and encrypt values at rest** - key
  management, rotation and audit are a separate problem; mixing them into a
  client-visible JSONB is the wrong boundary.

## How to verify the rule still holds

- `backend/tests/test_settings_registry.py` covers declaration validation,
  defaults merge, unknown-key 422, type/bounds 422, read/write permission
  enforcement, clinic isolation and the legacy billing delegation
  (`test_legacy_billing_endpoints_delegate`).
- `test_values_are_clinic_scoped` pins the tenant boundary: a second
  clinic's stored values are never returned.
- The module registry validates declarations when it registers every
  discovered module (`test_route_permissions.py` calls
  `register_discovered()`); `test_settings_registry.py` pins the unit
  rules, including that a declaration permission must be one of the
  module's declared permissions.

## References

- `backend/app/modules/billing/router.py` (legacy namespace endpoints)
- `backend/app/core/auth/router.py:969` (`_BudgetSettingsPatch`)
- `backend/app/core/auth/models.py` (`Clinic.settings` JSONB)
- `docs/features/settings-registry.md`
- `docs/technical/creating-modules.md` (module hooks)
