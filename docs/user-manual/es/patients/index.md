---
module: patients
last_verified_commit: 0e9a0ac
---

# Pacientes

El módulo de pacientes gestiona los registros de identidad de las
personas que atiende tu clínica: nombre, datos de contacto, demografía
y estado del ciclo de vida. Casi todos los demás módulos de DentalPin
enlazan con un paciente.

## Pantallas

- [Listado de pacientes](./screens/list.md) — buscar, navegar y crear
  pacientes.
- [Ficha del paciente](./screens/detail.md) — vista de un único
  paciente: tarjeta de identidad, datos extendidos y acciones que
  aportan otros módulos (recalls, fotos, planes de tratamiento, …).

## Referencia rápida

| Acción | Permiso requerido |
|--------|-------------------|
| Navegar pacientes | `patients.read` |
| Crear o editar un paciente | `patients.write` |
| Archivar un paciente (borrado lógico) | `patients.write` |

Los pacientes nunca se borran físicamente. Las filas archivadas
permanecen en la base de datos para auditoría e informes históricos;
quedan ocultas del listado y la búsqueda por defecto.

## Módulos relacionados

- **Recalls** — programa la próxima fecha de contacto del paciente.
  Activa el botón "Programar recall" en la ficha.
- **Planes de tratamiento** — vincula planes y presupuestos al
  paciente.
- **Multimedia / fotos** — adjunta archivos y fotografía clínica al
  paciente (o a entidades que pertenecen al paciente).
- **Agenda** — agenda citas para el paciente.

Para instrucciones paso a paso, sigue las guías por pantalla.

## Importar desde CSV

`POST /api/v1/patients/import.csv` (multipart `file`, `patients.write`):

```bash
curl -X POST "https://clinica/api/v1/patients/import.csv?dry_run=false" \
  -H "Authorization: Bearer $TOKEN" -F file=@pacientes.csv
```

Columnas: `first_name*`, `last_name*`, `phone`, `email`,
`date_of_birth` (AAAA-MM-DD o DD/MM/AAAA), `notes`,
`do_not_contact`, `national_id`, `national_id_type`,
`billing_name`, `billing_tax_id`. Separador `,` o `;`
(autodetectado), UTF-8, máximo 1000 filas / 1 MiB. La prueba
(defecto) solo valida y devuelve errores por fila más
`duplicates` (filas que coinciden con un paciente existente por
documento, o email + nacimiento; las filas repetidas dentro del
fichero devuelven `matched_on: "same_file"` con `patient_id` nulo);
al confirmar se omiten salvo `allow_duplicates=true`. Respuesta: `{total, valid, created,
skipped, errors, duplicates}`.
