# 0012 — Multi-tenancy en Dentalpin core (brief de implementación)

> **Audiencia**: agentes Claude Code que vayan a implementar estos cambios.
> **Estado**: propuesta de arquitectura, pendiente de ejecución por fases.
> **Última revisión**: 2026-05-17 — corregida premisa "single-tenant" (la app ya es shared-schema multi-clinic), separado vocabulario tenant vs clinic, plegadas fases 5 y 6, reducida fase 4, decisión `modules_enabled` por-tenant.

---

## 1. Contexto

Dentalpin es una plataforma open source de gestión de clínicas dentales construida con **FastAPI + SQLAlchemy (async) + Alembic + PostgreSQL**. Tiene arquitectura modular: cada módulo (`agenda`, `patients`, `billing`, `payments`, `treatment_plan`, etc.) es un paquete Python con su propio manifest, modelos y migraciones Alembic en rama propia.

### Estado real actual (corregido frente a versión anterior del brief)

La app **no** es single-tenant. Es **shared-schema multi-clinic-per-DB**:

- Existe entity `Clinic` (`backend/app/core/auth/models.py`) y join `ClinicMembership` — un user puede pertenecer a N clínicas con roles distintos.
- Toda tabla multi-tenant lleva `clinic_id` FK indexed y CLAUDE.md exige filtrar por `clinic_id` en cada query.
- `ClinicContext` ya se resuelve por JWT vía `get_clinic_context()` (`backend/app/core/auth/dependencies.py`) e inyecta el contexto a 40+ endpoints.
- La instancia tiene un **único engine global** apuntando a `DATABASE_URL` (`backend/app/database.py`).

### Vocabulario tenant ≠ clinic

Para evitar la trampa de "una clínica = una DB" (rompería multi-clinic-per-user):

- **Tenant** = cuenta SaaS / instalación lógica / unidad de aislamiento de DB. En self-hosted hay **un solo tenant** (`"default"`). En SaaS, N tenants, cada uno con su DB.
- **Clinic** = unidad clínica dentro de un tenant. Un tenant puede tener **una o varias** clínicas (modelo actual se preserva).
- Aislamiento físico (DB) = por tenant. Aislamiento lógico (filas) = por `clinic_id`.

### Objetivo del brief

Introducir **costuras** que permitan en el futuro montar un módulo SaaS externo (`dentalpin-saas`) con DB-per-tenant, **sin romper el modo self-hosted actual**. Los self-hosters seguirán configurando una `DATABASE_URL` y todo funcionará idéntico a hoy: un tenant `default` con N clínicas dentro.

### Lo que NO se hace en este brief

- No implementamos SaaS.
- No añadimos control plane ni modelos `Tenant`/`Cluster`.
- No tocamos provisioning, billing, custom domains, ni admin UI.
- No cambiamos UI ni endpoints públicos.
- **No tocamos `ClinicContext`** — sigue siendo el contexto que ven los endpoints. `TenantContext` envuelve por encima, no reemplaza.

Solo dejamos las interfaces y refactors que permitirán que un módulo externo lo implemente sin tocar core.

---

## 2. Principios de diseño

1. **Backward compatibility absoluta**. Una instancia con `DATABASE_URL=postgresql://...` debe arrancar y funcionar exactamente como antes. Los tests existentes deben pasar sin modificarse (salvo imports puntuales).
2. **Tenant explícito, nunca implícito**. Nada de `contextvars` mágicas, nada de globals. El `TenantContext` se propaga por dependency injection.
3. **No duplicar conceptos existentes**. `ClinicContext`, event bus, storage abstraction, module registry y alembic multi-branch **ya existen**. El brief reutiliza, no reinventa.
4. **Interfaces pequeñas**. Cada abstracción tiene 2–4 métodos máximo. Si crece más, está mal diseñada.
5. **Sin overhead en single-tenant**. La implementación `SingleTenantResolver` debe ser O(1), sin cache, sin lookup, sin red.
6. **Módulos enabled por tenant**. `modules_enabled` vive en `TenantContext`, no es global. En self-hosted el set viene del registry (todos los módulos instalados). En SaaS lo determina el control plane por tenant. Esto desbloquea suscripciones por feature.
7. **Tipado estricto**. `from __future__ import annotations`, `mypy --strict` debe pasar en todo lo nuevo.
8. **Commits atómicos por fase**. Cada fase = un PR. No mezclar fases.

