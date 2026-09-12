# Operar una instancia de DentalPin

Guía para administradores y auto-alojados: instalar y eliminar módulos,
provocar reinicios, hacer copias de seguridad, recuperarse de errores.
Cubre los comandos que ejecuta un operador — no los internos de Python.

> **Audiencia**: usuario con conocimientos de operaciones y acceso por
> shell al host que ejecuta `docker compose up`. Para la documentación
> de contribuidores, ver `docs/technical/creating-modules.md`.

---

## 1. Requisitos previos

- Docker + Docker Compose en el host.
- Repositorio de DentalPin clonado (o artefactos de despliegue equivalentes).
- `.env` rellenado con `POSTGRES_PASSWORD`, `SECRET_KEY`, etc.
- Un stack en marcha: `docker compose up -d`.

Comprobación rápida:

```bash
curl -s http://localhost:8000/health
# {"status":"healthy","version":"0.1.0"}
```

---

## 2. Operaciones diarias

### Listar módulos

```bash
./bin/dentalpin modules list
```

Salida (recortada):

```
NAME            VERSION  STATE       CATEGORY  DEPENDS
billing         0.1.0    installed   official  clinical,catalog,budget
budget          0.1.0    installed   official  clinical,catalog
clinical        0.1.0    installed   official  -
```

Variante JSON: `./bin/dentalpin modules list --json`.

### Inspeccionar un módulo

```bash
./bin/dentalpin modules info billing
```

Muestra versión, estado, revisión aplicada, último cambio de estado y
errores. Forma JSON: el mismo comando con `--json`.

### Resumen de estado

```bash
./bin/dentalpin modules status
```

Recuentos por estado más las listas de pendientes y con error.

### Chequeo de salud

```bash
./bin/dentalpin modules doctor
```

Detecta:

- **Huérfanos** — filas de `core_module` cuyo código desapareció del disco.
- **Dependencias ausentes** — el módulo X depende de Y y no se encontró.
- **Errores de manifest** — violaciones de esquema en `MANIFEST`.
- **Módulos con error** — filas cuyo último paso de instalación o
  actualización falló.

El código de salida es distinto de cero cuando se detecta cualquier
problema; ideal para scripts de monitorización.

---

## 3. Instalar un módulo

### Módulos oficiales

Vienen incluidos en cada versión de DentalPin. Se instalan
automáticamente en el primer arranque de una base de datos nueva.
Reinstala si quedaron en `uninstalled`:

```bash
./bin/dentalpin modules install billing
./bin/dentalpin modules restart
```

### Módulos de la comunidad

```bash
# 1. Instalar el paquete Python en el contenedor del backend
docker compose exec backend pip install dentalpin-my-module

# 2. Programar la instalación
./bin/dentalpin modules install my_module

# 3. Reiniciar el backend — aplica migraciones + seed + ciclo de vida
docker compose restart backend
# o: POST /api/v1/modules/-/restart

# 4. Reconstruir el frontend si el módulo incluye una capa Nuxt
docker compose build frontend && docker compose up -d frontend
```

La salida del paso 2 lista la cadena de dependencias que se tocará:

```
Scheduled for install on next restart:
  - clinical
  - my_module
```

---

## 4. Actualizar un módulo

Actualiza el paquete del módulo (`pip install -U ...`) para que la nueva
versión aparezca en disco, y después:

```bash
./bin/dentalpin modules upgrade my_module
./bin/dentalpin modules restart
```

El reinicio ejecuta las nuevas migraciones, vuelve a aplicar los seeds y
llama al hook `post_upgrade(ctx, from_version)` del módulo.

Si las versiones de disco y base de datos ya coinciden, el comando
termina con "Module is already at the declared version."

---

## 5. Desinstalar un módulo

```bash
./bin/dentalpin modules uninstall my_module
docker compose restart backend
```

El reinicio:

1. **Hace copia de seguridad** de todas las tablas del módulo en
   `storage/backups/module_<name>_<timestamp>.sql` mediante
   `pg_dump --data-only`.
2. Llama al hook `uninstall(ctx)` del módulo.
3. Elimina todos los registros rastreados vía `core_external_id`.
4. Ejecuta `alembic downgrade <module>@base` — revierte solo la rama
   del módulo.
5. Cambia `core_module.state = uninstalled`.

### Por qué algunos módulos se niegan a desinstalarse

Dos salvaguardas:

