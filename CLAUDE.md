# CLAUDE.md

Working notes for AI agents on DentalPin.

## Project

DentalPin — source-available (BSL 1.1) dental clinic management software with a modular plugin architecture.

| Component | Tech |
|-----------|------|
| Backend | FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic |
| Frontend | Vue 3, Nuxt 4, Nuxt UI, TypeScript |
| Database | PostgreSQL (asyncpg) |
| Auth | JWT (access + refresh) |
| Container | Docker Compose |

License: BSL 1.1 (converts to Apache 2.0 after 4 years).

---

## Modular architecture (read first)

DentalPin is built as independent modules under `backend/app/modules/<name>/` with matching Nuxt layers. Treat the boundary as a contract.

**Hard rules:**
- Respect module isolation. Do **not** create cross-module dependencies that are not declared in the module's `manifest.depends`.
- Prefer the **event bus** for cross-module reactions. Direct service-to-service imports across modules are forbidden unless the target is in `depends`.
- Cross-module FKs are allowed **only** when the target is in `depends`. CI rejects migrations otherwise.
- Each module owns its Alembic branch (`branch_labels = ("<name>",)`). Never thread one module's revisions through another's chain — uninstall safety depends on it (issue #56).
- Permissions are namespaced: a module returns `resource.action` from `get_permissions()`; the registry prefixes with the module name.

**Before adding a feature, read `docs/technical/creating-modules.md`** — it is the source of truth for module structure, lifecycle, manifest, slots, events, tools/agents, and migrations.

**Engineering posture:**
- Think deeply before coding. Avoid over-engineering. Build only what the task needs.
- Refactor opportunistically when you spot duplication or drift, but keep refactors scoped — no drive-by rewrites.
- Do not introduce tech debt. If a shortcut is unavoidable, surface it explicitly in the PR description.

---

## When adding X, do Y (agent checklists)

| Trigger | Required actions |
|---------|------------------|
| New module | Create `backend/app/modules/<name>/CLAUDE.md` + `CHANGELOG.md`. Create `docs/technical/<name>/{overview,events,permissions}.md`. If the module has Nuxt pages, also `docs/user-manual/{en,es}/<name>/{index.md, screens/<slug>.md}` per page. Run `python backend/scripts/generate_catalogs.py`. Follow `docs/checklists/new-module.md`. |
| New screen (page under `<module>/frontend/pages/**`) | Create both `docs/user-manual/en/<module>/screens/<slug>.md` and `docs/user-manual/es/<module>/screens/<slug>.md` with the [frontmatter contract](./docs/technical/documentation-portal.md#2-frontmatter-contract-the-part-claude-relies-on). Screenshots into `docs/screenshots/<module>/`. |
| New endpoint | Document under the gating permission's row in `docs/technical/<module>/permissions.md`. Bump `last_verified_commit` on every screen MD whose `related_endpoints` covers it. |
| New event published or consumed | Add to `EventType` in `backend/app/core/events/types.py`. Add row to `docs/technical/<module>/events.md`. Re-run `generate_catalogs.py`. Document publisher payload in module CLAUDE.md. |
| New permission | Return from `get_permissions()` (no module prefix). List in `manifest.role_permissions`. Add row to `docs/technical/<module>/permissions.md`. Add to `frontend/app/config/permissions.ts` if user-facing. |
| New agent-exposed capability | Declare a `Tool` in `backend/app/modules/<name>/tools.py` and return it from the module's `get_tools()`. **Wrap an existing service method — never duplicate business logic.** Filter by `ctx.clinic_id`. Set `permissions=[...]` to the gating RBAC string the HTTP route uses, and `category` conservatively (`WRITE` for mutations, `DESTRUCTIVE` for deletes/irreversible side-effects). Set `exposes_free_text=True` if the result is free prose (it is then excluded from the cloud LLM path under redaction). **Return native values (UUID/Decimal/datetime/Pydantic) — `jsonify` at the registry chokepoint coerces them; don't hand-`str()`/`.isoformat()`/`float()`.** Name PII fields with redactor-known keys (`full_name`, `phone`, `email`, `dni`, `*_id`) so they tokenize. Document it under "Tools exposed" in the module CLAUDE.md. See [`docs/technical/copilot-agentic-architecture.md`](./docs/technical/copilot-agentic-architecture.md) §3. |
| Touched a screen's behaviour or visuals | Update the matching screen MD in **both** `docs/user-manual/{en,es}/<module>/screens/`. Refresh screenshots if visuals changed. Bump `last_verified_commit` in each locale. |
| Architectural decision | Copy `docs/adr/TEMPLATE.md` → `docs/adr/NNNN-title.md`. |
| New domain term (ES↔EN) | Append to `docs/glossary.md`. |
| New documentation file | Pick the folder by type from the **Documentation policy** table below. Never drop new files at `docs/` root. |
| Touched any module | Update its `backend/app/modules/<name>/CHANGELOG.md` under `## Unreleased`. |
| Cross-module FK or import | Target module MUST be in `manifest.depends`. CI rejects otherwise. |

Full docs-update recipe: [`docs/checklists/updating-docs.md`](./docs/checklists/updating-docs.md).
Architecture + rationale: [`docs/technical/documentation-portal.md`](./docs/technical/documentation-portal.md) ([ADR 0009](./docs/adr/0009-documentation-portal.md)).

Reference material:

- Checklists: `docs/checklists/`
- Per-module CLAUDE.md template: `docs/checklists/module-claude-template.md`
- ADRs: `docs/adr/` (start with 0001 for the modular contract)
- Glossary: `docs/glossary.md`
- Module catalog: `docs/modules-catalog.md` (auto-generated)
- Event catalog: `docs/events-catalog.md` (auto-generated)
- Reference modules to copy from: `patients` (simple), `schedules` (removable), `treatment_plan` (heavy deps), `verifactu` (compliance)

---

## Documentation policy

`/docs` is organized by **type** of doc. Pick the folder from the table; never drop new files at `docs/` root. CI (`scripts/check_docs_layout.py`) enforces this.

| Doc type | Folder |
|----------|--------|
| End-user / admin how-to (Spanish, screenshots) | `docs/user-manual/` |
| Product feature spec / UX brief (*what* + *why*) | `docs/features/` |
| Cross-cutting tech reference, tech plans, module-author guide | `docs/technical/` |
| Module-specific deep-dive | `docs/modules/<name>.md` |
| Architectural decision (rule + rationale) | `docs/adr/NNNN-title.md` |
| Agent / dev checklist | `docs/checklists/` |
| Diagram source (Mermaid / PlantUML) | `docs/diagrams/` |
| Image asset (PNG / SVG) | `docs/screenshots/` |
| Operational runbook / end-to-end workflow | `docs/workflows/` |
| Auto-generated catalog | `docs/` root, suffix `-catalog.md` |

**Only these files live at `docs/` root:** `README.md` (taxonomy index), `glossary.md`, `events-catalog.md`, `modules-catalog.md`. Anything else fails CI.

Decision tree + folder descriptions: [`docs/README.md`](./docs/README.md).

---

## Quick start

```bash
docker-compose up
docker-compose exec backend python -m pytest -v
cd backend && ruff check . && ruff format --check .
cd backend && uv lock                    # after changing dependencies in pyproject.toml — uv.lock is what Docker installs (#356); CI fails on drift
cd frontend && npm run lint
cd frontend && npm run typecheck:layers   # vue-tsc over host + all module layers (stop the frontend container first; modules.json is auto-restored, and CI guards it — see #264)

# Reset DB + reseed demo data (use after tests wipe tables)
./scripts/reset-db.sh        # drop, dentalpin db upgrade (core + installed modules)
./scripts/seed-demo.sh       # demo clinic, users, sample data
./scripts/seed-demo.sh --lang ta                  # + India GST demo (Tamil UI; module must be installed)
./scripts/seed-demo.sh --lang en --country in      # + India GST demo (English UI) — see docs/modules/india_gst.md §3.5

# Demo login
# admin@demo.clinic / demo1234
```

---

## RBAC

Source of truth: `backend/app/core/auth/permissions.py`.

Roles get **core** grants from `ROLE_PERMISSIONS` plus **module** grants
merged at runtime from each module's `manifest.role_permissions` (prefixed
with the module name) via `get_role_permissions()`. The core table is
deliberately small — clinical/module permissions live in the modules:

```python
ROLE_PERMISSIONS: Final[dict[str, list[str]]] = {
    "admin": ["*"],                                # wildcard — every namespace
    "dentist": ["agents.view", "agents.supervise"],
    "hygienist": [],
    "assistant": [],
    "receptionist": [],
}
# A module manifest contributes, e.g.:
#   role_permissions = {"receptionist": ["patients.read", "patients.write"]}
# → merged in as "patients.read" / "patients.write" for receptionist.
```

Wildcards: `*` = all; `module.*` = all in that module. Matching strips the
trailing `.*` to a dotted prefix, so `billing.*` matches `billing.x.y` but
not `billing_x.y`.

**Backend — protect endpoints:** (permission strings are module-prefixed)
```python
from app.core.auth.dependencies import get_clinic_context, require_permission

@router.get("/patients")
async def list_patients(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("patients.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ...
```

**Frontend — single source of truth:** `frontend/app/config/permissions.ts`. Always reference `PERMISSIONS.resource.action`, never hardcode strings.

```typescript
import { PERMISSIONS } from '~/config/permissions'
const { can, canAny, isAdmin } = usePermissions()
if (can(PERMISSIONS.patients.write)) { /* ... */ }
```

```vue
<UButton
  v-if="can(PERMISSIONS.patients.write)"
  icon="i-lucide-plus"
  @click="..."
>
  {{ t('patients.create') }}
</UButton>
```

Adding a permission: return it from the module's `get_permissions()` (unprefixed) → grant it to roles in the module's `manifest.role_permissions` → `require_permission("module.resource.action")` on the endpoint → add to `config/permissions.ts` → use via `usePermissions().can(PERMISSIONS.x.y)`. (Core-level permissions like `admin.*`/`agents.*` are the exception — those live in `ROLE_PERMISSIONS`/`CORE_PERMISSIONS`.)

---

## Frontend patterns

Composables:

| Composable | Purpose |
|------------|---------|
| `useAuth` | `user`, `permissions`, `login()`, `logout()` |
| `usePermissions` | `can()`, `canAny()`, `isAdmin` |
| `useApi` | HTTP client with auth + token refresh |
| `useClinic` | `currentClinic`, `cabinets` |
| `useModules` | Navigation (filtered by permissions) |
| `useUsers` | User management (admin) |

State via `useState` (SSR-compatible):
```typescript
const user = useState<User | null>('auth:user', () => null)
```

API calls:
```typescript
import type { ApiResponse, PaginatedResponse, Patient } from '~/types'
const api = useApi()

const list = await api.get<PaginatedResponse<Patient>>('/api/v1/patients')        // .data is Patient[]
const one  = await api.get<ApiResponse<Patient>>('/api/v1/patients/123')          // .data is Patient
const made = await api.post<ApiResponse<Patient>>('/api/v1/patients', { ... })    // .data is Patient
```

UI: Nuxt UI (`UButton`, `UInput`, `UCard`, `UModal`, `USelect`, `UFormField`, `UBadge`, `UAvatar`, `USkeleton`).

TS aliases inside a layer: `~` = layer root, `~~` = host frontend root (use for shared types: `import type { Patient } from '~~/app/types'`).

---

## Backend patterns

### Endpoint shape

```python
from app.core.schemas import ApiResponse, PaginatedApiResponse

@router.get("/resources", response_model=PaginatedApiResponse[ResourceResponse])
async def list_resources(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("module.resource.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedApiResponse[ResourceResponse]:
    items, total = await ResourceService.list(db, ctx.clinic_id, page, page_size)
    return PaginatedApiResponse(
        data=[ResourceResponse.model_validate(i) for i in items],
        total=total, page=page, page_size=page_size,
    )

@router.post("/resources", response_model=ApiResponse[ResourceResponse], status_code=201)
async def create_resource(
    data: ResourceCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("module.resource.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[ResourceResponse]:
    resource = await ResourceService.create(db, ctx.clinic_id, data.model_dump())
    return ApiResponse(data=ResourceResponse.model_validate(resource))
```

### Service layer

Business logic only, no HTTP concerns. Static methods on a `ResourceService` class. Routers stay thin.

### Multi-tenancy (mandatory)

Every query MUST filter by `clinic_id`:

```python
# CORRECT
select(Patient).where(Patient.clinic_id == ctx.clinic_id)

# WRONG — security vulnerability
select(Patient).where(Patient.id == patient_id)
```

The same rule applies inside agent tool handlers.

---

## Database conventions

```python
class MyModel(Base):
    __tablename__ = "my_models"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- UUID primary keys, TIMESTAMPTZ timestamps, JSONB for flexible fields.
- Soft delete via `status` (never hard-delete patient data).
- Index `clinic_id` on every multi-tenant table.

Migrations live in `backend/app/modules/<name>/migrations/versions/` on a per-module branch. See `docs/technical/creating-modules.md` §3 (`migrations/`) for the branching rules and the `--branch-label` invocation.

```bash
docker-compose exec backend python -m app.cli db upgrade   # core + installed modules (ADR 0020)
docker-compose exec backend alembic upgrade heads          # every branch, dev only
```

---

## API conventions

Wrappers from `backend/app/core/schemas.py`:

| Case | Schema |
|------|--------|
| Single item | `ApiResponse[T]` |
| Paginated list | `PaginatedApiResponse[T]` |
| Error | `ErrorResponse` |

**Exception:** auth token endpoints (`/login`, `/register`, `/refresh`) return raw tokens, not wrapped.

Status codes: `200` GET/PUT, `201` POST, `204` DELETE, `400` bad request, `401` unauth, `403` forbidden, `404` not found, `409` conflict, `422` validation.

---

## Module quick reference

Full guide: `docs/technical/creating-modules.md`. Skeleton:

```python
class MyModule(BaseModule):
    manifest = {
        "name": "mymodule",
        "version": "0.1.0",
        "category": "official",        # or "community"
        "depends": ["patients"],       # declared dependencies — enforced
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {"admin": ["*"]},
    }

    def get_models(self) -> list: return [MyModel]
    def get_router(self) -> APIRouter: return router
    def get_permissions(self) -> list[str]: return ["resource.read", "resource.write"]
    def get_event_handlers(self) -> dict: return {"patient.created": self._on_patient_created}
    # get_tools() is optional — BaseModule returns []; override only when exposing tools
```

Event bus:
```python
from app.core.events import event_bus
event_bus.publish("patient.created", {"patient_id": str(patient.id)})
```

---

## Testing

```bash
docker-compose exec backend python -m pytest -v
docker-compose exec backend python -m pytest tests/test_auth.py -v
docker-compose exec backend python -m pytest --cov=app
```

Fixtures from `conftest.py`: `db_session`, `client`, `auth_headers`.

```python
@pytest.mark.asyncio
async def test_create_patient(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/patients",
        json={"first_name": "John", "last_name": "Doe"},
        headers=auth_headers,
    )
    assert response.status_code == 201
```

For modules with `removable=True`, also cover the round-trip uninstall (see `docs/technical/creating-modules.md` §9).

---

## Environment

```bash
DATABASE_URL=postgresql+asyncpg://dental:dental_dev@db:5432/dental_clinic
SECRET_KEY=your-secret-key-min-32-chars
ENVIRONMENT=development   # development | test | production
TESTING=false
DEMO_MODE=false           # public demo: blocks user edits/removal + module lifecycle (see block_in_demo)
```

---

## Troubleshooting

- **"relation does not exist"** / tables wiped after tests: `./scripts/reset-db.sh` then `./scripts/seed-demo.sh`. Manual fallback: `DELETE FROM alembic_version;` then `python -m app.cli db upgrade`.
- **Frontend changes not showing**: `docker-compose up -d --build frontend`.
- **Permission denied but should have access**: check `clinic_memberships` row, exact permission string, `/me` payload, then re-login.

---

## Code style

- Code in English; UI strings in Spanish (i18n).
- Python: type hints required, ruff for lint/format.
- TypeScript: strict mode, ESLint.
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`).
- No over-engineering. No tech debt. Refactor when it pays off, not preemptively.
