# Changelog — contacts module

## Unreleased

- fix(#1245): the contact search: a typed `%` or `_` now matches literally, as in payments (#1033). `%` used to list every row, and `ana_lopez` also matched `ana.lopez`.
- fix(#976): `PATCH` with `null` for `name`, `contact_type` or `is_active` is a 422 (was a 500 from the NOT NULL column).

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- feat(i18n): Hindi (`hi`) locale for the module's frontend layer.
- test(#552): branch-scoped uninstall round-trip test (heads, branch downgrade, reinstall).

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- feat(#232): sidebar entry grouped under the Inventory header (`nav.section` "inventory").
- feat(#334): Hungarian (hu) locale for the module's frontend layer.

- feat(i18n): Arabic (ar) locale for the module's frontend layer.

- feat(#131): German (de) locale for the module's frontend layer.

- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.
- Initial version: lab/supplier/other contact CRUD, name search, type
  filter, soft delete, EN/ES/FR translations.
- Review fixes: dropped the frontend coupling to the not-yet-existing
  `suppliers` / `supplier_ratings` modules, `auto_install=False`,
  POST returns 201 and DELETE 204, delete asks for confirmation,
  type filter is clearable, `nav.contacts` added to host locales.