- `removable: false` en el manifest (oficiales). Se puede forzar con
  `--force` si de verdad es lo que quieres.
- Sin rama de Alembic (módulos legacy de la Fase A). No pueden hacer
  downgrade limpio; la desinstalación está bloqueada incluso con
  `--force`. Espera a la Fase B.
- Dependencias inversas — otro módulo instalado lista este en su
  `depends`. Desinstala primero los dependientes, o pasa `--force`.

---

## 6. Reinicios

Tres vías, efecto idéntico (SIGTERM al backend y Docker lo relanza):

| Canal | Comando |
|-------|---------|
| Pista del CLI | `./bin/dentalpin modules restart` imprime el siguiente paso |
| REST | `POST /api/v1/modules/-/restart` (token de admin) |
| Host | `docker compose restart backend` |

El relanzamiento tarda 3-5 segundos. El lifespan procesa cada fila
`to_*` en orden topológico antes de aceptar tráfico. Los errores por
módulo quedan registrados en `core_module.error_message`; el resto del
stack arranca igualmente.

---

## 7. Reconstrucciones del frontend

Los módulos de la comunidad con capa Nuxt requieren reconstruir el
frontend:

```bash
docker compose build frontend && docker compose up -d frontend
```

30-60 s de inactividad en la interfaz. Los módulos oficiales **no**
necesitan reconstrucción — ya están en el bundle; alternar su
visibilidad es un filtro sobre `/api/v1/modules/-/active`.

Si el frontend arranca pero un módulo no aparece:

1. Inspecciona `frontend/modules.json` — debería listar la ruta de la
   capa del módulo.
2. Ejecuta `./bin/dentalpin modules sync-frontend` para regenerar el
   archivo.
3. Confirma que el usuario tiene el permiso listado en
   `navigation[].permission`.

---

## 8. Copias de seguridad

Las copias por módulo viven en `storage/backups/` dentro del volumen
`storage_data` del backend:

```bash
docker compose exec backend ls -l /app/storage/backups
```

Cada desinstalación produce un archivo `.sql` con los INSERT de todas
las tablas que el módulo poseía. Restaura con:

```bash
docker compose exec -T db psql -U dental -d dental_clinic \
  < storage/backups/module_my_module_20260420T080000Z.sql
```

El esquema debe existir previamente (reinstala primero el módulo y
después restaura los datos).

Para copias de la base de datos completa usa tu flujo habitual de
Postgres (pg_dump, restauración a un punto en el tiempo, etc.) — el
sistema de módulos no lo sustituye.

---

## 9. Recuperación

### Una instalación fallida

`dentalpin modules doctor` lista el módulo con su error. Opciones:

1. Corrige la causa raíz (normalmente un bug de migración o seed) y
   después `dentalpin modules install <name>` + reinicio para
   reintentar.
2. Ríndete: `dentalpin modules orphan <name>` (lo marca como
   desinstalado sin ejecutar el flujo de desinstalación). Hazlo solo
   cuando el módulo no estaba realmente presente en disco.

### Un `to_install` atascado

Ocurre cuando un fallo tumba el backend a mitad de un paso. Reinicia —
el procesador del lifespan reintenta desde el primer paso incompleto.
El diseño idempotente hace que migrate/seed/lifecycle sean seguros de
re-ejecutar.

```bash
docker compose exec backend \
  psql -U dental -d dental_clinic \
  -c "SELECT * FROM core_module_operation_log ORDER BY id DESC LIMIT 20;"
```

### Una fila huérfana

El código del módulo se eliminó del disco sin desinstalarlo (p. ej.
alguien desinstaló el paquete Python directamente). El arranque fallará
de forma visible:

```
Orphan modules (in DB, missing from disk):
  - ghost
```

Opciones:

- Restaurar el paquete (`pip install dentalpin-ghost`).
- Marcarlo como desinstalado:

  ```bash
  ./bin/dentalpin modules orphan ghost
  ```

La vía de huérfano **no** ejecuta los pasos de desinstalación (no se
revierten las migraciones, no se purgan los external ids, no se hace
copia de seguridad). Úsala con cuidado.

### Permiso denegado tras un cambio de rol

Borra las cookies de autenticación del usuario y vuelve a iniciar
sesión. Los permisos se cargan desde `/me` al iniciar sesión; las
sesiones antiguas conservan la lista anterior.

---

## 10. Referencia rápida de SQL

Ejecutar dentro de `docker compose exec db psql -U dental -d dental_clinic`:

