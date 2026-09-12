---
module: sdi_it
last_verified_commit: 0000000
---

# Facturación electrónica para Italia (SDI)

Este módulo opcional convierte las **facturas a empresas** de la clínica en
ficheros FatturaPA y los entrega al Sistema di Interscambio (SDI) de la
Agenzia delle Entrate, y después sigue los recibos que el SDI devuelve.

Solo afecta a las facturas cuyo destinatario es una empresa, una aseguradora,
un fondo o un profesional con *partita IVA*. **Las facturas a pacientes nunca
se envían al SDI**: la ley italiana prohíbe la factura electrónica para
servicios sanitarios a particulares (art. 10-bis DL 119/2018). Esas facturas
se emiten en PDF desde Facturación como siempre, y sus datos corresponden al
módulo del Sistema Tessera Sanitaria.

## Pantallas

Ambas páginas están en **Ajustes → Facturación e impuestos**:

- **Facturación electrónica (SDI)** — régimen fiscal, referencia de la
  exención, timbre virtual y el envío al SDI (manual o PEC), con prueba del
  buzón.
- **Ficheros SDI** — cada fichero generado, su estado, el recibo y las
  acciones: descargar el XML, marcar como subido, importar un recibo,
  regenerar tras un rechazo, enviar ahora (PEC).

La página de la factura muestra un **panel SDI** con la misma información y
acciones para esa factura, y un distintivo `SDI` en el listado.

## Antes de empezar

- El NIF de la clínica en **Ajustes → General** debe ser su partita IVA
  (11 dígitos); la razón social y la dirección rellenan el bloque del emisor.
- Los destinatarios empresa necesitan su partita IVA en los datos de
  facturación. Su código destinatario SDI (7 caracteres) o su PEC pueden
  guardarse en la dirección de facturación como `sdi_code` / `pec`; si no,
  el SDI deja la factura en el área reservada del destinatario.
- Elige el envío:
  - **Manual**: descarga cada XML, súbelo en *Fatture e Corrispettivi* o
    envíalo desde tu cliente PEC, e importa el fichero de recibo que
    devuelve el SDI.
  - **PEC**: introduce el buzón PEC de la clínica (SMTP e IMAP); el sistema
    envía los ficheros y lee los recibos cada dos minutos.

## Los recibos

| Recibo | Estado mostrado | Qué hacer |
|---|---|---|
| RC — ricevuta di consegna | Entregado | nada |
| MC — impossibilità di recapito | No entregable | la factura es válida; avisa al destinatario de que está en su área reservada |
| NS — notifica di scarto | Rechazado | corrige los datos de la factura y **Regenerar y reenviar**: el nuevo fichero conserva número y fecha |

Los ficheros y recibos se conservan diez años; los registros que llegaron al
SDI impiden desinstalar el módulo.
