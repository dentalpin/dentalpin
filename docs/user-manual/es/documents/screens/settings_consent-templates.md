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

## Dar formato al texto

El texto del consentimiento es texto plano con un pequeño conjunto de
formato tipo Markdown. El paciente lo ve en la tablet y se imprime igual
en el PDF firmado.

| Escribe | Obtienes |
|---------|----------|
| `# Título` | Título grande |
| `## Subtítulo` o `### Subtítulo menor` | Títulos más pequeños |
| `**texto**` | **Negrita** |
| `*texto*` | *Cursiva* |
| `- elemento` o `* elemento` al inicio de línea | Lista con viñetas |
| `1. elemento` al inicio de línea | Lista numerada |
| Una línea en blanco | Párrafo nuevo |

Un salto de línea dentro de un párrafo se conserva tal como se escribe.
Todo lo demás se muestra tal cual: no se admiten HTML, enlaces, imágenes
ni tablas, y aparecen como texto. Las plantillas existentes sin formato se
ven igual que antes. Bajo el cuadro de texto aparece un breve recordatorio
de esta sintaxis.

Ejemplo:

```
# Extracción dental

Se le va a extraer **una pieza dental** con anestesia local.

## Riesgos posibles
- Sangrado
- Inflamación durante 2-3 días

## Después de la intervención
1. Muerda la gasa durante 30 minutos
2. Evite bebidas calientes hoy
```

## Quién puede usarlo

Quien tenga `documents.write` (administradores y dentistas por defecto).
Los auxiliares pueden elegir una plantilla en la ficha del paciente,
pero no ven esta pantalla.