```sql
-- Todos los módulos + estado + error
SELECT name, state, version, installed_at, error_message
FROM core_module
ORDER BY name;

-- Operaciones pendientes
SELECT name, state, last_state_change
FROM core_module
WHERE state LIKE 'to_%';

-- Registro de operaciones reciente
SELECT module_name, operation, step, status, created_at
FROM core_module_operation_log
ORDER BY id DESC
LIMIT 25;

-- Registros de seed rastreados de un módulo
SELECT xml_id, table_name, record_id, noupdate
FROM core_external_id
WHERE module_name = 'inventory';

-- Limpiar el puntero de Alembic (peligroso — lo usa reset-db.sh)
DELETE FROM alembic_version;
```

---

## 11. Tabla de resolución de problemas

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `relation "core_module" does not exist` | Los tests borraron todas las tablas | `docker compose exec backend alembic upgrade head` |
| Módulo atascado en `to_install` | Fallo a mitad de un paso | Inspeccionar `core_module_operation_log`, reiniciar el backend |
| `403 Permission denied: billing.read` | El rol carece del permiso | Revisar `ROLE_PERMISSIONS`, confirmar el `/me` cacheado |
| Barra lateral del frontend vacía | `/api/v1/modules/-/active` falló (¿token inválido?) | Revisar la consola del navegador, volver a iniciar sesión |
| Página de módulo comunitario 404 | Falta la ruta de la capa en `modules.json` | `./bin/dentalpin modules sync-frontend` + reconstruir el frontend |
| Desinstalación bloqueada: "no Alembic branch" | Módulo legacy de la Fase A | No soportado; esperar a la Fase B |
| Desinstalación bloqueada: "required by ..." | Existe una dependencia inversa | Desinstalar primero los dependientes, o `--force` |

---

## 12. Dónde reportar errores

GitHub: https://github.com/dentalpin/dentalpin/issues — incluye la
salida de:

```bash
./bin/dentalpin modules doctor --json
./bin/dentalpin modules info <affected-module> --json
docker compose logs backend --tail 100
```

Para reportes de seguridad contacta con los mantenedores en privado en
lugar de abrir un issue público.

---

## 13. Interfaz de gestión de módulos (`/settings/modules`)

Todo lo descrito en §§2–6 también está disponible como página web de
administración — sin necesidad de acceso a la terminal. Abre
**Ajustes → Módulos** (`/settings/modules`).

- **Permisos:** ver la página requiere `admin.clinic.read`; los botones
  Instalar / Desinstalar / Actualizar / Aplicar requieren
  `admin.clinic.write`. Otros roles ven un mensaje de acceso denegado.
- **Lista de módulos:** todos los módulos descubiertos con su estado
  (`installed`, `uninstalled`, `to_install`, `to_upgrade`,
  `to_remove`, `disabled`, `error`), versión, insignia de categoría
  (oficial/comunitario), dependencias y resumen.
- **Instalar:** disponible para módulos desinstalados e instalables
  presentes en disco. El modal de confirmación muestra la cadena
  transitiva de dependencias que se programará.
- **Actualizar:** disponible para módulos instalados cuyo manifiesto en
  disco difiere de la versión instalada (se muestra como
  "instalada → en disco"). El modal programa la actualización; como
  las instalaciones, necesita Aplicar + reinicio (abajo) para
  ejecutarse. La alcanzabilidad de dependencias la impone Instalar,
  no esta señal.
- **Desinstalar:** disponible para módulos instalados y removibles. El
  modal avisa de la copia de seguridad `pg_dump` automática (§8).
  Cuando dependencias inversas bloquean la eliminación, el error se
  muestra en el propio modal con opción de reintentar forzando.
- **Aplicar cambios:** las operaciones programadas quedan pendientes
  hasta pulsar **Aplicar**. El backend se reinicia, la página consulta
  `GET /-/status` hasta que `pending=[]` y refresca la lista y la barra
  lateral. Un aviso superior muestra siempre los módulos pendientes.
- **Aviso de diagnóstico:** cuando `GET /-/doctor` reporta huérfanos,
  dependencias faltantes, errores de manifiesto o módulos en error, un
  aviso los resume al inicio de la página.
- **Panel de detalle:** por módulo, datos clave (estado, categoría,
  fecha de instalación, revisiones), el mensaje de error si lo hay, el
  registro reciente de operaciones (migrate → seed → lifecycle →
  finalize por operación) y el manifiesto en bruto.
