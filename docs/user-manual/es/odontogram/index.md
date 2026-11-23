---
module: odontogram
last_verified_commit: 4e5364c6
---

# Odontograma y flujo de diagnóstico

El odontograma forma parte de la pestaña **Clínica** del paciente. Úsalo
para registrar un diagnóstico en un diente, indicar sus superficies y,
tras la revisión del profesional, añadir un procedimiento asociado a un
plan de tratamiento.

## Registrar un diagnóstico

1. Abre el paciente y entra en **Clínica**.
2. Selecciona el modo **Diagnóstico** y pulsa el diente.
3. En el primer paso, elige un diagnóstico del catálogo. **Siguiente**
   permanece deshabilitado hasta seleccionar uno.
4. En el segundo paso, marca las superficies afectadas. Puedes pulsar el
   diagrama o los botones de superficie; al pulsar la corona en la vista
   lateral se marca la superficie vestibular. **Atrás** vuelve a la
   selección de diagnóstico y conserva la selección actual.
5. Confirma para guardar el diagnóstico. Si el elemento del catálogo
   tiene un procedimiento recomendado, la aplicación pregunta si deseas
   añadirlo a un plan. El profesional debe confirmar la acción; también
   se puede añadir un procedimiento manualmente.

## Planes de tratamiento

La barra lateral del diagnóstico muestra una acción destacada para crear
un plan o continuar un borrador. Si hay varios borradores, primero se
elige el plan. Si el paciente aún no tiene plan, la tarjeta lo indica y
permite ir directamente a su creación.

## Uso adaptable

El odontograma se adapta al ancho disponible en escritorio, tableta y
móvil. La vista lateral sigue visible junto a la oclusal y el modal
mantiene los controles accesibles mediante desplazamiento.

## Permisos

- `odontogram.read`
- `odontogram.write`
- `odontogram.treatments.read`
- `odontogram.treatments.write`

## Recursos técnicos

- [Resumen técnico](../../../technical/odontogram/overview.md)
- [Permisos](../../../technical/odontogram/permissions.md)
- [Eventos](../../../technical/odontogram/events.md)

## Recursos técnicos

- [Resumen técnico](../../../technical/odontogram/overview.md)
- [Permisos](../../../technical/odontogram/permissions.md)
- [Eventos](../../../technical/odontogram/events.md)
