---
module: patients
screen: import
route: /patients/import
related_endpoints:
  - POST /api/v1/patients/import.csv
related_permissions:
  - patients.write
related_paths:
  - backend/app/modules/patients/csv_import.py
  - backend/app/modules/patients/frontend/pages/patients/import.vue
  - backend/app/modules/patients/frontend/composables/usePatientCsvImport.ts
last_verified_commit: f7c72c6f
---

# Importar pacientes desde CSV

Añade muchos pacientes de una vez a partir de un archivo CSV, por
ejemplo una exportación de tu programa anterior o una hoja de cálculo.
Primero se revisa el archivo; no se guarda nada hasta que lo confirmes.

Se abre desde la lista de pacientes con **Importar CSV**. El botón y la
pantalla requieren el permiso `patients.write`.

## 1. Preparar el archivo

- La primera fila contiene los nombres de columna. **Obligatorias:**
  `first_name`, `last_name`. **Opcionales:** `phone`, `email`,
  `date_of_birth`, `notes`, `do_not_contact`, `national_id`,
  `national_id_type`, `billing_name`, `billing_tax_id`. El resto de
  columnas se ignora, así que una exportación de otro sistema se puede
  importar sin borrar columnas, pero los nombres anteriores tienen que
  coincidir exactamente.
- **Descargar plantilla** te da un archivo con la cabecera correcta y
  una fila de ejemplo.
- Valores separados por comas o por punto y coma (se detecta solo).
  Guarda el archivo en UTF-8.
- Fechas como `AAAA-MM-DD` o `DD/MM/AAAA`. `do_not_contact` admite
  sí/no, true/false o 1/0; vacío significa no.
- Como máximo 1000 filas y 1 MB por archivo. Divide una lista más
  grande en varios archivos e impórtalos uno tras otro.

## 2. Revisar el archivo

Elige el archivo y pulsa **Revisar archivo**. Se ejecuta la importación
sin guardar nada y se muestra:

- **Filas**, **Válidas**, **Con errores** y **Posibles duplicados**.
- **Filas con errores**: la línea del archivo y el motivo (falta el
  nombre, un email no válido, una fecha en otro formato…). Estas filas
  nunca se importan; corrígelas en el archivo y vuelve a importarlo.
- **Posibles duplicados**: filas que coinciden con un paciente existente
  por documento de identidad, o por email y fecha de nacimiento a la
  vez, con un enlace a ese paciente. También aparece una fila que
  repite una fila anterior del mismo archivo.

Si el archivo no se puede leer (no está en UTF-8, le falta una columna
obligatoria, supera los límites), se muestra el motivo en lugar del
resultado.

## 3. Importar

Pulsa **Importar pacientes (N)**. N es el número de filas válidas menos
los posibles duplicados. Marca **Importar también los duplicados** para
crear también esas filas.

Cada paciente se crea igual que si se hubiera dado de alta a mano, así
que los demás módulos reaccionan como siempre. Un archivo grande puede
tardar un poco. Al terminar, la pantalla indica cuántos pacientes se han
creado y cuántos se han omitido por duplicados.

Si la importación falla a medias, revisa la lista de pacientes antes de
volver a intentarlo: es posible que algunos ya se hayan creado, y la
comprobación de duplicados solo reconoce filas con documento de
identidad o con email y fecha de nacimiento.
