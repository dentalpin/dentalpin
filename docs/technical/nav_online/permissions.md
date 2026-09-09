---
module: nav_online
last_verified_commit: 0000000
---

# nav_online — permissions

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `nav_online.settings.read` | View connection | `GET /api/v1/nav_online/settings` |
| `nav_online.settings.configure` | Edit credentials, test, enable | `PUT /api/v1/nav_online/settings`, `POST /api/v1/nav_online/settings/test-connection` |
| `nav_online.records.read` | Submission log | `GET /api/v1/nav_online/records`, `GET /api/v1/nav_online/records/{id}/xml` |
| `nav_online.queue.manage` | Retry / process now | `POST /api/v1/nav_online/records/{id}/retry`, `POST /api/v1/nav_online/queue/process-now` |

Role grants: admin `*`; dentist and receptionist `records.read`.
