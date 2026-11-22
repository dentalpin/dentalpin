# Changelog — lab_orders module

## Unreleased

- fix(#976): `PATCH` with `null` for `lab_contact_id`, `work_type` or `status` is a 422 (was a 500 from the NOT NULL column).

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- fix(#718): `received_date` is stamped with the clinic's calendar date, not
  the server's.
- feat(i18n): Hindi (`hi`) locale for the module's frontend layer.

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- fix(#522): the `sent_date` default read the UTC day rather than the local
  one. Now uses `toISODate`.

- feat(#232): sidebar entries grouped under the Lab header (`nav.section` "lab").
- feat(#334): Hungarian (hu) locale for the module's frontend layer.

- feat(i18n): Arabic (ar) locale for the module's frontend layer.

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

