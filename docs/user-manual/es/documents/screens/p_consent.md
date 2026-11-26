---
module: documents
screen: p_consent
route: /p/consent
last_verified_commit: f8114943
related_endpoints:
  - GET /api/v1/documents/public/consents/current
  - POST /api/v1/documents/public/consents/current/sign
related_paths:
  - backend/app/modules/documents/frontend/pages/p/consent/index.vue
---

# Firma de consentimiento en tablet

Abre el enlace facilitado por la clínica en la tablet sin una sesión del personal. Lee el texto, indica si firmas como paciente, tutor o representante y escribe tu nombre. Dibuja la firma y confirma. El enlace caduca a los 30 minutos y solo admite una firma. Para revocar un consentimiento se utiliza otro enlace y se recoge una firma independiente.

El personal puede mostrar un código QR o copiar el enlace para abrirlo en la tablet. El administrador debe configurar en `ALLOWED_ORIGINS` la dirección pública de la aplicación como primer origen. Las vistas previas sin firmar llevan la marca BORRADOR; una revocación firmada se identifica como revocada.

El texto del consentimiento puede incluir títulos, negrita, cursiva y listas. Se muestra ya formateado y se imprime igual en el PDF firmado.
