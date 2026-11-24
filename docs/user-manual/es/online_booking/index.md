---
last_verified_commit: 0000000
---
# Solicitudes de reserva online

La reserva online debe activarse por un administrador y requiere correo configurado y una página pública de confirmación. La disponibilidad sigue el horario del profesional elegido en la configuración; las citas de otros profesionales no la bloquean. Si ese profesional se desactiva o se retira de la clínica, la página pública deja de ofrecer horas y de aceptar solicitudes hasta que un administrador elija un profesional activo. El enlace de correo confirma la solicitud; recepción decide si acepta o rechaza. Confirmar no crea una cita.

Una solicitud confirmada retiene el hueco hasta que recepción decide o empieza la hora solicitada. Antes de aceptar, el sistema vuelve a comprobar las citas; si existe un conflicto, muestra un error para que recepción lo resuelva. Las solicitudes rechazadas o caducadas se eliminan tras 30 días; los datos de contacto de las aceptadas se borran tras 90 días.

La página pública ([página de reserva](screens/booking-page.md)) forma parte de DentalPin en `/p/booking/<id de la clínica>`; enlázala o incrústala en tu web con un iframe. Permite elegir motivo y hueco, introducir datos de contacto y superar ALTCHA. El enlace recibido exige pulsar «Confirmar solicitud»; abrirlo no crea ni confirma una cita.

El calendario destaca solo los días con huecos y permite avanzar por semanas. El teléfono y el correo son obligatorios. El personal autorizado puede cambiar el logotipo, color, textos, URL de la política de privacidad y las webs autorizadas a incrustar la página desde «Ajustes de la página pública».
