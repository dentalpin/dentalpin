# treatment_consumables — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints / tools |
|------------|-------|-------------------|
| `treatment_consumables.read` | List links, picker options | `GET /api/v1/treatment_consumables`, `GET .../link-options`, agent tool `get_treatment_consumables` |
| `treatment_consumables.write` | Create, edit quantity, unlink | `POST/PATCH/DELETE /api/v1/treatment_consumables*` |

Default role mapping: **admin** manages; **dentist** reads (the mapping
is chairside-relevant). Other roles get nothing out of the box and can
be widened from the module admin UI.
