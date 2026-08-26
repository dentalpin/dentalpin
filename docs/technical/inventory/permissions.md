---
module: inventory
last_verified_commit: db2caa92
---

# inventory — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `inventory.read` | List/view items, low-stock filter, valuation, movements | `GET /api/v1/inventory/`, `GET /api/v1/inventory/{item_id}`, `GET /api/v1/inventory/valuation`, `GET /api/v1/inventory/{item_id}/movements` |
| `inventory.write` | Create, edit, adjust stock, delete/deactivate | `POST /api/v1/inventory/`, `PATCH …/{item_id}`, `POST …/{item_id}/adjust`, `DELETE …/{item_id}` |

Default role mapping — the whole team participates; stock levels are
operational data, not sensitive (same breadth precedent as
`patient_relationships`):

| Role | Permissions |
|------|-------------|
| `admin` | all (`*`) |
| `dentist` | read, write |
| `hygienist` | read, write |
| `assistant` | read, write |
| `receptionist` | read, write |

Agent tools reuse the same two permission strings. Tools returning
user-entered item names/notes are marked `exposes_free_text=True` so
they stay off the cloud LLM path under redaction.
