# Copilot & the agentic layer — technical plan (Issue #81)

Status: **plan / not yet implemented**. This is the technical/architecture plan for the `copilot` module and the core agentic primitives it sits on. It is the implementation contract for the design approved in the design phase. Companion: the ADRs listed in §13.

> **Scope cut (owner):** v1 = thin vertical slice + **mandatory PHI redaction** + **OpenAI provider only**. The `Provider` protocol stays vendor-agnostic so Anthropic plugs in later with zero changes below `app/core/llm/`. Deferred: Anthropic provider, RAG/pgvector, proactive/scheduled agents, self-hosted/Ollama provider, admin dashboards. Rationale in the design phase; not repeated here.
>
> **Drift note (2026-09, audit DOCS-01):** this page is the frozen v1-design
> record — the scope cut above is historical. `AnthropicProvider` has since
> landed in `backend/app/core/llm/` (factory resolves `openai` + `anthropic`
> via settings keys); RAG/proactive-agents/Ollama/admin-dashboards remain
> deferred as stated.

---

## 1. Layering recap & what each layer changes

| Layer | Where | New / changed |
|---|---|---|
| **A — core engine** (reusable by any agent surface) | `app/core/agents/`, `app/core/llm/` | `Provider` protocol + **`OpenAIProvider`** + provider factory (Anthropic later); `orchestrator.py` (provider-agnostic tool loop); `redaction.py` (PHI boundary); one optional field on `Tool`. |
| **B — tool contract** (owned by each domain module) | `app/modules/<m>/tools.py` | `get_tools()` wraps that module's own services. v1 backfill: `patients`, `agenda`. Elevated to a documented module obligation. |
| **C — copilot surface** (thin consumer) | `app/modules/copilot/` + Nuxt layer | Conversation persistence, SSE chat, per-clinic settings/budget, drawer + `/copilot` page. `depends: []`. |

