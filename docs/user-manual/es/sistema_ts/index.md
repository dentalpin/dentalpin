---
module: sistema_ts
last_verified_commit: 0000000
---

# Sistema Tessera Sanitaria (Italia)

Este módulo opcional comunica las **facturas a pacientes** de la clínica
al Sistema Tessera Sanitaria, para que los gastos aparezcan en la
declaración precumplimentada de cada paciente (730 precompilato). Envía
automáticamente: cada factura pagada a un particular en el siguiente
ciclo, los abonos como reembolsos, las facturas anuladas como
cancelaciones.

Las facturas a empresas no son cosa suya (van por el módulo SDI); ambos
son excluyentes por ley.

## Pantallas

Ambas páginas están en **Ajustes → Facturación e impuestos**:

- **Sistema Tessera Sanitaria** — tu acceso al Sistema TS (usuario = tu
  codice fiscale registrado en sistemats.it, contraseña, pincode), el
  certificado de cifrado (se usa el incluido en el módulo hasta que subas
  uno nuevo), la identidad del remitente (codice fiscale del titular;
  códigos de región/ASL/estructura solo para estructuras), el resumen del
  año con el plazo del **31 de enero** y los recuentos, y el tipo de gasto
  (`tipoSpesa`) por tratamiento del catálogo.
- **Envíos al Sistema TS** — cada documento enviado, con su estado,
  protocollo y mensajes; reintentar tras un rechazo; enviar ahora.

En la ficha del paciente, la tarjeta **Oposición Sistema TS** registra la
objeción del paciente: los documentos se envían igualmente, pero sin el
codice fiscale, y los ya aceptados se reenvían anonimizados. En la
factura, un panel muestra lo enviado para esa factura.

## Antes de empezar

- Regístrate en sistemats.it como *erogatore* para obtener las
  credenciales.
- El NIF de la clínica en Ajustes → General debe ser su partita IVA.
- Los pacientes necesitan su codice fiscale en la ficha (documento).
- Elige el tipo de gasto de los tratamientos que no sean prestaciones
  sanitarias normales (p. ej. `IC` para estética, no deducible).
- Prueba primero: el entorno **Pruebas** habla con el servicio de test del
  Sistema TS; pasa a **Producción** cuando las respuestas sean aceptadas.

## Estados

| Estado | Significado | Qué hacer |
|---|---|---|
| Por enviar | en cola para el siguiente ciclo | nada |
| Aceptado / Aceptado con avisos | el Sistema TS devolvió un protocollo | nada; los avisos se muestran |
| Rechazado | error bloqueante (p. ej. un codice fiscale no válido) | corrige los datos y **Reintentar** |
| Fallido | el servicio no respondió tras ocho intentos | revisa las credenciales y **Reintentar** |
