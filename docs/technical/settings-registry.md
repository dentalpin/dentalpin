# Module settings registry

How modules declare simple clinic settings and get storage, validation,
RBAC and a generated form without a migration. Rule: ADR 0041.
Product brief: `docs/features/settings-registry.md`.

## Contract

A module overrides `BaseModule.get_settings()` and returns
`SettingSpec` objects from `app.core.settings.spec`:

```python
from app.core.settings.spec import SettingSpec

def get_settings(self) -> list[SettingSpec]:
    return [
        SettingSpec(
            key="default_payment_term_days",
            type="integer",
            default=30,
            permission="billing.read",
            write_permission="billing.admin",
            label_key="billingSettings.fields.defaultPaymentTermDays.label",
            description_key="billingSettings.fields.defaultPaymentTermDays.description",
            min_value=0,
            max_value=365,
        ),
    ]
```

| Field | Required | Meaning |
|---|---|---|
| `key` | yes | `snake_case`, unique within the module. The namespace is the module name. |
| `type` | yes | `string`, `integer`, `boolean` or `enum`. |
| `default` | yes | Effective value when nothing is stored. `None` requires `nullable=True`. |
| `permission` | yes | Module-prefixed permission required to read the value and its declaration through this API. It gates the settings API only, not the raw namespace: the whole namespace is also returned to every member by `GET /api/v1/auth/clinics`. |
| `label_key` | yes | i18n key the generated form renders. |
| `scope` | no | `clinic` only. `device` is rejected until a device identity exists. |
| `write_permission` | no | Stronger permission for writes; defaults to `permission`. |
| `description_key` | no | i18n key for the field help text. |
| `choices` | enum only | Non-empty tuple of allowed strings. |
| `min_value` / `max_value` | integer only | Inclusive bounds. |
| `max_length` | string only | Positive maximum length. |
| `multiline` | string only | Render a textarea instead of an input. |
| `nullable` | no | Allows `null` (used for optional free text). |

Declarations are validated when the module is registered: unique keys,
`<module>.`-prefixed permissions, supported type/scope, matching default,
enum defaults inside `choices`. A bad declaration fails discovery, not a
request.

## Storage

Values live in the existing `clinics.settings` JSONB column:

```json
{ "billing": { "default_payment_term_days": 45 }, "country": "ES" }
```

No new table and no migration. `clinics.settings` is returned to every
member of the clinic (`ClinicMetadataResponse.settings`, served by
`GET /api/v1/auth/clinics`), so **never declare credentials, API keys or
tokens here** - those stay in bespoke `<module>_settings` tables or
encrypted storage.

Stored values are validated on read; a value that no longer matches its
declaration falls back to the default instead of breaking the form.

## API

`GET /api/v1/settings/{module}`

```json
{
  "data": {
    "module": "billing",
    "settings": [
      {
        "key": "default_payment_term_days",
        "type": "integer",
        "default": 30,
        "writable": true,
        "label_key": "billingSettings.fields.defaultPaymentTermDays.label",
        "choices": [],
        "min_value": 0,
        "max_value": 365,
        "max_length": null,
        "multiline": false,
        "nullable": false
      }
    ],
    "values": { "default_payment_term_days": 45 }
  }
}
```

Only declarations the caller may read are returned, and `values` only
contains those keys. `writable` reflects `write_permission` for the
current role.

`PATCH /api/v1/settings/{module}`

```json
{ "values": { "default_payment_term_days": 45, "invoice_footer_text": null } }
```

- Unknown key: `422`, nothing written.
- Wrong type, out of bounds, too long: `422`, nothing written.
- Key the caller may not read or write: `403`, nothing written.
- Module not active or no declarations: `404`.
- Empty `values` object: `200` with the current declarations and values.

PATCH requires both the read permission and the write permission of
every key in the payload, so a write-only role cannot change a value it
cannot see. A caller with no readable declarations receives `200` with
empty `settings` and `values`; an unknown or inactive module receives
`404`.

Writes take a row lock on the clinic, merge the declared keys into the
module namespace and commit. Fields not sent are left untouched; an
empty payload skips the write entirely.

The route is authenticated by `get_clinic_context` (clinic membership)
and authorized **per declaration**; it intentionally has no single
`require_permission` gate because one module can expose settings with
different read and write permissions.

## Frontend

`SettingsModuleForm` (`frontend/app/components/settings/SettingsModuleForm.vue`)
renders the GET payload: labels and help text from the declaration keys,
switches for booleans, number inputs with bounds, textareas for
multiline strings, selects for enums, disabled fields when not writable
and a save button that PATCHes only the writable fields the user changed.
An empty required integer blocks the save with an inline error instead of
being silently dropped. Both form calls suppress the shared toaster and
surface their own empty-spin state and error message.

A module registers a settings page from its client plugin:

```ts
registerSettingsPage({
  path: 'preferences',
  category: 'billing',
  labelKey: 'billingSettings.title',
  descriptionKey: 'billingSettings.description',
  icon: 'i-lucide-settings-2',
  permission: PERMISSIONS.billing.read,
  component: () => import('../components/BillingSettingsPage.vue'),
  order: 30
})
```

The page component is a thin wrapper:

```vue
<template>
  <SettingsModuleForm module="billing" />
</template>
```

## Rules

- One namespace per module: a module cannot declare into another module's
  settings.
- Never store secrets; `clinics.settings` is client-visible.
- `device` scope is reserved, not implemented.
- Existing hand-rolled settings keep their contracts until a module
  delegates them to `ClinicSettingsService` (billing is the pilot; its
  legacy `GET/PUT /api/v1/billing/settings` endpoints now go through the
  service). The billing pilot declares no `max_length` on its strings
  because the legacy `PUT` contract is unbounded; capping would reject
  values that already exist. The legacy endpoints keep their original
  single `billing.admin` write gate while the generic PATCH requires read
  and write per field.

## Tests

- `backend/tests/test_settings_registry.py` - declarations, defaults,
  404/422/403, per-field read/write permissions, clinic isolation.
- `frontend/tests/utils/settingsForm.test.ts` - form initialization and
  writable payload.
- `frontend/tests/components/settingsModuleForm.test.ts` - render,
  read-only disabling, changed-fields PATCH, no-op save, boolean toggle,
  the required-integer inline error and the billing page mounting the
  generic form.
- `backend/tests/test_route_permissions.py` and the manifest tests keep
  the surrounding contracts in CI.
