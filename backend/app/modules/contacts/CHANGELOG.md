# Changelog — contacts module

## Unreleased

- feat(#131): German (de) locale for the module's frontend layer.

- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.
- Initial version: lab/supplier/other contact CRUD, name search, type
  filter, soft delete, EN/ES/FR translations.
- Review fixes: dropped the frontend coupling to the not-yet-existing
  `suppliers` / `supplier_ratings` modules, `auto_install=False`,
  POST returns 201 and DELETE 204, delete asks for confirmation,
  type filter is clearable, `nav.contacts` added to host locales.
