---
module: patients
screen: list
route: /patients
related_endpoints:
  - GET /api/v1/patients
  - GET /api/v1/patients/recent
  - POST /api/v1/patients
related_permissions:
  - patients.read
  - patients.write
related_paths:
  - backend/app/modules/patients/router.py
  - backend/app/modules/patients/frontend/pages/patients/index.vue
last_verified_commit: f7c72c6f
screenshots:
  - patients.png
---

# Listado de pacientes

Muestra todos los pacientes activos de la clínica. Desde aquí puedes
buscar, filtrar, abrir la ficha de un paciente o crear uno nuevo.

## De un vistazo

- **Vista por defecto:** solo pacientes activos. Los archivados quedan
  ocultos; el endpoint de listado no los devuelve por defecto.
- **Filtro de estado:** los chips seleccionan exactamente lo pedido.
  *Archivados* por sí solo lista únicamente pacientes archivados; con
  los dos chips salen ambos. Al limpiar el filtro se quita la
  restricción, no se vuelve a activos.
- **Panel de recientes:** la barra lateral muestra los pacientes
  abiertos más recientemente — proviene del endpoint
  `GET /api/v1/patients/recent`.
- **Paginación:** 20 pacientes por página. El selector de tamaño de
  página permite ampliarlo; el backend admite hasta 100.

## Cómo encontrar un paciente

1. Escribe nombre, apellido o número de documento en la caja de
   búsqueda. La consulta filtra por coincidencias exactas y parciales.
2. Pulsa **Enter** o espera al debounce — los resultados se actualizan
   en sitio.
3. Haz clic en una fila para abrir la
   [ficha del paciente](./detail.md).

## Cómo crear un paciente

> Requiere el permiso `patients.write`.

1. Pulsa **Nuevo paciente** en la barra superior derecha.
2. Rellena nombre y apellidos. Contacto, **documento (NIF/NIE)** y
   fecha de nacimiento son opcionales y se pueden completar después
   desde la ficha. El documento se usa como NIF en las facturas si
   no se definen datos de facturación aparte.
3. Pulsa **Guardar**. El nuevo paciente aparece arriba del listado y
   el sistema publica un evento `patient.created` para que otros
   módulos (recalls, notificaciones…) reaccionen.

Para añadir muchos pacientes a la vez, pulsa **Importar CSV** a su lado
y sigue [Importar desde CSV](./import.md).

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Navegar y buscar el listado | `patients.read` |
| Ver el botón **Nuevo paciente** | `patients.write` |
| Ver el botón **Importar CSV** | `patients.write` |

## Resolución de problemas

- **El listado está vacío tras una instalación nueva.** Ejecuta
  `./scripts/seed-demo.sh` para cargar datos de demo.
- **Un paciente recién creado no aparece.** Comprueba el filtro
  *Estado*: si solo está seleccionado *Archivados*, las filas activas
  quedan fuera.
