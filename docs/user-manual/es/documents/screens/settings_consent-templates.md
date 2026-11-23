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

# Plantillas de consentimiento

Se encuentra en **Configuración → Clínico → Plantillas de consentimiento**.
Aquí la clínica guarda los textos de los consentimientos informados que
los pacientes firman en la tablet. La ficha del paciente solo permite
elegir una plantilla; crearlas y editarlas se hace en esta pantalla.

## Qué puedes hacer

- **Ver** las plantillas de la clínica, ordenadas por título, con las
  primeras líneas de cada texto. Las plantillas archivadas también se
  muestran, atenuadas y marcadas como **Archivada**.
- **Crear** una plantilla — escribe un título (hasta 200 caracteres) y el
  texto del consentimiento, y pulsa **Guardar plantilla**.
- **Editar** una plantilla — pulsa **Editar plantilla** en su fila,
  cambia el título o el texto y guarda. **Cancelar** descarta el cambio.

- **Archivar** una plantilla — pulsa **Archivar** en su fila cuando la
  clínica ya no la use. Una plantilla archivada deja de aparecer en el
  selector de la ficha del paciente, así que no se pueden crear nuevos
  consentimientos con ella.
- **Restaurar** una plantilla archivada — pulsa **Restaurar** para que
  vuelva a estar disponible.

Editar o archivar una plantilla no modifica los consentimientos ya
creados a partir de ella: el texto se copia a cada consentimiento al
crearlo, y esos consentimientos siguen visibles y se pueden firmar o
revocar. Las plantillas no se pueden eliminar.

## Quién puede usarlo

Quien tenga `documents.write` (administradores y dentistas por defecto).
Los auxiliares pueden elegir una plantilla en la ficha del paciente,
pero no ven esta pantalla.
