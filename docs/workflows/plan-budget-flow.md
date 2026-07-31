# Flujo Plan de Tratamiento ↔ Presupuesto ↔ Cita — Documento de uso

> **Audiencia:** personal de clínica (doctores, recepción, coordinadores) y agentes IA que asisten en la implementación. Manual breve de "cómo se hace cada cosa".
>
> **Alcance:** describe el ciclo completo desde que un paciente necesita un plan hasta que se completa o se cierra. No cubre instalación ni configuración técnica.

---

## 1. ¿Qué es este flujo?

Cuando un paciente necesita varios tratamientos, no se citan uno a uno: se construye primero un **plan de tratamiento** (qué hay que hacer, en qué orden), luego un **presupuesto** (cuánto cuesta), el paciente decide, y entonces se agendan las citas para ejecutarlo.

Tres actores:

- **Doctor** — decide qué tratamientos necesita el paciente.
- **Recepción / Coordinador** — convierte el plan en presupuesto, lo envía al paciente, persigue la respuesta y agenda citas.
- **Paciente** — recibe presupuesto, acepta o rechaza.

---

## 2. Estados del Plan y del Presupuesto (glosario)

### Plan de tratamiento

| Estado | Qué significa | Quién puede editar |
|---|---|---|
| **Borrador** | Diseño clínico en curso. El doctor está añadiendo y ajustando tratamientos. | Doctor |
| **Pendiente** | El plan está confirmado. Mientras el presupuesto siga en `Borrador` el plan sigue siendo editable (los cambios se reflejan en el presupuesto); en cuanto se **envía** al paciente, queda bloqueado. | Doctor/Recepción (hasta enviar) |
| **Activo** | Paciente aceptó el presupuesto. Listo para agendar citas y ejecutar tratamientos. | Nadie |
| **Completado** | Todos los tratamientos del plan están hechos. | Nadie |
| **Cerrado** | Plan terminado sin completarse. Lleva motivo (`closure_reason`). Reabrible. | Nadie |

**Motivos de cierre (`closure_reason`):**

- `rejected_by_patient` — El paciente rechazó el presupuesto.
- `expired` — El presupuesto caducó sin respuesta y nadie reactivó.
- `cancelled_by_clinic` — La clínica retiró el plan (duplicado, error).
- `patient_abandoned` — El paciente dejó de venir a mitad del tratamiento.
- `other` — Texto libre.

### Presupuesto

| Estado | Qué significa |
|---|---|
| **Borrador** | Recepción lo está preparando. Aún no enviado al paciente. |
| **Enviado** | Mandado al paciente (email/SMS/en mano). Esperando respuesta. |
| **Aceptado** | Paciente firmó conformidad. |
| **Rechazado** | Paciente declinó. |
| **Caducado** | Pasaron 30 días desde el envío sin respuesta. Reenviable. |
| **Cancelado** | La clínica lo anuló (típico al renegociar antes de que el paciente respondiera). |

---

## 3. El camino feliz, paso a paso

### Paso 1 — El doctor crea el plan (Borrador)

1. En la ficha del paciente, abre la pestaña **Planes de tratamiento**.
2. Pulsa **Nuevo plan**.
3. Añade tratamientos al plan: desde el odontograma o desde el catálogo. Marca pieza/superficie cuando aplique.
4. Reordena, edita cantidades, ajusta lo que necesite. El plan se guarda como **Borrador**.

### Paso 2 — El doctor confirma el plan

Cuando el doctor decide que el plan está cerrado clínicamente:

1. Pulsa **Confirmar plan**.
2. Se abre un modal con el resumen: total estimado, número de tratamientos, aviso *"El plan pasará a Pendiente y se generará un presupuesto borrador para recepción."*
3. Pulsa **Confirmar**.

Resultado:

- Plan: `Borrador` → **`Pendiente`**.
- Presupuesto borrador autogenerado a partir de los items del plan.
- El plan **sigue siendo editable** mientras el presupuesto esté en
  `Borrador`: añadir o quitar tratamientos se refleja automáticamente
  en las líneas del presupuesto. El bloqueo llega al **enviar** el
  presupuesto al paciente — a partir de ahí es un contrato.

> Si el doctor quiere descartar el presupuesto borrador por completo,
> puede pulsar **Reabrir para editar**: el plan vuelve a `Borrador` y
> el presupuesto se cancela.

### Paso 3 — Recepción prepara el presupuesto

En la **Bandeja de planes**, tab **Por presupuestar**:

1. Recepción abre la fila del paciente.
2. Revisa precios, aplica descuentos (línea o global), configura financiación si procede.
3. Define la fecha de validez (`valid_until`).
4. Pulsa **Enviar al paciente**.

