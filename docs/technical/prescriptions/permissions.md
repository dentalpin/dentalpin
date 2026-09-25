# prescriptions — permissions

| Permission | Grants | Gated endpoints |
|---|---|---|
| `prescriptions.read` | list/get, warnings, templates read, PDF, page | `GET` routes |
| `prescriptions.write` | drafts, templates, prescriber profile | `POST/PATCH/DELETE` except issue/cancel |
| `prescriptions.issue` | issue + cancel | `POST .../issue`, `POST .../cancel` |

Role defaults: admin/dentist `*`; hygienist/assistant/receptionist
read-only (issuing stays prescriber-only).
