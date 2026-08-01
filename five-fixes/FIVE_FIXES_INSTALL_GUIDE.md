# Five-Item Fix — Install Guide

## Item 1 — DOCUMENT_GENERATED into staff_activity: no fix shipped, and here's why

Before touching anything I re-read `staff_activity/handlers.py` directly.
Its subscription mechanism isn't an explicit list of events — it's
`vars(EventType)` filtered by an **opt-out** list (`_SKIP_EVENTS`), wired
through the standard `get_event_handlers()` path (confirmed in
`staff_activity/__init__.py`). `DOCUMENT_GENERATED`,
`PAYROLL_PERIOD_PROCESSED`, and `PAYROLL_PAYMENT_MADE` are all real
`EventType` members, none of them appear in `_SKIP_EVENTS`, so they are
**already being logged automatically, right now**, with no code change
needed.

My original review's automated scan looked for literal
`EventType.X:` dict keys and explicit `.subscribe(EventType.X)` calls —
it couldn't see this dynamic pattern, which is actually more elegant
than what I assumed (new events get tracked by default, instead of
requiring someone to remember to add each one). That was a false
positive on my part. Adding an explicit handler now would just create
duplicate log entries. Nothing included in this zip for item 1 —
verify for yourself with:
```powershell
docker compose exec backend python -c "from app.modules.staff_activity.handlers import _tracked_event_types; print('document.generated' in _tracked_event_types())"
```
Should print `True`.

## Item 2 — Letterhead settings page registered

New file: `documents/frontend/plugins/settings.client.ts`, following
`medical_reference`'s exact pattern — bare `path` slug, explicit
`registerSettingsPage` import, `component` as a plain arrow function.
Category is `general` (same category as the existing Clinic Info page —
letterhead is the same kind of clinic-identity setting, just consumed by
generated documents instead of the app chrome). Added a
`documents.letterhead.settingsDescription` i18n key to `en`/`es`/`fr`
(not `pt` — that's a separate, larger, not-yet-decided issue per the
review).

**One thing worth testing carefully, not guaranteed risk-free**: you
asked me to register the page at its current location
(`pages/settings/letterhead.vue`) rather than move it, which I did. The
last time I registered a page this way (`medical_reference`'s original
attempt), it broke — but that failure had two *other* bugs bundled in at
the same time (wrong path format, missing import), both of which are
already correctly avoided here, so I can't be certain the file-location
detail alone was ever actually the cause. `letterhead.vue` does have its
own `definePageMeta({ middleware: ['auth'] })` — a Nuxt page-only
compiler macro — sitting in a file now also being dynamically imported
as a plain component. If that causes an error, the fix is: delete
`definePageMeta(...)` and the manual `if (!can(...)) navigateTo(...)` — a
Settings-registry component doesn't need either, since the shell already
gates on the `permission` field. I did not make that change preemptively
since you asked for registration only and I wasn't certain it was
actually necessary — test it first.

## Item 3 — Payroll staff picker

Replaced the raw UUID `UInput` with a `USelectMenu` showing
`"First Last (email)"`, backed by the existing `GET /api/v1/auth/users`
endpoint via the host's `useUsers()` composable — no new backend
endpoint needed, it was already there. One correction: you described
this as "the same USelect pattern as the treatment picker in
treatment_consumables," but that component actually uses a hand-built
debounced `UInput` + manual results list, not `USelectMenu` at all. I
used `USelectMenu` instead since it's a proven, already-working pattern
in this exact codebase (`ReferenceSearchInput.vue`), and functionally
closer to what "searchable dropdown" means. Also filters out staff who
already have a payroll profile (the `user_id` column is unique, so a
duplicate would just 409) — except the profile currently being edited,
which stays selectable.

## Item 4 — pyproject.toml entry-points

All 13 modules added, verified programmatically against the actual
`BaseModule` subclass name in each module's `__init__.py` (not
guessed/pattern-matched from the module name) — `pyproject.toml` now
lists all 42 modules with zero duplicates, and re-parses as valid TOML.

## Item 5 — Medications pagination

Two files, matching the established two-part pattern from the
`inventory`/`medical_reference` fixes: the frontend composable's default
bumped from 100 → 1000, **and** the backend's `Query(..., le=100)` cap
raised to `le=1000` — bumping only the frontend would have done nothing,
since the backend was silently clamping any higher request back down to
100 regardless.

One correction to the original review's wording: it said the composable
"does not pass page_size... so the backend returns only the default 20."
On rereading the actual file, the composable already had its own
internal default of 100 (not 20) — so the real effective cap before this
fix was 100, not 20. The underlying problem was the same either way
(silent truncation, no pager), just at a different threshold than
originally described.

## Install

```powershell
Expand-Archive -Path five-fixes.zip -DestinationPath . -Force
docker compose down
docker compose up -d --build
```

No migrations — every change here is code-only (routes, composables,
frontend registration, packaging metadata).

## Verify

- **#2**: Settings → General → "Letterhead" appears and opens without error. If it errors, apply the `definePageMeta` fix described above.
- **#3**: Payroll → Add staff member → the field shows a searchable list of real names/emails, not a text box. Add one, confirm it saves and the new profile shows the right person. Try adding the same person again — should be excluded from the list already.
- **#4**: `docker compose exec backend python -c "from importlib.metadata import entry_points; print(len(entry_points(group='dentalpin.modules')))"` should print `42`.
- **#5**: Medications list shows more than 100 items if your catalog has grown past that (check your actual count first — the medic_.json-derived seed data alone was 133).

## Commit

```powershell
git add -A
git commit -m "Fix: documents letterhead registration, payroll staff picker, pyproject.toml entry-points, medications pagination"
git tag phase15.1-working
git push origin my-version --tags
```
