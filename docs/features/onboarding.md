# First-run onboarding: setup wizard, seeded defaults, getting-started card

> Status: shipped (v2.3). Owner: host (`core/auth`) + per-module rules. Spec last updated: 2026-08-16. Decision record: [ADR 0018](../adr/0018-onboarding-seeding-and-state.md).

## Why

Before this work `/setup` collected six fields (admin account, clinic name, tax id) and dropped the admin on an empty dashboard: no VAT types, no treatment catalog, no invoice series (so no invoice could be issued), no cabinet, a 24/7 schedule and no colleague to book. Country was never asked, so every install became `Europe/Madrid` / `EUR`. The only follow-up was a two-item checklist hidden under `/settings`, dismissed per browser.

Goal: a clinic that is **operative right after `/setup`** and a **guided "getting started" card** on the dashboard that walks the admin through what is left — reusing the real settings screens, not a second set of forms — so nobody needs support to start working.

## Success criteria

- `/setup` → first login in **≤ 2 minutes** on desktop and phone (375 px).
- After `/setup` a Spanish clinic can, without visiting settings: open the agenda with real hours and one cabinet, budget from a priced catalog with the right VAT, and issue a `FAC-…` invoice.
- The dashboard card reflects **real data** (steps resolve themselves when the underlying data exists), is per-clinic (server-side), and disappears when done or hidden.
- Adding a colleague never requires SMTP: an invite link the admin can copy or send via WhatsApp.

## Flow

### 1. `/setup` (pre-login, guest layout)

Two steps, language switcher in the header (changes the wizard language on the fly). Until the admin touches that switcher, the wizard language follows the selected country's preset — a browser defaulting to en-US no longer leaves a Spanish clinic in English after picking España.

1. **Administrator account** — first/last name, email, password ×2 (8+ chars, letter + digit; mirrored server-side), and an **"I attend patients myself"** switch (on by default — solo practices are the common case) that flips `is_professional` on the admin membership so the *Team* step resolves without a second user.
2. **Clinic** — clinic name, **country** (searchable; guessed from browser timezone, then locale), tax id (label / placeholder from the country preset; Spain gets a non-blocking NIF/CIF checksum warning and a blocking format check), a collapsible **"Clinic address"** block (street, postal code, city — optional, but filling the street completes the *Clinic info* step right from the wizard), a collapsible "Timezone and currency" block pre-filled from the preset (opened automatically for countries without a preset), and an info line listing what will be created for them.

Submit → `POST /api/v1/auth/setup` → auto-login → `/`.

### 2. What the server creates (`clinic.created`)

`POST /auth/setup` commits clinic + admin + membership and publishes `clinic.created` `{clinic_id, country, currency, timezone, language, vat_preset, created_by, source}`. Modules subscribe and seed, each in its own session, idempotently:

| Module | Seeds |
|---|---|
| catalog | VAT types from the country preset (`es` → exento / 10 % / 21 %; `generic` → exento) + categories + the default treatment catalog (prices at 0 for non-EUR clinics) |
| billing | `FAC` (invoice) and `RECT` (credit note) default series |
| agenda | one cabinet ("Gabinete 1" / "Room 1" by clinic language) |
| schedules | Mon–Fri weekly hours (ES: 09–14 + 16–20; otherwise 09–18) |

A failing seed never fails setup; the card shows the gap.

### 3. Dashboard card "Puesta en marcha" (admins)

Full-width card on the dashboard hero row. Progress bar over the **required** steps; each pending step has *Configurar* (opens an inline mini-modal when the rule provides one, else the real settings page in guided mode) and *Omitir*. Optional steps sit in a collapsible group. *Ocultar* dismisses for the whole clinic; when the last required step resolves the card marks the clinic complete (toast) and collapses to a compact "done" row (100 % bar, one line, the optional group and a *Cerrar* button) instead of lingering full-height until the next navigation.

Rules (owner → data):

