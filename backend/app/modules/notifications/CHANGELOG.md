# Changelog — notifications module

## Unreleased

- feat(#231 PR1): SMS channel core support. `Channel.SMS` enum;
  `_resolve_channel` SMS branch (destination = patient E.164 phone,
  `sms_enabled` opt-out honoured even on force_send, text-only so both
  template and session kinds resolve); `sms` in the ordered
  preferred/fallback channel list (replaces the hardcoded
  email/whatsapp pair); per-clinic `sms_daily_limit` (default 100/day,
  skips with `sms_rate_limited`); `sms_enabled` + `sms_opt_in_at` on
  preferences and `preferred_channel` accepting `sms`
  (`notif_0005_sms_channel`).
- fix(#326): the SMTP onboarding rule carries `permission: 'notifications.settings.read'`.

- refactor(#126): budget_sent treatment names resolve through the shared `app.core.i18n_names.catalog_name` helper (was es → en → first value).

- feat(#343): patient communications in German, Hungarian, Polish and Italian — full email-template sets under `backend/templates/email/{de,hu,pl,it}/`, the clinic communication-language gate and pickers extended to all 9 UI languages, and parity gaps in existing locales filled (`en` verifactu `.txt` bodies, `invoice_sent` for es/fr/pt). A parity test now pins every locale to the same template set.

- feat(#334): Hungarian (hu) locale for the module's frontend layer.

- fix(#325): the built-in EmailAdapter registers from `on_activate()` instead of at import in `channels/registry.py` (ADR 0020); activation order still guarantees email precedes vendor channels.

- fix(#101): the module's frontend adopts the useApi error contract — 400/409/422 failures the UI used to swallow now toast the backend's message; calls whose surrounding code already presents the error pass `errorToast: false` (single toast), and hand-built error reads use the shared `errorMessage`/`errorDetail` helpers.

- feat(#287): clinic-wide channel configuration — `preferred_channel`, `fallback_enabled`, `manual_channels` on clinic_notification_settings (migration notif_0004) with `available_channels` computed from the adapter registry; the gateway resolves auto-sends as preferred→fallback instead of per-type channel lists; missing preference rows no longer block WhatsApp (opt-out, bug 11); manual `POST /send` accepts `channels` and no longer 400s phone-only WhatsApp sends; every contact guard is email-OR-phone; the broken 7/14-day budget reminder actually sends (new `budget_reminder` handler + templates); skip rows carry the real channel; Settings page grew a Channels card; the type table gained invoice_sent/budget_reminder/recall_reminder.

- fix(#287): an explicit `whatsapp_enabled=False` opt-out blocks WhatsApp even under `force_send` — same contract as `email_enabled` (the reminder cron and staff Send buttons pass `force_send` and must not override a recorded opt-out); missing rows still don't block.

- feat(#287): `settings.read` granted to dentist/assistant/receptionist so every manual-send surface can read the clinic channel config and render its channel buttons (write stays admin-only).


- feat(#207): `GET /notifications/channels` reports which channels are configured for the clinic (each adapter's `supports`); the patient-summary WhatsApp conversation card hides until the channel is actually available instead of offering a reply box that can only 409.

- feat(#131): German (de) locale for the module's frontend layer.

- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.
- fix(#184): type-check clean — per-type settings read/written through typed helpers (`settingsFor()`, generic `updateLocalSetting`) instead of casts; `UModal :ui.width` is `content` in Nuxt UI v4.
- fix(#183): the six event handlers are transactional (ADR 0019) and no longer fire `asyncio.create_task` at a fresh session. That task raced the request's commit, and lost for `patient.created`: the patient row was invisible, so the **welcome message was never queued**. Each body runs in a savepoint — queueing must not be able to fail the appointment it announces.
- refactor: `NotificationGateway.enqueue` flushes instead of committing; the session's owner (`get_db`, or the scheduler job) commits.
- feat(onboarding): optional getting-started rule `smtp` — suggests configuring the email sender.

- i18n: add Tamil locale (`notifications-ta.json`) with full UI coverage.

- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- fix(ui): surface the API error instead of a generic toast in the settings, SMTP and manual-send composables.
  `catch {}` discarded the server's message, so any failure read as
  "Error" with no way to tell what went wrong. Now via
  `errorMessage()` / `errorDetail()`.

- i18n: add Portuguese locale (`notifications-pt.json`) with full UI coverage.

- i18n: add French locale (`fr.json`) with full UI coverage.

- feat(conversation): inbound replies + bidirectional WhatsApp (Phase 2A,
  ADR 0017). ``communication_messages`` gains ``direction`` (outbound/inbound)
  and ``body_text``; it is now the full per-patient thread (Alembic
  ``notif_0003``). New gateway methods ``record_inbound_reply`` (idempotent,
  opens the 24h window via ``last_inbound_at``, publishes
  ``notification.reply_received``) and ``resolve_patient_by_phone``. The
  channel resolver allows free-form (``message_kind="session"``) WhatsApp only
  inside the 24h window. New conversation API (``GET /conversations/{patient_id}``,
  ``POST /conversations/{patient_id}/reply``) + ``ConversationThread`` card on
  the patient summary. New ``NotificationService.upsert_provider_template``
  public seam so vendor modules can register HSM template mappings.

- feat(multichannel): turn the email-only module into a channel-agnostic
  gateway. New ``channels/`` package (``ChannelAdapter`` protocol,
  ``OutboundMessage``/``AdapterResult``, idempotent ``channel_registry``,
  built-in ``EmailAdapter``). Vendor modules register adapters at import
  time. See ADR 0016.
- feat(outbox): ``gateway.NotificationGateway.enqueue`` persists a ``queued``
  row (no network in-request) and a ``dispatch_outbox`` scheduled job
  (every 45s) sends with ``FOR UPDATE SKIP LOCKED`` + exponential backoff.
  ``do_not_contact`` is now a hard block on every channel.
- refactor(models): ``email_logs`` → ``communication_messages`` (outbox +
  audit in one table, ``channel``/``attempts``/``next_attempt_at``/
  ``dedup_key``/delivery timestamps); ``email_templates`` →
  ``notification_templates`` (``channel`` + ``provider_template_name`` for
  WhatsApp HSM); per-channel WhatsApp opt-in on ``notification_preferences``;
  new generic ``clinic_channel_settings``. Alembic ``notif_0002`` (data
  preserved, ``channel`` backfilled to ``email``).
- refactor(send-path): handlers, the reminder cron, and the manual-send
  route now ``enqueue`` instead of sending synchronously; the reminder
  dedup moved from a ``context_data["appointment_id"]`` scan to a
  ``dedup_key`` unique index. Removed the dead ``send_notification``/
  ``create_log`` service methods.
- feat(events): ``notification.queued/sent/failed/delivered/reply_received``.
  ``EMAIL_SENT/FAILED`` are dual-published for ``channel=email`` for one
  release so ``patient_timeline`` keeps working unchanged.
- feat(agents): ``tools.py`` exposes ``send_notification`` (WRITE) wrapping
  the gateway; respects consent, never bypasses ``do_not_contact``.
- refactor(scheduler): declare the ``appointment_reminders`` interval job
  via ``get_scheduled_jobs()`` instead of being imported by name in
  ``app/core/scheduler.py``.
- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast pattern (4 sites) in ``useNotificationSettings`` now that ``useApi`` accepts ``object`` payloads.
- fix(isolation): declare ``catalog`` in ``manifest.depends`` — the
  email-template handlers and the preview endpoint already imported
  catalog models to render line items. The dependency was real,
  just undeclared. ``KNOWN_VIOLATIONS`` allowlist trimmed
  accordingly.
- chore(events): subscribe via ``EventType.X`` constants instead of
  string literals — the events were already registered in the enum,
  the handler dict was the last drift site.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

## 0.1.0 — initial

- Email templates, per-patient preferences, SMTP/console providers.
- APScheduler-backed sending queue (`tasks.py`).
- Subscribes to 6 events across patients, agenda, budget, billing.
