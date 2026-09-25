---
module: agenda
screen: check-in
route: /p/check-in/[token]
related_endpoints:
  - POST /api/v1/agenda/public/check-in/{token}
related_permissions: []
related_paths:
  - backend/app/modules/agenda/frontend/pages/p/check-in/[token].vue
  - backend/app/modules/agenda/router.py
last_verified_commit: cf863c34c6bcf3ccfdfb5b1de38a03700ea44cbd
---

# Registro con QR (página del paciente)

Página pública del código QR de una cita. Sin cuenta ni inicio de
sesión — el token de la URL es toda la credencial (válido 15
minutos, una sola cita).

## Lo que ve el paciente

- **Registrando…** mientras se canjea el código.
- **Registrado** si todo va bien. Reescanear el mismo código
  simplemente confirma el estado actual.
- **Código no válido** si el token caducó, es falso o está mal
  escrito, con botón para reintentar.
