# Changelog — medication_catalog module

## Unreleased

- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.

- Name normalisation now matches the unique index key exactly
  (`lower(btrim(name))`); a duplicate that differed only in inner
  whitespace used to escape the 409 and surface as a raw 500.
- Settings entry is gated on `medication_catalog.read` instead of
  `write`, so dentists (read-only by manifest) can actually open the
  list; write actions stay behind `canWrite`.

## 0.1.0 — initial release

- Clinic-wide medication catalog: name, dose, unit, pharmaceutical
  form (fixed set), prescribable and active status. CRUD under
  Settings → Clinical, no sidebar entry.
- Idempotent 56-item dental seed list: runs on `clinic.created`
  (own session), via `POST /medication_catalog/seed`, and re-runnable
  after imports without duplication.
- Case-insensitive unique names per clinic: service-level 409 plus a
  functional unique index closing the concurrent-create race at the DB.
- Agent tool `list_medications` (READ, cloud-eligible — structured data
  only).
- Search by name, form/status filters, server-side pagination.
- `auto_install=False`, `removable=True`, own Alembic branch
  (`medication_catalog`), uninstall round-trip + tenant isolation +
  duplicate-name + seed idempotency tests.
- Default roles: admin full, dentist read-only.
- Docs: technical overview/events/permissions pages, user manual en+es
  with real `last_verified_commit`, module CHANGELOG, CLAUDE.md tools
  section.
