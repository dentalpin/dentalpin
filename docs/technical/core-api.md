# DentalPin Core API

Public contract that DentalPin modules (official + community) can rely
on. Everything in this document is covered by the deprecation policy
in §7 — change-without-notice is a bug.

**Scope:** Fase B complete. The patient/appointment/timeline split is
reflected throughout; the `clinical` module no longer exists. Marked
sections are additive; breaking changes bump the core version's major.

---

## 1. `BaseModule`

Located at `app.core.plugins.BaseModule`. Abstract class every module
inherits from.

### Class attributes

| Attribute | Type | Required | Purpose |
|-----------|------|----------|---------|
| `manifest` | `dict` | yes (new modules) | Declarative metadata — see §2. |

Legacy path: modules may override `name`, `version`, and `dependencies`
as properties. Prefer `manifest`.

### Methods to implement

| Method | Returns | Notes |
|--------|---------|-------|
| `get_models()` | `list[type[DeclarativeBase]]` | SQLAlchemy classes to register. |
| `get_router()` | `APIRouter` | Mounted at `/api/v1/<name>/`. |
| `get_permissions()` | `list[str]` | Module-local strings; registry namespaces them. |
| `get_event_handlers()` | `dict[str, Callable]` | Optional. |

### Lifecycle hooks (async, optional)

| Hook | Signature | When |
|------|-----------|------|
| `install` | `async def install(self, ctx: ModuleContext) -> None` | First install, after migrations + seed. |
| `uninstall` | `async def uninstall(self, ctx: ModuleContext) -> None` | Before data delete + downgrade. |
| `post_upgrade` | `async def post_upgrade(self, ctx: ModuleContext, from_version: str) -> None` | After upgrade migrations + re-seed. |

Default implementations are no-ops.

### Derived

`get_manifest() -> Manifest` — parsed, validated dataclass. The
registry uses this; modules rarely call it directly.

---

## 2. Manifest schema

Full schema. Fields validated at discovery time by `Manifest.from_dict`
and at CI time by `app.core.plugins.manifest_validator`.

```python
MANIFEST = {
    # Identity — required
    "name": "billing",                        # snake_case, unique
    "version": "1.0.0",                       # semver X.Y.Z

    # Compat
    "min_core_version": "1.0.0",              # optional
    "max_core_version": "2.0.0",              # optional

    # Metadata — recommended
    "summary": "Invoices + payments",
    "author": "DentalPin Core Team",
    "license": "BSL-1.1",

    # Trust tier — required
    "category": "official",                   # "official" | "community"

    # Dependencies — required (list, may be empty)
    "depends": ["patients", "catalog"],

    # Policies — required booleans
    "installable": True,                      # false = hidden from UI
    "auto_install": True,                     # officials only
    "removable": False,                       # officials are pinned

    # Seed data — optional
    "data_files": ["data/defaults.yaml"],

    # RBAC declarative — recommended
    "role_permissions": {
        "admin": ["*"],
        "dentist": ["*"],
        "hygienist": ["read"],
    },

    # Frontend integration — optional
    "frontend": {
        "layer_path": "frontend",              # community only
        "navigation": [
            {
                "label": "nav.billing",       # i18n key
                "to": "/billing/invoices",
                "icon": "i-lucide-receipt",
                "permission": "billing.invoices.read",
                "order": 40,
            }
        ],
    },
}
```

---

## 3. `ModuleContext`

Passed to lifecycle hooks. Dataclass at
`app.core.plugins.ModuleContext`.

| Field | Type | Purpose |
|-------|------|---------|
| `module_name` | `str` | The calling module. |
| `db` | `AsyncSession` | Scoped to the current unit of work. |
| `event_bus` | `EventBus` | Publish events during install/upgrade. |
| `logger` | `logging.Logger` | Pre-named `app.modules.<name>`. |

---

## 4. Event bus

Located at `app.core.events.event_bus`. Singleton.

```python
from app.core.events import event_bus

event_bus.publish("inventory.restocked", {"item_id": "..."})
event_bus.subscribe("patient.created", my_handler)
event_bus.unsubscribe("patient.created", my_handler)
```