---

## 3. Fases

Las fases están ordenadas por dependencia y riesgo. Cada una es un PR independiente.

### Fase 1 — Tenant context e interfaces

Añade código nuevo, no cambia nada existente. Riesgo bajo.

**Relación con `ClinicContext`**: `TenantContext` vive **por encima** de `ClinicContext`. El endpoint sigue inyectando `Depends(get_clinic_context)`; el resolver de tenant se ejecuta antes para decidir a qué DB conectar. `ClinicContext` no se toca en esta fase.

#### 1.1 Crear `backend/app/core/tenancy/__init__.py`

```python
from .context import TenantContext
from .resolver import TenantResolver
from .single import SingleTenantResolver

__all__ = ["TenantContext", "TenantResolver", "SingleTenantResolver"]
```

#### 1.2 Crear `backend/app/core/tenancy/context.py`

`TenantContext` debe ser un `@dataclass(frozen=True, slots=True)` con estos campos:

- `slug: str` — identificador legible (`"default"` en self-hosted).
- `db_url: str` — connection string Postgres async (`postgresql+asyncpg://...`).
- `storage_prefix: str` — prefijo para object storage (`""` en self-hosted, `"tenants/<slug>/"` en SaaS).
- `modules_enabled: frozenset[str]` — módulos activos en este tenant. **Decisión arquitectónica**: el set es por-tenant, no por-instancia. En self-hosted se construye desde el `ModuleRegistry` (todos los módulos instalados); en SaaS lo provee el control plane según suscripción/plan.
- `metadata: Mapping[str, Any]` — campo libre para que el módulo SaaS añada info (plan, cluster_id, etc.) sin que core lo conozca. Tipo `types.MappingProxyType` para que sea inmutable.

Incluir:

- `__post_init__` que valide que `db_url` no esté vacío.
- Método `with_metadata(**kwargs) -> TenantContext` que devuelve copia con metadata extendida.
- Docstring explicando que es inmutable y se pasa por valor, y que `clinic_id` **no** vive aquí — sigue en `ClinicContext`.

#### 1.3 Crear `backend/app/core/tenancy/resolver.py`

```python
from typing import Protocol, runtime_checkable
from starlette.requests import Request
from .context import TenantContext

@runtime_checkable
class TenantResolver(Protocol):
    async def resolve(self, request: Request) -> TenantContext: ...
    async def resolve_by_slug(self, slug: str) -> TenantContext: ...
```

`resolve_by_slug` existe para contextos sin request: jobs background, CLI, tests. **No** crear excepciones custom aún; usar `LookupError` si no se encuentra. Cada implementación decidirá si lo envuelve en HTTP 404 o no.

#### 1.4 Crear `backend/app/core/tenancy/single.py`

`SingleTenantResolver` lee de settings (Pydantic Settings) los valores `DATABASE_URL`, `TENANT_SLUG` (default `"default"`), y construye `modules_enabled` consultando el `ModuleRegistry` existente (`backend/app/core/plugins/registry.py`) — todos los módulos cargados pasan. Devuelve siempre el mismo `TenantContext` precomputado. Ignora el `request` (loguea a debug si quieres, no más).

#### 1.5 Publicar `tenant.resolved` en event bus existente

El event bus ya existe (`backend/app/core/events/bus.py`, `event_bus` singleton). Solo añadir el nuevo type:

- `backend/app/core/events/types.py` — añadir constante `TENANT_RESOLVED = "tenant.resolved"`.
- Publicar desde `SingleTenantResolver.resolve()` con payload `{"tenant_slug": ctx.slug}`.

No crear bus nuevo (lo había propuesto Fase 5 — se elimina).

#### 1.6 Tests

Crear `backend/tests/core/tenancy/test_context.py` y `test_single_resolver.py`:

- `TenantContext` es hashable, comparable por valor, inmutable (`pytest.raises(FrozenInstanceError)` al intentar mutar).
- `SingleTenantResolver.resolve()` devuelve el mismo objeto en llamadas sucesivas.
- `resolve_by_slug("default")` funciona, `resolve_by_slug("otro")` lanza `LookupError`.
- `modules_enabled` refleja módulos del registry al instante de resolución.

---

### Fase 2 — Engine pool y refactor de `get_db`