Si el paciente **no tiene teléfono ni fecha de nacimiento** en ficha, antes de enviar la app pide un **código de acceso** (4-6 dígitos): recepción lo introduce y se lo da **verbalmente** al paciente (no por email ni SMS, para que el código no viaje por el mismo canal que el link).

Resultado:

- Presupuesto: `Borrador` → **`Enviado`**.
- Email y/o SMS al paciente con el link único.
- La fila se mueve al tab **Esperando paciente**.

### Paso 4 — El paciente decide

El paciente recibe un correo/SMS con un link único. Al abrir el link, antes de ver el presupuesto, se le pide **un dato de verificación** (para proteger su información):

1. **Por defecto**: últimos 4 dígitos de su teléfono.
2. **Si no tiene teléfono en su ficha**: su fecha de nacimiento.
3. **Si no tiene ninguno de los dos**: un código de 4-6 dígitos que recepción configuró al enviar el presupuesto y le ha dado verbalmente.

Tras verificar, en el móvil ve:

- Tratamientos itemizados con precios.
- Total y forma de pago.
- Tres botones: **Aceptar y firmar**, **Tengo dudas**, **No me interesa**.

> **Bloqueo por intentos fallidos**: 10 intentos fallidos totales (o 5 en 15 minutos) bloquean el link. Recepción debe reenviar (genera nuevo presupuesto v+1 con token nuevo).

#### 4a — Acepta

1. Paciente pulsa **Aceptar y firmar**.
2. Firma digital (nombre + checkbox + opcional firma manuscrita).
3. Confirmación: *"La clínica te contactará para agendar tu primera cita."*

Resultado:

- Plan: `Pendiente` → **`Activo`**.
- Presupuesto: `Enviado` → **`Aceptado`**, con `accepted_via=remote_link`.
- La fila se mueve al tab **Sin cita** en la bandeja de recepción.

#### 4b — Tiene dudas

1. Pulsa **Tengo dudas** y elige motivo + comentario opcional.
2. Recepción recibe notificación. **El estado del presupuesto NO cambia.**
3. Recepción llama al paciente y, según la conversación, renegocia o reenvía el mismo presupuesto.

#### 4c — Rechaza

1. Pulsa **No me interesa** y opcionalmente deja motivo.
2. Plan: `Pendiente` → **`Cerrado`** con `closure_reason=rejected_by_patient`.
3. Presupuesto: `Enviado` → **`Rechazado`**.
4. La fila se mueve al tab **Cerrados**.

### Paso 5 — Recepción agenda la primera cita

En la bandeja, tab **Sin cita**:

1. Recepción abre la fila del paciente con plan `Activo`.
2. Pulsa **Agendar** y elige tratamientos del plan a programar para la primera cita.
3. Selecciona doctor, gabinete, fecha y hora desde la agenda.

Resultado: cita creada y vinculada a los items del plan elegidos.

### Paso 6 — Ejecución

A medida que el paciente acude a sus citas:

1. Doctor marca tratamientos como completados desde la pestaña de la cita o desde el odontograma.
2. Si quedan items pendientes y no hay próxima cita programada, la fila aparece en el tab **Sin próxima cita**.
3. Cuando el último item se marca completado, el plan pasa automáticamente a **`Completado`**.

---

## 4. Cómo se hace cada cosa (recetas)

### 🟢 Aceptación verbal en clínica (con o sin firma tablet)

El paciente está sentado en recepción y dice "sí, lo quiero".

1. En la bandeja, tab **Esperando paciente**, abre la fila.
2. Pulsa **Marcar aceptado en clínica**.
3. Modal: opción de capturar firma con tablet o saltar.
4. Pulsa **Confirmar**.

Resultado: Plan → `Activo`, presupuesto → `Aceptado` con `accepted_via=in_clinic`.

### 🟡 Renegociar presupuesto (paciente quiere quitar tratamientos)

El paciente acepta dos tratamientos pero no el implante.

1. Recepción abre el presupuesto enviado.
2. Pulsa **Renegociar**.
3. Modal de aviso: *"Esto cancelará el presupuesto actual. El plan volverá a Borrador para que ajustes los tratamientos. ¿Continuar?"*
4. Pulsa **Continuar**.

Resultado:

- Presupuesto v1: `Enviado` → `Cancelado` (queda en historial).
- Plan: `Pendiente` → `Borrador` (desbloqueado para recepción).

5. Recepción quita el implante del plan y pulsa **Confirmar plan**.
6. Se genera presupuesto v2 en `Borrador`. Recepción lo envía al paciente.