Sync + async handlers supported. Async handlers are scheduled as
background tasks. Exceptions are logged but do not propagate to
publishers.

### Core event catalog (stable)

All payload keys are strings. UUIDs are serialized as strings.

| Event | Payload keys |
|-------|--------------|
| `clinic.created` | `clinic_id`, `country`, `currency`, `timezone`, `language`, `vat_preset`, `created_by`, `source` — published by `POST /auth/setup` after commit; subscribers seed defaults idempotently in their own session (ADR 0018) |
| `patient.created` | `patient_id`, `clinic_id` |
| `patient.updated` | `patient_id`, `clinic_id`, `changes` |
| `patient.archived` | `patient_id`, `clinic_id` |
| `patient.medical_updated` | `patient_id`, `clinic_id`, `user_id` |
| `appointment.scheduled` | `appointment_id`, `patient_id`, `clinic_id` |
| `appointment.updated` | `appointment_id`, `clinic_id`, `changes` |
| `appointment.completed` | `appointment_id` |
| `appointment.cancelled` | `appointment_id` |
| `appointment.no_show` | `appointment_id` |
| `treatment.completed` | `treatment_id`, `patient_id`, `clinic_id` |
| `budget.created` | `budget_id`, `clinic_id` |
| `budget.sent` | `budget_id`, `clinic_id` |
| `budget.accepted` | `budget_id`, `clinic_id` |
| `budget.rejected` | `budget_id`, `clinic_id` |
| `invoice.created` | `invoice_id`, `clinic_id` |
| `invoice.issued` | `invoice_id`, `clinic_id` |
| `invoice.sent` | `invoice_id`, `clinic_id` |
| `invoice.paid` | `invoice_id`, `clinic_id` |
| `payment.recorded` | `payment_id`, `invoice_id`, `clinic_id` |
| `document.uploaded` | `document_id`, `patient_id`, `clinic_id`, `title`, `document_type` |

See `backend/app/core/events/types.py` for the full `EventType` enum.

---

## 5. Shared schemas

`app.core.schemas`:

```python
ApiResponse[T]         # {"data": T, "message": str | None}
PaginatedApiResponse[T]  # adds total/page/page_size
ErrorResponse          # {"data": None, "message": str, "errors": [...]}
```

HTTP status conventions:

| Code | Use |
|------|-----|
| 200 | GET / PUT success |
| 201 | POST create |
| 204 | DELETE |
| 400 | Validation-free bad request |
| 401 | Missing / bad token |
| 403 | Authenticated but not permitted |
| 404 | Not found |
| 409 | Conflict (duplicate) |
| 422 | Body validation failed |

---

## 6. Slots (frontend extension points)

Registered via `useModuleSlots().register(name, entry)` and consumed
via `<ModuleSlot :name="..." :ctx="..." />`.

### Canonical names (v1)

| Slot | Host | `ctx` shape |
|------|------|-------------|
| `patient.detail.tabs` | `/patients/:id` | `{ patient: Patient }` |
| `patient.detail.sidebar` | `/patients/:id` | `{ patient: Patient }` |
| `appointment.detail.actions` | appointment modal | `{ appointment: Appointment }` |
| `dashboard.widgets` | `/` | `{}` |
| `settings.sections` | `/settings` | `{}` |

### Entry shape

```ts
interface SlotEntry<Ctx = unknown> {
  id: string                    // unique, stable — enables HMR idempotence
  component: Component          // Vue component; defineAsyncComponent OK
  order?: number                // lower renders first
  permission?: string           // namespaced; hidden when can() is false
  condition?: (ctx: Ctx) => boolean
}
```

---

## 7. Importable core models

Safe to import from modules (stable across the v2 line):

```python
from app.core.auth.models import Clinic, ClinicMembership, User
from app.modules.patients.models import Patient
from app.modules.agenda.models import Appointment, Cabinet
from app.modules.patient_timeline.models import PatientTimeline
```

