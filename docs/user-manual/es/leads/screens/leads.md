---
module: leads
screen: leads
route: /leads
related_endpoints:
  - GET /api/v1/leads/
  - POST /api/v1/leads/
  - PATCH /api/v1/leads/{lead_id}
  - POST /api/v1/leads/{lead_id}/convert
related_permissions:
  - leads.read
  - leads.write
related_paths:
  - backend/app/modules/leads/router.py
  - backend/app/modules/leads/frontend/pages/leads/index.vue
last_verified_commit: dd2611ce
---

# Cola de solicitudes

La cola de **/leads** lista las consultas que han entrado y no coincidían con
ningún paciente. Es la lista de trabajo de recepción: leer la consulta, llamar
a la persona y convertirla en paciente o descartar la tarjeta.

## El listado

Cada tarjeta muestra las iniciales de quien consulta, con el color del estado,
el nombre con su etiqueta de estado, el **motivo** (de qué va la llamada), el
teléfono y la descripción recortada a una línea y — en pantallas anchas — una
**tira semanal con los días en que se le puede llamar** y cuánto tiempo hace que
llegó la consulta. Los textos largos se recortan en la tarjeta; el panel lateral
los muestra completos.

| Estado | Significado |
|---|---|
| **Nueva** | Recibida, todavía no la ha llamado nadie. |
| **Contactada** | Recepción ya se ha puesto en contacto. |
| **Convertida** | Ha pasado a ser paciente desde esta tarjeta (la tarjeta conserva el enlace). |
| **Descartada** | No va a ninguna parte — se conserva como registro, nunca se borra. |

- La cola **se abre filtrada por *Nuevas*** —el trabajo que queda por hacer— para
  que las convertidas y las descartadas no la llenen. El chip muestra
  `Estado · 1`: el filtro se ve, no es un valor por defecto escondido.
- Los filtros de **estado** admiten varios estados a la vez. Si quitas la
  selección se muestran *todos* los estados, incluidas las convertidas y las
  descartadas: nada queda fuera de tu alcance.
- Marcar una tarjeta como **Contactada**, **Convertida** o **Descartada** la saca
  de la vista por defecto; cambia el chip (o quítalo) para volver a encontrarla.
- El **buscador** mira en el nombre, el teléfono y el email.

## Convertir una solicitud en paciente

Al pulsar una tarjeta se abre el panel lateral derecho. Es el sentido de toda
la página: rellenas la ficha del paciente mientras sigues viendo qué pedía la
persona.

1. **Panel de la consulta** (solo lectura) — motivo, descripción, la tira
   semanal con los días y la franja horaria en que se le puede llamar, teléfono,
   email y la fecha de recepción.
2. **Aviso de duplicado** — si ya existe un paciente con el mismo teléfono, un
   aviso enlaza a esa ficha. No bloquea la conversión: hay familias que
   comparten teléfono.
3. **Formulario del paciente** — precargado desde la consulta:
   - **Nombre** — el nombre único del formulario se parte por el **primer**
     espacio: `Marta Ruiz` queda como *Marta* + *Ruiz*, y *Marta de la Fuente*
     como *Marta* + *de la Fuente*. Si el nombre es una sola palabra, el apellido
     queda vacío para que lo completes. Es una suposición, así que los dos
     campos siguen siendo editables.
   - **Teléfono** y **email** — copiados tal cual llegaron.
   - **Notas** — se quedan **vacías a propósito**. El motivo y la disponibilidad
     son logística de esta llamada, no datos del paciente: se quedan en la
     tarjeta y en el panel de arriba, y nunca se copian a la ficha. Escribe ahí
     solo lo que pertenece a la historia clínica.
   - **DNI/NIF** y **fecha de nacimiento** se quedan vacíos: el formulario no
     los pide.
4. **Crear paciente** — se habilita cuando hay nombre y apellido. Al guardar,
   el panel muestra una confirmación con un enlace **Abrir paciente**; no te
   saca de la página, porque la siguiente consulta suele estar a un clic.

Si la tarjeta ya está **Convertida**, el panel sustituye el formulario por un
aviso y un enlace *Abrir paciente*. Una solicitud no se puede convertir dos
veces.

## Añadir una solicitud a mano

**Nueva solicitud** (arriba del listado, requiere `leads.write`) abre un
formulario pequeño para una consulta tomada por teléfono: nombre, teléfono y
motivo son obligatorios; email y descripción son opcionales. La disponibilidad
es un **selector semanal**: marca los días en que se le puede llamar y, si
importa, elige *Mañanas*, *Tardes* o *Noches* (déjalo en *Cualquier hora* si no
te lo dijo). Al crear no hay selector de estado: una consulta recién llegada es
*Nueva* por definición.

Guardar tiene **dos resultados posibles**, y el mensaje te dice cuál ha sido:

- **La persona es nueva** — la tarjeta se guarda y aparece arriba del listado.
- **El teléfono o el email ya pertenece a un paciente** — no se añade nada a
  Solicitudes entrantes. Recibes otro mensaje, con el nombre del paciente, que
  te dice que se ha añadido una llamada a **Recordatorios**. Búscala allí: la
  consulta no aparecerá nunca en esta lista.

Un teléfono compartido por una familia puede coincidir con varios pacientes;
cada uno recibe su llamada y el mensaje nombra la coincidencia más probable.

## Editar, marcar y descartar

El lápiz de una tarjeta abre el formulario de edición: corregir un teléfono mal
escrito, cambiar el motivo o mover la tarjeta a *Contactada*, *Convertida* o
*Descartada* después de la llamada.

**Marcar aquí una solicitud como Convertida no crea ningún paciente** ni lo
enlaza. Solo etiqueta la tarjeta. Para crear el paciente de verdad, usa el panel
de conversión: esa es la acción que escribe la ficha del paciente y la única que
la enlaza con la tarjeta.
## Lo que los formularios no dejan enviar

Los dos formularios (el de alta manual y el panel de conversión) validan antes
de enviar nada y te dicen qué campo está mal **en tu idioma**:

- **Email** — debe parecer una dirección: una `@`, algo delante y un dominio con
  punto (`nombre@example.com`). `marta@example` o `marta..ruiz@example.com` no
  pasan.
- **Teléfono** — solo dígitos, espacios y `+ ( ) - . /`, con al menos 6 dígitos.
  En el panel de conversión además tiene que caber en la ficha del paciente
  (20 caracteres).
- **Campos obligatorios** — nombre, teléfono y motivo en una solicitud; nombre y
  apellidos en un paciente.
- **Fecha de nacimiento** — no puede ser futura (ni de hace más de 120 años).

El campo se marca con el motivo y no se envía nada. El servidor valida el mismo
contenido, así que lo que el formulario acepta no se rechaza después.

