---
module: sistema_ts
last_verified_commit: 0000000
---

# sistema_ts — permissions

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `sistema_ts.settings.read` | View credentials status, identity, year overview, item types | `GET /api/v1/sistema_ts/settings`, `GET /api/v1/sistema_ts/item-types` |
| `sistema_ts.settings.configure` | Edit credentials and identity, enable, map item types | `PUT /api/v1/sistema_ts/settings`, `PUT /api/v1/sistema_ts/item-types/{id}` |
| `sistema_ts.documents.read` | Document list and per-invoice view | `GET /api/v1/sistema_ts/documents`, `GET /api/v1/sistema_ts/documents/by-invoice/{id}` |
| `sistema_ts.documents.manage` | Retry a rejected document, run a tick | `POST /api/v1/sistema_ts/documents/{id}/retry`, `POST /api/v1/sistema_ts/queue/process-now` |
| `sistema_ts.opposition.read` | See whether a patient opposes | `GET /api/v1/sistema_ts/opposition/{patient_id}` |
| `sistema_ts.opposition.write` | Record or revoke the opposition | `PUT /api/v1/sistema_ts/opposition/{patient_id}` |

Role grants: admin `*`; dentist `documents.read`, `opposition.read`,
`opposition.write`; receptionist `documents.read`, `documents.manage`,
`opposition.read`, `opposition.write`; hygienist and assistant
`opposition.read` (the flag shows in the patient record).
