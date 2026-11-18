---
module: gdpr
last_verified_commit: 0000000
route: /settings/people/patient-access-log
permissions: [gdpr.audit.read]
---

# Registro de accesos a pacientes

Abre la ficha de un paciente y selecciona **Accesos** para ver quién
accedió, cuándo y qué recurso consultó. En **Ajustes → Personas →
Registro de accesos a pacientes** puedes consultar los accesos de un usuario.

Indica las fechas inicial y final para descargar el CSV. El filtro incluye
ambos días y usa la zona horaria de la clínica. Las consultas repetidas de
un mismo tipo de recurso se agrupan en tramos fijos de diez minutos.
Las descargas y las exportaciones de portabilidad se registran por separado.

Tu rol necesita `gdpr.audit.read` para ver este registro y exportar el CSV.
La clínica conserva las entradas cinco años por defecto. Con
`gdpr.retention.write` puedes cambiar el plazo en esa misma pantalla de
ajustes. La limpieza diaria aplica el nuevo plazo a las entradas existentes.