### 🟡 Reenviar presupuesto caducado

El paciente no respondió en 30 días. Sistema marcó presupuesto como `Caducado`.

1. En la bandeja, tab **Esperando paciente**, la fila tiene badge "Presupuesto caducado".
2. Recepción pulsa **Reenviar**.
3. Modal: confirmar que se quiere clonar el presupuesto a un nuevo borrador con la misma información.
4. Pulsa **Confirmar**.

Resultado: nuevo presupuesto `Borrador` (versión n+1), el caducado queda en historial. Recepción ajusta si hace falta y envía.

> Si pasan otros 30 días sin acción tras la caducidad, el plan pasa a `Cerrado` con `closure_reason=expired` y se mueve al tab **Cerrados**.

### 🔴 Cerrar un plan activo (paciente abandonó)

El paciente lleva 2 meses sin venir y no responde llamadas.

1. Abre la ficha del plan activo.
2. Pulsa **Cerrar plan**.
3. Modal con motivo: elige `patient_abandoned`, `cancelled_by_clinic` u `other`. Texto libre opcional.
4. Pulsa **Confirmar**.

Resultado: Plan `Activo` → `Cerrado`. Items no completados quedan archivados pero registrados.

### 🟢 Reactivar un plan cerrado

El paciente que rechazó hace 6 meses vuelve y quiere retomar.

1. Busca el paciente, abre la ficha.
2. En la sección Planes, encuentra el plan `Cerrado` (puede usar el filtro de estado).
3. Pulsa **Reactivar plan**.
4. Modal de confirmación: *"Esto reactivará un plan cerrado el [fecha] por [motivo]. ¿Continuar?"*
5. Pulsa **Confirmar**.

Resultado:

- Plan: `Cerrado` → `Borrador`. Items recuperados con su estado original.
- Presupuesto previo se queda en historial.
- Doctor puede ajustar el plan; recepción genera nuevo presupuesto al confirmar.

### 🟡 Paciente quiere ver el presupuesto otra vez (perdió el correo)

1. En la bandeja, tab **Esperando paciente**, abre la fila.
2. Pulsa **Reenviar email** (o **WhatsApp** si el contacto lo tiene).
3. Reenvía el mismo link único.

Si el link expiró: usar **Renegociar** o **Reenviar** (clona a nuevo presupuesto).

### 🟢 Marcar al paciente como contactado (sin cambiar estado)

Recepción llama al paciente para hacer seguimiento.

1. En la bandeja, fila del paciente, pulsa el icono de **Marcar contactado**.
2. Añade nota corta de la conversación.
3. La fila actualiza "último contacto" sin cambiar estado.

Esta acción es para que recepción pueda priorizar a quién llamar después.

---

## 5. La Bandeja de planes (centro de operaciones de recepción)

Acceso: menú lateral → **Operaciones → Bandeja de planes** (URL: `/operations/pipeline`).

Cinco tabs:

| Tab | Contenido | Acción típica |
|---|---|---|
| **Por presupuestar** | Plan `Pendiente` con presupuesto `Borrador` aún sin enviar | Revisar precios, **Enviar** |
| **Esperando paciente** | Plan `Pendiente` con presupuesto `Enviado` o `Caducado` | Llamar, reenviar, marcar aceptado en clínica |
| **Sin cita** | Plan `Activo` sin ninguna cita futura | **Agendar** primera cita |
| **Sin próxima cita** | Plan `Activo` con citas pasadas, items pendientes y sin cita futura | **Agendar** continuación |
| **Cerrados** | Plan `Cerrado` últimos 90 días | Reactivar, archivar |

**Cada fila muestra:**

- Foto + nombre del paciente.
- Total del presupuesto.
- Días en el estado actual.
- Último contacto (con quién y cuándo).
- Tratamientos pendientes (n / total).
- Botón principal contextual al tab.

**Acciones rápidas (sin entrar al detalle):**

- 📞 **Llamar** (`tel:` directo).
- 💬 **WhatsApp** (mensaje predefinido editable).
- 📧 **Reenviar email**.
- ✅ **Marcar contactado**.
- ✍️ **Marcar aceptado en clínica**.

**Filtros:** doctor responsable, rango de fechas, importe, gabinete. Búsqueda por nombre o número de presupuesto.

**Móvil:** la bandeja funciona en móvil con tap targets grandes y swipe-actions, porque recepción persigue por teléfono.

---

## 6. Notificaciones automáticas

### A recepción

- Presupuesto **aceptado** por paciente.
- Presupuesto **rechazado** por paciente (con motivo).
- Presupuesto **caducado** (30 días sin respuesta).
- Paciente **pidió cambios** desde el link.

