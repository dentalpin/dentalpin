---
module: leads
screen: intake-settings
route: /settings/integrations/leads
related_endpoints:
  - GET /api/v1/leads/settings
  - PATCH /api/v1/leads/settings
  - POST /api/v1/leads/settings/intake-key/rotate
  - PATCH /api/v1/leads/settings/intake-key
related_permissions:
  - leads.settings.read
  - leads.settings.write
related_paths:
  - backend/app/modules/leads/router.py
  - backend/app/modules/leads/frontend/components/settings/LeadsIntakeSettingsPage.vue
last_verified_commit: dd2611ce
---

# Ajustes del formulario web

Página en **Ajustes → Integraciones → «Formulario web»** (solo
administradores). Aquí está todo lo que necesita el formulario de la web de la
clínica: cuántas consultas se aceptan al día y la clave que autoriza el
formulario.

## Límite diario

El **límite diario** es el número máximo de consultas aceptadas en un día para
esta clínica.

- **`0` significa sin límite** — el formulario acepta siempre.
- El valor debe estar entre `0` y `5000`. Un número fuera de rango lo rechaza el
  servidor.
- **Bajar el límite por debajo de lo ya recibido hoy bloquea el formulario al
  instante.** Es la palanca de emergencia cuando el formulario está siendo
  inundado: pon el límite en el número actual y no entra ninguna consulta más.
  No borra nada ni reinicia nada.
- El límite es por clínica y se guarda con los datos de tu clínica, no en un
  fichero de configuración del servidor: puedes cambiarlo en mitad de una
  campaña sin que nadie reinicie nada.

## Volumen de hoy

Junto al límite ves el indicador: **«37 de 200 hoy»**. Cuenta todas las
consultas que han llegado hoy al formulario, incluidas las que han acabado como
llamada en Recordatorios y las que ha bloqueado el propio límite — por eso
durante una inundación el número sigue subiendo aunque el formulario esté
respondiendo *demasiadas peticiones*. Cuando se alcanza el límite, el indicador
se sustituye por un aviso: la entrada queda en pausa hasta mañana.

Con el límite en `0` se muestra solo el recuento, sin denominador.

El contador lo reinicia **el cambio de fecha**, y nada más: guardar el límite,
rotar la clave o desactivarla dejan a propósito el recuento de hoy intacto.

## Clave del formulario

La clave del formulario es la contraseña que la web envía en cada consulta. Es
lo que hace que el formulario rechace a todos los demás.

- La clave completa se muestra **una sola vez**, cuando la generas o la rotas.
  Cópiala en ese momento: después solo verás su prefijo (por ejemplo
  `lk_AbC12xYz`), si está activa y cuándo se usó por última vez.
- **Generar / rotar** crea una clave nueva (o sustituye la actual). La clave
  antigua deja de funcionar en el mismo instante.
- **Desactivar** (el interruptor de activa) es el botón de apagado: la clave
  sigue en el sistema pero se rechaza toda consulta hasta que la vuelvas a
  activar.
- Sin ninguna clave configurada, la entrada está cerrada: el formulario recibe
  un rechazo.

### ¿Rotar o desactivar?

- **Rota** cuando la clave se ha filtrado o se ha compartido: las consultas
  legítimas siguen funcionando con la nueva y la filtrada queda muerta.
- **Desactiva** cuando quieras parar la entrada por completo durante un tiempo.

> **Pega la clave nueva en tu web antes de cerrar esta página.** El formulario
> falla hasta que la web envíe la clave nueva — por eso rotar es una acción de
> administrador y no algo que recepción pueda hacer sin querer.

## URL del formulario y ejemplo

La página muestra la URL de entrada completa. Se construye con **la dirección
de la API de tu instalación** (la misma que usa la propia aplicación), no con la
dirección de la app: si la API se sirve en su propio host o puerto — como en un
entorno de desarrollo local (`http://localhost:8000`) — ese es el host al que
debe llamar tu web. Si envías la consulta a la dirección de la app, la respuesta
es una redirección al login, no `{"received": true}`. En un despliegue donde un
mismo servidor web (Caddy) sirve la app y la API, el origen es el mismo y la URL
es simplemente `https://tu-clinica.example.com/api/v1/leads/public/intake`.

**Copiar**, junto a la URL, la lleva directamente al portapapeles, y **Copiar**,
encima del ejemplo de aquí abajo, copia la petición completa: pégala en una
terminal (o pásasela a quien lleve tu web) y sustituye la clave de ejemplo por la
real:

```bash
curl -X POST https://tu-clinica.example.com/api/v1/leads/public/intake \
  -H "Content-Type: application/json" \
  -H "X-Lead-Key: lk_xxxxxxxxxxxxxxxx" \
  -d '{
        "full_name": "Marta Ruiz",
        "phone": "+34 600 111 222",
        "email": "marta@example.com",
        "motive": "Presupuesto de ortodoncia",
        "description": "Viene de Instagram.",
        "availability_days": ["tue", "thu"],
        "availability_slot": "afternoon"
      }'
```

Un envío correcto responde siempre lo mismo:

```json
{ "data": { "received": true }, "message": null }
```

Notas para quien construya el formulario:

- La respuesta nunca dice si la persona ya era paciente. Es la misma respuesta
  para todos, a propósito.
- `description` es opcional; el resto de campos son obligatorios.
- La disponibilidad es opcional y va **estructurada**: envía en
  `availability_days` los días que ofreces con los códigos
  `mon tue wed thu fri sat sun` y, si quieres, `availability_slot` con
  `morning`, `afternoon` o `evening`. Recepción los ve como una tira semanal.
  Da igual el orden — el servidor los guarda empezando por el lunes y descarta
  duplicados — pero este es el único campo que no es texto libre: una frase
  escrita aquí se rechaza.
- Mantén el campo oculto `website` en el formulario y déjalo vacío: es una
  trampa para bots, y si viene relleno se acepta en silencio y se descarta.
- La integración recomendada es un POST **desde el servidor** de tu web o de tu
  plataforma. Un `fetch()` de navegador lanzado directamente desde la web de la
  clínica necesita además que el origen de ese sitio esté permitido en la
  configuración CORS del servidor.
- Recuerda la regla de enrutado al escribir el mensaje de confirmación de tu
  web: una consulta cuyo teléfono o email ya pertenece a un paciente no crea una
  solicitud, añade una llamada en **Recordatorios**. No prometas «hemos creado
  tu solicitud» a quien ya es paciente.