---
module: documents
screen: settings_consent-templates
route: /settings/clinical/consent-templates
last_verified_commit: 823a556c
related_endpoints:
  - GET /api/v1/documents/consent-templates
  - POST /api/v1/documents/consent-templates
  - PUT /api/v1/documents/consent-templates/{template_id}
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
  of each text.
- **Create** a template — enter a title (up to 200 characters) and the
  consent text, then **Save template**.
- **Edit** a template — press **Edit template** on its row, change the
  title or text and save. **Cancel** discards the change.

Editing a template does not change consents already created from it: the
text is copied into each consent when it is created. Templates cannot be
deleted or archived from this screen yet.

## Who can use it

Users with `documents.write` (admins and dentists by default). Assistants
can pick a template on the patient card but do not see this page.
