# Plan técnico: workflow Plan ↔ Presupuesto ↔ Cita

> **Audiencia:** equipo de desarrollo + agentes IA. Implementación de las decisiones validadas en `docs/workflows/plan-budget-flow.md` (uso) y el plan UX en `~/.claude/plans/ahora-mismo-el-workflow-serialized-phoenix.md`.
>
> **Alcance:** cambios de modelo, migraciones, state machines, eventos, endpoints, cron jobs, frontend, i18n, permisos, pruebas y plan de despliegue por fases.

---

## 0. Resumen ejecutivo

- Añadir estados `pending` y `closed` (con `closure_reason`) a `TreatmentPlan`. Eliminar `cancelled` (sin app en producción, sin backfill defensivo).
- Extender `Budget` con `accepted_via`, `rejection_reason`, `public_token`, `viewed_at`, `last_reminder_sent_at`, `public_auth_method`, `public_auth_secret_hash`, `public_locked_at`.
- Vista pública del presupuesto protegida con **2 factores**: UUID token (posesión) + verificación con dato del paciente (conocimiento). Cascada: teléfono últimos 4 → fecha de nacimiento → código manual definido por recepción.
- Endpoints públicos sin auth de usuario (con verificación previa a 1 factor de conocimiento).
- 5+2 endpoints autenticados nuevos (confirmar, cerrar, reabrir, reactivar, renegociar, set-public-code, unlock-public).
- 1 endpoint nuevo `GET /treatment-plans/pipeline` con SQL JOIN cross-módulo (plan + budget + agenda).
- 4 cron jobs (caducar, recordatorios, auto-cierre, purgar logs).
- 7 eventos nuevos con **payload snapshot completo** (sin callbacks cross-módulo).
- Frontend: página `/treatment-plans/pipeline`, 7 modales, vista pública mobile con pantalla de verificación, página `/settings/budgets` con sub-rutas para configuración.
- ADR dedicado a la decisión 2-factor del link público.
- 3 PRs secuenciales + cleanup PR opcional para deuda preexistente de imports.

### Decisiones arquitectónicas validadas

| Tema | Decisión |
|---|---|
| Aislamiento entre módulos | **Refactor estricto**: snapshot completo en eventos. Eliminar imports cross-módulo que no estén declarados en `manifest.depends`. |
| Plan→Presupuesto en confirmación | Llamada síncrona directa `BudgetService.create_from_plan()` (treatment_plan tiene budget en depends). Atomicidad transaccional. |
| Pipeline cross-módulo | SQL JOIN directo en `TreatmentPlanService` (depends ya cubre budgets + appointments). |
| Eventos cross-módulo | Payload con snapshot completo. Suscriptores no importan modelos del publisher. |
| Auth secret de la cookie pública | Variable nueva `BUDGET_PUBLIC_SECRET_KEY` separada de `SECRET_KEY`. |
| Ruta de bandeja | `/treatment-plans/pipeline`. |
| Permisos | Granulares por acción nueva (`treatment_plans.confirm`, `.close`, `.reactivate`, `budgets.renegotiate`, `budgets.accept_in_clinic`). |
| ADR | Sí, dedicado para 2-factor del link público. |
| Canal envío MVP | Email solo. SMS/WhatsApp parked v2 (botón compartir WhatsApp en bandeja sí). |
| Reactivación de plan cerrado | Vuelve a `draft` sin presupuesto. Doctor confirma de nuevo → presupuesto v+1. |
| Caducidad configurable | Sí, UI nueva en `/settings/budgets`. |
| Despliegue | Directo a `main`. App no en producción → migraciones simples sin backfill defensivo. |
| Retención `BudgetAccessLog` | 90 días + cron de purga. |
| QA | Local con `docker-compose` + skill `/qa`. |

---

## 1. Cambios de modelo (DB)

### 1.1 `TreatmentPlan` — `backend/app/modules/treatment_plan/models.py`

| Campo | Tipo | Notas |
|---|---|---|
| `status` | `String` | Valores nuevos: `draft`, `pending`, `active`, `completed`, `closed`, `archived`. Eliminar `cancelled` (backfill). |
| `closure_reason` | `String?` | `rejected_by_patient` \| `expired` \| `cancelled_by_clinic` \| `patient_abandoned` \| `other`. Nullable. |
| `closure_note` | `Text?` | Texto libre opcional para `other` o detalle. |
| `closed_at` | `DateTime(tz=True)?` | Timestamp de transición a `closed`. |
| `confirmed_at` | `DateTime(tz=True)?` | Timestamp de transición a `pending` (analítica de tiempo en pipeline). |

Index nuevo: `idx_treatment_plans_clinic_status_closed (clinic_id, status, closed_at)` para acelerar tab "Cerrados".

### 1.2 `Budget` — `backend/app/modules/budget/models.py`

| Campo | Tipo | Notas |
|---|---|---|
| `accepted_via` | `String?` | `remote_link` \| `in_clinic` \| `manual`. Nullable hasta aceptación. |
| `rejection_reason` | `String?` | Motivo cuando `status=rejected` (catálogo cerrado del frontend público). |
| `rejection_note` | `Text?` | Comentario libre del paciente. |
| `public_token` | `UUID` | UUID v4. Único, indexado. Generado en `create_budget()`. |
| `viewed_at` | `DateTime(tz=True)?` | Primera vez que se abrió el link público. |
| `last_reminder_sent_at` | `DateTime(tz=True)?` | Último recordatorio automático enviado. |
| `public_auth_method` | `String` | `phone_last4` \| `dob` \| `manual_code` \| `none`. Resuelto al **enviar** según cascada (ver §1.4). Persistido para que la vista pública sepa qué pedir. |
| `public_auth_secret_hash` | `String?` | Solo si `public_auth_method=manual_code`: hash bcrypt/argon2 del código que recepción configuró. Nulo en otros métodos (la verificación lee de `Patient.phone` o `Patient.birth_date`). |
| `public_locked_at` | `DateTime(tz=True)?` | Setea cuando se alcanzan 10 intentos fallidos totales. Token queda inválido hasta reenvío. |

Index nuevo: `idx_budgets_public_token (public_token)` UNIQUE.

`BudgetSignature` ya existe; sigue siendo el sumidero del audit trail. `accepted_via` se duplica en `Budget` para que las queries de pipeline no necesiten join.

**Nueva tabla `BudgetAccessLog`** (auditoría de intentos):

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | PK |
| `budget_id` | UUID FK | |
| `attempted_at` | DateTime(tz=True) | |
| `ip_hash` | String | SHA-256 de IP (privacidad) |
| `success` | Boolean | |
| `method_attempted` | String | `phone_last4` / `dob` / `manual_code` |

