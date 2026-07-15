# DentalPin

[![en](https://img.shields.io/badge/lang-en-red.svg)](./README.md)
[![es](https://img.shields.io/badge/lang-es-yellow.svg)](./README.es.md)
[![fr](https://img.shields.io/badge/lang-fr-blue.svg)](./README.fr.md)

Software open source de gestión de clínicas dentales. Construido con arquitectura modular para la extensibilidad.

## ¿Por qué DentalPin?

Las clínicas dentales de todo el mundo comparten las mismas necesidades fundamentales: gestionar pacientes, programar citas, hacer seguimiento de tratamientos y dirigir su práctica de manera eficiente. Sin embargo, el panorama del software está fragmentado en docenas de soluciones localizadas y de código cerrado que encierran a las clínicas en contratos costosos y tecnología obsoleta.

**Creemos que es hora de cambiar.**

DentalPin se construye sobre una premisa simple: **una plataforma abierta para clínicas dentales en todas partes**. No otra solución regional, sino una base global que cualquier clínica pueda adoptar, cualquier desarrollador pueda extender y cualquier comunidad pueda localizar.

### ¿Por qué ahora?

La IA ha cambiado fundamentalmente lo que los equipos pequeños pueden construir. Funcionalidades que antes requerían grandes departamentos de desarrollo ahora pueden implementarse en días. Esta es nuestra ventana para crear el software dental de código cerrado que debería haber existido hace años — antes de que las clínicas quedaran encerradas en sistemas legacy de los que no pueden escapar.

### Nuestros principios

- **Código Abierto** — Los datos de su clínica le pertenecen. Su software también.
- **Modular** — Comience simple, añada lo que necesite. No pague por funcionalidades que nunca usará.
- **Global por Diseño** — Construido para la localización desde el primer día. Mismo núcleo, cualquier idioma, cualquier país.
- **API-Primero** — Cada funcionalidad es una API. Integre con todo, automatice todo.
- **Preparado para IA** — Estructurado para la era de la IA. Listo para programación inteligente, apoyo a la decisión clínica y automatización de flujos de trabajo.

### La visión

No solo estamos construyendo software — estamos construyendo la base de un ecosistema. Una plataforma donde los desarrolladores contribuyen módulos, las clínicas comparten mejoras y toda la comunidad dental se beneficia de la innovación colectiva.

Las clínicas merecen algo mejor que software cerrado y costoso de la década pasada. DentalPin es la alternativa abierta.

## ✨ Copiloto IA

DentalPin incluye un **asistente IA agentic integrado** que convierte toda la clínica en algo con lo que simplemente puede conversar. Pídale encontrar un paciente, liberar un espacio, perseguir un presupuesto sin respuesta, o informarle sobre el día por delante — en español o inglés — y actúa sobre sus datos reales.

![AI Copilot](docs/screenshots/ia.png)

Esto no es un chatbot añadido a posteriori. El Copiloto es un agente real que **planifica y ejecuta tareas multi-paso** llamando a las mismas operaciones que la interfaz de usuario, a través de pacientes, agenda, recordatorios, presupuestos, pagos y reportes.

- **Hace, no solo responde.** El agente ejecuta herramientas reales — buscar pacientes, reservar o reprogramar citas, registrar un pago, extraer los cobros del mes — y las encadena para completar una tarea de principio a fin.
- **Nunca excede su rol.** Cada llamada a herramienta se re-verifica contra los permisos RBAC del usuario que llama en el punto de control de ejecución. El Copiloto puede ver y hacer *exactamente* lo que ese usuario podría hacer a través de la interfaz — nada más, limitado a su clínica.
- **Sus datos están protegidos.** Los datos de salud se enmascaran antes de enviarlos al proveedor LLM: nombres, teléfonos, correos electrónicos e identificadores se reemplazan por tokens deterministas, y las herramientas clínicas de texto libre se excluyen del camino cloud. El enmascaramiento está activado por defecto.
- **Las escrituras preguntan primero.** Cualquier acción que modifique datos (reservas, pagos, ediciones) hace una pausa en medio de la conversación para su confirmación explícita antes de ejecutarse.
- **Flujos de trabajo guiados.** Playbooks listos para usar — *Resumen matinal*, *Preparar una consulta*, *Llenar un espacio*, *Recordatorios pendientes*, *Presupuestos sin respuesta* — inician tareas multi-paso comunes con un solo clic.
- **Briefings proactivos.** Elija recibir un resumen matinal determinista enviado por correo electrónico a su equipo, resumiendo el agenda del día, recordatorios pendientes y presupuestos abiertos — sin LLM, sin datos de salud fuera del sitio.
- **Modular por diseño.** El Copiloto consume herramientas publicadas por cada módulo a través de un registro compartido; cada módulo contribuye sus propias capacidades, por lo que el agente crece automáticamente a medida que se instalan nuevos módulos.

Agnóstico al proveedor en las capas internas (abstracción del proveedor LLM), con proveedor, modelo y presupuestos de tokens por clínica configurables por despliegue. Arquitectura: [docs/technical/copilot-agentic-architecture.md](docs/technical/copilot-agentic-architecture.md).

## Sitio web

Visite [**dentalpin.com**](https://www.dentalpin.com) para información del producto, características y detalles comerciales.

## Comunidad

Únase a nuestro [**canal de Telegram**](https://t.me/dentalpin) para soporte, ayuda con la instalación y preguntas.

## Capturas de pantalla

### Copilot IA
![AI Copilot](docs/screenshots/ia.png)

### Panel de control
![Dashboard](docs/screenshots/home.png)

### Gestión de pacientes
![Patients](docs/screenshots/patients.png)

### Agenda semanal
![Weekly Schedule](docs/screenshots/schedule-week.png)

### Planificación Kanban
![Kanban Schedule](docs/screenshots/schedule-canban.png)

### Gráfico de pagos
![Payments Chart](docs/screenshots/payments-chart.png)

### Configuración
![Settings](docs/screenshots/settings.png)

## Inicio rápido

```bash
# Iniciar servicios
docker-compose up -d

# Sembrar datos de demostración (inglés por defecto)
./scripts/seed-demo.sh

# O sembrar en español
./scripts/seed-demo.sh --lang es

# O sembrar en francés
./scripts/seed-demo.sh --lang fr
```

Abrir http://localhost:3000

### Credenciales de demostración

Todos los usuarios tienen contraseña: `demo1234`

| Email | Rol | Nombre (EN) | Nombre (ES) |
|-------|-----|-------------|-------------|
| admin@demo.clinic | admin | Admin Demo | Admin Demo |
| dentist@demo.clinic | dentist | Dr. Sarah Johnson | Dra. María García López |
| hygienist@demo.clinic | hygienist | Michael Williams | Carlos López Martínez |
| assistant@demo.clinic | assistant | Emily Davis | Ana Martínez Ruiz |
| receptionist@demo.clinic | receptionist | Jessica Brown | Laura Sánchez Pérez |

Consulte [docs/user-manual/demo.md](docs/user-manual/demo.md) para detalles completos sobre los datos de demostración.

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI (Python 3.11+) |
| Frontend | Nuxt 3 + Nuxt UI |
| Base de datos | PostgreSQL 15 |
| Autenticación | JWT con refresh tokens |

## Características

### Copilot IA
- **Asistente agentic** — Agente conversacional que planifica y ejecuta tareas multi-paso a través de pacientes, agenda, recordatorios, presupuestos, pagos y reportes llamando a operaciones reales
- **Paridad RBAC** — Cada acción re-verificada contra los permisos del usuario; el agente solo puede hacer lo que ese usuario podría hacer a través de la interfaz, limitado a su clínica
- **Enmascaramiento de datos de salud** — Identificadores de pacientes tokenizados antes de llegar al LLM; los datos clínicos de texto libre permanecen fuera del camino cloud. Activado por defecto
- **Escrituras confirmadas** — Las acciones que modifican datos hacen una pausa para confirmación explícita del usuario en medio de la conversación
- **Flujos de trabajo y resumen** — Playbooks con un clic (resumen matinal, preparar una consulta, llenar un espacio) más un resumen matinal por correo electrónico proactivo opcional
- **Bilingüe y agnóstico al proveedor** — Funciona en español, francés e inglés; proveedor LLM, modelo y presupuesto de tokens por clínica configurables

### Gestión clínica
- **Historiales de pacientes** — Perfiles completos con datos personales, información de contacto, historial médico y notas
- **Carta dental (Odontograma)** — Diagrama dentario interactivo con seguimiento de tratamientos por diente/superficie
- **Calendario de citas** — Vistas semanal y diaria con arrastrar y soltar, columnas profesionales, detección de conflictos
- **Catálogo de tratamientos** — Catálogo personalizable con códigos, precios, tipos de IVA y categorías

### Gestión financiera
- **Presupuestos** — Creación de presupuestos de tratamiento, seguimiento del flujo de aprobación (borrador → pendiente → aprobado/rechazado), captura de firma del paciente, generación de PDF
- **Facturas** — Generación de facturas a partir de presupuestos o de manera independiente, numeración automática, múltiples métodos de pago, exportación PDF
- **Pagos** — Seguimiento de pagos parciales, historial de pagos, cálculo de saldo

### Gestión de la práctica
- **Control de acceso basado en roles** — Cinco roles (admin, dentista, higienista, asistente, recepcionista) con permisos granulares
- **Gabinete/Sala de tratamiento** — Definición de salas de tratamiento con horarios y colores
- **Gestión de profesionales** — Asignación de citas a dentistas/higienistas específicos

### Experiencia de usuario
- **Selectores visuales** — Menús desplegables inteligentes mostrando pacientes recientes y tratamientos populares
- **Interfaz bilingüe** — Localización completa en español, francés e inglés
- **Modo oscuro** — Cambio de tema adaptado al sistema
- **Diseño responsive** — Funciona en escritorio y tableta

### Características técnicas
- **Arquitectura modular** — Sistema basado en plugins para una facilidad de extensión
- **Bus de eventos** — Comunicación entre módulos para notificaciones e integraciones
- **API REST** — API completa con documentación OpenAPI
- **Actualizaciones en tiempo real** — Interfaz reactiva con actualizaciones optimistas

## Desarrollo

### Prerrequisitos

- Docker y Docker Compose
- Python 3.11+ (para desarrollo local del backend)
- Node.js 18+ (para desarrollo local del frontend)

### Ejecución local

```bash
# Iniciar todos los servicios
docker-compose up

# O ejecutar el backend por separado
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# O ejecutar el frontend por separado
cd frontend
npm install
npm run dev
```

### Gestión de la base de datos

```bash
# Resetear la base de datos y ejecutar migraciones
./scripts/reset-db.sh

# Sembrar datos de demostración (inglés - por defecto)
./scripts/seed-demo.sh

# Sembrar datos de demostración (español)
./scripts/seed-demo.sh --lang es

# Sembrar datos de demostración (francés)
./scripts/seed-demo.sh --lang fr

# Configuración completa (reset + siembra en un solo comando)
./scripts/setup-demo.sh
```

### Ejecución de pruebas

```bash
# Unitarias + integración del backend (en Docker)
docker-compose exec backend python -m pytest -v

# Round-trip Alembic lento (opcional, ver docs/technical/creating-modules.md)
docker-compose exec backend python -m pytest -v -m alembic_roundtrip

# Unitarias del frontend (vitest)
cd frontend
npm run test
```

**E2E en navegador (Playwright)** se encuentra en `frontend/tests/e2e/` y dirige
la pila completa en `localhost:3000` → `:8000`. Se ejecuta en el host porque
el contenedor frontend Alpine no puede lanzar Chromium.

```bash
# Configuración inicial
(cd frontend && npm install && npx playwright install chromium)

# Asegúrese de que la pila esté arriba y con datos primero
docker-compose up -d
./scripts/seed-demo.sh

# Suite E2E completa (nav + RBAC + smoke test de detalle de paciente)
./scripts/e2e.sh

# Un solo archivo
./scripts/e2e.sh rbac

# Interfaz interactiva
./scripts/e2e.sh --ui
```

Runbook completo + referencia de fixtures: [docs/technical/e2e-testing.md](docs/technical/e2e-testing.md).

## Arquitectura

DentalPin utiliza una arquitectura modular tipo plugin. Cada funcionalidad es un módulo autónomo que:
- Declara sus modelos SQLAlchemy
- Proporciona un router FastAPI
- Puede suscribirse a eventos de otros módulos

Consulte [docs/architecture.md](docs/architecture.md) para más detalles.

## Licencia

Business Source License 1.1 (BSL 1.1)

**Limitación de uso:** No puede ofrecer DentalPin como un SaaS comercial para la gestión de clínicas dentales.

**Fecha de cambio:** 4 años desde el lanzamiento

**Licencia de cambio:** Apache 2.0

Consulte [LICENSE](LICENSE) para los términos completos.

## Contribuir

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para las directrices.

---

Respaldado por [Dentaltix](https://www.dentaltix.com)
