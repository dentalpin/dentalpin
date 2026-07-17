# Contacts module

Directory of external labs, suppliers, and other providers. Custom clinic
module — standalone, no dependency on any other module. Intended as the
foundation for the future lab-work-order module (Phase 3 of the clinic's
custom roadmap): an order will link to a contact created here.

## Public API

Routes mounted at `/api/v1/contacts/`.

- `GET    /contacts`          — list, filterable by type/name search; `contacts.read`
- `GET    /contacts/{id}`     — single contact; `contacts.read`
- `POST   /contacts`          — create; `contacts.write`
- `PATCH  /contacts/{id}`     — edit; `contacts.write`
- `DELETE /contacts/{id}`     — soft-delete (sets `is_active=false`); `contacts.write`

Deletion is soft (not a real database delete) so that once lab-order
history exists in Phase 3, an old order can still show which lab it went
to, even if that lab is no longer active.

## Dependencies

`manifest.depends = []` — standalone.

## Permissions

`contacts.read`, `contacts.write`. Default role grants: admin full access;
dentist/hygienist read-only; assistant/receptionist read+write (front-desk
staff are the ones expected to manage this directory day-to-day). Adjust
`role_permissions` in `__init__.py` to change this.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_contacts` | READ | `ContactService.list_contacts` | `contacts.read` |
| `create_contact` | WRITE | `ContactService.create_contact` | `contacts.write` |

## Events emitted / consumed

None.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=True`.
- Migrations on the `contacts` Alembic branch, chained directly off the
  core `0001` migration (no cross-module foreign keys).

## CHANGELOG

See `./CHANGELOG.md`.
