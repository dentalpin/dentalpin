---
module: documents
screen: settings_consent-templates
route: /settings/clinical/consent-templates
last_verified_commit: cf47bbfb
related_endpoints:
  - GET /api/v1/documents/consent-templates
  - POST /api/v1/documents/consent-templates
  - PUT /api/v1/documents/consent-templates/{template_id}
  - POST /api/v1/documents/consent-templates/{template_id}/archive
  - POST /api/v1/documents/consent-templates/{template_id}/unarchive
related_permissions:
  - documents.write
related_paths:
  - backend/app/modules/documents/frontend/components/settings/DocumentsConsentTemplatesPage.vue
  - backend/app/modules/documents/frontend/plugins/settings.client.ts
---

# Consent templates

Found under **Settings → Clinical → Consent templates**. It is where the
clinic keeps the texts used for informed consents that patients sign on
the tablet. The patient card only lets staff pick a template; creating
and editing happens here.

## What you can do

- **See** the clinic's templates, ordered by title, with the first lines
  of each text. Archived templates are listed too, muted and marked
  **Archived**.
- **Create** a template — enter a title (up to 200 characters) and the
  consent text, then **Save template**.
- **Edit** a template — press **Edit template** on its row, change the
  title or text and save. **Cancel** discards the change.

- **Archive** a template — press **Archive** on its row when the clinic no
  longer uses it. An archived template disappears from the template
  select on the patient card, so no new consent can be created from it.
- **Restore** an archived template — press **Restore** to make it
  available again.

Editing or archiving a template does not change consents already created
from it: the text is copied into each consent when it is created, and
those consents stay visible and can still be signed or revoked. Templates
cannot be deleted.

## Who can use it

Users with `documents.write` (admins and dentists by default). Assistants
can pick a template on the patient card but do not see this page.
