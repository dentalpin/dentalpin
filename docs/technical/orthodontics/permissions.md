# orthodontics - permissions

| Permission | admin | dentist | hygienist | assistant | receptionist | Endpoints |
|---|---|---|---|---|---|---|
| `orthodontics.cases.read` | ✓ | ✓ | ✓ | ✓ | ✓ | `GET /cases`, `GET /cases/{id}`, `GET /cases/{id}/controls`, `GET /settings` |
| `orthodontics.cases.write` | ✓ | ✓ | | ✓ | | `POST /cases`, `PATCH /cases/{id}`, `POST /cases/{id}/status` |
| `orthodontics.controls.write` | ✓ | ✓ | ✓ | ✓ | | `POST /cases/{id}/controls`, `PATCH /controls/{id}` |
| `orthodontics.settings.manage` | ✓ | ✓ | | | | (slice-b settings UI; seeds are read-side) |

User-facing permissions are mirrored in
`frontend/app/config/permissions.ts` (`PERMISSIONS.orthodontics.*`).
Photo upload inside the case sheet additionally requires
`media.documents.write` (hygienists see photos read-only).
