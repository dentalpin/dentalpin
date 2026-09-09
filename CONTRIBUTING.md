# Contributing to DentalPin

Thank you for your interest in contributing to DentalPin! This document will help you understand how to contribute effectively.

---

## Table of Contents

- [Understanding the Project](#understanding-the-project)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Conventions](#code-conventions)
- [Creating Modules](#creating-modules)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Good First Issues](#good-first-issues)

---

## Understanding the Project

### Business Model & License

DentalPin uses the **BSL 1.1** license (Business Source License):

- **Free to use** for clinics (self-hosted or cloud)
- **Contributions welcome** and encouraged
- **Prohibited** to host as a competing commercial SaaS
- **Converts to Apache 2.0** after 4 years

By contributing, you agree that your contributions will be licensed under BSL 1.1.

### Architecture Overview

DentalPin follows a layered architecture:

| Layer | Description |
|-------|-------------|
| **Core Platform** | Plugin system, auth, RBAC, event bus, API |
| **First-Party Modules** | clinical, odontogram, catalog, budgets, billing |
| **Ecosystem Modules** | Third-party integrations, specialties |

**Key principles:**
1. **Modular by Default** — Every feature is a module
2. **API-First** — If it's not in the API, it doesn't exist
3. **Multi-tenant** — All data is scoped by `clinic_id` (security-critical)

### Key Documentation

| Document | Purpose |
|----------|---------|
| [CLAUDE.md](CLAUDE.md) | Comprehensive technical documentation |
| [docs/technical/todos.md](docs/technical/todos.md) | Roadmap and feature backlog |
| [docs/technical/creating-modules.md](docs/technical/creating-modules.md) | Module development guide |

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Git
- Node.js 18+ (for frontend development outside Docker)
- Python 3.11+ (for backend development outside Docker)

### Setup

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/dentalpin.git
cd dentalpin

# 3. Start the development environment
docker-compose up

# 4. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/api/v1
# API Docs: http://localhost:8000/docs

# 5. Login with demo credentials
# Email: admin@demo.clinic
# Password: demo1234
```

### Development Without Docker (Optional)

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Development Workflow

### Branch Naming

```
feature/short-description    # New features
fix/issue-or-bug-description # Bug fixes
docs/what-you-documented     # Documentation
refactor/what-you-refactored # Code refactoring
```

### Making Changes

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Read relevant code first** — Understand existing patterns before adding new ones

3. **Make your changes** — Follow the code conventions below

4. **Run linters** before committing:
   ```bash
   # Backend
   docker-compose exec backend ruff check .
   docker-compose exec backend ruff format --check .

   # Frontend
   cd frontend && npm run lint
   ```

5. **Run tests**:
   ```bash
   # Backend (inside Docker)
   docker-compose exec backend python -m pytest -v

   # Frontend
   cd frontend && npm test
   ```

6. **Commit with conventional commits** (see below)

7. **Push and create a Pull Request**

### Conventional Commits

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add patient photo upload
fix: resolve calendar timezone display issue
docs: update module creation guide
refactor: extract appointment validation logic
test: add budget workflow tests
chore: update dependencies
```

**Format:** `type: short description`

- Use **imperative mood** ("add" not "added")
- Keep the first line under 72 characters
- Reference issues when relevant: `fix: resolve login error (#123)`

---

## Code Conventions

### Python (Backend)

```python
# Type hints required
async def create_patient(
    db: AsyncSession,
    clinic_id: UUID,
    data: PatientCreate,
) -> Patient:
    """Create a new patient.

    Args:
        db: Database session
        clinic_id: The clinic this patient belongs to
        data: Patient creation data

    Returns:
        The created patient
    """
    ...
```

**Rules:**
- Use `ruff` for linting and formatting
- Type hints on all functions
- Docstrings for public functions
- PEP 8 naming conventions

### TypeScript (Frontend)

```typescript
// Use Composition API with <script setup>
<script setup lang="ts">
import type { Patient } from '~/types'

const props = defineProps<{
  patientId: string
}>()

const { data: patient } = await useApi().get<Patient>(`/patients/${props.patientId}`)
</script>
```

**Rules:**
- ESLint + Prettier for formatting
- Strict TypeScript mode
- Vue 3 Composition API with `<script setup>`
- Use composables from `app/composables/`

### Internationalization (i18n)

All UI text must be translatable:

```vue
<!-- Good -->
<UButton>{{ t('patients.create') }}</UButton>

<!-- Bad - hardcoded text -->
<UButton>Create Patient</UButton>
```

Add translations to `frontend/i18n/locales/es.json` (Spanish is the primary language).

### Multi-Tenancy (Security Critical)

**Every database query MUST filter by `clinic_id`:**

```python
# CORRECT
select(Patient).where(
    Patient.clinic_id == ctx.clinic_id,
    Patient.id == patient_id
)

# WRONG - Security vulnerability!
select(Patient).where(Patient.id == patient_id)
```

### API Response Wrappers

Use standard response wrappers from `app.core.schemas`:

```python
from app.core.schemas import ApiResponse, PaginatedApiResponse

# Single item
@router.get("/patients/{id}", response_model=ApiResponse[PatientResponse])
async def get_patient(...) -> ApiResponse[PatientResponse]:
    return ApiResponse(data=patient)

# Paginated list
@router.get("/patients", response_model=PaginatedApiResponse[PatientResponse])
async def list_patients(...) -> PaginatedApiResponse[PatientResponse]:
    return PaginatedApiResponse(data=patients, total=total, page=page, page_size=page_size)
```

### RBAC Permissions

Protect endpoints with permissions:

```python
from app.core.auth.dependencies import get_clinic_context, require_permission

@router.post("/patients")
async def create_patient(
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("clinical.patients.write"))],
    ...
):
    ...
```

On the frontend, gate UI with the `PERMISSIONS` const + `usePermissions().can()`:

```vue
<script setup lang="ts">
import { PERMISSIONS } from '~/config/permissions'
const { can } = usePermissions()
</script>

<template>
  <UButton
    v-if="can(PERMISSIONS.patients.write)"
    @click="createPatient"
  >
    {{ t('patients.create') }}
  </UButton>
</template>
```

---

## Creating Modules

DentalPin has a plugin architecture. See the full guide: [docs/technical/creating-modules.md](docs/technical/creating-modules.md)

### Quick Overview

```
backend/app/modules/{module_name}/
├── __init__.py      # Module class (required)
├── models.py        # SQLAlchemy models
├── schemas.py       # Pydantic schemas
├── router.py        # FastAPI endpoints
└── service.py       # Business logic
```

### Module Class

```python
class MyModule(BaseModule):
    @property
    def name(self) -> str:
        return "mymodule"

    @property
    def version(self) -> str:
        return "0.1.0"

    def get_models(self) -> list:
        return [MyModel]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["mymodule.read", "mymodule.write"]
```

### Database Migrations

After adding/changing models:

```bash
# Create migration
docker-compose exec backend alembic revision --autogenerate -m "add my feature"

# Apply migration
docker-compose exec backend alembic upgrade head
```

### Database Conventions

```python
class MyModel(Base):
    __tablename__ = "my_models"

    # UUIDs for all primary keys
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ALWAYS include clinic_id (multi-tenancy)
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinics.id"), nullable=False, index=True
    )

    # Timezone-aware timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

---

## Testing

### Running Tests

```bash
# All backend tests (inside Docker)
docker-compose exec backend python -m pytest -v

# Specific test file
docker-compose exec backend python -m pytest tests/test_patients.py -v

# With coverage
docker-compose exec backend python -m pytest --cov=app

# Frontend tests
cd frontend && npm test
```

### Writing Tests

```python
@pytest.mark.asyncio
async def test_create_patient(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/patients",
        json={"first_name": "John", "last_name": "Doe"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()["data"]  # Note: responses are wrapped
    assert data["first_name"] == "John"
```

### Available Fixtures

```python
@pytest.fixture
async def db_session():     # Fresh database per test
@pytest.fixture
async def client():         # HTTP client
@pytest.fixture
async def auth_headers():   # {"Authorization": "Bearer ..."}
```

---

## Submitting Changes

### Pull Request Guidelines

1. **One feature per PR** — Keep PRs focused and reviewable
2. **Tests required** — Add tests for new functionality
3. **Linting passes** — Run `ruff check` and `npm run lint`
4. **Update docs** — Update CLAUDE.md or relevant docs if behavior changes
5. **Screenshots** — Include screenshots for UI changes

### PR Template

```markdown
## Summary
Brief description of the changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactoring
- [ ] Documentation

## Testing
How did you test these changes?

## Screenshots (if applicable)
```

### Code Review Process

1. All PRs require at least one review
2. Address feedback promptly
3. Resolve all conversations before merging
4. Squash commits when merging (if many small commits)

---

## Good First Issues

Looking for something to work on? Check the [Good First Issues section in docs/technical/todos.md](docs/technical/todos.md#7-good-first-issues).

### Easy Contributions

| Area | Examples |
|------|----------|
| **Translations** | Add French, Portuguese, German translations |
| **Frontend** | Dark mode, keyboard shortcuts, skeleton loaders |
| **Backend** | ARM64 Dockerfile, improved seed data |
| **Documentation** | Tutorials, architecture diagrams |
| **Testing** | Increase test coverage, add E2E tests |

---

## Getting Help

- **Questions:** Open an issue with the "question" label
- **Bugs:** Open an issue with steps to reproduce
- **Feature requests:** Open a discussion first

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Thank You!

Every contribution matters — from fixing typos to adding major features. We appreciate your time and effort in making DentalPin better for the dental community.

### Contributors

Maintainers and the review bar: [MAINTAINERS.md](./MAINTAINERS.md).

DentalPin is what it is thanks to everyone who has shipped code, reviewed changes, reported what's broken and translated the product:

- [@martinezsalmeron](https://github.com/martinezsalmeron) — creator and maintainer
- [@lamanji](https://github.com/lamanji) — contacts, tasks, activity journal, inventory, medication catalog and the practice-management module chain
- [@ZoliQua](https://github.com/ZoliQua) — maintainer; i18n (de/hu/pl/it and module-layer coverage), onboarding, notifications channels, a11y and audit sweeps
- [@tresundios](https://github.com/tresundios) — India GST compliance module and the Tamil localization
- [@hirad121](https://github.com/hirad121) — public integrations API / webhooks (phase 1) and security hardening
- [@javier-delacruz](https://github.com/javier-delacruz)
- [@ermix3](https://github.com/ermix3)

(Ordering by merged contributions; add yourself here in your first PR if we forgot you.)
