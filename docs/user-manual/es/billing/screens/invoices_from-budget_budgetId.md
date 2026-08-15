---
module: billing
screen: from-budget
route: /invoices/from-budget/[budgetId]
related_endpoints:
  - GET /api/v1/billing/series
  - GET /api/v1/billing/settings
  - GET /api/v1/budget/budgets/{budget_id}
  - POST /api/v1/billing/invoices/from-budget/{budget_id}
related_permissions:
  - billing.read
  - billing.write
related_paths:
  - backend/app/modules/billing/frontend/pages/invoices/from-budget/[budgetId].vue
  - backend/app/modules/billing/router.py
last_verified_commit: 6c91240
---

# Factura desde presupuesto

Asistente para emitir una factura a partir de un presupuesto aceptado
del módulo `budget`. Permite **facturar total o parcialmente**: por
defecto todos los ítems sin facturar, pero puedes elegir qué líneas
y qué cantidades incluir.

## De un vistazo

- **Solo desde presupuestos aceptados.** Si el presupuesto no está
  en estado `accepted` (o tiene una factura activa sin cancelar),
  el botón *Crear factura* en el detalle del presupuesto no
  aparece.
- **Marcado por ítem.** Cada línea del presupuesto muestra `cantidad
  facturada / cantidad total`. Solo puedes añadir la diferencia o
  parte de ella; el backend rechaza superar la cantidad
  pendiente.
- **Snapshot de precios.** Las líneas se copian del presupuesto con
  su precio e IVA del momento — así la factura no se ve afectada
  por cambios posteriores del catálogo.
- **Los descuentos viajan con las líneas.** El descuento por línea
  **y** el descuento global del presupuesto (repartido entre las
  líneas, sin IVA) se escriben en cada línea de la factura — la
  factura suma lo que el paciente firmó. En facturación parcial el
  descuento se prorratea por la cantidad facturada. La vista previa
  muestra las mismas cifras que tendrá la factura.
- **Receptor.** Por defecto el paciente. Puedes definir un pagador
  distinto (compañía, mutua, familiar) antes de emitir.

## Facturar desde presupuesto

> Requiere `billing.write`.

1. Llega aquí desde el detalle del presupuesto (*Crear factura*).
2. Revisa la lista: marca o desmarca líneas y ajusta cantidades a
   facturar.
3. Si la factura va a un tercero, configura el pagador distinto.
4. **Crear factura**. Se invoca
   `POST /billing/invoices/from-budget/{budget_id}` con los ítems
   seleccionados. La factura nace en `draft` con los snapshots
   copiados.
5. Para emitirla, abre el [detalle](./invoices_id.md) y pulsa
   **Emitir**.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Cargar el asistente y ver el presupuesto | `billing.read` |
| Crear la factura | `billing.write` |

## Resolución de problemas

- **El botón *Crear factura* no estaba en el presupuesto.** El
  presupuesto no está en `accepted`, ya tiene una factura no
  cancelada o todos los ítems están facturados al 100%.
- **El backend devuelve 400 al crear.** Has marcado más cantidad de
  la pendiente. Comprueba `invoiced_quantity` vs `quantity` en cada
  ítem.
- **Falta una línea del presupuesto.** Está marcada como ya
  facturada al 100% (`invoiced_quantity == quantity`). Para revertir,
  anula la factura previa y vuelve a entrar aquí.
