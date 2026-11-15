---
module: core
screen: users
route: /settings/people/users
last_verified_commit: 71402014
---

# Usuarios de la clínica

Las personas administradoras pueden añadir cuentas del personal y gestionar sus permisos en **Configuración → Personas → Usuarios**.

## Añadir a una persona del equipo

1. Selecciona **Nuevo usuario** e introduce el nombre, correo electrónico y rol. Puedes dejar la contraseña vacía o definir una temporal.
2. Dentum crea un enlace de configuración de un solo uso y lo envía por correo cuando SMTP está configurado. La persona puede elegir su propia contraseña con ese enlace, incluso si definiste una temporal.
3. La pantalla indica si se envió el correo y permite copiar el enlace o compartirlo manualmente. Dentum nunca incluye contraseñas en el mensaje.
4. La persona abre el enlace, crea su contraseña e inicia sesión. El enlace caduca en siete días y solo se puede usar una vez.

## Reenviar el acceso o restablecer una contraseña

Usa la acción del enlace de acceso en la fila de la persona. Dentum crea un enlace nuevo de un solo uso y lo envía por correo cuando SMTP está disponible. También puedes copiarlo y compartirlo directamente. Trátalo como una contraseña: quien tenga el enlace puede establecer la contraseña de la cuenta.

El envío requiere un proveedor SMTP configurado para la instancia de Dentum. Si la pantalla indica que no pudo enviar el correo, consulta la guía de correo para despliegues.
