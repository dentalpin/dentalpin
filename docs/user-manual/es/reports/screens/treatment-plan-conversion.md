---
module: reports
screen: treatment-plan-conversion
route: /reports/treatment-plan-conversion
related_endpoints:
  - GET /api/v1/reports/treatment-plans/conversion
related_permissions:
  - reports.scheduling.read
related_paths:
  - backend/app/modules/reports/frontend/pages/reports/treatment-plan-conversion.vue
  - backend/app/modules/reports/services/plan_conversion.py
last_verified_commit: 5595761b
---

# Conversión de planes de tratamiento

Este informe sigue los planes confirmados por un profesional desde la
confirmación hasta la cita y la finalización del tratamiento. Ábrelo desde
**Informes → Planes de tratamiento**.

## Elegir un periodo

El informe agrupa los planes por la fecha en que el profesional los confirmó,
según la zona horaria local de la clínica. El periodo inicial es el mes actual.
Cambia **Desde** y **Hasta** para consultar otro periodo. La fecha inicial debe
ser anterior o igual a la fecha final.

Los borradores y los planes confirmados fuera del periodo quedan excluidos. Es
una vista por cohorte: las citas y los tratamientos completados después siguen
asociados a la fecha en que el profesional confirmó el plan.

## Interpretar las métricas

- **Planes confirmados** — planes confirmados durante el periodo seleccionado.
- **Planes con cita** — planes confirmados con al menos una cita vinculada que
  no esté cancelada. Cada plan cuenta una sola vez, aunque se reserven varios
  elementos.
- **Planes completados** — planes en estado completado o archivado con al menos
  un elemento completado.
- **Progreso de tratamiento** — elementos completados divididos entre los
  elementos no cancelados de la cohorte.

Los porcentajes de citas y planes completados usan el número de planes
confirmados como denominador. El progreso usa los elementos de tratamiento. Si
la cohorte está vacía, los porcentajes muestran cero.

## Acceso y solución de problemas

El informe requiere `reports.scheduling.read`. Si no tienes este permiso, pide a
un administrador de la clínica que lo conceda en **Ajustes → Usuarios → Roles**.

- **El informe está vacío.** Amplía el periodo o confirma que hubo planes
  aprobados por un profesional durante esas fechas. Los borradores no forman
  parte de la cohorte.
- **No se cuenta una cita.** La cita debe estar vinculada a un elemento del
  plan; las citas canceladas no cuentan.
- **El progreso es menor del esperado.** Marca como completados los elementos
  finalizados en el plan. Reservar una cita no completa el tratamiento.
