---
module: online_booking
screen: booking-page
route: /p/booking/[clinicId]
related_endpoints:
  - GET /api/v1/online_booking/public/{clinic_id}/config
  - GET /api/v1/online_booking/public/{clinic_id}/availability
  - GET /api/v1/online_booking/public/{clinic_id}/challenge
  - GET /api/v1/online_booking/public/{clinic_id}/logo
  - POST /api/v1/online_booking/public/{clinic_id}/requests
  - POST /api/v1/online_booking/public/{clinic_id}/confirm
related_permissions: []
related_paths:
  - backend/app/modules/online_booking/frontend/pages/p/booking/[clinicId].vue
  - backend/app/modules/online_booking/frontend/composables/usePublicBooking.ts
  - frontend/server/utils/bookingEmbed.ts
last_verified_commit: 64eb2ee
---
# Página pública de reserva

Los pacientes abren esta página sin cuenta. Está en la dirección de tu DentalPin: `https://<tu-dirección-de-dentalpin>/p/booking/<id de la clínica>`. En «Ajustes de la página pública» de [Solicitudes online](requests.md) aparece la dirección exacta.

## Qué ve el paciente

1. Elige el motivo de la visita, un día (los días sin horas libres están desactivados; con las flechas cambia de semana) y una hora.
2. Escribe nombre, apellidos, correo y teléfono (con prefijo internacional si no es español). Si lo activas, también responde «¿Ya eres paciente?» y puede añadir un comentario breve; la página le pide que no incluya datos médicos.
3. Marca la política de privacidad, supera la verificación ALTCHA y envía. La página le pide que revise su correo.
4. El enlace del correo abre la misma página con el botón **Confirmar solicitud**. Abrir el enlace no confirma nada; pulsar el botón, sí. La solicitud queda entonces pendiente de recepción.

La página usa tu logotipo, color principal, título e introducción. Está disponible en los doce idiomas de la aplicación; cada visitante elige el suyo en el selector y la primera propuesta sale de su navegador. En español e inglés se usan tus textos y nombres de motivo; en los demás idiomas se muestra el texto estándar traducido y los nombres de motivo en inglés. Si configuras una URL de redirección, el paciente va allí tras enviar la solicitud.

## Enlazar la página

Pon la dirección en un enlace o botón de tu web. Indícala también como **URL de la página pública** en los ajustes: los correos de confirmación enlazan a ella.

## Incrustar la página en tu web

Usa un iframe y añade tu web en **Webs autorizadas a incrustar la página** (un origen https por línea, por ejemplo `https://www.miclinica.com`, sin ruta):

```html
<iframe
  src="https://<tu-dirección-de-dentalpin>/p/booking/<id de la clínica>"
  title="Solicitar cita"
  width="100%"
  height="900"
  style="border:0"
  loading="lazy"
></iframe>
```

Solo las webs de la lista pueden mostrar la página dentro de un marco; cualquier otra ve un marco vacío. Los cambios se aplican en aproximadamente un minuto. Deja la **URL de la página pública** apuntando a la dirección de DentalPin, no a la página de tu web: el enlace de confirmación lleva un identificador en la dirección que un iframe de tu web nunca recibiría.

Si tu DentalPin es privado, pide a quien administra el servidor que deje accesible desde internet la página de reserva (las rutas exactas están en la documentación técnica).

## Cuando la página indica que no está disponible

Muestra «La reserva online no está disponible en este momento» si la reserva está desactivada, falta el profesional o la URL pública, o la dirección es incorrecta. Si la **URL de la política de privacidad** está vacía, el formulario se muestra pero no se puede enviar.
