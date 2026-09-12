---
module: sdi_it
last_verified_commit: 0000000
---

# sdi_it — permissions

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `sdi_it.settings.read` | View SDI configuration | `GET /api/v1/sdi_it/settings` |
| `sdi_it.settings.configure` | Edit regime, bollo, riferimento, PEC mailbox; enable; test the mailbox | `PUT /api/v1/sdi_it/settings`, `POST /api/v1/sdi_it/pec/test` |
| `sdi_it.records.read` | Record list, per-invoice panel and XML download | `GET /api/v1/sdi_it/records`, `GET /api/v1/sdi_it/records/by-invoice/{invoice_id}`, `GET /api/v1/sdi_it/records/{id}/xml` |
| `sdi_it.records.manage` | Mark exported, import receipts, requeue after scarto, run a PEC tick | `POST /api/v1/sdi_it/records/{id}/exported`, `POST /api/v1/sdi_it/receipts`, `POST /api/v1/sdi_it/records/{id}/requeue`, `POST /api/v1/sdi_it/queue/process-now` |

Role grants: admin `*`; dentist `records.read`; receptionist
`records.read`, `records.manage` (the front desk is who uploads files
and imports receipts in a small practice).