### A doctor

- Plan **cerrado** por rechazo del paciente.

### A paciente

- Presupuesto **enviado** (email/SMS) — siempre.
- **Recordatorios** a los 7 y 14 días sin responder — **opt-in por clínica**, off por defecto. Se activa en **Ajustes → Módulo Presupuestos → Recordatorios**.

---

## 7. Casos especiales y preguntas frecuentes

**¿Qué pasa si un paciente acepta solo parte del presupuesto?**
No hay aceptación parcial directa. Recepción **renegocia**: cancela el presupuesto, edita el plan (quita lo rechazado), genera un presupuesto nuevo. Queda historial de versiones.

**¿Puede un paciente tener varios planes a la vez?**
Sí. Cada plan tiene su propio ciclo. La bandeja los muestra como filas independientes.

**¿Se puede editar un plan en `Pendiente`?**
Depende del presupuesto. Si sigue en `Borrador` (aún no enviado), sí —
los cambios se sincronizan con el presupuesto. Si ya fue **enviado** al
paciente, no: hay que **Reabrir** (vuelve a `Borrador`, cancela el
presupuesto) o **Renegociar** desde el presupuesto, según quién haga la
edición y el motivo.

**¿Qué pasa con los items completados al cerrar un plan activo?**
Se archivan pero quedan registrados en el historial clínico del paciente y en el odontograma.

**¿El paciente ve el historial de versiones del presupuesto?**
No. Solo ve el presupuesto vigente (último enviado y no cancelado). Recepción sí ve todas las versiones desde el plan.

**¿Si la clínica no usa recordatorios, qué pasa?**
Recepción persigue manualmente desde la bandeja. La columna "días esperando" ordena automáticamente del más antiguo al más reciente.

**¿La firma digital tiene validez legal?**
La firma queda registrada con timestamp, IP, user agent y nombre escrito. Cumple los requisitos de aceptación expresa para presupuestos sanitarios en España. El detalle legal está en `docs/modules/budget.md`.

**¿Qué pasa si el paciente no recuerda su teléfono o fecha de nacimiento?**
Si fallan la verificación, tienen 5 intentos en 15 minutos antes del bloqueo temporal y 10 totales antes del bloqueo definitivo. Si quedan bloqueados, llaman a la clínica y recepción reenvía (genera nuevo presupuesto y nuevo link).

**¿Por qué el código manual se da verbalmente y no por email?**
Si el código viajara en el mismo email que el link, no protegería: alguien con acceso al email tendría link + código. Darlo en persona o por teléfono separa los canales y mantiene la protección.

---

## 8. Permisos por rol

| Acción | admin | dentist | hygienist | assistant | receptionist |
|---|---|---|---|---|---|
| Crear/editar plan en Borrador | ✅ | ✅ | — | — | — |
| Confirmar plan | ✅ | ✅ | — | — | — |
| Reabrir plan | ✅ | ✅ | — | — | — |
| Editar presupuesto Borrador | ✅ | ✅ | — | ✅ | ✅ |
| Enviar presupuesto | ✅ | ✅ | — | ✅ | ✅ |
| Marcar aceptado en clínica | ✅ | ✅ | — | ✅ | ✅ |
| Renegociar presupuesto | ✅ | ✅ | — | ✅ | ✅ |
| Cerrar plan | ✅ | ✅ | — | — | ✅ |
| Reactivar plan cerrado | ✅ | ✅ | — | — | ✅ |
| Ver bandeja de planes | ✅ | ✅ | ✅ | ✅ | ✅ |
| Agendar citas desde bandeja | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 9. Resumen visual del ciclo

```
                                                 ┌── completar todos los items ──► COMPLETADO
                                                 │
BORRADOR ──Confirmar──► PENDIENTE ──acepta──► ACTIVO ──cancela clínica──┐
   ▲                       │                                            │
   │                       │ rechaza/caduca/cancela                     │
   │                       ▼                                            │
   └──── Reactivar ◄──── CERRADO  ◄─────────────────────────────────────┘
                       (closure_reason)
```

---

## 10. Referencias

- Plan de flujo y UX completo: `~/.claude/plans/ahora-mismo-el-workflow-serialized-phoenix.md` (planificación interna).
- Módulo Treatment Plan (técnico): `backend/app/modules/treatment_plan/CLAUDE.md`.
- Módulo Budget (técnico): `docs/modules/budget.md` y `backend/app/modules/budget/CLAUDE.md`.
- Glosario ES↔EN: `docs/glossary.md`.
