---
module: payroll
screen: profiles
route: /payroll/profiles
last_verified_commit: 0b59a2a2
related_endpoints:
  - GET /api/v1/payroll/profiles
  - POST /api/v1/payroll/profiles
  - PATCH /api/v1/payroll/profiles/{id}
  - GET /api/v1/auth/users
related_permissions:
  - payroll.read
  - payroll.write
related_paths:
  - backend/app/modules/payroll/frontend/pages/payroll/profiles/index.vue
---

# Perfiles

En la entrada **Perfiles** de la nómina (solo admin). La lista muestra
una tarjeta por perfil con tipo de pago, importe base, moneda y marcas
bancarias enmascaradas (`···1234` — el texto plano nunca se muestra).

## Qué puedes hacer

- **Crear** un perfil: elige al empleado del personal de la clínica,
  fija condiciones mensuales/por horas, importe base y moneda, y adjunta
  cuenta bancaria y NIF si hace falta (solo escritura).
- **Editar** condiciones: secretos con reemplazo — deja el campo vacío
  para mantener el valor, rellénalo para rotarlo. Desactiva con el
  interruptor en vez de eliminar.
