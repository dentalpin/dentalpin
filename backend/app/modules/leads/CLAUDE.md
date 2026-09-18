# leads module

Inbound enquiries from the clinic external website form. One rule decides
everything: an enquiry whose phone **or** email already belongs to a patient
of this clinic (non-archived) never becomes a lead — it queues a **recall** in
the `recalls` module instead; only a genuinely new person becomes a lead card
on `/leads`, convertible into a patient through a right-side drawer pre-filled
from the enquiry.

That routing lives in exactly one place, `LeadIntakeService.route`, so the
public form and the front desk cannot drift apart.

## Public API

Routes mounted at `/api/v1/leads/`. Collection routes are declared as `/` and
the app runs with `redirect_slashes=False`: call `/api/v1/leads/` **with** the
trailing slash (`/api/v1/leads` 404s).

| Method | Path | Permission |
|---|---|---|
| GET | `/` | `leads.read` |
| POST | `/` | `leads.write` **+** `patients.read` — manual create, returns the outcome union |
| GET | `/{lead_id}` | `leads.read` |
| PATCH | `/{lead_id}` | `leads.write` — all-optional body + `exclude_unset` (404 on another clinic id) |
| POST | `/{lead_id}/convert` | `leads.write` **+** `patients.write` |
| GET | `/settings` | `leads.settings.read` — cap, gauge, key status (never the key) |
| PATCH | `/settings` | `leads.settings.write` — `daily_cap`, 0 = unlimited |
| POST | `/settings/intake-key/rotate` | `leads.settings.write` — plaintext returned once |
| PATCH | `/settings/intake-key` | `leads.settings.write` — `is_active` kill switch |
| POST | `/public/intake` | **no permission** — `X-Lead-Key` is the auth |

The second permission on each cross-module route is deliberate: `POST /`
discloses the matched patient name (`patients.read`), `/convert` creates a
patient (`patients.write`). `POST /public/intake` is declared on
`public_router.py` and has no clinic context — never add `get_clinic_context`
"for consistency": it would demand a JWT the clinic website does not have.

## Dependencies

`manifest.depends = ["patients", "recalls"]`.

- **`recalls`** — the routing rule is the module core: a matched enquiry
  writes a recall through `RecallService.create`. With recalls uninstalled
  there is nowhere for it to go and the rule would silently degrade into
  "create the duplicate lead this module exists to prevent". **Consequence:
  `leads` cannot be installed without `recalls`** (the loader resolves the
  chain), and the uninstall order is leads first.
- **`patients`** — the `patient_id` FK (migration `depends_on = ("pat_0003",)`)
  and `PatientService.create_patient` on conversion.

There is **no** FK and no import against `recalls`: the recall is the recalls
module own row, linked by `(clinic_id, patient_id, reason)` inside that module.

## Permissions

`leads.read`, `leads.write`, `leads.settings.read`, `leads.settings.write`.
Manifest grants: admin `*`; dentist `read`; assistant and receptionist
`read` + `write`; hygienist none.

`settings.*` are granted to **no role except admin** (through `"admin": ["*"]`)
— on purpose. The intake key is a secret and rotating it silently breaks the
clinic website until a human pastes the new key in, so it belongs to whoever
owns the website, not to the front desk. Do not "helpfully" grant
`settings.write` to `receptionist`.

## Tools exposed

