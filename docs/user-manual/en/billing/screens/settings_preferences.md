---
module: billing
screen: settings-preferences
route: /settings/billing/preferences
related_endpoints:
  - GET /api/v1/settings/{module}
  - PATCH /api/v1/settings/{module}
related_permissions:
  - billing.read
  - billing.admin
related_paths:
  - backend/app/modules/billing/frontend/components/BillingSettingsPage.vue
  - frontend/app/components/settings/SettingsModuleForm.vue
  - backend/app/core/settings/router.py
last_verified_commit: 4bceb829
---

# Billing preferences

Clinic-level billing preferences. The screen renders the settings the
billing module declares, so new declarations appear without a hand-built
form. The values are stored with the clinic; invoice issuance keeps the
values entered on each invoice.

## At a glance

- **Default payment term.** Clinic preference for the payment term, in
  days (0 to 365).
- **Invoice footer.** Free text stored with the billing preferences, for
  example payment instructions or a legal note.
- **Bank account.** Account details stored with the billing preferences.
  Both free-text fields accept multiple lines.
- **Permissions.** `billing.read` sees the values; `billing.admin` can
  change them. Fields the role cannot change render disabled.

## Edit the preferences

> Requires `billing.admin`.

1. Open **Settings > Billing > Preferences**.
2. Change the values you need. Only modified fields are submitted.
3. Select **Save**. The screen reloads the stored values and confirms.

Clearing a free-text field removes the stored value; emptying the default
payment term shows an inline message and the save does not run.

## Related screens

- [Invoice series (settings)](./settings_invoice-series.md) - numbering
  prefixes and counters.