Patient moved out of core on purpose: it's a real module with its own
manifest, version and migration surface (`auto_install: True`,
`removable: False`). A lab-oriented fork could replace it with a
`lab_clients` module without forking core.

---

## 8. `ModuleService`

`app.core.plugins.ModuleService`. Public methods:

| Method | Purpose |
|--------|---------|
| `reconcile_with_db()` | Sync in-memory registry to `core_module`. |
| `list_modules()` | Combined disk + DB view. |
| `get_info(name)` | Single module details. |
| `status()` | Summary (counts by state, pending, errored). |
| `doctor()` | Diagnostic checks (orphans, missing deps, manifest errors). |
| `orphan(name)` | Mark a missing-from-disk module as uninstalled. |
| `install(name, force=False)` | Schedule install; returns dependency chain. |
| `uninstall(name, force=False)` | Schedule uninstall; blocks legacy + reverse-dep. |
| `upgrade(name)` | Schedule upgrade when manifest version diverges. |

All methods are async. `ModuleOperationError` wraps policy violations
(blocked uninstall, unknown module, etc.).

---

## 9. Module lifecycle REST

All routes under `/api/v1/modules`.

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| GET | `/modules` | `admin.clinic.read` | Full list including DB state. |
| GET | `/modules/-/active` | authenticated | Filtered for current role. |
| GET | `/modules/-/status` | `admin.clinic.read` | Counts + pending. |
| GET | `/modules/-/doctor` | `admin.clinic.read` | Diagnostic report. |
| GET | `/modules/{name}` | `admin.clinic.read` | Single module. |
| POST | `/modules/{name}/install` | `admin.clinic.write` | 202 + scheduled list. |
| POST | `/modules/{name}/uninstall` | `admin.clinic.write` | 202 + restart required. |
| POST | `/modules/{name}/upgrade` | `admin.clinic.write` | 202 if version changed. |
| POST | `/modules/-/restart` | `admin.clinic.write` | 202 + SIGTERM to self. |

---

## 9b. Roles REST (issue #46, ADR 0024)

All routes under `/api/v1/roles`, scoped to the caller's clinic.

| Method | Path | Permission | Notes |
|--------|------|------------|-------|
| GET | `/roles` | `admin.roles.read` | 5 system roles + clinic custom roles, with effective grants. |
| GET | `/roles/catalog` | `admin.roles.read` | Every grantable permission code. |
| POST | `/roles` | `admin.roles.write` | Create a custom role. 409 on system/duplicate name, 422 on unknown code. |
| PUT | `/roles/{id}` | `admin.roles.write` | Update a custom role; a rename follows memberships. |
| DELETE | `/roles/{id}` | `admin.roles.write` | 409 while any member holds it. |
| PUT | `/roles/{id}/overrides` | `admin.roles.write` | Per-clinic grant/revoke on a system role; `admin` never accepts revokes. |

Custom roles are assignable to members only with `RBAC_FROM_DB=true`.

---

## 10. Deprecation policy

Until DentalPin v1.0 is tagged:

- Breaking changes can land with an announcement in the CHANGELOG.

From v1.0 onwards:

- **Additive changes** (new fields, new slots, new events) are
  shipped freely at minor versions.
- **Breaking changes** require:
  1. A deprecation warning that fires at runtime for at least one
     minor release.
  2. A `CHANGELOG.md` entry describing the migration path.
  3. A major version bump when removed.
- Unannounced breaking changes are bugs and will be reverted.

Modules that declare `min_core_version` get an error at install time
if the current core is older. Use this to require new slots / events.

---

## 11. Versioning the core

The core itself follows semver. Modules read the current version from
`app.__version__` (placeholder until v1.0 tag). After v1.0, the CI
pipeline checks every PR touching `backend/app/core/` for:

- Added events → record in this document + CHANGELOG.
- Removed or renamed events/slots → require deprecation window.
- Changed `Manifest` schema → migration path documented.

---

## Where to go next

- `docs/technical/creating-modules.md` — the full authoring guide.
- `docs/user-manual/operations.md` — install/restart/backup/troubleshooting for admins.
- `backend/tests/fixtures/sample_module/` — minimal working example.
