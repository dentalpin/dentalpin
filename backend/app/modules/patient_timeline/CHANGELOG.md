# Changelog — patient_timeline module

## Unreleased

- fix(#948): the appointment-lifecycle and orthodontic handlers take `db` and record inside a savepoint of the publisher's transaction. A booking that created the patient and the appointment together lost its timeline entry to the `patient_timeline_patient_id_fkey` violation; a failed timeline insert still cannot roll back the booking.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- docs(#707): CLAUDE.md claimed the routes mount at
  `/api/v1/patient-timeline/`; the loader mounts every module under its
  Python name, so the real prefix is `/api/v1/patient_timeline/`.

- feat(#657): owns the `patient_timeline` GDPR erasure coverage scope
  (`get_erasure_contributors()`). The feed is retained as the clinic's
  record of events (Art. 17(3)(b)) and nothing is redacted; the row only
  replaces one `gdpr` used to hardcode, so uninstalling the module now
  removes the claim with it.

- feat(i18n): the frontend layer's directional spacing, borders, text alignment and inset positioning now resolve against the document direction (physical→logical CSS utilities, Arabic RTL support).

- refactor(#309): the demo seed moved to the host seeds package (`app/seeds/patient_timeline_demo.py`) — the module deliberately declares only `patients`, and the seed's five cross-module imports had it on the isolation allowlist; all five entries drained.

- feat(#287): subscribes the generic notification.sent/notification.failed events (all channels) instead of the legacy email.* pair — WhatsApp outbound now shows on the timeline.

- i18n(#131/#275): demo-seed treatment names fall back to any non-empty
  catalog translation after `es→en→fr→pt→ta`.

- fix(#184): type-check clean — guard the IntersectionObserver entry before reading `isIntersecting`.
- docs(#183): handlers documented as own-session/payload-only — the timeline records what the payload carries and must never be able to fail the event it logs.
- i18n: add `pt` fallback to treatment name resolution in the demo
  timeline seed.

- feat(agents): expose `tools.py` — `get_patient_timeline` (READ)
  wrapping `TimelineService.get_timeline`. Returns structured event
  metadata only (type/category/title/timestamp); free-text description +
  event_data omitted so no un-redactable prose reaches the cloud LLM.
  Issue #81 P0 batch.

- perf(list): drop the ``select_from(query.subquery())`` count
  anti-pattern in ``TimelineService.get_timeline``; count now runs
  directly over the indexed ``(clinic_id, patient_id)`` filter.
- fix(isolation): ``PatientTimeline.patient`` no longer uses
  ``back_populates="timeline_entries"`` — that attribute was removed
  from the foundational ``patients`` module so it would stop pointing
  at this consumer. Relationship stays one-directional.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

### Added (plan/budget workflow rework, 2026-04-29)

- Subscribed to 8 new cross-module events with snapshot payloads:
  `treatment_plan.{confirmed,closed,reactivated}` and
  `budget.{rejected,expired,renegotiated,viewed,reminder_sent}`. All
  rendered as Spanish-titled timeline entries; no upstream ORM imports.

## 0.1.0 — initial

- Unified activity log per patient.
- Subscribes to 22 events across the system.
- Append-only model with archive instead of delete.
