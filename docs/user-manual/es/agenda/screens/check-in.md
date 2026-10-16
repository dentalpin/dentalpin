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
last_verified_commit: 693ea9f45713ec91219886dc89a1cf4d194d0e07
---

# Registro con QR (página del paciente)

Página pública del código QR de una cita o del enlace del
recordatorio. Sin cuenta ni inicio de sesión — el token de la URL es
toda la credencial (una sola cita).

## Lo que ve el paciente

- **QR del mostrador** (escaneado en la clínica): registra
  automáticamente.
- **Enlace del recordatorio** (del email/SMS): muestra un botón de
  confirmación y solo registra al pulsarlo, así los pre-lectores de
  correo nunca pueden registrar a nadie.
- **Registrado** si todo va bien. Reescanear el mismo código
  simplemente confirma el estado actual.
- **Demasiado pronto / registro cerrado** fuera de la ventana de la
  cita (dos horas antes del inicio hasta una hora después del fin),
  con la hora de la cita.
- **Código no válido** si el token caducó, es falso o está mal
  escrito, con botón para reintentar.
