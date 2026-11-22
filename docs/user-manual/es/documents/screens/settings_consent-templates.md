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

# Plantillas de consentimiento

Se encuentra en **Configuración → Clínico → Plantillas de consentimiento**.
Aquí la clínica guarda los textos de los consentimientos informados que
los pacientes firman en la tablet. La ficha del paciente solo permite
elegir una plantilla; crearlas y editarlas se hace en esta pantalla.

## Qué puedes hacer

- **Ver** las plantillas de la clínica, ordenadas por título, con las
  primeras líneas de cada texto.
- **Crear** una plantilla — escribe un título (hasta 200 caracteres) y el
  texto del consentimiento, y pulsa **Guardar plantilla**.
- **Editar** una plantilla — pulsa **Editar plantilla** en su fila,
  cambia el título o el texto y guarda. **Cancelar** descarta el cambio.

Editar una plantilla no modifica los consentimientos ya creados a partir
de ella: el texto se copia a cada consentimiento al crearlo. Por ahora
las plantillas no se pueden eliminar ni archivar desde esta pantalla.

## Quién puede usarlo

Quien tenga `documents.write` (administradores y dentistas por defecto).
Los auxiliares pueden elegir una plantilla en la ficha del paciente,
pero no ven esta pantalla.
