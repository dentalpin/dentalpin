---
module: notifications
screen: notification_templates
route: /settings/communications/templates
related_endpoints:
  - GET /api/v1/notifications/templates/editor/{template_key}
  - POST /api/v1/notifications/templates/editor/{template_key}/preview
  - PUT /api/v1/notifications/templates/editor/{template_key}
  - DELETE /api/v1/notifications/templates/editor/{template_key}
related_permissions:
  - notifications.templates.read
  - notifications.templates.write
related_paths:
  - backend/app/modules/notifications/frontend/components/settings/NotificationTemplatesPage.vue
last_verified_commit: 0000000
---

# Notification templates

Open **Settings → Notifications → Templates**. Select a message type,
channel, and template language. The status shows whether that combination
uses clinic text or a system default, or has no system text.

- **Email** supports a subject, an HTML body, and optional plain text.
- **WhatsApp** supports plain text when the clinic has selected manual WhatsApp.
  Use the provider settings for approved WhatsApp templates.
- **SMS and Web Push** show the configured copy in read-only mode.

Choose a variable to insert it in the last focused field. Some fields are
optional. You can omit optional sample values in the preview to check that
your template still reads correctly. The preview uses fictional examples.
Save after checking the result. The server reports syntax and variable
errors next to the affected field.

To remove a clinic override, choose **Restore default** and confirm. Any
provider mapping is preserved. A WhatsApp variant with **No system text**
has no copy to fall back to. Existing drafts keep the text already prepared
for staff.

## Permissions

- `notifications.templates.read` allows viewing and previewing.
- `notifications.templates.write` allows saving and restoring.
