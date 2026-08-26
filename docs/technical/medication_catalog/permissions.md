# medication_catalog — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints / tools |
|------------|-------|-------------------|
| `medication_catalog.read` | List, search, view | `GET /api/v1/medication_catalog`, agent tool `list_medications` |
| `medication_catalog.write` | Create, edit, delete, re-seed | `POST/PATCH/DELETE /api/v1/medication_catalog*`, `POST /medication_catalog/seed` |

Default role mapping:

- **admin**: full management (Settings → Clinical is admin territory).
- **dentist**: read-only — prescribers need the list; the future
  prescription flow consumes it read-only.
- other roles: none out of the box. Clinics can widen from the module
  admin UI.