Es el cambio más invasivo. Requiere revisar todos los call sites. **No mergear sin que toda la suite de tests existente pase.**

**Estado actual** (`backend/app/database.py`):
- `engine = create_async_engine(settings.DATABASE_URL, ...)` — singleton global
- `async_session_maker = async_sessionmaker(engine, ...)` — factory global
- `get_db()` cede sesión del factory global
- 40+ `from app.database import get_db` en routers/services

**Riesgos no triviales** que deben verificarse antes de merge:
- **Event handlers globales**: módulos registran handlers al import time (`event_bus.subscribe(...)`). Si un handler toca DB, hoy usa la sesión global; con engine por tenant tendrá que recibir tenant/sesión vía payload del evento. Auditar handlers antes de mergear 2b.
- **conftest fixtures**: `db_session`, `client`, `auth_headers` en `backend/tests/conftest.py` asumen engine global. Necesitan un `SingleTenantResolver` de test o un override.
- **Scripts y seed**: `scripts/seed-demo.sh`, `scripts/reset-db.sh` y código bajo `backend/scripts/` instancian conexiones fuera del request lifecycle. Migrar a aceptar `tenant_slug` como argumento.

**División en sub-PRs** para limitar el blast radius:
- **PR 2a**: introducir `EnginePool` y `get_db` parametrizado por `TenantContext`, manteniendo `SingleTenantResolver` que devuelve `settings.DATABASE_URL`. Mantener el singleton viejo como fallback temporal; toda la suite verde sin cambios.
- **PR 2b**: migrar call sites no-endpoint (jobs, scripts, seed, event handlers que tocan DB) a recibir contexto explícito. Eliminar el singleton viejo.

#### 2.1 Crear `backend/app/core/db/engine_pool.py`

Clase `EnginePool` con:

```python
class EnginePool:
    def __init__(
        self,
        max_engines: int = 100,
        ttl_seconds: int = 3600,
        pool_size: int = 5,
        max_overflow: int = 10,
    ): ...

    async def get(self, tenant: TenantContext) -> AsyncEngine: ...
    async def dispose(self, db_url: str) -> None: ...
    async def dispose_all(self) -> None: ...
```

Implementación:

- Cache LRU con TTL. Usar `cachetools.TTLCache` con lock.
- Key del cache: `tenant.db_url`. **No** la `slug`, porque un mismo tenant podría cambiar de cluster en el futuro y el `db_url` cambiaría.
- Crear engines con `create_async_engine` con `pool_pre_ping=True`, `pool_recycle=1800`.
- **Race condition**: usar `asyncio.Lock` por key para evitar crear el mismo engine dos veces en concurrencia. Patrón double-check locking.
- Al hacer `dispose`, llamar a `engine.dispose()` para cerrar conexiones limpias.
- En shutdown de la app (`lifespan`), `dispose_all`.

#### 2.2 Refactor de `backend/app/database.py`

Localización exacta de `get_db()` actual: `backend/app/database.py:50-60`. Es la única implementación; todos los imports vienen de aquí. En PR 2a renombrar la antigua a `_legacy_get_db` (no eliminar), exponer la nueva con el mismo nombre.

Nueva implementación:

```python
async def get_db(
    request: Request,
    tenant: TenantContext = Depends(get_tenant),
) -> AsyncIterator[AsyncSession]:
    engine = await request.app.state.engine_pool.get(tenant)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
```

Y crear `get_tenant`:

```python
async def get_tenant(request: Request) -> TenantContext:
    resolver: TenantResolver = request.app.state.tenant_resolver
    return await resolver.resolve(request)
```

Ambos exportados desde `dentalpin/core/deps.py` o equivalente.

#### 2.3 Setup en `lifespan` de la app

En el `lifespan` de FastAPI (`backend/app/main.py`, ya existe; ahí se llama `register_discovered()` + `mount_modules(app, installed)`):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine_pool = EnginePool(...)
    app.state.tenant_resolver = SingleTenantResolver(settings)
    yield
    await app.state.engine_pool.dispose_all()
```

`SingleTenantResolver` es el default. El módulo SaaS, cuando se instale, sobrescribirá `app.state.tenant_resolver` con `SaasTenantResolver`. **Documentar esto como el punto de extensión.**

#### 2.4 Migrar call sites

Buscar todos los usos de la antigua dependency (`Depends(get_db)`, `Depends(get_session)`, etc.) y verificar que siguen funcionando. La firma no cambia desde el punto de vista del endpoint:

```python
@router.get("/pacientes")
async def list_pacientes(db: AsyncSession = Depends(get_db)):
    ...