Index `(budget_id, attempted_at)` para rate limit / lockout queries.

### 1.3 Settings por clínica — `clinic.settings` JSONB (`backend/app/core/auth/models.py:35`)

Nuevas claves (todas opcionales, con default por código). Editables vía la nueva UI `/settings/budgets`.

```jsonc
{
  "budget_reminders_enabled": false,            // default false (opt-in)
  "budget_expiry_days": 30,                     // editable en UI (rango 7-180)
  "plan_auto_close_days_after_expiry": 30,      // editable en UI
  "budget_public_link_base_url": "https://...", // opcional, default a clinic_subdomain
  "budget_public_auth_disabled": false          // opt-in para desactivar verificación (asume riesgo)
}
```

No requiere migración (es JSONB ya existente). Solo defaults en el código que lee y endpoint nuevo `PATCH /api/v1/clinic/settings/budget` (ver §5.2).

### 1.4 Cascada de método de autenticación pública

Resuelta en **`BudgetWorkflowService.send_budget()`** ANTES de marcar `sent`. Determinista, persistida en `Budget.public_auth_method`:

```
1. Si clinic.settings.budget_public_link_auth_disabled == true:
       method = "none"
2. Sino, leer Patient asociado:
       a. Si patient.phone tiene ≥4 dígitos numéricos:
              method = "phone_last4"
       b. Sino si patient.birth_date no es nulo:
              method = "dob"
       c. Sino:
              method = "manual_code"
              → BLOQUEAR envío hasta que recepción configure un código.
                Frontend muestra modal "Este paciente no tiene teléfono ni
                fecha de nacimiento. Define un código de 4-6 dígitos para
                proteger el presupuesto."
                Backend rechaza con 422 + payload { reason: "auth_setup_required" }.
                Recepción introduce código → se hashea → presupuesto se envía.
```

**Validación contra el dato:**

| Method | Comparación |
|---|---|
| `phone_last4` | `value == patient.phone[-4:]` (extraer solo dígitos numéricos del teléfono normalizado) |
| `dob` | `value` parseado como ISO date == `patient.birth_date` |
| `manual_code` | `verify_password(value, budget.public_auth_secret_hash)` (constant-time) |
| `none` | siempre OK |

**Rate limit y lockout** (sobre `BudgetAccessLog`):

- Máximo 5 intentos fallidos por presupuesto en ventana de 15 min → 429.
- Tras 10 intentos fallidos totales → presupuesto bloqueado (`Budget.public_locked_at` se setea), recepción debe **reenviar** (clona a nuevo presupuesto con nuevo token). Notificación a recepción.
- Por IP: 20 intentos/h → 429 globalmente sobre todos los públicos.

---

## 2. Migraciones Alembic

Recordatorio: cada módulo en su branch. `branch_labels = ("treatment_plan",)` y `("budget",)` ya existen.

### 2.1 `treatment_plan/migrations/versions/<rev>_add_pending_closed_states.py`

App no en producción → migración simple sin backfill defensivo.

```python
def upgrade():
    op.add_column("treatment_plans", sa.Column("closure_reason", sa.String(50), nullable=True))
    op.add_column("treatment_plans", sa.Column("closure_note", sa.Text, nullable=True))
    op.add_column("treatment_plans", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("treatment_plans", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_treatment_plans_clinic_status_closed",
                    "treatment_plans", ["clinic_id", "status", "closed_at"])
    # App no en producción: migrar filas demo si las hay y descartar las problemáticas.
    op.execute("UPDATE treatment_plans SET status = 'closed', closure_reason = 'cancelled_by_clinic' WHERE status = 'cancelled'")
```

`downgrade`: dropea columnas + índice. No revierte status (no aplica al no haber datos de producción).

### 2.2 `budget/migrations/versions/<rev>_add_acceptance_metadata.py`

```python
def upgrade():
    op.add_column("budgets", sa.Column("accepted_via", sa.String(20), nullable=True))
    op.add_column("budgets", sa.Column("rejection_reason", sa.String(50), nullable=True))
    op.add_column("budgets", sa.Column("rejection_note", sa.Text, nullable=True))
    op.add_column("budgets", sa.Column("public_token",
                  postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("budgets", sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("budgets", sa.Column("last_reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("budgets", sa.Column("public_auth_method", sa.String(20), nullable=True))
    op.add_column("budgets", sa.Column("public_auth_secret_hash", sa.String(255), nullable=True))
    op.add_column("budgets", sa.Column("public_locked_at", sa.DateTime(timezone=True), nullable=True))
    # Backfill tokens existentes
    op.execute("UPDATE budgets SET public_token = gen_random_uuid() WHERE public_token IS NULL")
    # Backfill aceptados anteriores: marcamos como manual y desactivamos auth pública
    # (links históricos no usan flujo nuevo).
    op.execute("UPDATE budgets SET accepted_via = 'manual', public_auth_method = 'none' WHERE status = 'accepted'")
    # Resto de presupuestos antiguos: forzamos none también para no romper links existentes ya enviados
    op.execute("UPDATE budgets SET public_auth_method = 'none' WHERE public_auth_method IS NULL")
    op.alter_column("budgets", "public_token", nullable=False)
    op.alter_column("budgets", "public_auth_method", nullable=False)
    op.create_index("idx_budgets_public_token", "budgets", ["public_token"], unique=True)

    # Nueva tabla de auditoría
    op.create_table(
        "budget_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("budget_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("method_attempted", sa.String(20), nullable=False),
    )
    op.create_index("idx_budget_access_logs_budget_attempted",
                    "budget_access_logs", ["budget_id", "attempted_at"])
```

Requiere extensión `pgcrypto` (verificar `gen_random_uuid()` disponible). Alternativa: backfill por código en una `data_migration` Python.

---

## 3. State machines

### 3.1 `TreatmentPlan` — `backend/app/modules/treatment_plan/service.py`

Reemplazar `valid_transitions` (línea 243-252) por:

```python
VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft":     {"pending", "closed"},
    "pending":   {"active", "draft", "closed"},
    "active":    {"completed", "closed"},
    "completed": {"archived"},
    "closed":    {"draft"},
    "archived":  set(),
}
```

Nuevos métodos en `TreatmentPlanService` (wrappers sobre `update_status` con validación específica):

