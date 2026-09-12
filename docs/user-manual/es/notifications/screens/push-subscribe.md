---
module: notifications
screen: push-subscribe
route: /p/push/[token]
related_endpoints:
  - POST /api/v1/notifications/push/subscribe-tokens
  - GET /api/v1/notifications/public/push/subscribe/{token}
  - POST /api/v1/notifications/public/push/subscribe/{token}
related_permissions:
  - notifications.push.write
related_paths:
  - backend/app/modules/notifications/frontend/pages/p/push/[token].vue
---

# Suscripción push (paciente)

Página pública de consentimiento (sin login — el token de un solo
uso es la autenticación). La generación del token es solo por API
por ahora (POST subscribe-tokens); el paciente abre el enlace, ve
qué clínica lo pide y pulsa Activar. El navegador registra el service worker y canjea el
token con su suscripción. Los enlaces caducados/usados muestran un
mensaje con instrucciones para pedir uno nuevo a la clínica.
