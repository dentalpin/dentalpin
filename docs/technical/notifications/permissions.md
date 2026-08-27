---
module: notifications
last_verified_commit: 0000000
---

# Notifications — permissions

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Returned by `NotificationsModule.get_permissions()`
(relative names; the registry namespaces them as `notifications.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `notifications.templates.read` | _Describe what this allows._ | _List the endpoints._ |
| `notifications.templates.write` | _Describe what this allows._ | _List the endpoints._ |
| `notifications.preferences.read` | _Describe what this allows._ | _List the endpoints._ |
| `notifications.preferences.write` | _Describe what this allows._ | _List the endpoints._ |
| `notifications.logs.read` | Read message logs, a patient's conversation thread, and which channels are configured for the clinic. | `GET /notifications/conversations/{patient_id}`, `GET /notifications/channels` (#207), plus the log-listing endpoints. |
| `notifications.send` | _Describe what this allows._ | _List the endpoints._ |
| `notifications.settings.read` | Read clinic notification settings, incl. `preferred_channel` / `manual_channels` / computed `available_channels` — every manual-send surface needs it to render its channel buttons (#287), so all staff roles except hygienist hold it. | `GET /api/v1/notifications/settings` |
| `notifications.settings.write` | Change clinic notification settings (per-type toggles + channel configuration). Admin only. | `PUT /api/v1/notifications/settings` |

## Role assignment

See `backend/app/core/auth/permissions.py` for the canonical role table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/notifications/__init__.py` (or `module.py`).
2. Add the namespaced form to the relevant role(s) in
   `backend/app/core/auth/permissions.py`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.
