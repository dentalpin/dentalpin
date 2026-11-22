---
module: accounting_export
last_verified_commit: f70d47ff
---

# Exportar a gestoría

Este módulo opcional genera un fichero descargable con las **facturas** y
los **cobros** de un periodo para entregárselo a tu gestoría, sin tener
que copiarlos a mano desde la aplicación.

El módulo **solo exporta** datos de facturación ya existentes: no crea
facturas ni documentos fiscales nuevos.

## Pantallas

- [Exportar a gestoría](./screens/accounting-export.md) — elige el
  periodo, previsualiza y descarga el ZIP.

## Qué se exporta

Se exportan únicamente las **facturas emitidas** y los **cobros
asignados a esas facturas**. Los cobros no ligados a ninguna factura no
aparecen, y nunca se cruza lo cobrado con lo facturado.

El ZIP contiene dos ficheros CSV:

- `facturas.csv` — número, serie, fecha, cliente, NIF, base, tipo de
  IVA, cuota de IVA, total y estado.
- `cobros.csv` — fecha del cobro, factura, importe, método y referencia.
  Una devolución aparece como una fila propia con importe **negativo**, en
  el día en que se devolvió.

## Referencia rápida

| Acción | Permiso |
|--------|---------|
| Ver la página y previsualizar | `accounting_export.export.read` |
| Descargar el export | `accounting_export.export.run` |

Por defecto solo el rol **administrador** tiene estos permisos.

## Módulos relacionados

- **Facturación** — origen de las facturas y de los cobros asignados.
- **Pagos** — aporta el método, la fecha y la referencia de cada cobro.
