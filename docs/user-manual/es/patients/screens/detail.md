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
  - GET /api/v1/periodontogram/patients/{patient_id}/snapshots
  - GET /api/v1/periodontogram/patients/{patient_id}/timeline
  - GET /api/v1/periodontogram/patients/{patient_id}/draft
  - POST /api/v1/periodontogram/patients/{patient_id}/draft
  - GET /api/v1/periodontogram/snapshots/{snapshot_id}
  - GET /api/v1/periodontogram/snapshots/{snapshot_id}/indices
  - PATCH /api/v1/periodontogram/snapshots/{snapshot_id}/teeth/{tooth_number}
  - PATCH /api/v1/periodontogram/snapshots/{snapshot_id}/teeth/{tn}/sites/{site_code}
  - POST /api/v1/periodontogram/snapshots/{snapshot_id}/close
  - DELETE /api/v1/periodontogram/snapshots/{snapshot_id}
related_permissions:
  - patients.read
  - patients.write
  - periodontogram.read
  - periodontogram.write
related_paths:
  - backend/app/modules/patients/router.py
  - backend/app/modules/patients/frontend/pages/patients/[id].vue
  - backend/app/modules/periodontogram/frontend/components/PeriodontogramView.vue
  - backend/app/modules/periodontogram/frontend/components/PeriodontogramChart.vue
  - backend/app/modules/periodontogram/router.py
last_verified_commit: 42ccbba7
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

<a id="periodontogram"></a>

## Periodontograma (sub-vista de diagnóstico)

> Requiere `periodontogram.read`. Módulo opcional: actívalo desde
> *Admin → Módulos → Periodontograma → Instalar*.

La sub-pestaña **Periodontograma** vive dentro de *Clínica →
Diagnóstico*, junto al odontograma. Reúne el slider de histórico, el
banner de índices y la representación SEPA de las dos arcadas. La
ayuda dentro de la app llega aquí mediante el ancla `#periodontogram`.

### De un vistazo

```
┌────────────────────────────────────────────────────────────────────┐
│ [Banner ámbar — solo si miras un snapshot pasado] ............... │
│                                                                    │
│ [Slider de fechas]──●──────●──●─────────[Hoy]                      │
│                                                                    │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ [Pill] Borrador / Cerrada · 23 mar 2026                        │ │
│ │ BoP 18%  ·  PI 12%  ·  CAL 1.8mm  ·  Bolsas ≥5mm: 3            │ │
│ └────────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ SUPERIOR                                                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Tabla SEPA (9 filas × 16 dientes)                            │ │
│  │  Dientes — cara vestibular                                    │ │
│  │  Dientes — cara palatina (flip vertical)                      │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ INFERIOR                                                           │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Dientes — cara lingual (flip vertical)                       │ │
│  │  Dientes — cara vestibular                                    │ │
│  │  Tabla SEPA                                                   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ [Botonera sticky — solo borradores]                                │
│  [⏳ Guardado]      [Descartar borrador]  [Cerrar sesión ✓]       │
└────────────────────────────────────────────────────────────────────┘
```

### Estado vacío

Si el paciente no tiene ningún snapshot ni borrador, la sub-pestaña
muestra una tarjeta con el botón **Iniciar exploración**. Al pulsarlo
se crea un borrador prerelleno y se carga la vista completa.

### Captura por celda

1. **Sitio (sondaje, margen, sangrado, placa, supuración).** Pulsa
   cualquier dot del diente o cualquier sub-celda de las filas
   *Sangrado / Placa / Margen gingival / Sondaje*. Se abre un modal
   con cinco campos.
2. **Diente (movilidad, pronóstico, furca, anchura encía).** Pulsa
   sobre la fila correspondiente del diente. Se abre un modal con
   los campos por diente. Furca solo aparece en molares.

Los cambios se autoguardan con un retardo de 600 ms (debounce). El
indicador inferior izquierdo del periodontograma muestra el estado:
*Guardando…* / *Cambios pendientes* / *Guardado*.

### Heatmap visual

El sondaje pinta cada dot según la profundidad:

| Sondaje | Color |
|---------|-------|
| 0–3 mm | Verde |
| 4 mm | Amarillo |
| 5–6 mm | Naranja |
| ≥ 7 mm | Rojo |

Sangrado y placa añaden indicadores pequeños sobre el dot
(rojo y azul respectivamente).

### Histórico

El slider superior es el mismo componente que usa el odontograma:
cada nodo es un snapshot cerrado. Al seleccionar una fecha pasada
aparece un banner ámbar y todos los inputs quedan deshabilitados.
*Volver al actual* descarga el snapshot más reciente o el borrador
activo si lo hay.

### Cerrar sesión

Desde la botonera inferior, *Cerrar sesión* abre un modal de
confirmación con un campo opcional para una nota clínica. Al
confirmar:

1. Se vuelcan al backend los cambios pendientes en cola.
2. Se calculan los índices SEPA y se persisten en el snapshot.
3. El snapshot pasa a `closed`, aparece en el slider y los inputs
   quedan deshabilitados.

### Descartar borrador

*Descartar borrador* elimina todos los datos del draft activo. No es
reversible — el modal lo advierte antes de confirmar.

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
- En el menú de cada cobro del historial: **Asignar a presupuesto…**
  (mueve un anticipo a cuenta al presupuesto elegido y, si tiene
  facturas emitidas, las imputa) y **Reembolsar**. El menú muestra
  solo las acciones que tu rol permite.

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

Debajo de los canales hay un interruptor por tipo de mensaje
(recordatorio de cita, envío de presupuesto, envío de factura,
recordatorio de revisión…). Desactivar un tipo lo bloquea en todos los
canales, también en los envíos manuales del personal; el encendido o
apagado de cada tipo para toda la clínica sigue en los ajustes de
notificaciones.

## Grupos

La tarjeta de **Grupos** lista las etiquetas locales asignadas al
paciente (p. ej. *vip*, *riesgo-recall*). Con
`patient_segments.write` puedes asignar grupos existentes, crear
nuevos sobre la marcha o quitarlos. Los grupos son solo etiquetas —
sin puntos ni caducidad.

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
