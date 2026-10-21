# Settings registry

> Status: in progress (ADR 0041). Modules: core seam + billing pilot.
> Spec last updated: 2026-10-20.

## Problem

Simple clinic settings are implemented three different ways:

- `clinics.settings` JSONB namespaces served by hand-written endpoints:
  `billing` (`backend/app/modules/billing/router.py`), `budget`,
  `communications`, `onboarding` (`backend/app/core/auth/router.py`).
- Bespoke `<module>_settings` tables with their own models, services and
  routers: copilot, india_gst, leads, nav_online, notifications, razorpay,
  recalls, sdi_it, sistema_ts, sms_gateway, telephony, whatsapp_kapso,
  whatsapp_webhook.
- Values with no API at all, read directly where needed.

Every new setting repeats the same plumbing (migration, table, schemas,
clinic scoping, permission checks, frontend form), and there is no way for
the frontend to discover what settings a module exposes. Settings screens
are hand-built page by page.

## Goal

One declarative seam for simple, non-secret, clinic-scoped settings:

- the owning module declares the setting once;
- the core validates, stores, serves and scopes it;
- the frontend renders the form from the declaration.

## Non-goals (v1)

- **Secrets.** API keys, tokens and SMTP passwords stay in their bespoke
  tables or encrypted storage. `clinics.settings` is returned to every
  member of the clinic (`ClinicMetadataResponse.settings`), so declared
  settings are never credentials.
- **Device scope.** No device identity exists in the auth model yet; the
  spec field exists but `"device"` is rejected.
- **Migration of existing tables.** Existing surfaces keep their contracts.
  Modules migrate by delegating their router to the core service, starting
  with billing.
- **Cross-module access.** A module only declares and reads its own
  namespace.

## Design

### Storage

`clinics.settings[<module>][<key>]`, using the existing JSONB column. No new
table and no data migration. Existing namespaces are untouched.

### Declarations

`BaseModule.get_settings() -> list[SettingSpec]` (default: empty). A spec
carries:

| Field | Meaning |
|---|---|
| `key` | Module-local key (unique within the module). |
| `type` | `string` \| `integer` \| `boolean` \| `enum`. |
| `default` | Effective value when nothing is stored. |
| `scope` | `clinic` only in v1. |
| `permission` | Permission required to read the value and its declaration. |
| `write_permission` | Optional stronger permission for PATCH; defaults to `permission`. |
| `nullable` | Allows an explicit `null` (optional free text); a `false` integer cannot be emptied. |
| `label_key` / `description_key` | i18n keys for the generated form. |
| `choices`, `min_value`, `max_value`, `max_length`, `multiline` | Validation and rendering hints. |

Declarations are validated when the module is discovered: unique keys,
module-prefixed permissions, supported type/scope, defaults matching the
declared type. A bad declaration fails module discovery instead of failing
at request time.

### API

- `GET /api/v1/settings/{module}` returns the module's readable
  declarations plus effective values (`stored ?? default`) and a `writable`
  flag per field. Modules with no declarations answer 404.
- `PATCH /api/v1/settings/{module}` takes a partial `values` object. Unknown
  keys, wrong types, out-of-bounds values and non-writable fields are
  rejected (422 for shape, 403 for permission). Every key also requires
  its read permission, and an empty `values` object is a no-op. The
  clinic row is locked, the namespace is merged and only declared keys
  are written.

Values are read through the service, which validates stored data and falls
back to the default when the stored value no longer fits the declaration.

### Frontend

One generic component, `SettingsModuleForm`, driven by the GET response:
labelled inputs, enum choices, bounds, a disabled state when the field
is not writable and a save action that PATCHes only the fields the user
changed and sends no request when nothing changed. Emptying a required
integer blocks the save with an inline message instead of silently
dropping the key. The billing module
gets a settings page registered under
Settings > Billing that mounts the generic form.

### Pilot: billing

Billing declares its three existing settings
(`default_payment_term_days`, `invoice_footer_text`, `bank_account_info`)
with the same defaults, bounds and permissions as today, and its legacy
`GET/PUT /api/v1/billing/settings` endpoints delegate to the service. The
public contract does not change. The new page fills a UI gap: the endpoints
exist but nothing rendered them yet. The stored values are clinic
preferences for the settings surface; invoice issuance keeps the values
entered on each invoice.

## Acceptance criteria

1. A module can declare settings and have them validated at discovery
   without a migration or a new table.
2. `GET /settings/{billing}` returns declarations and default values for a
   reader; PATCH persists only declared keys and returns the merged result.
3. Unknown keys, invalid types, out-of-bounds values and unauthorized
   writes are rejected with the documented status codes and never touch
   storage.
4. Settings are clinic-scoped: a second clinic sees defaults, not the first
   clinic's values.
5. Billing's legacy settings endpoints behave exactly as before and now go
   through the service.
6. The billing settings page renders from declarations, saves with PATCH and
   reflects permissions.
7. Existing suites, catalogs and docs gates stay green.

## Test plan

- Backend: `backend/tests/test_settings_registry.py` (validation, defaults,
  404, 422, 403, write permission split, clinic isolation, legacy billing
  delegation, the declaration-legacy key-set invariant and inactive/empty
  module 404s).
- Manifest: declaration validation is covered where module manifests are
  validated.
- Frontend: `frontend/tests/components/settingsModuleForm.test.ts` covers
  render, read-only disabling, the changed-fields PATCH, the no-op save,
  the boolean toggle and the billing page resolving the generic form;
  `frontend/tests/utils/settingsForm.test.ts` covers the payload helpers.
- Battery: `scripts/dev-verify.sh` (no `--fast` because Vue files change)
  plus `--with-pytest --module billing`.

## Risks

- Values written outside the registry (hand-edited JSONB, legacy endpoints
  using different defaults) can drift; read-time fallback limits the damage
  but does not repair rows, and the form never writes an unchanged fallback
  value back.
- Per-field permissions make a mixed PATCH fail as a whole; documented so
  callers send only writable fields.
- Existing secret tables stay; the portal must not imply the registry
  replaces them.