`tools.py` — thin wrappers over the services, every one filtered by
`ctx.clinic_id`.

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_leads` | READ | `LeadService.list_leads` | `leads.read` |
| `get_lead` | READ (`exposes_free_text`) | `LeadService.get_lead` | `leads.read` |
| `create_lead` | WRITE | **`LeadIntakeService.route`** | `leads.write` |
| `update_lead` | WRITE | `LeadService.update_lead` | `leads.write` |
| `convert_lead_to_patient` | WRITE | `LeadService.convert` | `leads.write` |
| `update_intake_settings` | WRITE | `LeadSettingsService.update` | `leads.settings.write` |

**Intake-key rotation and the `is_active` toggle are deliberately NOT exposed
as tools** — the one exception to "expose every mutating service method". An
LLM that decides to "fix intake" by rotating the key breaks the clinic website
with no undo, and the clinic would not know why the form went quiet. It is not
a `DESTRUCTIVE` tool either: it is simply not a tool.
`tests/modules/leads/test_settings.py` asserts the tool set and that no tool
name contains `key` or `rotate`.

`create_lead` **routes** (it never inserts blindly), so the agent has to say
"they are already a patient, a call-back was queued" (`outcome=recall_queued`)
instead of "created".

## Events

This module publishes and consumes **no events of its own** (D7). The recall it
creates does publish `recall.created` — through `recalls`, whose
`RecallService.create` is the writer — which feeds `activity_journal` and, when
installed, `recall_reminders`. That is also why there is no
`docs/technical/leads/events.md`.

## Configuration

Two surfaces, and the cap is not in the environment:

- **Daily intake cap** — the `leads_settings.daily_cap` column (default 200,
  `0` = unlimited, validated `0..5000`), edited by the clinic at
  **Settings → Integrations → "Formulario web"**
  (`/settings/integrations/leads`). There is no `LEADS_INTAKE_DAILY_CAP` and
  there must not be one: the column default *is* the default.
- **Env vars** — `LEADS_INTAKE_MAX_BODY_KB` (default 8) and nothing else. There
  is deliberately no captcha switch and no daily cap here.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Own Alembic branch **`leads`** (`leads_0001`, `down_revision="0001"`,
  `depends_on=("pat_0003",)`), registered in `alembic.ini` `version_locations`.
- `uninstall()` (default no-op) + its downgrade drop only `leads`,
  `leads_intake_keys`, `leads_settings`. The round-trip test asserts that
  `recalls`, `recall_contact_attempts` and `recall_settings` survive.

## Gotchas

- **One insert path for leads, ever.** `LeadService.create_lead` is called only
  from `LeadIntakeService.route`. Any second caller — a new endpoint, a tool,
  a seed script — re-creates the duplicate lead this module exists to prevent.
- **Never hand-write the `Recall` insert.** `RecallService.create` carries the
  `(patient, reason)` dedupe *and* publishes `recall.created`; a raw
  `Recall(...)` would stack duplicate call-backs and drop the activity journal.
- **Dedupe + note append.** A repeat enquiry refreshes the same active
  `(patient, "other")` recall instead of stacking a second one, and the
  composed note (motive / description verbatim, plus the availability as a
  language-free token like `mon, wed · afternoon`, blank-line separated) is
  **appended** behind a `---` separator — never overwritten,
  because a staff member may have written their own `other` recall on that
  row. The block is skipped when it is already present and when appending
  would exceed the 4000-character cap.
- **`do_not_contact` → `needs_review`.** The default call list filters
  opted-out patients out, so a `pending` recall for one would be invisible and
  the enquiry would vanish. Outbound contact stays blocked independently by the
  notifications gateway, even with `force_send`.
- **Known gap: a repeat enquiry from an opted-out patient stacks.** The dedupe
  looks for an *active* recall (`find_pending_for`), and `needs_review` is not one, so
  a second enquiry from the same `do_not_contact` patient inserts a second
  `needs_review` row instead of refreshing the first. Every other match dedupes
  normally. Fixing it means widening the dedupe inside `recalls` (`ACTIVE_STATUSES`), a
  change to that module, not a workaround here.
- **`recall_reminders` side effect (accepted — do not bypass).** With
  `recall_reminders` installed the recall also queues the patient-facing
  `recall_reminder` message. Do not route around `RecallService.create` to
  suppress it: that trades a slightly odd automated message for a missing
  `recall.created`. The levers are the notification template/preferences, or
  not installing `recall_reminders`.
- **Phone matching is a heuristic: trailing 9 digits.** `matching.phone_key`
  makes `+34 600 111 222`, `600 111 222` and `600111222` one patient. Numbers
  shorter than 9 digits compare whole, so a short legacy number can
  false-positive — which is why the drawer still lets a human confirm. The SQL
  twin in `find_matching_patients` and the frontend `phoneKey` helper must
  change together with it.
- **The intake response never varies by branch (D12).** A new lead, a queued
  recall and a matched opted-out patient all answer the same 201 body: an
  unauthenticated caller must not be able to probe "is this phone one of your
  patients?". No different status, wording, header or obvious timing.
- **The cap counts before it writes.** `consume_daily_quota` counts the attempt
  in the same atomic `UPDATE … RETURNING` that reads the cap, so blocked
  attempts stay visible in `day_count` (the flood gauge). Do not "fix" it to
  count only accepted inserts.
- **The 429 path commits before it raises.** `get_db` rolls the session back
  when a handler raises, so without the explicit `await db.commit()` in
  `public_router.intake_lead` a blocked attempt would be discarded and a flood
  would look like it never happened. `test_intake.py` asserts the counter
  through a *separate* connection exactly for this.
- **`leads_settings` is created with `INSERT … ON CONFLICT DO NOTHING`,** never
  select-then-insert. The row is lazy and two concurrent first-ever intakes are
  a real race; the loser would 500 on the unique violation.
- **Never reset `day_count` from rotation, the settings PATCH or the toggle.**
  Rotating the key stops a flood; wiping the counter would hand the attacker a
  fresh daily budget and hide the evidence. Only the date rolling over resets it.
- **Availability is structured (days + slot) and never becomes patient data.**
  `availability_days` is a canonical mon..sun list (the service dedupes and
  orders it), `availability_slot` is `morning`/`afternoon`/`evening` or NULL. The
  public intake contract therefore takes **codes, not a sentence** — a free-text
  value is rejected — and `leads_0002` drops the old text column. Weekday
  labels come from `Intl.DateTimeFormat` in the UI (the narrow forms are correct in
  all ten locales — Spanish gives L, M, X, J, V, S, D), so there are no
  per-day i18n keys; only `leads.slots.*` is translated.
- **The lead payloads reject unknown fields (`extra="forbid"`).** `LeadIntakeCreate`, `LeadCreate` and `LeadUpdate`
  all forbid extras, so a website still posting the retired `availability` string
  gets a **422 naming the field** instead of having it silently dropped — a
  contract change has to be loud. Guarded by
  `test_intake.py::test_retired_free_text_availability_is_rejected`.
- **Motive and availability are never copied into the patient record.** They are
  logistics for one call: the convert drawer starts with **notes empty** and the
  staff writes what belongs in the chart. The only place they are rendered
  outside this module is the recall note, for the matched-patient path where no
  lead card exists.
- **The convert drawer name split is a heuristic.** One `full_name` is split at
  the **first** whitespace (`Marta de la Fuente` → `Marta` / `de la Fuente`); a
  single-token name leaves `last_name` empty for the user to complete. Both
  fields stay editable and nothing is written until the user confirms.
- **No `recall_id` column on `leads`.** The link is
  `(clinic_id, patient_id, reason)` and the dedupe lives in the recalls module;
  an FK would buy nothing and couple the two branches.
- **CORS.** The intended integration is a **server-side** POST from the clinic
  website or its host (WordPress handler, Webflow form action, Zapier/n8n). A
  browser `fetch()` straight from the clinic site additionally needs that
  origin in `ALLOWED_ORIGINS` (`app/config.py`, comma-separated) — mention it,
  do not change CORS code.
- **Rotate returns the plaintext exactly once.** Never store it, never return
  it from `GET /settings`, never log it (`key_prefix` + `clinic_id` at most).
- **A literal `@` in an i18n message must be written `{'@'}`.** vue-i18n reads
  `@` as linked-message syntax and refuses to compile the file otherwise:
  ``leads.validation.email`` is the message that needs it ("…for example
  name`{'@'}`example.com"). Every locale uses the same escape, so the parity
  test stays happy, and `npx vitest run tests/i18n` compiles every message.
- **The intake URL the UI shows is built from the app's API base**
  (`runtimeConfig.public.apiBaseUrl`), never from `window.location.origin`: the API and the
  app are different origins whenever they are not served together, and the
  SPA origin answers the clinic's website with a login redirect. The backend
  returns the path only — it deliberately does not guess hostnames.
- **slowapi is disabled outside production** (`ENVIRONMENT=production` and not
  `TESTING`), so no test can assert a 429 from the rate limiter; do not remove
  the decorators either — they are the production guard.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`

## CHANGELOG

See `./CHANGELOG.md`.