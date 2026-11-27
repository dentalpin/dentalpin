---
module: documents
screen: settings_consent-templates
route: /settings/clinical/consent-templates
last_verified_commit: f8114943
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

## Formatting the text

The consent text is plain text with a small set of Markdown-style
formatting. The patient sees it on the tablet and it is printed the same
way in the signed PDF.

| Type this | You get |
|-----------|---------|
| `# Title` | Large heading |
| `## Subtitle` or `### Smaller subtitle` | Smaller headings |
| `**text**` | **Bold** |
| `*text*` | *Italic* |
| `- item` or `* item` at the start of a line | Bulleted list |
| `1. item` at the start of a line | Numbered list |
| A blank line | New paragraph |

A line break inside a paragraph is kept as written. Anything else is shown
exactly as typed: HTML, links, images and tables are not supported and
appear as plain text. Existing templates look the same as before when
they are plain paragraphs and line breaks. Two things change: several spaces
in a row and indentation at the start of a line collapse into a single space,
and lines that start with `- ` or `1. ` become lists (numbered lists keep the
numbers you typed). A short reminder of this syntax appears under the text box.

Example:

```
# Tooth extraction

You are going to have **one tooth removed** under local anaesthesia.

## Possible risks
- Bleeding
- Swelling for 2-3 days

## After the procedure
1. Bite on the gauze for 30 minutes
2. Avoid hot drinks today
```

## Variables (blanks filled in for you)

Instead of leaving blanks such as `Patient: ____` for staff to fill in by
hand, write a variable in the text. It is replaced when a consent is created
from the template, so the professional sees the filled text, can still edit
it before the patient signs, and the signed PDF shows exactly what was on
screen. The template itself keeps the variable.

| Write this | It becomes |
|------------|-----------|
| `{{ patient_name }}` | The patient's full name |
| `{{ patient_id_document }}` | The patient's ID document number (DNI/NIE/passport) |
| `{{ patient_birth_date }}` | The patient's date of birth |
| `{{ clinic_name }}` | The clinic name, as printed in the PDF header |
| `{{ professional_name }}` | The name of the user creating the consent |
| `{{ professional_license }}` | That user's professional licence number |
| `{{ date }}` | Today's date, in the clinic's language format |

If the value is not on file (for example the patient has no ID document
recorded), a visible `____` is inserted so you notice it and can type it in
while editing the consent. A name that is not in the list is left exactly as
written and the patient card shows a warning. Values are inserted as plain
text: a patient called `*Ana*` is printed as `*Ana*`, not in italics.
Existing consents are never changed. A short list of the variables appears
under the text box.

## Who can use it

Users with `documents.write` (admins and dentists by default). Assistants
can pick a template on the patient card but do not see this page.