| Método | Origen | Destino | Validación adicional | Evento publicado |
|---|---|---|---|---|
| `confirm(plan_id, user_id)` | `draft` | `pending` | Plan tiene ≥1 item | `treatment_plan.confirmed` |
| `reopen(plan_id, user_id)` | `pending` | `draft` | Cancela budget actual si existe | `treatment_plan.status_changed` |
| `close(plan_id, reason, note, user_id)` | `*` | `closed` | `reason` en catálogo | `treatment_plan.closed` |
| `reactivate(plan_id, user_id)` | `closed` | `draft` | — | `treatment_plan.reactivated` |
| `accept_from_budget(plan_id)` | `pending` | `active` | Llamado por handler de `budget.accepted` | `treatment_plan.status_changed` |
| `reject_from_budget(plan_id, reason)` | `pending` | `closed` con `closure_reason=rejected_by_patient` | Llamado por handler de `budget.rejected` | `treatment_plan.closed` |

`confirm()` además dispara la creación del budget draft si no existe (a través del handler ya presente del módulo budget que escucha `treatment_plan.confirmed`).

`_check_and_complete_plan` (línea 687) se mantiene; transiciona `active → completed`.

### 3.2 `Budget` — `backend/app/modules/budget/workflow.py`

Tabla `VALID_TRANSITIONS` (línea 14-22) se mantiene. Nuevas/modificadas funciones:

| Función | Cambio |
|---|---|
| `accept_budget(budget_id, accepted_via, signer_name, signature_data?)` | Nueva firma. Persiste `accepted_via` en `Budget`. Crea `BudgetSignature`. |
| `reject_budget(budget_id, reason, note?)` | Nueva firma. Persiste `rejection_reason` y `rejection_note` en `Budget` (además de history). |
| `cancel_for_renegotiation(budget_id, user_id)` | Nuevo. Cancela budget + publica `budget.renegotiated` que dispara `plan.reopen`. |
| `mark_viewed(budget_id)` | Nuevo. Setea `viewed_at` si nulo. Publica `budget.viewed` (idempotente). |
| `check_expired_budgets()` | Existente (línea 301-347). Extender: publicar `budget.expired` event con payload `{plan_id, days_overdue}`. |
| `send_reminder(budget_id)` | Nuevo. Publica `budget.reminder_sent`. Setea `last_reminder_sent_at`. |
| `clone_to_new_draft(budget_id, user_id)` | Nuevo. Clona en versión `n+1` `draft` (modelo ya soporta `parent_budget_id` y `version`). |

---

## 4. Eventos nuevos

`backend/app/core/events/types.py`:

```python
TREATMENT_PLAN_CONFIRMED = "treatment_plan.confirmed"
TREATMENT_PLAN_CLOSED = "treatment_plan.closed"
TREATMENT_PLAN_REACTIVATED = "treatment_plan.reactivated"
BUDGET_EXPIRED = "budget.expired"
BUDGET_RENEGOTIATED = "budget.renegotiated"
BUDGET_VIEWED = "budget.viewed"
BUDGET_REMINDER_SENT = "budget.reminder_sent"
# Añadidos con issue #162:
BUDGET_CANCELLED = "budget.cancelled"
BUDGET_SUPERSEDED = "budget.superseded"
```

Re-correr `python backend/scripts/generate_catalogs.py` (regla de CLAUDE.md raíz).

### Suscripciones

