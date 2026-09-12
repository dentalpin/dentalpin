---
module: razorpay
screen: settings-razorpay
route: /settings/razorpay
related_endpoints:
  - GET /api/v1/razorpay/settings
  - PUT /api/v1/razorpay/settings
related_permissions:
  - razorpay.settings.read
  - razorpay.settings.write
related_paths:
  - backend/app/modules/razorpay/frontend/pages/settings/razorpay/index.vue
last_verified_commit: bd4b52b9
---

# /settings/razorpay

Conecta la cuenta de Razorpay propia de la clínica para que recepción
pueda cobrar pagos mediante UPI, QR, tarjetas y enlaces de pago
directamente desde DentalPin. Se accede desde **Ajustes → Facturación
e impuestos → Razorpay**, o directamente en `/settings/razorpay`.

## Permisos

Solo lectura con `razorpay.settings.read`. Todos los campos y el
botón **Guardar** requieren además `razorpay.settings.write`
(administrador por defecto).

## Secciones

1. **Credenciales de la API**
   - **Modo** — Prueba o Producción. Usa Prueba hasta haber verificado
     un cobro completo de principio a fin con un pago de prueba real
     de Razorpay.
   - **ID de clave** — del panel de Razorpay. No es secreto; el
     navegador lo necesita para abrir el pago de Razorpay.
   - **Clave secreta** — del panel de Razorpay. Solo escritura: una
     vez guardada, el campo siempre aparece vacío con un aviso de que
     ya hay una clave configurada. Déjalo en blanco en un guardado
     posterior para mantener la existente; escribe un valor nuevo solo
     para reemplazarla.
   - **Activo** — solo una conexión activa y totalmente configurada se
     ofrece a recepción como método de cobro. Desactívalo para ocultar
     la acción "Cobrar con Razorpay" sin perder las credenciales
     guardadas.
2. **Webhook**
   - **URL del webhook** — una URL de solo lectura específica de esta
     clínica (incluye el id de la propia clínica). Cópiala en la
     configuración de webhooks del panel de Razorpay para esta cuenta.
   - **Secreto del webhook** — el secreto con el que Razorpay firma
     los eventos del webhook, disponible en la misma pantalla del
     panel donde se creó el webhook. También es solo escritura.
   - **Estado del webhook** — las últimas marcas de tiempo de
     recepción/procesamiento y el último tipo de evento, para que un
     administrador pueda ver de un vistazo si Razorpay realmente está
     llegando a esta clínica. Si Razorpay reporta un problema, aquí
     también aparece el último error y cuándo ocurrió.

## Qué hace Guardar — y qué no hace

Guardar almacena la configuración; **no** verifica que el par
clave/secreto realmente funcione, ni que el webhook sea accesible — la
única forma de confirmarlo es probar un cobro real (en modo Prueba) y
comprobar que el bloque de estado del webhook se actualiza después.
Esta pantalla no tiene un botón de "Probar conexión" en esta versión.

## Pantallas relacionadas

- `/payments` — donde aparece "Cobrar con Razorpay" en cuanto esta
  pantalla muestra **Activo** con una clave secreta y un secreto de
  webhook configurados.
