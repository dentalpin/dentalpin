---
module: patients
screen: detail
route: /patients/[id]
related_endpoints:
  - GET /api/v1/patients/{patient_id}
  - PUT /api/v1/patients/{patient_id}
  - DELETE /api/v1/patients/{patient_id}
  - GET /api/v1/patients/{patient_id}/extended
  - PUT /api/v1/patients/{patient_id}/extended
related_permissions:
  - patients.read
  - patients.write
related_paths:
  - backend/app/modules/patients/router.py
  - backend/app/modules/patients/frontend/pages/patients/[id].vue
last_verified_commit: 829bdd25
---

# Ficha del paciente

Vista de panel del paciente. Una cabecera persistente que muestra
identidad, alergias críticas y acciones rápidas, y debajo un conjunto
de pestañas. La pestaña por defecto **Resumen** es un dashboard
modular donde cada bloque lo aporta un módulo distinto (planes,
agenda, cobros, odontograma, historial médico). Los bloques son
también deep-links — un click llega al detalle.

## Diseño

- **Cabecera sticky** — avatar, nombre, edad, DNI, contacto, chips de
  alergias críticas (alergia, embarazo, anticoagulante…) y botones
  *Editar* + *Acciones ▾* (Cita, Cobrar, Nota, Archivar).
  Permanece visible al hacer scroll y entre pestañas.
- **Resumen (dashboard)** — grid de smart-cards aportadas por cada
  módulo dueño vía el slot `patient.summary.cards`:
  - **Plan activo** *(treatment_plan)* — nombre, progreso, n/m
    tratamientos. Click → detalle del plan.
  - **Próxima cita** *(agenda)* — día/hora/profesional. Click → cita.
  - **Última visita** *(agenda)* — fecha/hora/profesional de la última
    cita completada; «Sin visitas previas» si el paciente nunca ha
    venido. Click → cita (o la agenda con el paciente preseleccionado
    si no hay ninguna).
  - **Saldo** *(payments)* — debe / a cuenta / cobrado. Click →
    Administración → Cobros.
  - **Diagnósticos** *(odontogram)* — hallazgos sin tratar. Click →
    odontograma en modo diagnóstico.
  - **Historial médico** *(patients_clinical)* — alergias,
    enfermedades sistémicas, medicación. Click → editar historial.
  - **Acciones rápidas** *(patients)* — Cita, Presupuesto, Documento
    y el slot `patient.summary.actions` para módulos hermanos
    (recalls *Set recall*, notificaciones, etc.).
- **Pestañas** — Datos, Clínica, Administración, Galería, Histórico.
  En Clínica y Administración el sub-nav es un pill-bar con todos los
  modos visibles desde el primer momento (Diagnóstico · Planes ·
  Citas · Histórico / Presupuestos · Facturación · Cobros · Documentos).
- **Mobile** — la cabecera se condensa, las cards se apilan a una
  columna y aparece una barra inferior fija (Cita · Cobrar · Nota).

## Editar identidad

> Requiere `patients.write`.

1. Pulsa el icono del lápiz en la cabecera, o el botón **Editar** de
   la sub-pestaña *Identidad*.
2. Actualiza nombre, contacto, documento, demografía. Los datos
   extendidos viven detrás de *Identidad → Extendido* y se guardan
   por el endpoint `/extended`.
3. **Guardar** publica un evento `patient.updated` con los campos
   modificados, para que los dependientes (recalls, notificaciones…)
   puedan reaccionar.

## Archivar un paciente

> Requiere `patients.write`. **Nunca** se borra físicamente.

1. Abre el menú **⋮ Más** en la cabecera resumen.
2. Pulsa **Archivar paciente**.
3. Confirma. El `status` del paciente pasa a `archived`, la fila se
   oculta del listado por defecto y se publica un evento
   `patient.archived`.
4. Para restaurar, ejecuta un `UPDATE` SQL sobre la columna `status` —
   no hay flujo en la app para des-archivar todavía.

## Pestaña Pagos — "Pendiente de cobrar"

La pestaña **Administración → Pagos** muestra el ledger del paciente
(total pagado, deuda, saldo a cuenta) y, cuando hay deuda real, una
tarjeta de **Pendiente de cobrar** al principio.

- La tarjeta lista las sesiones recién completadas que aún no están
  cubiertas por los pagos del paciente (FIFO).
- El total del paciente se calcula como `clinic_receivable =
  earned − net_paid`.
- El botón **Cobrar X €** abre el modal de cobro con el importe ya
  rellenado; recepción elige método y **Destino** (presupuesto
  abierto o *a cuenta*) y confirma. Un cobro *a cuenta* no toca
  facturas ni presupuestos; el modal lo indica.
- Tras el cobro, la tarjeta desaparece o reduce su importe según
  cuánto se cobró.
- En el menú de cada cobro del historial: **Ver detalle**, **Asignar
  a presupuesto…** (mueve un anticipo a cuenta al presupuesto elegido
  y, si tiene facturas emitidas, las imputa) y **Reembolsar**.

## Pestaña Presupuestos

**Administración → Presupuestos** lista los presupuestos del paciente. Los
generados desde un plan de tratamiento llevan la etiqueta "Vinculado a
plan `<número de plan>`" junto a la fecha, para distinguirlos de los
presupuestos sueltos.

## "No contactar"

El flag `do_not_contact` es la opción de exclusión operativa. Cuando
está activo:

- El módulo de recalls excluye al paciente de cualquier cola.
- Futuros módulos de comunicación (email, SMS) DEBEN respetarlo.
- El paciente sigue apareciendo en el listado y se puede abrir con
  normalidad — solo deja de recibir contactos automatizados.

## Preferencias de notificación

La tarjeta de resumen lleva preferencias por paciente y canal: canal
preferido (email, WhatsApp o SMS), interruptor de SMS (solo se envía
con opt-in) e idioma. `do_not_contact` prevalece sobre todo.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver la ficha | `patients.read` |
| Editar identidad / extendido | `patients.write` |
| Archivar | `patients.write` |
| Acciones de módulos hermanos (recalls, notificaciones…) | El permiso del módulo hermano. |

## Resolución de problemas

- **No veo los botones Editar y Archivar.** Tu rol no tiene
  `patients.write`. Un administrador puede concederlo en
  *Ajustes → Usuarios → Roles*.
- **Falta una pestaña que esperaba.** Esa pestaña la aporta un módulo
  hermano (p. ej., *Planes de tratamiento*). Asegúrate de que ese
  módulo está instalado y de que tienes su permiso de lectura.