### Refinements to the approved design doc (decided during the architecture audit)
1. **Inline confirmation is a turn-level pause, not the core `AgentApprovalQueue`.** Acceptance criteria require the *actor* to confirm their own write mid-turn. That is modelled as conversation state (an assistant `tool_use` with no `tool_result` yet), resolved by a confirm/reject call. The async `AgentApprovalQueue` stays reserved for the later service/supervisor mode.
2. **Frontend streaming uses `fetch()` + `ReadableStream.getReader()`**, not `EventSource`/`useEventSource` — `EventSource` is GET-only and cannot send the `Authorization: Bearer` header this app uses (`useApi.ts:29-52`).
3. **Per-clinic config + budget live in a dedicated `copilot_settings` table** (atomic monthly counters), not `Clinic.settings` JSONB.
4. **The global drawer mounts via a new `app.overlays` host slot** — the generic mount point for agent surfaces (reused by future voice #64). One small host edit; copilot stays otherwise host-decoupled and removable.
5. **`AgentContext.permissions = get_role_permissions(ctx.role)`** (the wildcard grant list). The chokepoint's `permission_matches(required, granted)` already resolves wildcard grants, so this is identical to what routers enforce — no expansion needed for the backend path.

---

## 2. Layer A — core engine

### 2.1 LLM provider (`app/core/llm/`)
The whole point of this sub-package is that **the orchestrator never knows which vendor it talks to.** It works on neutral types; each provider adapts to/from its wire format.

- `base.py` — neutral message + event types and the protocol:
  - `ProviderMessage` — vendor-agnostic turn: `role (system|user|assistant|tool)` + a list of content blocks (`text`, `tool_use{id,name,input}`, `tool_result{tool_call_id,content}`). Each provider serializes these to its own shape (Anthropic content blocks vs OpenAI `tool_calls`/`role:"tool"` messages).
  - `class Provider(Protocol)`: `async def complete(self, *, system: str, messages: list[ProviderMessage], tools: list[dict], model: str, max_tokens: int) -> AsyncIterator[ProviderEvent]`.
  - `ProviderEvent` union (vendor-agnostic): `TextDelta`, `ToolUse(id, name, input)`, `Usage(input_tokens, output_tokens)`, `Done(stop_reason)`.
- `openai_provider.py` — `OpenAIProvider` over the `openai` SDK (`client.chat.completions.create(..., stream=True)` or the Responses API). Tool schemas via `tool_to_openai_schema()` (`app/core/agents/tools/schema.py:28`). Maps OpenAI streaming deltas → `ProviderEvent`: assembles fragmented `tool_calls` deltas (id/name/arguments arrive in pieces) into a single `ToolUse`; reads usage from the final chunk (`stream_options={"include_usage": True}`).
- `anthropic_provider.py` — `AnthropicProvider` over the `anthropic` SDK (`client.messages.create(..., stream=True)`), tool schemas via `tool_to_anthropic_schema()` (`app/core/agents/tools/schema.py:19`). Same single-tool posture (`disable_parallel_tool_use`); tool results are serialized as `tool_result` blocks merged into the next `user` turn; dotted tool names map `.` ↔ `-` (Anthropic's name charset, same trick as OpenAI).
- `factory.py` — `get_provider(name: str) -> Provider` resolving `"openai"` and `"anthropic"` (raise a clear "unsupported provider" error for anything else; further vendors slot in later). The bridge passes the provider-matching `dialect` to `registry.schemas_for(...)` and the chosen `model` string.
- **Resolution order:** per-clinic `copilot_settings.provider` (defaults to `"openai"`) + `.model` override the global defaults in `app/config.py`. The providers read `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`; a provider with no key configured is rejected at settings-save time so a clinic can't select a provider the deployment can't serve.
- Deps: `openai>=1.40` and `anthropic>=0.40` in `backend/pyproject.toml`.

Redaction, budget, audit, and the inline-confirm pause are all **upstream of the provider** and therefore vendor-agnostic — adding Anthropic changed nothing outside `app/core/llm/` beyond the dialect hint and settings validation.

### 2.2 Orchestrator (`app/core/agents/orchestrator.py`)
The reusable tool-use loop. **No HTTP / SSE / copilot knowledge.** Signature sketch:

```
async def run_turn(
    *, ctx: AgentContext, provider: Provider, system: str,
    history: list[ProviderMessage], tool_names: list[str],
    redactor: Redactor, budget: BudgetGuard,
) -> AsyncIterator[TurnEvent]
```

Loop per turn:
1. `budget.check()` → if over limit, yield `BudgetExceeded` and stop.
2. `redactor.redact_outgoing(history)` → tokenized messages + tool schemas (`ctx.tools.schemas_for(tool_names, "anthropic")`, already permission-filtered in §4).
3. `provider.complete(...)`; stream `TextDelta` → yield `Token` (rehydrated for display). Accumulate `ToolUse` + `Usage`.
4. On `ToolUse`:
   - **READ tool** → execute immediately via `ctx.tools.call(...)` (the chokepoint), redact the result, append `tool_result`, continue the loop.
   - **WRITE/DESTRUCTIVE tool** → **do not execute.** Yield `ConfirmationRequired(call_id, tool, args)` and **return** (turn suspended). The unanswered `tool_use` is the persisted pending state.
5. On `Done` with no tool calls → yield `Final`, tally `Usage` into `budget`.

The orchestrator calls `ctx.tools.call()` for execution, so guardrails + RBAC + Pydantic + audit are inherited unchanged. Copilot uses a `GuardrailConfig` with `auto_require_approval_for_destructive=False` and `require_approval_for=[]` (inline confirm replaces the queue) but keeps `max_actions_per_minute/session` and `blocked_tools` (the hard denylist).

### 2.3 Redaction (`app/core/agents/redaction.py`)
The PHI boundary. Per-session `SymbolTable` mapping real value ↔ stable opaque token (`PATIENT_7a3f`, `PHONE_22b1`, `EMAIL_…`, `APPT_…`). API: `redact_outgoing(payload) -> payload'`, `rehydrate(text) -> text'`, `resolve_tool_args(args) -> args'`.

**v1 coverage (mandatory, honest about its edges):**
- **Structured tool inputs/results** — key-based redaction over the JSON: a PII key denylist (`first_name`, `last_name`, `full_name`, `phone`, `mobile`, `email`, `dni`, `nif`) plus UUID-valued `*_id` fields known to reference patients/appointments → tokenized; the same value always maps to the same token within a session (so the model can reason about "the same patient").
- **Seeded context entities** — the names/ids in `context_jsonb` are pre-loaded into the symbol table at session start.
- **User free text** — substring replacement of entities already in the symbol table. **Known gap:** a name typed by the user for an entity not yet loaded cannot be caught without NER. Documented; NER is a later milestone.
- **Free-text-returning tools** (e.g. a future "summarize history") carry `Tool.exposes_free_text=True` (new optional field, default `False`) and are **excluded from the cloud path** in v1 — the registry filters them out of `tool_names` when redaction is on. None of the v1 tools (§3) return free prose, so v1 ships clean.
- Rehydration runs on every `Token` before it reaches the client and on tool-call args before `ctx.tools.call()`.

`Tool` gains exactly one optional field: `exposes_free_text: bool = False`. No other change to the frozen dataclass.

### 2.4 Config (`app/config.py`)
Add `OPENAI_API_KEY: str = ""`, `COPILOT_PROVIDER_DEFAULT: str = "openai"`, `COPILOT_MODEL_CHAT_OPENAI: str = "gpt-4.1"`, `COPILOT_MAX_TOKENS: int = 4096`, `COPILOT_REDACTION_DEFAULT: bool = True`. Per-clinic `copilot_settings` overrides provider and model. (`ANTHROPIC_API_KEY` + Anthropic model default are added when that provider lands.)

---

## 3. Layer B — the tool contract & v1 backfill

### 3.1 The `tools.py` pattern (the maintainability guarantee)
Each module gets a `tools.py`; `__init__.py.get_tools()` returns `tools.get_tools()`. Handlers call the module's **own** existing service with `ctx.clinic_id` — zero logic duplication.

```python
# backend/app/modules/patients/tools.py
class SearchPatientsArgs(BaseModel):
    query: str
    limit: int = 20

async def _search(ctx: AgentContext, p: SearchPatientsArgs):
    items, _ = await PatientService.list_patients(ctx.db, ctx.clinic_id, search=p.query, page=1, page_size=p.limit)
    return [{"id": str(i.id), "full_name": f"{i.first_name} {i.last_name}", "phone": i.phone} for i in items]

def get_tools() -> list[Tool]:
    return [Tool(name="search_patients", description="Buscar pacientes por nombre/teléfono/email.",
                 parameters=SearchPatientsArgs, handler=_search,
                 permissions=["patients.read"], category=ToolCategory.READ)]
```

### 3.2 v1 tool set (only what the slice needs)
| Module | Tool | Category | Wraps | Permission |
|---|---|---|---|---|
| `patients` | `search_patients` | READ | `PatientService.list_patients` | `patients.read` |
| `patients` | `get_patient` | READ | `PatientService.get_patient` | `patients.read` |
| `patients` | `create_patient` | WRITE | `PatientService.create_patient` | `patients.write` |
| `agenda` | `get_day_overview` | READ | `AppointmentService.list_appointments` (day filter) | `agenda.appointments.read` |
| `agenda` | `book_appointment` | WRITE | `AppointmentService.create_appointment` | `agenda.appointments.write` |
| `agenda` | `cancel_appointment` | DESTRUCTIVE | `AppointmentService.cancel_appointment` | `agenda.appointments.write` |

**Deferred:** `find_free_slots` (free-slot computation lives in `schedules`; it registers its own tool when its slice lands — no cross-module import from `agenda`). All other modules backfill incrementally under the same contract.

#### Post-v1 backfill

The live inventory is each module's `CLAUDE.md` "Tools exposed" table.
Additions since v1, newest last:

| Module | Tool | Category | Permission |
|---|---|---|---|
| `agenda` | `get_appointment`, `list_cabinets`, `list_professionals` | READ | `agenda.appointments.read` / `agenda.cabinets.read` |
| `schedules` | `get_availability`, `find_free_slots` | READ | `schedules.availability.read` (+`agenda.appointments.read`) |
| `payments` | `payments_summary`, `collections_by_method` | READ | `payments.reports.read` |
| `reports` | `billing_report`, `top_clients_by_billing`, `scheduling_report` | READ | `reports.billing.read` / `reports.scheduling.read` |
| `patient_timeline` | `get_patient_timeline` | READ | `patient_timeline.read` |
| `catalog` | `list_catalog_items`, `get_catalog_item` | READ | `catalog.read` |
| `agenda` | `reschedule_appointment`, `update_appointment_status` | WRITE | `agenda.appointments.write` |
| `patients` | `update_patient` (contact data only) | WRITE | `patients.write` |
| `recalls` | `list_due_recalls`, `get_recall` (`exposes_free_text`) | READ | `recalls.read` |
| `recalls` | `create_recall`, `log_contact_attempt`, `snooze_recall`, `complete_recall` | WRITE | `recalls.write` |
| `budget` | `list_budgets`, `get_budget` | READ | `budget.read` |
| `budget` | `send_budget` (emails the patient) | DESTRUCTIVE | `budget.write` |
| `billing` | `list_invoices`, `get_invoice` (invoice axis only, `include_payments=False`) | READ | `billing.read` |
| `payments` | `record_payment` | WRITE | `payments.record.write` |
| `payments` | `patient_payment_history` (collection axis only) | READ | `payments.record.read` |

#### Playbooks (composite capabilities — decision record)

Multi-step workflows (daily briefing, prepare-visit, fill-gap-from-
recalls) are **prompt-level playbooks**, not composite tools: a
`_PLAYBOOKS` block appended to the static system prompt in
`copilot/bridge.py` plus permission-gated suggestion chips in
`CopilotSuggestions.vue`. Rationale: the model already chains
registered tools; every step still passes the registry chokepoint
(RBAC, guardrails, audit, redaction). A composite tool inside copilot
would need a synthetic context, its own partial-failure handling and a
second orchestration path to maintain. Revisit only if observed chains
prove unreliable in practice (repeated retry loops); record evidence
before changing the approach.

### 3.3 Contract elevation (so it never drifts)
- **Root `CLAUDE.md`** "When adding X, do Y" — new row: *New agent-exposed capability* → declare a `Tool` in `<module>/tools.py`, wrap the existing service (no logic dup), set `permissions` to the gating RBAC string and `category` conservatively (DESTRUCTIVE for side-effects / deletes), mark `exposes_free_text=True` if it returns prose, document under "Tools exposed" in the module `CLAUDE.md`.
- **`docs/checklists/new-module.md`** — add a "Agent tools" section.
- **`docs/checklists/module-claude-template.md`** — add a "Tools exposed" table.
- **Scaffold** — `backend/scripts/scaffold_module_docs.py` already stubs docs; add a `tools.py` stub emitter (or document the copy-paste pattern) so every new module is born agent-addressable.

---

## 4. Permission parity (the hard rule, mechanically)

- The copilot endpoint resolves `ClinicContext` via `Depends(get_clinic_context)` and builds `AgentContext.permissions = get_role_permissions(ctx.role)` (`app/core/auth/permissions.py:65`) — the exact grant list `require_permission` checks against. `clinic_id = ctx.clinic_id`.
- Tool schemas offered to the model are pre-filtered: `tool_names = [n for n in registry.list() if caller_can_use(n)]`, where `caller_can_use` ANDs each tool's declared `permissions` against `ctx.permissions` using `permission_matches`. The model never sees tools the user couldn't call.
- Execution re-checks at the chokepoint (`ToolRegistry.call`) regardless — defence in depth. Every handler filters by `ctx.clinic_id`.
- **Net:** the agent can neither see nor do anything the calling user couldn't through the UI. Proven by the RBAC + isolation tests in §11.

---

## 5. Layer C — the `copilot` module

### 5.1 Files & wiring
```
backend/app/modules/copilot/
  __init__.py          # CopilotModule(BaseModule)
  models.py            # CopilotConversation, CopilotMessage, CopilotSettings
  schemas.py           # Pydantic request/response
  service.py           # ConversationService, CopilotSettingsService, BudgetGuard
  orchestrator_bridge.py # builds AgentContext + Provider + Redactor, drives core orchestrator, frames SSE
  router.py            # /api/v1/copilot endpoints
  redaction_policy.py  # PII key denylist for this deployment (or import core defaults)
  migrations/versions/cop_0001_initial.py
  frontend/            # Nuxt layer (§7)
  CLAUDE.md  CHANGELOG.md
```
- Entry point in `backend/pyproject.toml`: `copilot = "app.modules.copilot:CopilotModule"`.
- `alembic.ini` `version_locations` += `app/modules/copilot/migrations/versions`.
- Manifest: `depends: []`, `installable: True`, `auto_install: False`, `removable: True`, `category: "official"`, `role_permissions` per §5.4, `frontend.layer_path: "frontend"`, `frontend.navigation: [{label:"copilot.nav", to:"/copilot", icon:"i-lucide-sparkles", permission:"copilot.chat", order:90}]`.

### 5.2 Data model (own Alembic branch `("copilot",)`, `down_revision="0001"`)
- **`copilot_conversations`** — `id, clinic_id (FK, idx), user_id (FK), session_id (FK agent_sessions.id), title, context_jsonb, model, status, total_input_tokens, total_output_tokens, cost_cents, created_at, updated_at`.
- **`copilot_messages`** — `id, conversation_id (FK, idx), clinic_id (idx), role (system|user|assistant|tool), content_jsonb (text + tool_use/tool_result blocks), tool_call_id, tool_name, input_tokens, output_tokens, created_at`. **Source of truth for resuming a suspended turn** (an assistant `tool_use` with no matching `tool_result` = awaiting confirmation).
- **`copilot_settings`** — `clinic_id (PK), provider, model, redaction_enabled (default true), monthly_token_limit, monthly_cost_limit_cents, period_start, period_input_tokens, period_output_tokens, period_cost_cents, updated_at`. Lazy `get_or_create` (RecallSettings pattern, `recalls/service.py:599`).

Every `copilot_conversation` opens a core `Agent` (type `"copilot"`, lazy per-clinic `get_or_create`) + `AgentSession` (`AgentService.start_session`) so all tool calls land in `agent_audit_logs` automatically.

### 5.3 Endpoints (`/api/v1/copilot`, all `ApiResponse`-wrapped except the SSE stream)
| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/sessions` | `copilot.chat` | create conversation; seed `context_jsonb` from body; create Agent+AgentSession |
| POST | `/sessions/{id}/messages` | `copilot.chat` | append user msg; **SSE stream** of `token` / `tool_call` / `tool_result` / `confirmation_required` / `done` / `budget_exceeded` |
| POST | `/sessions/{id}/confirmations/{call_id}` | `copilot.chat` | `{decision: confirm|reject}` → execute (or skip) the pending WRITE/DESTRUCTIVE tool, persist `tool_result`, **resume** the turn as a new SSE stream |
| GET | `/sessions` / `/sessions/{id}/messages` | `copilot.history.read` (`read_all` to see others') | replay |
| POST | `/sessions/{id}/end` | `copilot.chat` | close |
| GET/PATCH | `/settings` | `copilot.configure` (admin) | model + budget + redaction toggle |

### 5.4 Permissions & events
- `get_permissions()` → `["chat", "history.read", "history.read_all", "supervise", "configure"]` (no prefix; registry → `copilot.*`). `role_permissions`: admin `["*"]`; dentist/hygienist/assistant/receptionist `["chat", "history.read"]`.
- New `EventType` constants (`app/core/events/types.py`): `COPILOT_SESSION_STARTED`, `COPILOT_SESSION_ENDED`, `COPILOT_TOOL_INVOKED`, `COPILOT_BUDGET_THRESHOLD_REACHED`. Published via `await event_bus.publish(...)` with `clinic_id` stringified. Re-run `generate_catalogs.py`.

---

## 6. The two core flows (sequence)

### Ask (read-only)
`POST /sessions/{id}/messages` → persist user msg → SSE open → orchestrator: budget ok → redact → provider streams tokens (rehydrated → `token` events) → model calls `search_patients` (READ) → `registry.call` (RBAC+clinic+audit) → redact result → loop → provider final answer → `done` (usage tallied). One round trip, no pause.

### Act (write, inline confirm)
… provider calls `book_appointment` (WRITE) → orchestrator yields `confirmation_required{call_id, tool, args}` and **suspends** (assistant `tool_use` persisted, no `tool_result`). SSE closes. Drawer renders an approval card with the (rehydrated) args. User taps **Confirmar** → `POST /sessions/{id}/confirmations/{call_id}{decision:confirm}` → `registry.call(book_appointment)` executes (audit row written) → persist `tool_result` → **resume**: reload history, call provider again → streams the confirmation sentence → `done`. **Reject** → persist a `tool_result` of "usuario canceló" → resume → model acknowledges. Booking happens **only** after confirm — satisfies the acceptance criterion.

---

## 7. Frontend (Nuxt layer)

- **Mount:** add a `<ModuleSlot name="app.overlays" :ctx="{}" />` to `frontend/app/layouts/default.vue` (one host edit, the agent-surface mount point). Copilot's `plugins/overlays.client.ts` registers `CopilotMount.vue` into it: renders nothing inline, **teleports** a FAB + `<USlideover>` drawer to `body`, and binds the global `Cmd/Ctrl+K` listener (model: `components/settings/SettingsSearch.vue:41-70`). Removing the module removes the slot entry → zero residue.
- **Streaming:** `composables/useCopilotStream.ts` — `fetch(url, {method:'POST', headers:{Authorization:Bearer …}, body})`, read `res.body.getReader()`, parse `data: …\n\n` frames into typed events. (Not `useEventSource`; see §1.2.) Token storage/headers per `useApi.ts` / `useAuth.ts`.
- **Components:** `CopilotDrawer`, `CopilotMessageList`, `CopilotComposer`, `CopilotToolCallCard` (collapsed args/result), `CopilotConfirmationCard` (Confirmar/Cancelar → confirmations endpoint), `CopilotCitation`. Auto-imported (`{path:'./components', pathPrefix:false}`).
- **Page:** `frontend/pages/copilot/index.vue` → `/copilot` (history + long sessions).
- **Context capture:** `CopilotMount` reads `useRoute()` + `useClinic()` to build `context_jsonb` (`{patient_id?, appointment_id?, screen}`) on session create — so "agéndale revisión" needs no restated patient.
- **i18n:** `i18n/locales/{en,es}.json`, namespaced `copilot.*`; **ES default, EN parity**.
- **Permissions:** add `copilot: {chat, historyRead, configure}` to `frontend/app/config/permissions.ts`; gate launcher/page with `can(PERMISSIONS.copilot.chat)`.
- **Mobile-first** for drawer (full-height sheet on small viewports) and `/copilot` page (project rule).
- **Settings page** via `plugins/settings.client.ts` → `registerSettingsPage({category:'workspace', permission:'copilot.configure', …})` for model + budget + redaction toggle.

---

## 8. SSE & DB-session handling (the footgun)
The streaming endpoint resolves auth/context with the request-scoped `Depends(get_clinic_context)` **before** streaming. Inside the SSE generator it opens its **own** `async with async_session_maker() as db:` for the orchestrator/persistence work (commit per tool call + per persisted message), instead of relying on `Depends(get_db)` whose lifetime around a streaming body is fragile. `AgentContext.db` = that generator-scoped session. `media_type="text/event-stream"`, frames `f"data: {json.dumps(evt)}\n\n"`.

---

## 9. Budget enforcement
`BudgetGuard` reads `copilot_settings`; before each provider call checks `period_*` vs limits. ≥80% → publish `COPILOT_BUDGET_THRESHOLD_REACHED` once per period (banner via `app.banners`). ≥100% → orchestrator yields `budget_exceeded`, no provider call. After each turn, `Usage` increments `period_*` (atomic `UPDATE … SET period_input_tokens = period_input_tokens + :n`). Period rolls when `period_start` month changes (lazy reset on read).

---

## 10. Build order (v1)
1. **Core engine** — `app/core/llm/` (neutral types + protocol, `OpenAIProvider`, factory; `openai` dep, config), `orchestrator.py`, `redaction.py`, `Tool.exposes_free_text`. Unit-tested with a fake provider; one live smoke test against OpenAI.
2. **Tool backfill** — `patients/tools.py`, `agenda/tools.py` + `get_tools()` wiring. Registry tests.
3. **copilot backend** — models + migration branch, settings/budget, conversation service, orchestrator bridge, SSE endpoint, confirm endpoint, events, permissions, entry point, alembic.ini.
4. **copilot frontend** — `app.overlays` slot, mount/drawer/composer/cards, `useCopilotStream`, page, i18n, permissions.ts, settings page.
5. **Docs + catalogs + ADRs** — §12, §13; run `generate_catalogs.py` + `scaffold_module_docs.py --modules copilot`.

---

## 11. Test plan (templates from the audit)
Backend (`pytest`, fixtures `client`/`auth_headers`/`db_session`/`test_clinic` from `conftest.py:99-201`):
- **Tool unit** — each v1 tool: success path + clinic-scope (mirror `test_agents_registry.py:116`).
- **RBAC parity** — receptionist `AgentContext` (perms from `get_role_permissions("receptionist")`) → a `payments`-gated tool returns `permission denied` (mirror `test_agents_registry.py:170`); same user's `search_patients` works.
- **Multi-tenancy isolation** — a tool invoked with clinic A's `ctx` cannot read clinic B's row (mirror `test_media.py` cross-clinic 404 → here assert empty/denied).
- **Inline confirm** — drive the orchestrator with a fake provider that emits a `book_appointment` tool_use: assert the turn **suspends** with `confirmation_required` and **no** appointment row exists; POST confirm → row created + audit row; POST reject → no row, audit reflects skip.
- **Redaction** — assert no raw `full_name`/`phone`/`email`/patient-UUID appears in the payload handed to the fake provider; assert displayed tokens are rehydrated; assert a tool flagged `exposes_free_text` is excluded from `tool_names` when redaction is on.
- **Budget** — over-limit `copilot_settings` → orchestrator yields `budget_exceeded`, provider never called.
- **Provider abstraction** — run the orchestrator turn against a fake provider emitting the neutral `ProviderEvent` sequence; assert redaction/confirm/audit behave purely on neutral types (proves Anthropic will drop in later untouched). Assert `factory.get_provider` raises on unsupported names and `settings` PATCH rejects a provider whose API key is unset.
- **Uninstall round-trip** — install → converse → uninstall leaves core agent tables + other modules intact (`test_uninstall_roundtrip.py` pattern).

Manual: `docker-compose up`, login `admin@demo.clinic`, `Cmd+K`, run an Ask ("pacientes que se llamen María") and an Act ("agenda revisión a María mañana 10:00" → confirm card → confirm → booked).

---

## 12. Docs obligations (CLAUDE.md "When adding X")
New module ⇒ `app/modules/copilot/{CLAUDE.md, CHANGELOG.md}`; `docs/technical/copilot/{overview,events,permissions}.md` (scaffold); user-manual EN+ES per screen + screenshots in `docs/screenshots/copilot/`; new `EventType`s + `docs/technical/copilot/events.md`; `generate_catalogs.py`; **contract-elevation edits** (root `CLAUDE.md` row + checklist + template + scaffold stub, §3.3); `frontend/app/config/permissions.ts`.

## 13. ADRs (`docs/adr/`, next = 0014)
- **0014 — Agent permission parity & the tool chokepoint** (why `ctx.permissions = get_role_permissions(role)`; tools never widen access; inline-confirm vs `AgentApprovalQueue`).
- **0015 — Agentic layer as a core platform primitive** (orchestrator/provider/redaction in `app/core`; `tools.py` contract; `app.overlays` surface slot; PHI redaction mandatory).

## 14. Open risks for implementation
- **Free-text redaction gap** (§2.3) — v1 excludes free-text tools from cloud; communicate the limitation in UI copy. NER is a later milestone.
- **Turn resume correctness** — resuming from `copilot_messages` must reconstruct the exact `tool_use`/`tool_result` ordering the provider expects; cover with the inline-confirm test.
- **SSE session lifetime** (§8) — verify the generator-scoped session under load; no reliance on `Depends(get_db)` during streaming.
- **`agenda.book_appointment` validation** — the tool must surface the service's conflict/validation errors as a structured `tool_result` so the model can explain failures rather than the stream 500-ing.

## 15. Redaction guarantees and limits

The PHI boundary in `app/core/agents/redaction.py` tokenizes patient
identifiers before any payload reaches a cloud LLM provider.  This
section states precisely what is guaranteed, what is not, and what the
tokenization means under GDPR.

### What is guaranteed

1. **Structured fields** — any JSON key matching the PII denylist
   (`first_name`, `last_name`, `full_name`, `name`, `patient_name`,
   `phone`, `mobile`, `telephone`, `phone_number`, `email`,
   `email_address`, `dni`, `nif`, `tax_id`, `national_id`) is replaced
   with a deterministic token (`NAME_<hash>`, `PHONE_<hash>`, etc.)
   before the payload leaves the server.  UUID-valued reference keys
   (`id`, `patient_id`, `appointment_id`) are tokenized when the value
   is a valid UUID.

2. **Seeded context entities** — names and IDs from the conversation's
   `context_jsonb` blob are pre-loaded into the per-session symbol table
   at session start, so they are redacted even if they appear as
   free-text later in the conversation.

3. **Known-entity free text** — substring replacement of every value
   already present in the symbol table.  If "María García" was loaded
   as a structured field, any subsequent user-typed occurrence of that
   exact string is tokenized.

4. **Free-text-returning tools excluded** — tools carrying
   `Tool.exposes_free_text=True` are filtered out of the tool list
   offered to the cloud provider when redaction is enabled.  Today
   that flag is set by tools in `recalls`, `activity_journal` and
   `expenses` (grep `exposes_free_text=True`); those tools are simply
   unavailable to the model while redaction is on.

5. **Deterministic tokens** — the same real value always maps to the
   same token (`SHA-1(real)[:6]`, unsalted), within a session *and*
   across sessions, so the model can reason about "the same patient"
   across turns without seeing the real value, and a resumed
   conversation can rebuild its symbol table by re-redacting history.

### What is NOT guaranteed

1. **Unknown free-text PII** — a name, phone number, or identifier
   typed by the user as free text for an entity **not yet loaded** into
   the symbol table cannot be caught without named-entity recognition
   (NER).  The orchestrator performs substring replacement of *known*
   values only; novel identifiers pass through to the provider in
   cleartext.  NER is deferred to a later milestone.

2. **Anonymization** — tokens are deterministic short hashes, not
   random nonces.  This is **pseudonymization** under GDPR Article
   4(5), not anonymization.  A party that possesses the symbol table
   (i.e. the DentalPin server) can reverse every token.  There is no
   secret or salt in the hash: the cloud provider receives only the
   tokenized form and holds no table, but a party with a candidate
   list (common names, phone-number ranges) can confirm a guess by
   hashing it.  Tokens reduce identifiability; they do not remove it.

3. **Cross-session correlation** — because tokens are unsalted and
   deterministic, the same patient yields the same token in every
   conversation, every session and every clinic on the server.  A cloud
   provider observing many sessions can therefore link a token across
   conversations and build frequency patterns.  The per-session symbol
   table bounds what the server rehydrates, not what the provider can
   correlate.  A per-clinic salt would confine correlation to one
   clinic without breaking resume; it is not implemented.

### GDPR and deployment guidance

- The redaction boundary implements **pseudonymization** (GDPR Art.
  4(5)) as a technical measure under Art. 25 (data protection by
  design) and Art. 32 (security of processing).
- Deployments processing health data at scale (which dental records
  are) should include the copilot's data flow in their **Data
  Protection Impact Assessment** (DPIA, Art. 35) — specifically the
  pseudonymization scope, the free-text gap, and the cloud provider's
  data-processing agreement.
- The gap is acceptable for v1 because: (a) the primary interaction
  pattern is structured tool calls (search/book/cancel), not free-text
  clinical notes; (b) rehydration is server-side, so the model only
  ever sees and emits tokens; (c) free-text tools are excluded from the
  cloud path.  Revisit if real transcripts show free-text PII leakage
  is common.