```

Lo único que cambia es que ahora internamente `get_db` resuelve el tenant. En single-tenant, mismo comportamiento.

**Importante**: si hay código que importa una sesión global (algo como `from dentalpin.db import session` y la usa fuera de un endpoint), hay que refactorizarlo. Documentar cada uno y decidir caso por caso. Para jobs background, aceptar `tenant: TenantContext` como argumento y resolver el engine con el pool.

#### 2.5 Tests

- Test de `EnginePool`: que cachea, que respeta TTL, que dispose funciona, que dos `get()` concurrentes para el mismo tenant no crean dos engines (usar `asyncio.gather` + spy).
- Test de integración: arrancar la app con `SingleTenantResolver`, hacer requests, verificar que las queries van a la DB configurada.
- Test de aislamiento (preparatorio para SaaS): crear dos `TenantContext` con dos `db_url` distintos, verificar que el engine pool devuelve engines distintos.

---

### Fase 3 — Storage backend abstraído

Aplica: la app sí maneja archivos.

**Estado actual**: ya existe abstracción de storage en `backend/app/modules/media/storage/`:
- `base.py` — ABC `StorageBackend` con `store/retrieve/delete/exists` async
- `local.py` — `LocalStorageBackend` con `aiofiles`
- `__init__.py` — factory `get_storage_backend()` con `@lru_cache`
- Settings: `STORAGE_BACKEND`, `STORAGE_LOCAL_PATH`, `STORAGE_MAX_FILE_SIZE`, `STORAGE_ALLOWED_MIME_TYPES`

**Lo que falta**:
- Backend S3-compatible
- Wrapper tenant-scoped que añada `tenant.storage_prefix`
- Método `get_url` con presigned URL / HMAC token

#### 3.1 Decisión arquitectónica: mover storage a core

La abstracción vive hoy en `modules/media/` pero core (y otros módulos: budget exports, payments invoices, etc.) la necesita. Mover a `backend/app/core/storage/` (mantener re-export desde `modules/media` para no romper imports). Documentar en CLAUDE.md y en el módulo `media` que la abstracción es ahora de core.

#### 3.2 Extender la interfaz existente

Añadir métodos a la ABC actual sin romper consumidores:
- `get_url(key, expires_in=3600, download_name=None) -> str` — presigned URL o HMAC token contra endpoint interno
- Mantener `store/retrieve/delete/exists` con sus firmas actuales

#### 3.3 `S3CompatibleStorage`

Para Hetzner Object Storage, R2, MinIO, AWS S3. Usar `aioboto3`. `get_url` devuelve presigned URL. Constructor recibe `bucket`, `endpoint_url`, `region`, `access_key`, `secret_key`.

#### 3.4 Tenant-aware storage

El prefix del tenant se aplica **automáticamente** en una capa wrapper:

```python
class TenantScopedStorage:
    def __init__(self, backend: StorageBackend, prefix: str):
        self._backend = backend
        self._prefix = prefix.rstrip("/") + "/" if prefix else ""

    async def put(self, key: str, ...) -> StorageObject:
        return await self._backend.put(self._prefix + key, ...)
    # ...
```

Y la dependency:

```python
async def get_storage(
    request: Request,
    tenant: TenantContext = Depends(get_tenant),
) -> StorageBackend:
    backend = request.app.state.storage_backend
    return TenantScopedStorage(backend, tenant.storage_prefix)
```

En self-hosted, `storage_prefix` es `""` y el wrapper no añade nada.

#### 3.5 Configuración

Settings con discriminador:

```python
class StorageSettings(BaseSettings):
    backend: Literal["local", "s3"] = "local"
    # local
    path: Path = Path("/var/lib/dentalpin/storage")
    # s3
    bucket: str | None = None
    endpoint_url: str | None = None
    # ...
