---
module: leads
last_verified_commit: dd2611ce
---

# Solicitudes entrantes

**Solicitudes entrantes** (en inglés, *leads*) es la cola de consultas que
llegan desde el formulario de contacto de tu web — o que recepción apunta a
mano — y que **no** coinciden con ningún paciente que ya tengas.

> **Las consultas de pacientes que ya existen no aparecen aquí.** Cuando el
> teléfono o el email ya pertenece a uno de tus pacientes, DentalPin añade una
> llamada a **Recordatorios** con el texto de la consulta en la nota del
> recordatorio. Comprueba Recordatorios antes de dar por hecho que el
> formulario no funciona.

Es un módulo opcional: un administrador lo activa desde **Ajustes → Módulos**.
Una vez activo, **Solicitudes entrantes** aparece en la barra lateral para
quien tenga permiso para verlo.

## Pantallas

- [Cola de solicitudes](./screens/leads.md) — el listado de tarjetas, el filtro
  por estado y el panel de conversión.
- [Ajustes del formulario web](./screens/intake-settings.md) — el límite diario,
  el volumen de hoy y la clave del formulario.

## Referencia rápida

| Acción | Permiso necesario |
|---|---|
| Ver la cola de solicitudes | `leads.read` |
| Añadir, editar, descartar o convertir una solicitud | `leads.write` |
| Ver el límite diario y la clave del formulario | `leads.settings.read` |
| Cambiar el límite diario, rotar o desactivar la clave | `leads.settings.write` |

Por defecto, los odontólogos pueden consultar la cola; auxiliares y recepción
también pueden trabajarla; solo los administradores ven la página de ajustes.

## Conviene saber

- **El límite diario y la clave del formulario se configuran en Ajustes →
  Integraciones → «Formulario web»**, no en la cola de solicitudes.
- **Convertir una solicitud crea la ficha del paciente.** Marcarla como
  *Convertida* a mano no la crea — mira [la cola de solicitudes](./screens/leads.md).
- **Las solicitudes nunca se borran.** *Descartada* es la forma de quitarla de
  en medio, y una solicitud *convertida* conserva el enlace con el paciente que
  generó.
- Cuando una consulta coincide con un paciente que ya existe no se pierde nada:
  la llamada está esperando en Recordatorios.