# Changelog — copilot module

## Unreleased

- i18n: add French locale (`fr.json`) with full UI coverage.

- feat(pending): "Pendientes" feed (IA redesign Fase 2, ADR 0015). New
  read-only `GET /pending` aggregates overdue recalls + budgets awaiting
  response through the tool registry with the caller's role (RBAC parity;
  no new tables, `depends = []` holds). Drawer gains a [Pendientes | Chat]
  segmented control (`CopilotPending.vue` + `CopilotDrawer.vue`); each row
  deep-links to the owning module. Cash-mismatch and the "Hecho"/done
  timeline filter are deferred until their tools exist.

- feat(nudges): event-driven proactive nudges (ADR 0014 §Deferred). New
  `copilot_nudges` table (`cop_0004`); `appointment.cancelled` →
  "fill the freed slot from recalls?" nudge, deduped per appointment with
  a same-day TTL and per-viewer permission gating. New endpoints
  `GET /nudges` + `POST /nudges/{id}/dismiss` (`copilot.chat`); drawer
  renders banners (`CopilotNudges.vue`) whose text/prompt are localized
  client-side from `kind` + `payload`. Subscription only — `depends = []`
  holds.

- feat(observability): `GET /copilot/metrics` (gated by `copilot.supervise`)
  — read-only usage dashboard aggregating `agent_audit_logs` (filtered to
  copilot agents) for tool-call counts, error rate, average latency,
  conversation count, top tools, and monthly token-budget usage. No new
  table. Surfaced as a "Usage" card on the settings panel.

- feat(digest): morning digest v2 — multi-recipient + clinic-timezone
  aware. `copilot_settings.digest_recipient_user_id` (single FK) becomes
  `digest_recipient_user_ids` (JSONB list, migration `cop_0003`); the
  task sends one email per recipient, each scoped to that recipient's
  role, and matches `digest_hour` against the clinic's local hour
  (`clinics.timezone`) instead of server-local. Settings PATCH validates
  recipients are clinic members; the settings panel gains a recipient
  multi-select.

- refactor(scheduler): declare the morning-digest job via
  `get_scheduled_jobs()` instead of being imported by name in
  `app/core/scheduler.py`. The scheduler now registers jobs only for
  loaded modules, so an uninstalled copilot contributes no job (resolves
  the import-coupling tech debt noted in ADR 0014).

- fix(settings): `CopilotSettingsService.update` validated `OPENAI_API_KEY`
  even when the PATCH did not touch `provider`, breaking digest-only opt-in
  on deployments without a key (CI). Now validates only on provider change.

- feat(digest): opt-in morning digest email (proactivity v1, ADR 0014) —
  deterministic daily briefing (today's agenda, overdue recalls, budgets
  awaiting response) gathered through the tool registry with the
  recipient's role permissions. New `copilot_settings` columns
  (`cop_0002`), hourly scheduler job, ES/EN email templates, settings
  page at `/settings/integrations/copilot`, `copilot.digest.sent` event.

- feat(playbooks): system prompt now ships three multi-step playbooks
  (daily briefing, prepare visit, fill gap from recalls) and the
  empty-state suggestions gained `workflows`, `recalls` and `money`
  categories with six new permission-gated chips (ES+EN).

- fix(bridge): `_tool_names_for` now actually excludes `exposes_free_text`
  tools when redaction is enabled (the CLAUDE.md contract promised this but
  no tool had the flag until `recalls.get_recall` landed).

- chore(copilot): `auto_install=True` — the module now installs on every
  clinic by default instead of requiring manual activation from the module
  admin UI.

- fix(copilot): after a confirmed write tool, publish the mutated module's
  namespace on the shared client `useDataBus` so the owning page refetches.
  Fixes appointments booked via the copilot not appearing in the agenda
  until a manual reload — the row persisted, but the decoupled agenda view
  was never told to refresh. Generic: forwards `{module}` from the tool name,
  no hardcoded consumer.

- fix(copilot): `CopilotSlotCard` reads `find_free_slots`' new `free_windows`
  shape and renders each as a real time range + duration (e.g. "16:00–19:00
  · 3h") instead of a bare start-time chip.

- feat(copilot): UI Fase 1 (PR-C) — humanized confirmations + copy. Write
  confirmations now render labeled rows (`CopilotConfirmCard`) instead of raw
  JSON: ids resolved to names via a session name cache harvested from read
  tools (`patient_id` → "Olivia Wilson"), ISO datetimes formatted, a friendly
  action line, and a red ring + "can't be undone" note for destructive tools
  (cancel/delete/refund). Assistant messages get a hover "copy" button.
  ES/EN parity. Frontend-only.

- chore(copilot): default OpenAI chat model → `gpt-5.4-mini`
  (`COPILOT_MODEL_CHAT_OPENAI`). The OpenAI provider now sends
  `max_completion_tokens` instead of `max_tokens` for GPT-5 / o-series
  models, which reject the legacy param.
- feat(copilot): UI Fase 1 — rich result cards. Tool results now render as
  typed cards instead of a bare chip: `CopilotPatientCard` (search_patients,
  get_patient), `CopilotAppointmentCard` (get_day_overview, get_appointment),
  `CopilotSlotCard` (find_free_slots, get_availability), with a generic
  key/value fallback for the rest (reports, timeline, …) via
  `CopilotResultCard`. The tool chip is now an accordion (expanded by
  default) toggling the card; `ToolUiMessage` carries `args`/`result`;
  locale-aware date/money formatting (`useCopilotFormat`); ES/EN parity.
  Frontend-only; no backend or tool-contract changes.
- fix(copilot): expose "New conversation" action (calls `reset()`) on the
  `/copilot` page header and the slide-over header, shown once a
  conversation has messages and disabled while streaming. Previously an
  open conversation could not be cleared from the UI.
- feat(copilot): UI Fase 0 — rebrand the surface to **"IA"** across i18n
  (ES/EN), markdown rendering for assistant replies (`CopilotMarkdown`,
  `marked` + `isomorphic-dompurify`, sanitized), permission-filtered
  empty-state starter chips (`CopilotSuggestions`), a live activity phase
  indicator ("Trabajando…/Redactando…" instead of static "Pensando…"), and
  a privacy trust line under the composer. Frontend-only; no backend or
  contract changes.

- feat(copilot): initial backend — conversational agent over DentalPin
  (issue #81 Layer C). Tables `copilot_conversations`, `copilot_messages`,
  `copilot_settings` on the `copilot` Alembic branch. SSE chat
  (`/sessions/{id}/messages`) driving the core orchestrator, inline
  write-confirmation (`/sessions/{id}/confirmations/{call_id}`),
  per-clinic provider/model/budget settings, and per-clinic token budget.
  Conversations link to a core `agent_sessions` row so tool calls audit
  to `agent_audit_logs`. Mandatory PHI redaction; OpenAI provider only in
  v1. `auto_install=False`, `removable=True`.
- feat(copilot): Nuxt layer — global `<CopilotMount>` (FAB + slide-over,
  Cmd/Ctrl+K) mounted via the new host `app.overlays` slot, a `/copilot`
  page, streaming chat over `fetch`+`ReadableStream` (`useCopilotStream`),
  tool-call chips and inline confirmation cards (`useCopilot`). Mobile-
  first, ES default + EN parity, permission-gated by `copilot.chat`.