| Evento | Suscriptor | Acción |
|---|---|---|
| `treatment_plan.confirmed` | `budget` | Crea budget draft con líneas del plan. |
| `budget.accepted` | `treatment_plan` | `pending → active`; desde #162 también `closed(rejected_by_patient) → active` al aceptar una versión reenviada. |
| `budget.rejected` | `treatment_plan` | `pending → closed` con `closure_reason=rejected_by_patient`. |
| `budget.expired` | `treatment_plan` | NO cambia estado inmediato. Solo log timeline. Cron separado auto-cierra tras N días. |
| `budget.renegotiated` | `treatment_plan` | `pending → draft`. |
| `budget.cancelled` (#162) | `treatment_plan` | `pending → draft` (cancelación directa desde el módulo de presupuestos). No se publica cuando el cancel lo inicia `reopen()` del propio plan. |
| `budget.superseded` (#162) | `treatment_plan` | Re-apunta `plan.budget_id` a la nueva versión creada por `/resend`. Publicado tras el commit (el suscriptor apunta una FK a la fila nueva). |
| `treatment_plan.confirmed/closed/reactivated` | `patient_timeline` | Inserta entrada en timeline. |
| `budget.expired/reminder_sent/viewed` | `patient_timeline` | Inserta entrada en timeline. |

---

## 5. Endpoints

### 5.1 `treatment_plan` — `backend/app/modules/treatment_plan/router.py`

| Método | Path | Permiso | Body / Query |
|---|---|---|---|
| `POST` | `/api/v1/treatment-plans/{id}/confirm` | `clinical.treatment_plans.confirm` | — |
| `POST` | `/api/v1/treatment-plans/{id}/reopen` | `clinical.treatment_plans.write` | — |
| `POST` | `/api/v1/treatment-plans/{id}/close` | `clinical.treatment_plans.close` | `{ reason, note? }` |
| `POST` | `/api/v1/treatment-plans/{id}/reactivate` | `clinical.treatment_plans.reactivate` | — |
| `POST` | `/api/v1/treatment-plans/{id}/contact-log` | `clinical.treatment_plans.write` | `{ channel, note }` |
| `GET` | `/api/v1/treatment-plans/pipeline` | `clinical.treatment_plans.read` | `tab`, `doctor_id?`, `from?`, `to?`, `min_amount?`, `q?`, `page`, `page_size` |

`GET /pipeline` devuelve `PaginatedApiResponse[PipelineRow]`. `PipelineRow` agrega:
- patient (id, full_name, photo_url, phone)
- plan (id, status, total_items, items_completed, days_in_status)
- budget (id, status, total, valid_until, last_reminder_sent_at)
- next_appointment (datetime?, cabinet?, doctor?)
- last_contact (timestamp?, channel?, note?)

Implementación: query SQL en `TreatmentPlanService.list_pipeline()` con joins a `budgets` y `appointments` (depends ya cubre ambos). Filtra por tab vía `WHERE` clauses específicos.

### 5.2 `budget` — `backend/app/modules/budget/router.py`

**Públicos (sin auth de usuario; con verificación 2-factor cuando `public_auth_method != "none"`):**

| Método | Path | Body | Cookie sesión requerida |
|---|---|---|---|
| `GET` | `/api/v1/public/budgets/{token}/meta` | — | No |
| `POST` | `/api/v1/public/budgets/{token}/verify` | `{ method, value }` | No |
| `GET` | `/api/v1/public/budgets/{token}` | — | Sí (o `method=none`) |
| `POST` | `/api/v1/public/budgets/{token}/accept` | `{ signer_name, signature_data? }` | Sí (o `method=none`) |
| `POST` | `/api/v1/public/budgets/{token}/reject` | `{ reason, note? }` | Sí (o `method=none`) |
| `POST` | `/api/v1/public/budgets/{token}/request-changes` | `{ reason, note? }` | Sí (o `method=none`) |

**`/meta`** devuelve `{ requires_verification: bool, method: "phone_last4"|"dob"|"manual_code"|"none", clinic_name, locked: bool, expired: bool }`. Sin datos sensibles. Permite a la SPA decidir qué pantalla mostrar.

**`/verify`** valida la cascada (§1.4). Si OK, setea cookie `budget_session_<token>`:
- `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/api/v1/public/budgets/<token>`.
- Valor: JWT firmado con `SECRET_KEY`, claims `{ sub: budget_id, exp: now+30min }`.
- TTL 30 min. Renovable en cada request exitoso.

**`/accept`, `/reject`, `/request-changes`** usan dependency `Depends(get_public_budget_session)` que valida cookie + token.

**Validaciones de acceso:**
- Token UUID válido, presupuesto existe.
- `valid_until >= today` (si caducado → 410 Gone con `{ status: "expired" }`).
- `public_locked_at` nulo (si bloqueado → 423 Locked).
- Status en `{sent}` (draft no es público; solo previsualización autenticada).
- Idempotencia: si ya `accepted` o `rejected`, `/accept` y `/reject` devuelven 409 con estado actual; `/meta` y `/` siguen funcionando para mostrar pantalla "ya respondiste".

**Rate limit (slowapi):**
- `/verify`: 5 intentos / 15 min por token + 20 / hora por IP. Excedido → 429.
- `/meta`: 60 / min por IP.
- Resto: heredan rate limit por sesión validada.

**Autenticados (nuevos):**

| Método | Path | Permiso | Body |
|---|---|---|---|
| `POST` | `/api/v1/budgets/{id}/renegotiate` | `clinical.budgets.write` | — |
| `POST` | `/api/v1/budgets/{id}/accept-in-clinic` | `clinical.budgets.accept_in_clinic` | `{ signer_name, signature_data? }` |
| `POST` | `/api/v1/budgets/{id}/resend` | `clinical.budgets.write` | — (clona a v+1 draft, nuevo token + auth re-resuelta) |
| `POST` | `/api/v1/budgets/{id}/send-reminder` | `clinical.budgets.write` | — (manual) |
| `POST` | `/api/v1/budgets/{id}/set-public-code` | `clinical.budgets.write` | `{ code }` (4-6 dígitos) — solo cuando paciente sin teléfono ni DOB. Setea `public_auth_method=manual_code` + `public_auth_secret_hash`. |
| `POST` | `/api/v1/budgets/{id}/unlock-public` | `clinical.budgets.write` | — limpia `public_locked_at` y log previo. Útil tras resolver duda con paciente sin reenviar. |
| `PATCH` | `/api/v1/clinic/settings/budget` | `admin` | `{ budget_expiry_days?, plan_auto_close_days_after_expiry?, budget_reminders_enabled?, budget_public_auth_disabled? }`. Vive en `budget` o en `core` — proponemos en core (`backend/app/core/auth/router.py`) ya que `clinic` y `settings` son core. |

---

## 6. Cron / jobs

`backend/app/core/scheduler.py` (línea 50-60, donde está `appointment_reminders`):

```python
scheduler.add_job(expire_budgets, CronTrigger(hour=2, minute=0),
                  id="expire_budgets", max_instances=1)
scheduler.add_job(send_budget_reminders, CronTrigger(hour=9, minute=0),
                  id="send_budget_reminders", max_instances=1)
scheduler.add_job(auto_close_expired_plans, CronTrigger(hour=3, minute=0),
                  id="auto_close_expired_plans", max_instances=1)
scheduler.add_job(purge_budget_access_logs, CronTrigger(hour=4, minute=0),
                  id="purge_budget_access_logs", max_instances=1)
```

**`expire_budgets()`**: llama a `BudgetWorkflowService.check_expired_budgets()`. Ya existe — se extiende para publicar evento.

**`send_budget_reminders()`**: para cada clínica con `budget_reminders_enabled=true`, query budgets `sent` con `sent_at` hace 7d o 14d sin `last_reminder_sent_at` posterior. Envía email + publica `budget.reminder_sent`.

**`auto_close_expired_plans()`**: query plans `pending` cuyo budget asociado está `expired` desde hace > `plan_auto_close_days_after_expiry` (default 30). Llama a `TreatmentPlanService.close(reason='expired')`.

**`purge_budget_access_logs()`**: borra filas de `BudgetAccessLog` con `attempted_at < NOW() - 90 days`. Cumple política de retención. Single SQL `DELETE` con LIMIT por chunks si crece mucho.

---

## 7. Frontend

### 7.1 Página `/treatment-plans/pipeline`

Path: `backend/app/modules/treatment_plan/frontend/pages/treatment-plans/pipeline.vue`

Estructura:
- `<UTabs>` con 5 tabs (queryparam `?tab=`).
- Por tab: `<UTable>` desktop, lista de `<UCard>` mobile (responsive switch en md breakpoint).
- Composable nuevo `usePipeline()` con fetch por tab, paginación, filtros.
- Filtros como queryparams (`doctor_id`, `from`, `to`, `min_amount`, `q`).
- Acciones por fila: dropdown menu + botón principal contextual.

Permission gate: `<NuxtPage>` envuelto en `<PermissionGate :require="'clinical.treatment_plans.read'">`.

### 7.2 Modales (todos en `treatment_plan/frontend/components/clinical/modals/`)

| Modal | Disparo | Contenido clave |
|---|---|---|
| `ConfirmPlanModal.vue` | Botón "Confirmar plan" en detalle | Resumen items, total, aviso de generación de presupuesto |
| `ReopenPlanModal.vue` | Botón "Reabrir" en plan `pending` | Aviso de cancelación de budget |
| `ClosePlanModal.vue` | Botón "Cerrar plan" | Selector closure_reason + textarea note |
| `ReactivatePlanModal.vue` | Botón en plan `closed` | Muestra fecha + motivo previo, confirma reactivación |
| `RenegotiateBudgetModal.vue` | En budget `sent` | Aviso de cancelación + reapertura |
| `AcceptInClinicModal.vue` | En budget `sent` | Input nombre + canvas firma opcional |
| `ContactLogModal.vue` | En filas de bandeja | Selector canal + textarea nota |
| `SetPublicCodeModal.vue` | Al enviar presupuesto si paciente sin tel ni DOB | Input código 4-6 dígitos + confirmación + aviso "Comparte este código verbalmente con el paciente" |

Todos usan `defineEmits(['confirm', 'cancel'])` y `<UModal>`.

### 7.3 Vista pública del presupuesto

Path: `backend/app/modules/budget/frontend/pages/public/budget-[token].vue`

Características:
- `definePageMeta({ layout: 'public', auth: false })`
- SSR-friendly: token validado server-side, render bloquea hasta tener datos.
- Mobile-first: layout columna única, paddings 16px, fonts 16-18px.
- Tres CTAs como botones grandes (`size="lg"`).
- Modal de firma para "Aceptar y firmar": canvas + input nombre + checkbox conformidad.

**Flujo de pantallas (state machine del cliente):**

```
1. Llega al link → fetch /meta
2. Si meta.locked → pantalla "Acceso bloqueado" + tel clínica.
3. Si meta.expired → pantalla "Presupuesto caducado" + tel clínica.
4. Si meta.requires_verification = true:
       Pantalla de verificación según meta.method:
         - phone_last4: input numérico 4 dígitos, autofocus, inputmode=numeric
         - dob: 3 selects (día/mes/año) o input date type, según UX móvil
         - manual_code: input numérico 4-6 dígitos, hint "Te lo dio recepción"
       POST /verify con { method, value }.
       Si 200 → set cookie por backend, transición a pantalla de presupuesto.
       Si 401 → mostrar "Dato incorrecto. Te quedan N intentos."
       Si 423 → "Acceso bloqueado, llama a la clínica."
       Si 429 → "Demasiados intentos. Espera 15 minutos."
5. Pantalla de presupuesto: tratamientos, total, 3 CTAs.
6. Tras aceptar/rechazar: pantalla de confirmación.
```

**Estados especiales tras decidir:**
- Ya aceptado: pantalla de confirmación + sin CTAs.
- Ya rechazado: mensaje neutro + tel clínica.

Layout `public` nuevo si no existe: `frontend/layouts/public.vue` (sin sidebar, sin auth).

**Componente nuevo**: `BudgetVerifyForm.vue` — recibe prop `method`, emite `verified` al éxito. Encapsula los 3 inputs según method.

### 7.5 Página de ajustes `/settings/budgets`

Path: `backend/app/modules/budget/frontend/pages/settings/budgets/index.vue`

Layout: grid de cards. Cada card es un acceso a una sub-página de configuración. Patrón consistente para crecer (futuras sub-páginas: plantillas de email, formas de pago, etc.).

```
/settings/budgets/
  index.vue                     # grid de cards
  expiry.vue                    # caducidad: días + auto-cierre
  reminders.vue                 # toggle recordatorios + plantillas
  public-link.vue               # toggle auth pública + base URL
```

Cards iniciales en MVP:

| Card | Sub-ruta | Configura |
|---|---|---|
| **Caducidad y auto-cierre** | `/settings/budgets/expiry` | `budget_expiry_days`, `plan_auto_close_days_after_expiry` |
| **Recordatorios automáticos** | `/settings/budgets/reminders` | `budget_reminders_enabled`, futuro: días personalizados |
| **Link público y verificación** | `/settings/budgets/public-link` | `budget_public_auth_disabled`, futuro: base URL custom |

Permisos: solo `admin` puede acceder. Gate con `<PermissionGate :require="'admin'">`.

Endpoint backend: el `PATCH /api/v1/clinic/settings/budget` ya descrito en §5.2 cubre los 3 sub-formularios.

### 7.4 Botones en detalle del plan existente

`backend/app/modules/treatment_plan/frontend/pages/treatment-plans/[id].vue`:
- Plan `draft`: botón **Confirmar plan**.
- Plan `pending`: botón **Reabrir** (secundario).
- Plan `pending` o `active`: botón **Cerrar plan** (terciario, color rojo).
- Plan `closed`: botón **Reactivar plan**.
- Badge de estado con colores semánticos: amarillo `pending`, verde `active`, gris `completed`/`closed`, rojo si `closed.reason=rejected_by_patient`.

---

## 8. i18n

Strings nuevos en `backend/app/modules/treatment_plan/frontend/i18n/locales/es.json` (y `en.json`):

```jsonc
{
  "plans.status.pending": "Pendiente",
  "plans.status.closed": "Cerrado",
  "plans.closure_reason.rejected_by_patient": "Rechazado por paciente",
  "plans.closure_reason.expired": "Caducado",
  "plans.closure_reason.cancelled_by_clinic": "Cancelado por la clínica",
  "plans.closure_reason.patient_abandoned": "Paciente abandonó",
  "plans.closure_reason.other": "Otro motivo",
  "plans.actions.confirm": "Confirmar plan",
  "plans.actions.reopen": "Reabrir",
  "plans.actions.close": "Cerrar plan",
  "plans.actions.reactivate": "Reactivar plan",
  "pipeline.title": "Bandeja de planes",
  "pipeline.tabs.por_presupuestar": "Por presupuestar",
  "pipeline.tabs.esperando_paciente": "Esperando paciente",
  "pipeline.tabs.sin_cita": "Sin cita",
  "pipeline.tabs.sin_proxima_cita": "Sin próxima cita",
  "pipeline.tabs.cerrados": "Cerrados"
}
```

Strings nuevos en `backend/app/modules/budget/frontend/i18n/locales/es.json`:

```jsonc
{
  "budget.actions.send_to_patient": "Enviar al paciente",
  "budget.actions.renegotiate": "Renegociar",
  "budget.actions.accept_in_clinic": "Marcar aceptado en clínica",
  "budget.actions.resend": "Reenviar",
  "budget.public.cta_accept": "Aceptar y firmar",
  "budget.public.cta_doubts": "Tengo dudas",
  "budget.public.cta_reject": "No me interesa",
  "budget.public.expired": "Este presupuesto ha caducado. Contacta con la clínica.",
  "budget.public.already_accepted": "Ya has aceptado este presupuesto.",
  "budget.public.verify.title": "Verifica tu identidad",
  "budget.public.verify.intro": "Para proteger tu información, confirma un dato antes de ver tu presupuesto.",
  "budget.public.verify.phone_last4_label": "Últimos 4 dígitos de tu teléfono",
  "budget.public.verify.dob_label": "Tu fecha de nacimiento",
  "budget.public.verify.manual_code_label": "Código que te ha dado la clínica",
  "budget.public.verify.submit": "Continuar",
  "budget.public.verify.invalid": "Dato incorrecto. Te quedan {n} intentos.",
  "budget.public.verify.locked": "Acceso bloqueado por demasiados intentos. Llama a la clínica.",
  "budget.public.verify.rate_limited": "Demasiados intentos. Espera 15 minutos.",
  "budget.rejection_reason.price": "Precio",
  "budget.rejection_reason.time": "Falta de tiempo",
  "budget.rejection_reason.second_opinion": "Segunda opinión",
  "budget.rejection_reason.other": "Otro"
}
```

---

## 9. Permisos

`backend/app/core/auth/permissions.py` y módulos:

Nuevos permisos retornados por `treatment_plan.get_permissions()`:
- `treatment_plans.confirm`
- `treatment_plans.close`
- `treatment_plans.reactivate`
- (existentes ya cubren read/write)

Nuevos permisos retornados por `budget.get_permissions()`:
- `budgets.renegotiate`
- `budgets.accept_in_clinic`

Mapeo a roles (en `manifest.role_permissions` de cada módulo):
- `admin: ["*"]` — sin cambios.
- `dentist: ["*"]` — sin cambios (ya tiene wildcard en clinical).
- `receptionist`: añadir explícitamente `clinical.treatment_plans.close`, `clinical.treatment_plans.reactivate`, `clinical.budgets.*`.
- `assistant`: similar a receptionist excepto `close` y `reactivate` (que son sólo recepción/admin).
- `hygienist`: solo `clinical.treatment_plans.read`.

Frontend: añadir constants en `frontend/app/config/permissions.ts`.

---

## 10. Tests

### Backend unit/integration

`backend/app/modules/treatment_plan/tests/`:

- `test_state_machine.py`: cada transición válida e inválida, validación de items required en confirm.
- `test_pipeline_endpoint.py`: cada tab devuelve filas correctas con fixtures (plan + budget + appointment).
- `test_close_reactivate.py`: ciclo completo close → reactivate.
- `test_event_handlers.py`: budget.accepted activa plan, budget.rejected lo cierra.

`backend/app/modules/budget/tests/`:

- `test_public_endpoints.py`: token válido, expirado, idempotencia (doble aceptación → 409), rate limit.
- `test_public_auth.py`: cascada (phone_last4 OK; falta phone → DOB; falta ambos → manual_code requerido bloquea envío). Lockout tras 10 fallos. Cookie sesión 30min. Validaciones constant-time del manual_code.
- `test_renegotiate.py`: cancela budget + reabre plan vía evento.
- `test_expiry_cron.py`: mock fecha, verifica transición a `expired`.
- `test_reminders_cron.py`: mock fecha + opt-in toggle.

### End-to-end

`backend/tests/test_plan_budget_flow.py`:

1. Doctor crea plan + 3 items → confirm → asserts: plan `pending`, budget `draft` creado.
2. Receptionist envía → asserts: budget `sent`, `public_token` presente.
3. Cliente HTTP sin auth abre `/api/v1/public/budgets/{token}` → asserts: 200 + `viewed_at` set.
4. Cliente acepta → asserts: plan `active`, budget `accepted`, signature row creada.
5. Marcar todos los items completed → asserts: plan `completed`.

### Frontend smoke

- Test componente `pipeline.vue` con fetch mockeado.
- Test modal `ConfirmPlanModal` emite evento confirm.
- Browser QA con `/qa` skill al final del PR 2 y PR 3.

---

## 10.bis Refactor estricto de aislamiento (deuda preexistente)

**Contexto:** hoy `budget` importa `TreatmentPlan` y `PlannedTreatmentItem` aunque `budget.manifest.depends = ["patients", "catalog"]`. Esto viola la regla del proyecto. Se aprovecha este trabajo para limpiar.

**Imports a eliminar:**

| Archivo | Línea | Import actual | Sustitución |
|---|---|---|---|
| `backend/app/modules/budget/__init__.py` | 107-108 | `from app.modules.treatment_plan.models import TreatmentPlan` (handler de evento) | Leer `plan_id` y `items` del payload; no consultar la BD del módulo origen |
| `backend/app/modules/budget/__init__.py` | 182 | `from app.modules.treatment_plan.models import TreatmentPlan` | idem |
| `backend/app/modules/budget/__init__.py` | 239-240 | `from app.modules.treatment_plan.models import PlannedTreatmentItem` | idem |
| `backend/app/modules/budget/router.py` | 96 | `from app.modules.treatment_plan.models import TreatmentPlan` | Si el endpoint necesita info del plan, mover a treatment_plan/router.py (treatment_plan SÍ depende de budget) o usar `Budget.plan_number_snapshot` denormalizado |

**Acción derivada:** denormalizar campos clave del plan en `Budget` cuando se crea (snapshot at write):

| Campo nuevo en `Budget` | Source | Por qué |
|---|---|---|
| `plan_number_snapshot` | `TreatmentPlan.plan_number` | Mostrar referencia humana sin join |
| `plan_status_snapshot` | `TreatmentPlan.status` | Filtros básicos en endpoints de budget sin import |

> Si una vista necesita estado actual del plan (no snapshot), **vive en treatment_plan**, no en budget. Treatment_plan tiene depends correcto y puede leer ambos.

**Eventos publicados con snapshot completo:**

```jsonc
// treatment_plan.confirmed (publicado por TreatmentPlanService.confirm)
{
  "plan_id": "...",
  "plan_number": "PLAN-2026-0042",
  "clinic_id": "...",
  "patient_id": "...",
  "patient_full_name": "...",
  "items": [
    { "id": "...", "catalog_item_id": "...", "tooth": 16,
      "surfaces": ["O","M"], "quantity": 1, "estimated_price": 120.00 }
  ],
  "total_estimated": 1200.00,
  "confirmed_at": "2026-04-28T10:00:00Z",
  "confirmed_by_user_id": "..."
}
```

Suscriptores (patient_timeline, futuras integraciones) **nunca** importan modelos de treatment_plan; consumen el payload.

**Tests adicionales:** un test de aislamiento que recorre `backend/app/modules/budget/` con `ast` o `grep` y falla si encuentra imports de `app.modules.treatment_plan`. Convierte la regla en CI guard.

---

## 11. Plan de despliegue (3 PRs secuenciales)

### PR 1 — Backend: state machine + endpoints + refactor aislamiento + cron + ADR

- ADR `docs/adr/NNNN-budget-public-link-auth.md` (decisión 2-factor).
- **Refactor preliminar** (§10.bis): denormalizar campos snapshot en Budget, eliminar imports cross-módulo. Test guard.
- Migraciones treatment_plan + budget.
- Models updates (incluye `plan_number_snapshot`, `plan_status_snapshot`).
- Service + workflow updates con nuevos métodos.
- Endpoints autenticados nuevos (incluye `set-public-code`, `unlock-public`, `PATCH /clinic/settings/budget`).
- Endpoints públicos del presupuesto (`/meta`, `/verify`, `/`, `/accept`, `/reject`, `/request-changes`).
- Cron jobs (4).
- Eventos nuevos con snapshot completo + handlers patient_timeline.
- Variable `BUDGET_PUBLIC_SECRET_KEY` en `.env.example`.
- Tests backend.
- Re-generate catalogs (`docs/events-catalog.md`, `docs/modules-catalog.md`).
- CHANGELOG en treatment_plan + budget + patient_timeline.

Verificación local: `./scripts/reset-db.sh && ./scripts/seed-demo.sh && pytest`.

### PR 2 — Frontend: bandeja + modales + ajustes + integraciones

- Página `/treatment-plans/pipeline`.
- 7 modales.
- Composable `usePipeline()`.
- Página `/settings/budgets` con index + 3 sub-páginas.
- Permissions config update (granulares).
- i18n strings.
- Botones nuevos en detalle del plan + badges con colores semánticos.
- Tests frontend smoke.
- Browser QA con `/qa`.

### PR 3 — Vista pública del presupuesto + emails

- Layout `public.vue`.
- Página `pages/public/budget-[token].vue` con state machine de pantallas.
- Componente `BudgetVerifyForm.vue`.
- Templates de email: `budget_sent.html`, `budget_reminder.html` (sin código manual; el código va verbal).
- Browser QA mobile con `/qa`.

Mantener PR 1 mergeable sin PR 2 (los nuevos endpoints están sin frontend pero no rompen nada). PR 2 sin PR 3 funciona (la vista pública usa endpoints ya en PR 1).

---

## 12. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Backfill `cancelled → closed` afecta integraciones externas que filtran por `cancelled` | Hacer search global pre-merge; añadir alias temporal en API si necesario |
| Token público leak por logs / referrers | UUID v4 + 2-factor verification (phone_last4 / dob / manual_code) + lockout + `valid_until`. Sin token en query string de redirects. Header `Referrer-Policy: no-referrer` en vista pública. |
| Atacante con link adivina phone_last4 | Rate limit 5/15min + lockout 10 totales + invalida token al bloquear → fuerza reenvío manual |
| Brute force de manual_code 4 dígitos | Hash bcrypt + mismas reglas de rate limit. 10⁴ × lockout = inviable. |
| Datos de paciente desactualizados (teléfono cambió) | Recepción usa `unlock-public` o reenvía con `manual_code` |
| `manual_code` filtrado por mismo canal email | Recepción lo da **verbalmente** al paciente, no por email/SMS — el modal `SetPublicCodeModal` lo deja claro |
| Cron solapa o duplica envíos de recordatorio | `max_instances=1` en APScheduler + `last_reminder_sent_at` como guard |
| Auto-cierre demasiado agresivo borra trabajo | Publica evento `treatment_plan.auto_close_pending` 24h antes; recepción puede detenerlo. (V2 si se considera necesario.) |
| Receptionist sin permiso para confirmar plan rompe flujo | Doctor confirma. Receptionist gestiona post-confirmación. UX deja claro quién hace qué. |
| Migración timeout en clínicas con muchos budgets | Backfill `public_token` por chunks si la tabla es grande (>100k filas) |
| Eventos perdidos por reinicio durante transición | Patrón actual sin durabilidad. Aceptable MVP. Anotar para v2: outbox pattern. |

---

## 13. Decisiones a confirmar antes de empezar

1. **Estado `cancelled` deprecated**: backfill + remove vs mantener como alias retrocompatible. **Recomendación: remove**. Limpio.
2. **Estado `archived`**: se mantiene como soft-archive de `completed` (oculta de filtros default). No se mezcla con `closed`.
3. **Múltiples firmas en el mismo budget**: primera firma persiste; visitas posteriores muestran "ya aceptado". No re-emisión.
4. **`budget_expiry_days` configurable** desde MVP: hard-coded 30 con override en `clinic.settings`. Sin UI en MVP.
5. **Email templates**: usar `email_notifications.md` como base; templates nuevos `budget_sent.html` y `budget_reminder.html`. El email NO debe contener el `manual_code` cuando se use; el código se entrega solo verbalmente.
6. **Auth pública 2-factor — confirmada**: cascada `phone_last4 → dob → manual_code`. Toggle `budget_public_auth_disabled` por clínica para opt-in a "sin verificación". Lockout tras 10 fallos exige reenvío.
7. **Cookie de sesión pública**: JWT firmado con `SECRET_KEY`, scope al token, TTL 30 min, HttpOnly + Secure + SameSite=Strict.

---

## 14. Archivos a crear / modificar (referencia rápida)

### Backend nuevos

```
backend/app/modules/treatment_plan/migrations/versions/<rev>_add_pending_closed_states.py
backend/app/modules/budget/migrations/versions/<rev>_add_acceptance_metadata.py
backend/app/modules/treatment_plan/tests/test_state_machine.py
backend/app/modules/treatment_plan/tests/test_pipeline_endpoint.py
backend/app/modules/treatment_plan/tests/test_close_reactivate.py
backend/app/modules/budget/tests/test_public_endpoints.py
backend/app/modules/budget/tests/test_renegotiate.py
backend/tests/test_plan_budget_flow.py
```

### Backend modificar

```
backend/app/modules/treatment_plan/models.py            # nuevos campos
backend/app/modules/treatment_plan/service.py           # transitions
backend/app/modules/treatment_plan/router.py            # endpoints
backend/app/modules/treatment_plan/events.py            # handlers
backend/app/modules/treatment_plan/__init__.py          # role_permissions, get_permissions
backend/app/modules/budget/models.py                    # nuevos campos + snapshots denormalizados
backend/app/modules/budget/workflow.py                  # transitions + check_expired
backend/app/modules/budget/router.py                    # public + nuevos auth endpoints + REMOVE imports cross-módulo
backend/app/modules/budget/service.py                   # REMOVE imports cross-módulo (Patient via param)
backend/app/modules/budget/__init__.py                  # role_permissions, get_permissions, REMOVE imports cross-módulo en handlers
backend/app/core/events/types.py                        # nuevos eventos
backend/app/core/scheduler.py                           # 3 jobs nuevos
backend/app/modules/patient_timeline/events.py          # handlers nuevos
backend/app/modules/patient_timeline/__init__.py        # subscribe a eventos nuevos
backend/app/modules/treatment_plan/CHANGELOG.md
backend/app/modules/budget/CHANGELOG.md
backend/app/modules/patient_timeline/CHANGELOG.md
backend/app/modules/treatment_plan/CLAUDE.md            # documentar nuevos estados
backend/app/modules/budget/CLAUDE.md                    # documentar accepted_via, public link
docs/events-catalog.md                                  # auto-generado
docs/modules-catalog.md                                 # auto-generado
```

### Frontend nuevos

```
backend/app/modules/treatment_plan/frontend/components/clinical/modals/ConfirmPlanModal.vue
backend/app/modules/treatment_plan/frontend/components/clinical/modals/ReopenPlanModal.vue
backend/app/modules/treatment_plan/frontend/components/clinical/modals/ClosePlanModal.vue
backend/app/modules/treatment_plan/frontend/components/clinical/modals/ReactivatePlanModal.vue
backend/app/modules/treatment_plan/frontend/components/clinical/modals/ContactLogModal.vue
backend/app/modules/treatment_plan/frontend/composables/usePipeline.ts
backend/app/modules/budget/frontend/components/clinical/modals/RenegotiateBudgetModal.vue
backend/app/modules/budget/frontend/components/clinical/modals/AcceptInClinicModal.vue
backend/app/modules/budget/frontend/components/clinical/modals/SetPublicCodeModal.vue
backend/app/modules/budget/frontend/components/public/BudgetVerifyForm.vue
backend/app/modules/budget/frontend/pages/public/budget-[token].vue
backend/app/modules/budget/frontend/pages/settings/budgets/index.vue
backend/app/modules/budget/frontend/pages/settings/budgets/expiry.vue
backend/app/modules/budget/frontend/pages/settings/budgets/reminders.vue
backend/app/modules/budget/frontend/pages/settings/budgets/public-link.vue
backend/app/modules/treatment_plan/frontend/pages/treatment-plans/pipeline.vue
frontend/layouts/public.vue                              # si no existe
docs/adr/NNNN-budget-public-link-auth.md                 # ADR nuevo
backend/tests/test_module_isolation.py                   # CI guard de imports cross-módulo
```

### Frontend modificar

```
backend/app/modules/treatment_plan/frontend/pages/treatment-plans/[id].vue   # nuevos botones + badges
backend/app/modules/treatment_plan/frontend/i18n/locales/es.json
backend/app/modules/treatment_plan/frontend/i18n/locales/en.json
backend/app/modules/budget/frontend/i18n/locales/es.json
backend/app/modules/budget/frontend/i18n/locales/en.json
frontend/app/config/permissions.ts                                            # constants nuevos
```

---

## 15. Verificación end-to-end

### Manual (post-PR 3)

1. `docker-compose up && ./scripts/reset-db.sh && ./scripts/seed-demo.sh`.
2. Login `admin@demo.clinic / demo1234`.
3. Crear plan en paciente demo → 3 items → **Confirmar** → verificar plan `pending` + budget `draft` en bandeja.
4. Aplicar 10% descuento + **Enviar al paciente** → verificar email en logs y `public_token` generado.
5. Abrir link público en navegador anónimo → pantalla de verificación pide últimos 4 del teléfono → introducir → ver presupuesto → **Aceptar y firmar**.
   - Variante: borrar `phone` del paciente demo, reenviar → pide DOB.
   - Variante: borrar también `birth_date`, intentar enviar → modal pide configurar código manual; introducir; verbalmente al paciente; en navegador pide código.
6. Volver a app → plan `active`, fila en tab "Sin cita".
7. Agendar primera cita → ejecutar (marcar tratamientos completed) → plan auto-completa al último.

### Caminos alternativos

- Renegociar: enviar → renegociar → editar plan → reenviar → aceptar.
- Caducar: forzar `valid_until` pasado → ejecutar cron `expire_budgets` manualmente → verificar.
- Reactivar: rechazar desde link → tab "Cerrados" → reactivar → ciclo reinicia.
- Aceptación en clínica: enviar → recepción marca aceptado en clínica con firma → plan activo.

### Automatizado

```bash
docker-compose exec backend python -m pytest backend/app/modules/treatment_plan/tests/ -v
docker-compose exec backend python -m pytest backend/app/modules/budget/tests/ -v
docker-compose exec backend python -m pytest backend/tests/test_plan_budget_flow.py -v
docker-compose exec backend python -m pytest --cov=app
```

---

## 16. ADR a crear

`docs/adr/NNNN-budget-public-link-auth.md` — esqueleto:

```markdown
# Autenticación 2-factor del link público de presupuesto

## Status
Accepted (2026-04-XX)

## Context
El presupuesto contiene PII sanitaria (nombre, tratamientos, importes).
Compartir solo por UUID token deja la información expuesta si el link se
reenvía o se comparte por canales públicos (WhatsApp, screenshots, etc.).

## Decision
Vista pública protegida con dos factores:
1. UUID v4 (factor de posesión, en el link).
2. Verificación con dato del paciente (factor de conocimiento), con
   cascada determinista resuelta al enviar:
   teléfono últimos 4 → fecha de nacimiento → código manual de recepción.

Rate limit y lockout. Cookie de sesión scoped al token con TTL 30min,
firmada con `BUDGET_PUBLIC_SECRET_KEY` independiente.

## Alternatives considered
- Solo UUID: insuficiente vs link sharing.
- Password en mismo email: cero ganancia (mismo canal).
- OTP por SMS: alta seguridad, alto coste y fricción.
- DOB + tel últimos 4 (multi-factor): mayor fricción, parking para v2.

## Consequences
+ Protege PII contra link sharing sin coste de SMS.
+ Pacientes mayores/baja literacy: dato propio fácil de recordar.
- Requiere phone o DOB en ficha del paciente; sin ellos, recepción debe
  configurar código manual y darlo verbalmente.
- Lockout puede frustrar pacientes; se mitiga con reenvío fácil.

## References
- Plan técnico: `docs/workflows/plan-budget-flow-tech-plan.md` §1.4, §5.2
- Doc de uso: `docs/workflows/plan-budget-flow.md`
```

---

## 17. Referencias

- Plan UX y flujo: `~/.claude/plans/ahora-mismo-el-workflow-serialized-phoenix.md`.
- Documento de uso: `docs/workflows/plan-budget-flow.md`.
- Módulo Treatment Plan: `backend/app/modules/treatment_plan/CLAUDE.md`.
- Módulo Budget: `docs/modules/budget.md` + `backend/app/modules/budget/CLAUDE.md`.
- Creación de módulos: `docs/technical/creating-modules.md`.
- Glosario: `docs/glossary.md`.
- ADRs relevantes: `docs/adr/` (consultar índice).
