# Changelog — lab_orders module

## Unreleased

- feat(#131): German (de) locale for the module's frontend layer.
- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.

## 0.1.0 — initial release

- Lab work order create/read/update with status tracking (`sent` →
  `in_progress` → `ready` → `received` / `cancelled`), auto-stamping
  `received_date` on the transition into `received`. No hard delete —
  cancellation is a status change.
- Patient + laboratory-contact linkage, clinic-scoped on every query,
  validation and agent tool; display-name enrichment.
- Prosthodontic fields: impression type, antagonist information and
  Vita Classical shade.
- Status changes publish `lab_order.status_changed` transactionally
  (ADR 0019); no bundled subscriber.
- Agent tools: `list_lab_orders`, `create_lab_order`,
  `update_lab_order_status`.
- `auto_install=False`, `removable=True`; own Alembic branch with
  uninstall round-trip and tenant-isolation service tests.
- EN/ES/FR/PT/TA locales; technical overview/events/permissions pages;
  bilingual user manual; searchable sidebar entries gated by role.

