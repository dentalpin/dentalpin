---
module: billing
screen: invoice-series
route: /settings/invoice-series
related_endpoints:
  - GET /api/v1/billing/series
  - POST /api/v1/billing/series
  - POST /api/v1/billing/series/{series_id}/reset
  - PUT /api/v1/billing/series/{series_id}
related_permissions:
  - billing.admin
related_paths:
  - backend/app/modules/billing/frontend/pages/settings/invoice-series/index.vue
  - backend/app/modules/billing/router.py
last_verified_commit: b1b82f5
---

# Series de facturación

Configuración de las series numéricas que asignan número fiscal a las
facturas al emitirlas. Aquí gestionas prefijos, contadores y cuál
está activa por ejercicio.

## De un vistazo

- **Estructura de una serie.** Código (`FAC`, `ABO`, etc.), prefijo
  legible (`FACT-2026-`), contador actual, ejercicio (año), tipo de
  documento (`invoice` o `credit_note`) y si está activa.
- **Activa por tipo y ejercicio.** Solo una serie por tipo y por
  año puede estar activa. Emitir una factura usa la serie activa
  para su tipo y consume su contador.
- **Reset del contador.** Solo si la serie aún no se ha usado en el
  ejercicio actual. Una vez emitida la primera factura, el reset
  queda bloqueado para preservar la auditoría fiscal.
- **Reinicio anual.** Activar *Reiniciar numeración cada año* a mitad de
  ejercicio no reinicia la numeración: las facturas de este año
  siguen desde el último número y la serie vuelve a 1 el próximo
  enero.
- **Permisos.** Toda gestión de series requiere `billing.admin`.
  Otros roles pueden ver el listado pero no editar.

## Crear una serie

> Requiere `billing.admin`.

1. Pulsa **Nueva serie**.
2. Define código, prefijo, ejercicio y tipo (factura o abono).
3. Marca *Activa* si va a sustituir a la actual; al guardar, la
   anterior queda inactiva automáticamente para el mismo (tipo,
   ejercicio).

## Reiniciar contador

> Requiere `billing.admin`. Solo en series sin uso en el ejercicio.

1. Selecciona la serie y pulsa **Reiniciar**.
2. El contador vuelve a 0. La acción se bloquea si ya existe alguna
   factura emitida con esa serie en el ejercicio.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver listado de series | `billing.read` |
| Crear, editar, activar/desactivar, reiniciar | `billing.admin` |

## Resolución de problemas

- **"No se puede reiniciar contador".** Ya hay facturas emitidas
  contra esta serie en el ejercicio actual; bloqueado por
  seguridad. Crea una nueva serie para el siguiente ejercicio.
- **Una nueva factura no asigna número.** No hay serie activa para
  el tipo (factura o abono) y ejercicio actual. Activa o crea una.
- **No veo la opción de editar.** Tu rol no es `billing.admin`.
