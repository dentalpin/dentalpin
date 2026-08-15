# Changelog — schedules module

## Unreleased

- i18n: add Polish locale (`pl.json`) with full UI coverage.leased

- i18n: add Tamil locale (`ta.json`) with full UI coverage.

- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- fix(ui): surface the API error instead of a generic toast in the clinic-hours and professional-hours settings pages.
  `catch {}` discarded the server's message, so any failure read as
  "Error" with no way to tell what went wrong. Now via
  `errorMessage()` / `errorDetail()`.

- fix(professionals): professional-hours eligibility and analytics now
  check `ClinicMembership.is_professional` instead of `role IN
  (dentist, hygienist)` — an admin who also practises gets working
  hours (core migration 0006).

- i18n: add Portuguese locale (`pt.json`) with full UI coverage.

- i18n: add French locale (`fr.json`) with full UI coverage.

- fix(agents): `find_free_slots` now returns contiguous free **windows**
  (`free_windows` with real `start`/`end`/`minutes`) instead of a single
  fixed-size slot per gap that masked its true extent. The agent could not
  tell a 9:00–9:30 hole from a 9:00–18:00 one; now it can. `slot_minutes`
  becomes a minimum-duration filter; `part_of_day` filtering is overlap-based
  (`_in_part` → `_overlaps_part`).

- feat(agents): expose `tools.py` — `get_availability` (READ) wrapping
  `AvailabilityService.resolve` (open working windows for a day; the
  agent combines it with `agenda.get_day_overview` to find gaps). Issue
  #81 P0 batch.
- feat(agents): add `find_free_slots` (READ) — real bookable gaps for a
  professional (open hours minus booked appointments), filterable by
  duration / part-of-day / window, nearest first. Reads agenda
  appointments (agenda is in `depends`). Issue #81 P1 batch.

- refactor(perms): migrate hardcoded ``can('schedules.{clinic_hours.write, professional.read, professional.write, professional.own.write}')`` strings in ``ClinicHoursPage`` and ``ProfessionalSchedulesPage`` to ``PERMISSIONS.schedules.*`` (new entries in the host permissions config).
- Settings UI migrated to host's settings registry: clinic-hours and
  professional-schedules are now registered as cards/pages under
  `/settings/workspace`. Replaces the legacy `settings.sections` slot
  and the `pages/settings/*.vue` file-based routes (2026-04-28).
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

## 0.1.0 — initial

- Clinic weekly schedule + per-day overrides.
- Per-professional weekly schedule + overrides.
- `/api/v1/schedules/availability` resolver consumed by the agenda
  frontend with a 404-tolerant composable fallback.
- Occupancy analytics computed from `appointment.*` events.
- First officially-removable optional module (issue #39).