```

Factory en lifespan que crea el backend según `settings.storage.backend`.

#### 3.6 Tests

- `LocalFilesystemStorage`: put/get/delete/exists roundtrip en tmpdir.
- `TenantScopedStorage`: verifica que el prefix se aplica en todas las operaciones.
- Mock de S3 con `moto` para testear `S3CompatibleStorage`.

---

### Fase 4 — Migraciones Alembic parametrizadas

Pequeño e independiente. **Reducida frente a versión anterior**: el sistema multi-branch ya existe (`backend/alembic/env.py:117-133` llama `discover_version_locations()`, cada módulo tiene `branch_labels = ("<name>",)`). Solo falta override de URL.

#### 4.1 Modificar `backend/alembic/env.py`

Actualmente lee `DATABASE_URL` de settings. Añadir lectura de `-x db_url`:

```python
def get_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    if url := x_args.get("db_url"):
        return url
    return os.environ.get("DENTALPIN_MIGRATION_DB_URL") or settings.DATABASE_URL
```

Esto permite ejecutar `alembic upgrade heads -x db_url=postgresql://...` apuntando a cualquier DB. En self-hosted no cambia nada.

#### 4.2 CLI helper (opcional, posponer)

Crear `backend/app/cli/migrate.py` solo si el módulo SaaS lo necesita desde su orquestador. Para self-hosted ya existen `scripts/reset-db.sh` y la invocación directa de Alembic. **No añadir trabajo prematuro.**

#### 4.3 Migrations selectivas por módulo — fuera de scope

Los módulos se instalan via `ModuleRegistry` (UI/manifest), no via flag CLI. Mezclar "aplicar migraciones de un subset de módulos" con `modules_enabled` por-tenant requiere diseño separado (¿qué pasa si un tenant tiene `agenda` desactivado pero el módulo está cargado en la instancia?). **Diferir** a un brief específico de "módulos por-tenant en SaaS".

---

### Fase 5 — ~~Event bus~~ → Nuevos `EventType` en bus existente

**Eliminada como fase**. Razón: el event bus ya existe (`backend/app/core/events/bus.py`, singleton `event_bus`) con 184 `EventType` constantes y se usa activamente en módulos. No hace falta crearlo.

Lo único pendiente:

- Añadir constantes a `backend/app/core/events/types.py`:
  - `TENANT_RESOLVED = "tenant.resolved"` (ya cubierto en §1.5)
  - `APP_STARTUP = "app.startup"`
  - `APP_SHUTDOWN = "app.shutdown"`
  - `MODULE_INSTALLED = "module.installed"`, `MODULE_UNINSTALLED = "module.uninstalled"` (publicar desde `ModuleRegistry` cuando exista UI de install — diferir)
- Publicar `APP_STARTUP`/`APP_SHUTDOWN` desde el `lifespan` de `backend/app/main.py`

Trabajo: <1h. **No es un PR aparte** — incluir en PR de Fase 2 junto al lifespan setup.

¿Síncrono o Redis? El bus actual ya es async in-process. El módulo SaaS podrá sustituirlo con uno Redis-backed cuando lo necesite. Interfaz no cambia.

---

### Fase 6 — Settings refactor (DIFERIDO)

**Posponer hasta que exista el módulo SaaS real**. Razón: `backend/app/config.py` es hoy un `Settings(BaseSettings)` plano con ~30 campos y funciona. Refactor a clases anidadas (`DatabaseSettings`, `StorageSettings`, `TenancySettings`) es cosmético y no desbloquea ninguna fase técnica.

Lo único que sí entra ahora (mínima adición, no refactor):

- Añadir a `Settings` los campos `TENANT_SLUG: str = "default"` y `TENANCY_MODE: Literal["single", "external"] = "single"`.
- En el lifespan: si `TENANCY_MODE == "external"` y no hay resolver registrado por un módulo externo al final del bootstrap, lanzar error claro.

Esto cabe en el mismo PR que la Fase 2 sin reorganizar el resto.

---

### Fase 7 — Documentación

Las rutas siguen la policy de `/docs` (técnica → `docs/technical/`, no `docs/architecture/`).

#### 7.1 Crear `docs/technical/multi-tenancy.md`

Explicar:

- El modelo actual: shared-schema multi-clinic-per-DB, un tenant por instancia (`"default"`).
- Vocabulario tenant vs clinic con ejemplos.
- Las interfaces `TenantResolver`, `StorageBackend` (extendida), y los `EventType` de tenant lifecycle como puntos de extensión.
- Cómo un módulo externo (futuro `dentalpin-saas`) las implementa.
- Diagrama de qué vive en core vs qué vive en el módulo SaaS.

