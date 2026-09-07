# Copilot module

Conversational AI agent over DentalPin (issue #81). A thin **surface**
over the core agentic engine (`app/core/agents` + `app/core/llm`): it
persists conversations, streams chat over SSE, and gates writes with
inline confirmation. RBAC parity is the whole point — the agent can
never see or do anything the calling user couldn't through the UI.

## Public API

Routes mounted at `/api/v1/copilot/`.

- `POST   /sessions`                          — create chat session; `copilot.chat`
- `GET    /sessions`                          — list (own, or all with `read_all`); `copilot.history.read`
- `GET    /sessions/{id}/messages`            — replay transcript; `copilot.history.read`
- `POST   /sessions/{id}/messages`            — send a turn, **SSE** stream; `copilot.chat`
- `POST   /sessions/{id}/confirmations/{cid}` — confirm/reject a pending write, **SSE**; `copilot.chat`
- `POST   /sessions/{id}/end`                 — close; `copilot.chat`
- `GET    /settings` · `PATCH /settings`      — provider/model/budget/digest; `copilot.configure`
- `GET    /metrics`                            — usage observability (read-only); `copilot.supervise`
- `GET    /pending`                            — "Pendientes" feed (read-only, deep-links); `copilot.chat`
- `GET    /nudges`                             — active proactive nudges (viewer-gated); `copilot.chat`
- `POST   /nudges/{id}/dismiss`               — dismiss a nudge; `copilot.chat`

SSE events: `token`, `tool_call`, `tool_result`, `confirmation_required`,
`usage`, `done`, `budget_exceeded`, `error`.

## Dependencies

`manifest.depends = []`. Copilot consumes tools through the global
registry only; it never imports another module's service. Modules
participate by registering their own `tools.py`.

## Permissions

`copilot.chat`, `copilot.history.read`, `copilot.history.read_all`,
`copilot.supervise`, `copilot.configure` (declared relative; registry
namespaces them).

## Tools exposed

None — copilot is a consumer, not a provider, of tools.

## Events emitted

| Event | When | Payload keys |
|---|---|---|
| `copilot.session.started` | new conversation | `clinic_id`, `conversation_id`, `user_id` |
| `copilot.session.ended` | conversation closed | `clinic_id`, `conversation_id` |
| `copilot.digest.sent` | morning digest emailed | `clinic_id`, `recipient_user_id`, `date`, `email_status` |

(`copilot.tool.invoked` / `copilot.budget.threshold_reached` remain
reserved — the `GET /metrics` dashboard reads `agent_audit_logs` directly
rather than emitting per-call events.)

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| `appointment.cancelled` | `events.on_appointment_cancelled` | create a `copilot_nudges` row ("fill the freed slot from recalls?"), deduped per appointment, same-day TTL |

Subscription only — copilot never imports the publisher (ADR 0003), so
`depends = []` holds.

## Lifecycle

- `installable=True`, `auto_install=False` (optional module, opt-in per
  project rule), `removable=True`. Own Alembic branch `("copilot",)`.

## Gotchas / non-obvious invariants

- **Inline confirmation, not the approval queue.** A WRITE/DESTRUCTIVE
  tool suspends the turn (an assistant `tool_use` block with no matching
  `tool_result` in `copilot_messages`); the user resolves it via the
  confirmations endpoint. The core `AgentApprovalQueue` is reserved for
  the later service/supervisor mode. `COPILOT_GUARDRAILS` disables the
  queue triggers but keeps rate limits + denylist.
- **History is real space.** `copilot_messages` store real values; the
  redactor tokenizes only on the way to the provider. Tokens are
  deterministic, so a resumed turn re-derives the same token.
- **`AgentContext.permissions` is the caller's effective grant set** (flag-aware:
  DB resolution when `RBAC_FROM_DB` is on, the static merged map otherwise)
  — identical to what routers enforce. Every tool call re-checks at the chokepoint.
- **PHI redaction is mandatory** by default (`copilot_settings.redaction_enabled`).
  Tools flagged `exposes_free_text` are excluded from the cloud path.
  What the redactor does and does not guarantee (pseudonymization, the
  free-text gap, cross-session correlation):
  `docs/technical/copilot-agentic-architecture.md` §15.
- **SSE owns its DB session.** Streaming endpoints open their own
  `async_session_maker` session for the stream, not `Depends(get_db)`.
- **Morning digest (proactivity v1).** `tasks.py::send_morning_digests`
  runs hourly — registered via `get_scheduled_jobs()` (the module owns
  the `ScheduledJob` spec; the scheduler imports nothing) — and emails a deterministic
  (no-LLM) briefing to opted-in clinics
  (`copilot_settings.digest_enabled/digest_hour/digest_recipient_user_ids`,
  migrations `cop_0002`/`cop_0003`). **v2:** `digest_recipient_user_ids`
  is a JSONB list (one email per recipient, each scoped to that
  recipient's role) and `digest_hour` is matched against the **clinic's
  local hour** (`clinics.timezone`), not server-local. The recipient list
  has no FK — a deleted/expelled user leaves a stale id, which the task
  skips when it doesn't resolve to an active clinic member. Data is
  gathered ONLY via `tool_registry.call()` with the recipient's role
  permissions — never query other modules' tables from the task. Config
  UI at `/settings/integrations/copilot`. Design:
  `docs/technical/copilot/proactivity.md` + ADR 0014.
- **Nudges are event-driven, not LLM.** `events.on_appointment_cancelled`
  writes a `copilot_nudges` row; the drawer (`CopilotNudges.vue`) renders
  the localized text + chat prompt from `kind` + `payload` (the row
  stores no copy, so it stays locale-correct). Deduped per clinic on
  `dedupe_key`; `expires_at` is the next clinic-local midnight and expired
  rows are filtered out (no purge needed). `required_permission` gates
  visibility per viewer. Acting on a nudge sends its prompt as a chat
  turn and dismisses it.
- **Usage metrics read `agent_audit_logs`.** `GET /metrics`
  (`CopilotMetricsService`) joins audit logs to copilot agents
  (`agents.type == "copilot"`); there's no copilot-owned metrics table.
- **Pendientes aggregates via tools, not imports** (ADR 0015).
  `PendingService` calls `recalls.list_due_recalls` / `budget.list_budgets`
  through the registry with the caller's role — same path as chat/digest,
  so RBAC parity holds and `depends = []` stays true. It reuses one
  per-clinic agent + one session (metadata `surface=copilot_pending`) so a
  drawer open doesn't insert rows each time. Read-only: items deep-link to
  the owning module; the agent writes nothing here.

## Related ADRs / docs

- `docs/technical/copilot-agentic-architecture.md` (the full plan)
- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`

## CHANGELOG

See `./CHANGELOG.md`.
