---
module: razorpay
last_verified_commit: 8b8e9375
---

# razorpay — permissions

Namespaced by the registry from the module's `get_permissions()`.

| Permission | Gates | Endpoints |
|------------|-------|-----------|
| `razorpay.settings.read` | View connection status (masked) | `GET /api/v1/razorpay/settings` |
| `razorpay.settings.write` | Manage mode/credentials/webhook secret/active flag | `PUT /api/v1/razorpay/settings` |

Default role mapping: **admin only** (`role_permissions = {"admin": ["*"]}`).

Gateway collection/refund actions (the "Collect via Razorpay" panel,
transaction detail, refund-via-Razorpay) are gated by `payments`' own
`payments.record.{read,write,refund}` — see
`docs/technical/payment_gateways/permissions.md`. This module declares
no permission for those.

## Public endpoint (no permission)

`POST /api/v1/razorpay/webhook/{clinic_id}` is unauthenticated by
design (vendor callback). It is protected by a per-clinic HMAC
signature (`X-Razorpay-Signature`) verified against that clinic's own
configured webhook secret, plus a rate limit. Never trust the
`clinic_id` path segment for anything beyond selecting which secret to
verify against.
