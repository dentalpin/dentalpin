---
module: sms_gateway
last_verified_commit: 0f333000
---

# sms_gateway — permissions

Returned by `SmsGatewayModule.get_permissions()`
(relative names; the registry namespaces them as `sms_gateway.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `sms_gateway.settings.read` | View masked provider config, list registered providers | `GET /api/v1/sms_gateway/settings`, `GET /api/v1/sms_gateway/providers` |
| `sms_gateway.settings.write` | Select provider, store credentials, dry-run | `PUT /api/v1/sms_gateway/settings`, `POST /api/v1/sms_gateway/test` |

## Role assignment

Strictly admin (`*` wildcard). Provider credentials are admin
secrets; no other role holds these permissions in v1.

See `backend/app/modules/sms_gateway/__init__.py` for the canonical role table.
