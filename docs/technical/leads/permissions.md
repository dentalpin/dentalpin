---
module: leads
last_verified_commit: dd2611ce
---

# leads — permissions

Namespaced by the registry from the module `get_permissions()`
(`["read", "write", "settings.read", "settings.write"]`). One row per endpoint:

| Permission | Endpoint | Gates |
|---|---|---|
| `leads.read` | `GET /api/v1/leads/` | list, filter by `status`, search, page, sort |
| `leads.read` | `GET /api/v1/leads/{lead_id}` | one lead; 404 for an unknown **or** other-clinic id |
| `leads.write` + `patients.read` | `POST /api/v1/leads/` | manual creation by the front desk; returns the `lead_created` / `recall_queued` union and, on a match, the matched patient name |
| `leads.write` | `PATCH /api/v1/leads/{lead_id}` | edit a lead (all-optional body, `exclude_unset`); marking `converted` by hand does **not** create a patient |
| `leads.write` + `patients.write` | `POST /api/v1/leads/{lead_id}/convert` | create the patient and link the lead; 409 if already converted |
| `leads.settings.read` | `GET /api/v1/leads/settings` | cap, today gauge, intake-key status (never the key) |
| `leads.settings.write` | `PATCH /api/v1/leads/settings` | set `daily_cap` (`0..5000`, `0` = unlimited); never resets `day_count` |
| `leads.settings.write` | `POST /api/v1/leads/settings/intake-key/rotate` | create or rotate the intake key; plaintext returned **once** |
| `leads.settings.write` | `PATCH /api/v1/leads/settings/intake-key` | `{is_active}` — the kill switch; 404 when no key exists yet |
| — (no permission) | `POST /api/v1/leads/public/intake` | the clinic website form. `X-Lead-Key` **is** the auth: no clinic context, no `require_permission` |

## Why two permissions on two routes

Cross-module disclosure or write carries that module permission too:

- `POST /api/v1/leads/` returns `recalled_patient` (a `PatientBrief`) when the
  enquiry matched a patient, so it needs `patients.read` as well as
  `leads.write`. A `leads.write`-only role gets 403 on that branch.
- `POST /api/v1/leads/{lead_id}/convert` creates a patient record, so it needs
  `patients.write`. Dropping it would let a `leads.write`-only role create
  patients.

## Role defaults

`manifest.role_permissions` grants **admin** `*`, **dentist** `read`,
**assistant** and **receptionist** `read` + `write`, **hygienist** none.

`leads.settings.read` and `leads.settings.write` are granted to **no role
except admin** (through the `*` wildcard) — on purpose: the intake key is a
secret and rotating it breaks the clinic website until a human pastes the new
key in, so it belongs to whoever owns the website. Do not grant
`settings.write` to `receptionist` to make a flood easier to handle.

## Public endpoint (no permission)

`POST /api/v1/leads/public/intake` is unauthenticated by design: the caller is
the clinic website, which has no JWT. Protection is the per-clinic intake key
(`X-Lead-Key`, SHA-256 hashed at rest, one per clinic, revocable), the honeypot,
the 8 KB body cap, the per-clinic daily cap and the rate
limits. It returns the same body in every routing branch, so it can never be
used to ask "is this phone one of your patients?".