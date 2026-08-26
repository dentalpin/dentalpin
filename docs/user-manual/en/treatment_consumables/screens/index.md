---
module: treatment_consumables
screen: index
route: /treatment-consumables
related_endpoints:
  - GET /api/v1/treatment_consumables
  - POST /api/v1/treatment_consumables
  - PATCH /api/v1/treatment_consumables/{id}
  - DELETE /api/v1/treatment_consumables/{id}
  - GET /api/v1/treatment_consumables/link-options
related_permissions:
  - treatment_consumables.read
  - treatment_consumables.write
related_paths:
  - backend/app/modules/treatment_consumables/frontend/pages/treatment-consumables/index.vue
last_verified_commit: 38a49ffe
---

# Treatment consumables

Maps each catalog treatment to the inventory items it uses, and how
many of them (e.g. root canal → 2 anesthetic vials). Pure mapping:
stock is **not** deducted automatically.

## What you can do

- **Link a consumable**: each side has its own search box — find a
  treatment, find an inventory item, set the quantity and an optional
  note ("per session", "only if surgery"), confirm. Both sides are
  validated against your clinic; linking the same pair twice is
  rejected with a message.
- **Edit** the quantity and the note of any existing link.
- **Unlink** with confirmation.
- The history table shows every link with resolved names from both
  modules, the quantity with the item's own unit, and the note.
  Newest first, paginated.

## Who can use it

Admins manage links; dentists have read access. Requires the
`inventory` module to be installed.