#### 7.2 Actualizar `CLAUDE.md` (raíz)

Añadir sección "Multi-tenant architecture" con las reglas:

- Nunca importar una sesión DB global. Siempre usar `Depends(get_db)`.
- Nunca asumir que existe un solo tenant en core.
- `clinic_id` sigue siendo obligatorio en queries (regla existente no cambia). `TenantContext` aísla DB; `ClinicContext` aísla filas dentro de la DB.
- Cualquier código que itere "todos los tenants" pertenece al módulo SaaS, no a core.
- En código de core, si necesitas contexto de tenant en un job/CLI, recíbelo como parámetro explícito.
- `modules_enabled` se lee del `TenantContext`, no del registry global, cuando se quiere saber qué módulos ve un tenant.

#### 7.3 Crear `docs/technical/extension-points.md`

Tabla de puntos de extensión, con qué interface implementar, dónde registrar, y un ejemplo mínimo. Incluir: `TenantResolver`, `StorageBackend`, event subscribers (`event_bus.subscribe(...)`), módulos.

---

## 4. Plan de ejecución sugerido para Claude Code

Trabajar **una fase por PR**, no todo de golpe. Plan revisado tras detectar piezas ya existentes:

| Orden | Fase | Riesgo | Tamaño | Notas |
|-------|------|--------|--------|-------|
| PR 1 | Fase 1 — `TenantContext` + `SingleTenantResolver` + `TENANT_RESOLVED` event | Bajo | S | Añade código, no toca existente. Decisión clave: `modules_enabled` por-tenant |
| PR 2a | Fase 2 — `EnginePool` + `get_db` parametrizado (backward-compat) | **Alto** | L | No elimina singleton viejo; mantiene `_legacy_get_db` |
| PR 2b | Fase 2 — migrar call sites no-endpoint + eliminar legacy | **Alto** | M | Tests, scripts, handlers que tocan DB |
| PR 3 | Fase 3 — mover storage a core + S3 + `TenantScopedStorage` | Medio | M | Re-export desde `modules/media` para no romper imports |
| PR 4 | Fase 4 — alembic `-x db_url` | Bajo | XS | 1 función, 5 líneas |
| — | Fase 5 — bus events | — | — | Plegada en PR 1 y PR 2a (no es PR aparte) |
| — | Fase 6 — settings refactor | — | — | Diferida; añadir 2 campos en PR 2a |
| PR 5 | Fase 7 — docs técnicos + CLAUDE.md | Bajo | S | Tras PR 2b |

---

## 5. Nota estratégica

Este plan son ~5 PRs de refactor que **no añaden ni una feature visible** para el usuario final. Es trabajo de plataforma. El primer cliente migrado no va a notar nada.

Es trabajo correcto y bien dimensionado, pero **en mal momento si aún no hay producto-mercado validado**. La opción razonable hoy:

- **Hacer solo la Fase 1 ahora** (1–2 días). Deja la costura mental abierta sin coste real y bloquea el riesgo de "pintarse en la esquina" porque ya define el vocabulario tenant vs clinic.
- **Posponer Fases 2a/2b/3/4/7** hasta tener una segunda clínica externa real que justifique el SaaS.

Fase 1 sola ya bloquea malas decisiones futuras. Las demás son irreversibles en términos de tiempo invertido si el producto necesita pivotar.

---

## 6. Glosario rápido

- **Tenant**: unidad de aislamiento de DB. En self-hosted hay uno (`"default"`); en SaaS hay N. **No** es lo mismo que clínica.
- **Clinic**: unidad clínica con su `clinic_id`. Un tenant puede contener una o varias. El aislamiento entre clínicas dentro de un tenant es por fila (`WHERE clinic_id = ...`), no por DB.
- **Control plane**: la DB que guarda la lista de tenants y sus metadatos. Vive en el módulo SaaS, no en core.
- **Data plane**: las DBs de cada tenant con sus datos clínicos. Una por tenant en SaaS, una única en self-hosted.
- **Resolver**: el componente que, dado un request (o un slug), devuelve el `TenantContext` correspondiente.
- **`modules_enabled`**: subset de módulos visibles para un tenant. En self-hosted = todo lo del registry; en SaaS = lo que dicte la suscripción del tenant.
- **Costura** (seam): un punto de extensión definido por una interfaz que permite sustituir la implementación sin tocar los consumidores.
