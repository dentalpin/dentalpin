---
module: billing
screen: settings-preferences
route: /settings/billing/preferences
related_endpoints:
  - GET /api/v1/settings/{module}
  - PATCH /api/v1/settings/{module}
related_permissions:
  - billing.read
  - billing.admin
related_paths:
  - backend/app/modules/billing/frontend/components/BillingSettingsPage.vue
  - frontend/app/components/settings/SettingsModuleForm.vue
  - backend/app/core/settings/router.py
last_verified_commit: 9b2483eb491d80c7ceeef0aee2500d9458549047
---

# Preferencias de facturación

Preferencias de facturación de la clínica. La pantalla se genera a partir
de las declaraciones del módulo de facturación, así que las nuevas
declaraciones aparecen sin un formulario hecho a mano. Los valores se
guardan con la clínica; la emisión de facturas conserva los valores
introducidos en cada factura.

## De un vistazo

- **Plazo de pago por defecto.** Preferencia de la clínica para el plazo
  de pago, en días (de 0 a 365).
- **Pie de factura.** Texto libre guardado con las preferencias de
  facturación, por ejemplo instrucciones de pago o una nota legal.
- **Cuenta bancaria.** Datos de la cuenta guardados con las preferencias
  de facturación. Los dos campos de texto libre admiten varias líneas.
- **Permisos.** `billing.read` ve los valores; `billing.admin` puede
  cambiarlos. Los campos que el rol no puede cambiar se muestran
  deshabilitados.

## Editar las preferencias

> Requiere `billing.admin`.

1. Abre **Ajustes > Facturación > Preferencias**.
2. Cambia los valores necesarios. Solo se envían los campos modificados.
3. Pulsa **Guardar**. La pantalla recarga los valores guardados y confirma.

Vaciar un campo de texto libre borra el valor guardado; si se vacía el
plazo de pago por defecto, la pantalla muestra un aviso y no guarda.

## Pantallas relacionadas

- [Series de facturación (ajustes)](./settings_invoice-series.md) - prefijos
  y contadores de numeración.
