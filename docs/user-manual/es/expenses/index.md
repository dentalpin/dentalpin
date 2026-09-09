---
module: expenses
last_verified_commit: 3d0fc1d1
---

# Gastos

Seguimiento de gastos fijos y recurrentes de la clínica: alquiler,
suministros, salarios, material, equipamiento, seguro, mantenimiento y
otros. Cada gasto lleva fecha y descripción opcional; un resumen mensual
agrega los totales por categoría.

**Sensible por defecto**: solo `admin` ve el módulo al principio (el
alquiler y los salarios rozan la nómina). La clínica puede conceder
`expenses.read` / `expenses.write` a otros roles desde la UI de
administración de módulos.

## Pantallas

- [Lista de gastos](./screens/index.md): filtro por categoría, alta
  de gastos, totales mensuales por categoría y borrado con
  confirmación.

## Importar desde CSV

`POST /api/v1/expenses/import.csv` (multipart `file`, `expenses.write`):

```bash
curl -X POST "https://clinica/api/v1/expenses/import.csv?dry_run=false" \
  -H "Authorization: Bearer $TOKEN" -F file=@gastos.csv
```

Columnas: `category*` (rent|utilities|salaries|supplies|equipment|
insurance|maintenance|other), `amount*` (decimal > 0),
`expense_date*` (AAAA-MM-DD o DD/MM/AAAA), `description`.
Separador `,` o `;` (autodetectado), UTF-8, máximo 1000 filas /
1 MiB. La confirmación es todo o nada. Respuesta: `{total, valid,
created, errors}`.