| Order | Rule | Owner | Pending when | Mini-modal |
|---|---|---|---|---|
| 10 | Clinic info | host | name / tax id / street missing | — |
| 20 | Cabinets | host | no cabinets | `CabinetFormModal` |
| 30 | Clinic hours | schedules | still on the 24/7 template | `ClinicHoursQuickModal` |
| 40 | Team | host | no other active member and admin not professional | `UserCreateModal` |
| 50 | Catalog | catalog | 0 items | `CatalogSeedQuickModal` (loads the stock catalog via `POST /catalog/seed`, or hands off to the page) |
| 60 | Invoice series | billing | 0 series | — |
| 70 (opt.) | VeriFactu | host | country = ES and module not active | — |
| 80 (opt.) | Email sending | notifications | SMTP not configured | — |
| 90 (opt.) | First patient | patients | 0 patients | — |

### 4. Guided mode

*Modo guiado* opens the first pending step's page with `?onboarding=<ruleId>`. A sticky bar under the header shows "Paso N de M · `<step>`" with *Salir* and *Siguiente / Finalizar*; *Siguiente* re-checks the data and jumps to the next pending step, the last one returns to `/`. Query flag over composable state: survives reloads, deep-linkable, nothing to sync. The counter counts the **walk**, not the whole checklist: with 4 of 6 steps done, entering guided mode reads "Paso 1 de 2" (the pending list is frozen at start so a step resolved along the way keeps its position). Two target pages adapt to the flag: `/settings/general/clinic` mounts the edit form directly (guided mode exists to *fill in* data, not to read it), and the users page shows an inline "I attend patients myself" switch above the list while the admin isn't a professional yet.

### 5. Team invite links

Creating a user with an empty password creates a locked account and shows a one-time **access link** (`/set-password?token=…`, 7-day JWT bound to the user's `token_version`, single use). Copy or "Send via WhatsApp". The same action on an existing user's row works as an admin-driven password reset. The invitee sets a password and lands logged in.

## Mobile

Card rows keep 44 px targets; the guide bar truncates the step label and keeps both buttons; `/setup` is single-column with the derived-settings block collapsed by default.

## Not in scope (v1)

- Presets with fiscal logic for countries other than Spain (others get currency / timezone / language only).
- Per-professional colour or specialty (no such concept in the data model yet).
- Email invitations (the link is shareable by any channel).

## Endpoints added

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/api/v1/auth/setup/presets` | public | Country presets for the wizard |
| POST | `/api/v1/auth/setup` | public (5/h) | Now accepts `country`, `language`; applies preset; publishes `clinic.created` |
| PATCH | `/api/v1/auth/clinic/settings/onboarding` | `admin.clinic.write` | `{dismissed?, completed?, skip?[], unskip?[], reset?}` → `settings.onboarding` |
| POST | `/api/v1/auth/users/{id}/invite-link` | `admin.users.write` | One-time set-password token (blocked in demo mode) |
| POST | `/api/v1/auth/set-password` | public (10/h) | Consumes the token, returns access/refresh tokens |
| PUT | `/api/v1/auth/clinics` | `admin.clinic.write` | Mirrors `address.country` (ISO2) into `settings.country` |

## Key files

- `backend/app/core/auth/country_presets.py`, `router.py` (`setup`, `setup_presets`, `update_onboarding_state`, `create_user_invite_link`, `set_password_from_invite`)
- `backend/app/modules/{catalog,billing,agenda,schedules}/events.py::on_clinic_created`
- `frontend/app/pages/setup.vue`, `pages/set-password.vue`, `utils/countries.ts`, `utils/spanishTaxId.ts`
- `frontend/app/composables/{useOnboarding,useSettingsRegistry}.ts`, `components/onboarding/{OnboardingCard,OnboardingGuideBar}.vue`, `plugins/{settings.registry,onboarding.slots.client}.ts`
- Module rules: `backend/app/modules/{catalog,billing,schedules,notifications}/frontend/plugins/settings.client.ts`, `patients/frontend/plugins/slots.client.ts`
