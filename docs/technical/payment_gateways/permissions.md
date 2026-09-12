---
module: payment_gateways
last_verified_commit: 8b8e9375
---

# payment_gateways — permissions

This module declares **no permissions of its own**
(`get_permissions()` → `[]`). Every endpoint reuses `payments`' own
permission strings — initiating a gateway collection or refund *is*
recording a payment/refund in every way that matters to an authorizer,
and a module-own permission would only drift out of sync with
payments' role grants (same precedent as india_gst reusing
`billing.write` for draft-invoice GST fields).

| Permission (owned by `payments`) | Gates | Endpoints |
|------------|-------|-----------|
| `payments.record.read` | View a request/refund's status, gateway info for a payment | `GET /requests/{id}`, `GET /payments/{id}/gateway-info`, `GET /refunds/{id}`, `GET /payments/{id}/refunds` |
| `payments.record.write` | Start a collection, refresh status, cancel | `POST /requests`, `POST /requests/{id}/refresh`, `POST /requests/{id}/cancel` |
| `payments.record.refund` | Start a gateway refund | `POST /refunds` |

Default role mapping is whatever `payments`' own `role_permissions`
already grants — see `docs/technical/payments/permissions.md`. No
`role_permissions` entry in this module's manifest maps to a
module-namespaced permission (it declares `{"admin": ["*"]}` only to
satisfy the manifest-consistency test's "every module has at least
admin" invariant, which is a no-op since there is nothing under
`payment_gateways.*` to grant).

## Public endpoints

None. Every route requires authentication + one of the permissions
above.
