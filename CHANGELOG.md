# Changelog

All notable changes to DentalPin are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/) and the project
uses [Semantic Versioning](https://semver.org/).

The `v2.0` line is the first to ship with the post-Fase-B module
architecture: the monolithic `clinical` module is gone, replaced by
four purpose-built modules, and every official module now ships its
frontend as a Nuxt layer under its own Python package.

## [Unreleased]

### Changed

- **Clinic settings stored with an invalid value now read as the default**
  (ADR 0042). A module that declares its settings through the core
  settings registry validates each stored value on read. A value that fails
  its declaration (wrong type, out of range, longer than `max_length`)
  falls back to the declared default and logs a warning naming the module
  and key, where the old hand-written endpoints returned it coerced or
  as-is. Billing is the first module on the registry: its footer and bank
  details are now capped at 2000 characters, so a longer value saved before
  the cap reads as empty until it is re-entered.

## [2.9.0] - 2026-10-27

Hindi, four more LLM providers for the copilot, kiosk self check-in, and a
large correctness sweep (concurrency, tenant scoping, clinic-calendar dates,
422/409 instead of 500). Thanks @ZoliQua, @lamanji, @tresundios and
@abdd8433.

### Upgrade notes

- **Upgrade note (production):** `BUDGET_PUBLIC_SECRET_KEY` is now
  required. A production boot without it fails fast with an actionable
  message instead of signing public budget sessions with the staff-JWT
  `SECRET_KEY`. Blank, whitespace-only, and whitespace-padded values are
  also refused, so generate a clean value (e.g. `openssl rand -hex 32`)
  before upgrading; `docker-compose.prod.yml` and
  `docker-compose.coolify.yml` now both refuse to start without it.
- **Upgrade note (production):** `AGENDA_PUBLIC_SECRET_KEY` is now
  required on the same terms: a production boot without a clean value
  fails fast instead of signing QR check-in tokens with the staff-JWT
  `SECRET_KEY`. Set it alongside `BUDGET_PUBLIC_SECRET_KEY` (see the note above) before upgrading.
- **Heads-up (production email):** `EMAIL_PROVIDER=console` (the dev
  default) delivers nothing (#614). A production instance that never
  set `EMAIL_PROVIDER` boots normally but logs an ERROR when it first
  resolves the provider (on the first email, since resolution is lazy),
  writes metadata-only log lines (no bodies, no names), and reports
  sends as failed so the UI stops claiming delivery. Set
  `EMAIL_PROVIDER=smtp` with real credentials, or
  `EMAIL_ENABLED=false` if the instance sends no mail (sends are then
  skipped, not retried or reported as failed). The public demo is
  affected too: it runs production, so it now logs metadata and reports
  those sends as failed instead of printing the message and reporting it
  sent.

### Added

- **Module settings registry (ADR 0042).** Modules can declare simple
  clinic-scoped settings through `BaseModule.get_settings()`; the core
  validates them at discovery, stores values under
  `clinics.settings[<module>]` and serves them at
  `GET/PATCH /api/v1/settings/{module}` with per-setting read and write
  permissions. A generic `SettingsModuleForm` renders the declarations,
  PATCHes only the fields the user changed, sends no request on an
  unchanged save and blocks an emptied required integer with an inline
  message. Billing is the first module on it (Settings > Billing >
  Preferences), with its legacy settings endpoints delegating to the same
  service. The new
  strings are translated in de/fr/it/pt/pt-BR; ar/hi/hu/pl/ta/te fall
  back to English.

- **Copilot: Ollama LLM provider adapter** (self-hosted, local, no API
  key) over its OpenAI-compatible endpoint. `OLLAMA_SPEC` needs no key
  and reads its endpoint from a new `base_url_setting`
  (`OLLAMA_BASE_URL`, default `http://ollama:11434`); the factory threads
  it into `ProviderConfig`. Per-clinic selection; dev, prod and Coolify
  compose forward the setting, and an unreachable host raises an
  `LLMConfigError` naming `OLLAMA_BASE_URL` instead of the SDK's bare
  `Connection error.`. No bridge, settings or UI change (#332).
- **Copilot: OpenRouter + Groq LLM provider adapters** over their
  OpenAI-compatible endpoints (same subclass shape as Gemini;
  `OPENROUTER_API_KEY` / `GROQ_API_KEY` + per-clinic selection, specs
  registered from `on_activate`). No bridge, settings or UI change (#332).
- **Copilot: Gemini LLM provider adapter** over Google's OpenAI-compatible
  endpoint (same wire format and `openai` tool dialect as the OpenAI
  provider; `GEMINI_API_KEY` + per-clinic selection, spec registered from
  `on_activate`). No bridge, settings or UI change (#332).
- **Hindi (`hi`, हिन्दी) locale** — core app and every module layer,
  patient email templates, PDF labels (`hi_IN` money/date formatting,
  Devanagari via Noto Sans Devanagari), and a Hindi demo seed
  (`--lang hi`): an India GST clinic in New Delhi (GST state 07,
  GSTIN `07ABCDE1234F1Z2`) with Hindi patient names. `README.hi.md` added.
  Country-specific compliance modules (`verifactu`, `nav_online`,
  `sdi_it`, `sistema_ts`) and the Verifactu emails are not translated
  to Hindi; they fall back to English.
- **Kiosk self check-in, phase 1** (#480, ADR 0037). A patient checks in
  from the QR link in their reminder: the token records its source, the
  reminder carries the link, and check-in only opens within a window
  around the appointment's start time (#667, thanks @lamanji).

### Changed

- **Upgrade note (production):** `AGENDA_PUBLIC_SECRET_KEY` is now
  required on the same terms: a production boot without a clean value
  fails fast instead of signing QR check-in tokens with the staff-JWT
  `SECRET_KEY`. Set it alongside `BUDGET_PUBLIC_SECRET_KEY` (see its
  note below) before upgrading.
- Email templates missing in a locale now fall back to the English
  template instead of rendering nothing.
- **GDPR erasure now pulls a contributor registry, not a fan-out** (#546,
  ADR 0038). `gdpr` calls every registered erasure contributor
  (`notifications`, `recalls`) inside the erasure transaction and builds
  the per-scope coverage list (`ErasureCoverage`) from their answers — a
  scope with no contributor produces no row. `gdpr.erasure.executed` is a
  post-commit announcement. Fiscal, signature and clinical records stay
  retained (Art. 17(3)), hardcoded as interim rows until their
  contributors land. `ErasureResult.coverage_note` is removed in favor of
  the `coverage` list (no frontend reader affected).

### Security

- **A consent could be recorded against another clinic's patient.**
  `ConsentService.grant_or_withdraw` built the row straight from the
  payload id with no patient lookup, so any tenant got a 201 against any
  patient id — and an unknown id surfaced as a `ForeignKeyViolation`,
  i.e. a 500 for what is a bad request, with the 201/500 split acting as
  a cross-tenant patient-existence oracle (#562). Both paths now do a
  clinic-scoped patient lookup first: unknown or foreign ids answer 404
  on HTTP and `{"error": "patient not found"}` on the agent tool, before
  anything is written.
- **A budget could be assigned a professional from another clinic.**
  `assigned_professional_id` was a plain FK to `users` with no
  membership check, so a caller naming a user id from a different clinic
  had it stored — and the budget then rendered that user's name back. An
  unknown id surfaced as a `ForeignKeyViolation`, i.e. a 500 for what is
  a bad request. Both paths now answer 400, on create and on update. The
  patient on the same route was already checked against the clinic; the
  professional was not.
- **The backend no longer trusts `X-Forwarded-For` from any peer** (#623).
  `backend/Dockerfile` and every compose file ran uvicorn with
  `--forwarded-allow-ips *`; with `*` uvicorn takes the **leftmost**
  `X-Forwarded-For` entry, which the client writes. The login rate limit
  keys on `request.client.host` (`get_remote_address`), so a client
  sending a fresh header per attempt got a fresh bucket per attempt and
  the limit stopped existing — and the same value is stored as the
  session's `client_ip`, so the audit trail could be forged with it.
  The flag is gone; uvicorn now reads `FORWARDED_ALLOW_IPS`, which every
  compose file sets to loopback plus Docker's address pools and which
  deployments override for their own proxy chain
  (`.env.example`, `docs/user-manual/{en,es}/operations.md` §1).
  Restricted, uvicorn walks the header right-to-left and stops at the
  first hop outside the list, so the real client is used whether the
  proxy overwrites the header or appends to it — the append case is
  spoofable under `*` even behind a proxy. `_client_ip()` no longer
  re-parses the header, and the backend logs the effective value at
  startup (error in production if it is still `*`).
- **Coolify: trust Traefik's 10.0.x networks** (follow-up to #623).
  `docker-compose.coolify.yml` now defaults `FORWARDED_ALLOW_IPS` to also
  include `10.0.0.0/8`. Coolify creates its Docker networks there, so the
  previous default made every client resolve to Traefik's IP and turned
  the login rate limit global.
- **`allowed_tools` is now enforced, not just declared** (#558).
  `BaseAgent.allowed_tools` existed with zero enforcement references
  anywhere in `app/`, while `docs/technical/creating-modules.md` told
  module authors it was "a hard list — the agent cannot invoke anything
  outside it". `ToolRegistry.call` now checks it as step 2 of its
  enforcement order (before guardrails, so a call the agent was never
  allowed to make cannot consume its rate limit or open an approval
  request) and audits the refusal as `BLOCKED`. The list reaches the
  chokepoint through the new `AgentContext.allowed_tools`, where `None`
  means "no subsetting" — what copilot and other conversational
  surfaces use, so their behaviour is unchanged — and an empty list
  permits nothing, which is `BaseAgent`'s default.
- **Tenant scoping closed in four more places:** the recall suggestion
  patient lookup (#727), `patients_clinical` list helpers, 1:1 getters and
  bulk archive (#728), and the notification handlers' row reads (#729)
  now filter by clinic (thanks @lamanji).
- **Public budget page: per-IP lockout, production-only signing secret,
  audited accept/reject** (#636), and a minimized pre-verification
  payload (#647) (thanks @lamanji).
- **Copilot redaction closes its key gaps** and tokenizes known values
  wherever they appear in a tool result (#688).

### Fixed

- **A patient's opt-out from appointment reminders was ignored** (#683).
  Reminders, and staff sends of quotes and invoices, are forced sends, and
  the per-type opt-out was only checked for unforced ones. It now blocks
  every send, and the patient card has a switch per message type, so the
  opt-out can be recorded without calling the API by hand.
- **"Load default catalog" failed for a clinic with its own VAT type at a
  preset rate.** A second 0% type next to the seeded exempt one made
  `POST /catalog/seed` answer 500; the seed now reuses the system type.
- **A per-type notification opt-out with a misspelt key was stored and
  ignored** (#683). The keys are now a closed list, so an unknown one is a
  422; saving one opt-out keeps the patient's other recorded choices; and
  `recall_reminder`, `budget_reminder` and `invoice_sent` are part of the
  default record.
- **The recalls dashboard counted a different month on each host** (#684).
  `completed_this_month` and `conversion_rate` bounded the month with naive
  datetimes, which the driver reads in the app process's zone, so the same
  data answered 1 on a UTC container and 3 on a Europe/Madrid one. The month
  is now the clinic's (`Clinic.timezone`), on every host. The new
  `clinic_zone` / `clinic_zone_for` helpers in `app/core/utils/dates.py`
  return the clinic's zone for bounds like these.
- **The first invoice of a new year could not be issued** (#689). A
  series with `reset_yearly` (the default) restarts at 1 every January,
  but the fiscal backstop index made the sequential unique over the
  series' whole life, so on 1 January issuing answered 500. Invoices now
  store their `fiscal_year` and the sequential is unique per series and
  year (migration `bil_0006`).
- **Dates showed one day early in the Americas.** `new Date('2026-10-20')`
  is UTC midnight per spec, so in any zone behind UTC every date-only field
  (invoice and due dates, quote validity, payment dates, dates of birth, a
  recall's due month) rendered as the previous day — a November recall
  read as October in Mexico City. The host now exports `parseDateOnly`
  (`frontend/app/utils/wallClock.ts`, promoted from the payments report),
  and the date formatters in 13 modules go through it.
- **Two backend vocabularies reached the UI with no label** (#695). The
  patient file's appointment list rendered `appointments.checked_in` /
  `appointments.in_treatment` in the status badge, because it read a stale
  flat `appointments.<status>` namespace instead of the canonical
  `appointments.status.*`; the duplicate is deleted and the component now
  calls `useAppointmentStatus().statusLabel`. And `invoice.payments.methods`
  was missing `upi` / `netbanking` (#365) in all 12 host locales, so
  invoices, the financial by-method report and the dashboard tile labelled
  India's payment methods with their raw value — the labels the payments
  layer already ships were copied in. A new guard,
  `backend/tests/test_i18n_vocabulary_labels.py`, pins 20 (i18n namespace →
  closed backend vocabulary) pairs: neither locale parity (a key missing
  everywhere keeps parity) nor the literal-key resolver (#631, dynamic keys
  are out of its scope) can see this class.
- **The AI copilot could never be configured on the Coolify stack.**
  `docker-compose.coolify.yml` forwarded no LLM key at all — not
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
  `OPENROUTER_API_KEY` or `GROQ_API_KEY` — while
  `docker-compose.prod.yml` forwarded them. Neither file uses
  `env_file`, `CopilotSettings` stores provider and model but no key, and
  `copilot/bridge.py` resolves the key from deployment settings alone, so
  on Coolify every copilot request raised `LLMConfigError` regardless of
  what the operator set. Every provider key plus
  `COPILOT_PROVIDER_DEFAULT` is now forwarded, `.env.prod.example`
  names them, and a guard (`backend/tests/test_copilot_compose_wiring.py`)
  reads the keys off the registered provider specs so a new provider
  fails until both stacks forward it.
- **26 UI strings showed the i18n key instead of a message** (#631).
  `errors.loadFailed`, `errors.createFailed`, `errors.updateFailed` and
  `errors.deleteFailed` existed in no locale file, so a clinic saw a toast
  titled `errors.updateFailed`; `treatment_plan` alone had 21 of the sites.
  The four keys are now in all 12 host locales, `common.more` became the
  interpolated `common.andMore` (`+{count} more`), and the one `common.view`
  tooltip reuses the existing `common.viewDetails`. A new guard,
  `frontend/tests/i18n/key-resolution.test.ts`, resolves every literal
  `t('…')` key against the merged English set — the locale-parity test
  cannot see this class, because a key absent from *every* locale keeps
  parity perfectly.
- **Ten UI strings rendered one hardcoded language to every locale**
  (#697). `actions.change`, `common.optional`, `common.expand`,
  `common.collapse`, `clinical.diagnosis.openNotes`,
  `attachments.linkError`, `documents.viewError` and the three
  `photoGallery.*` upload/fetch messages existed in no locale file, so the
  default message passed at the call site is what rendered: an English
  clinic read "Cambiar" / "Opcional" / "Expandir" on the media upload
  controls and the patient alerts banner (two of them aria-labels), a
  Spanish one read "Error loading photos" in a toast. All ten are now in
  the 12 host locales, phrased from the strings each locale already uses
  for the same kind of message, and the redundant defaults are gone from
  the call sites. `key-resolution.test.ts` no longer skips a call that
  passes a default message — the default may stay, the key has to exist —
  which is the follow-up its own docstring asked for.
- **GDPR retention policies can no longer disagree with each other**
  (#562). Two active policies for one (clinic, category) made erasure
  eligibility pick one at random (unordered dict collapse). Creating a
  policy now supersedes its active predecessors in the same transaction
  (rows stay as history, and reactivation is not a path); a partial
  unique index (`gdpr_0002`, which first reconciles pre-existing
  duplicates) backstops concurrent creates, answered 409.
- **The breach register no longer accepts illegal transitions or forged
  stamps** (#562). `DataBreachService.update` took any status in any
  order (a `reported` breach could return to `under_review` keeping a
  stale reported latch) and any explicit `notified_authority_at`.
  Transitions now follow a fixed table (illegal moves answer 422) and
  the authority timestamp is stamped only by the `reported` transition.
  An Art. 33 entry with zero data categories is rejected at the schema.
- **An admin editing another user's clinical note always returned 500.**
  `NoteService.update` fetched the note without eager-loading `author`,
  and `ClinicalNoteResponse` declares that field, so building the
  response lazy-loaded the relationship inside an async session and
  raised `MissingGreenlet`. Editing your *own* note worked, because the
  author is the caller and already in the session's identity map — so
  the only broken path was the documented admin override, and it had no
  test. Found by exercising every mutating endpoint against a seeded
  database.
- **The split-host cookie warning told PaaS operators to set a value
  browsers reject** (#444). `_shared_parent` built `.onrender.com` from
  `app.onrender.com` + `api.onrender.com` — two labels, so it passed the
  existing "a public suffix is not a parent" check — and the guard then
  advised `COOKIE_DOMAIN=.onrender.com`, which the browser drops. The
  operator restarted the backend and nothing changed. Known hosting
  suffixes now resolve to no parent, and the remedy for that case points
  at `NUXT_API_PROXY=true` (shipped in 2.8.0 for exactly this shape)
  instead of suggesting they go and buy a domain. A real multi-label
  domain such as `.example.co.uk` is still suggested as before.
- **The help-portal build now fails on a fragment slug collision** and
  warns about a slug the app can never request (#573, partial). Two
  screens whose routes collapse to the same slug used to write the same
  `.html`, last one winning, with nothing to show it had happened — and
  the obvious fix for the periodontogram route (`{id}` → `[id]`) walks
  straight into that: it would have silently taken the patient-detail
  page's help away. The underlying question of how a query-selected
  sub-view gets its own fragment is still open on #573; this only makes
  the two failure modes visible.
- **Concurrent writes run once.** Budget numbers (#773), budget, agenda,
  treatment plan, payroll and prescription transitions (#775-#778) and
  every `SELECT … FOR UPDATE` (#771) now take a row lock that re-reads the
  row, so two clicks at the same instant no longer double a transition.
- **Dates follow the clinic's calendar, not the server's.** Invoice
  dates (#719), every server-side "today" (#720, #780), PDF timestamps
  (#706) and the agenda's patient summary (#739).
- **Clearing a field clears it.** Emptying an optional input used to
  answer 422 or silently keep the old value in patients_clinical,
  catalog, budget, agenda, media, billing, sdi_it, nav_online,
  sistema_ts, inventory, orthodontics and india_gst (#741-#749, #757,
  #767).
- **Deletes that hit a reference answer 409, not 500** (cabinets,
  webhook subscriptions, plan items, inventory items, linked orthodontic
  cases, invoice-series prefixes; #661, #751-#758), and a value wider than
  its column answers 422 (#702, #764).
- **Billing and reports:** an invoice cannot be credited past its total
  (#772); receivables are net of refunds again (#691); Verifactu rounds
  fiscal amounts like the invoice row (#692) and its ledger filters work
  (#725); a deleted treatment frees its internal code (#737); only an
  unlinked draft quote can be deleted (#760); a quote resend takes the
  next free version (#663).
- **The treatment-plan auto-close cron never ran** (#628): it queried a
  column that does not exist and failed silently every night.
- **Nuxt UI v4 leftovers:** pagination (#730) and dismissible alerts
  (#732) bind the v4 API; the odontogram diagnosis plan selector uses v4
  items (#726); the odontogram loads every page of treatments (#717).
- **The frontend called paths the backend does not mount** (#700); a new
  test checks every API path against the OpenAPI schema (#710).
- **Copilot tools:** `get_budget` crashed on any budget with a line item
  (#675); id parameters are typed as UUID and closed vocabularies as
  `Literal`, so the chokepoint rejects a bad value by name (#678, #682);
  `COPILOT_MAX_TOKENS` reaches the bridge (#673).
- Razorpay shows the real payment method (#653, thanks @abdd8433);
  prescriptions show a country-aware license caption (#668).

### Tests

- **Every declared scheduled job is now executed by a test** (#629).
  `test_scheduler_jobs.py` asserted the job *ids* and never called them,
  which is how the 03:00 auto-close cron shipped querying a column that
  does not exist and failed silently every night for months (#628).
  `test_scheduled_jobs_run.py` resolves all 17 declared jobs and runs
  each against a real (empty) schema — a schema-and-import smoke test,
  not behaviour coverage, which is what keeps it at ~12s. Confirmed it
  catches #628's regression when the old query is put back.
- **Four tests read the local clock while the code under test uses UTC**,
  so they pass in CI (UTC) and fail east of UTC for part of every day —
  `test_budget_expired_detail_410`, `test_strip_excludes_appointments_on_other_days`,
  `test_get_odontogram_at_date_returns_empty_state` and
  `test_opposition_roundtrip`. Each now uses `datetime.now(UTC).date()`,
  matching the route it asserts against. No product code changed.
  A new `backend-test-east-of-utc` CI job runs the clock-reading tests
  under `TZ=Pacific/Kiritimati` (UTC+14), selecting the files at run time
  so a new test of this shape is covered the day it lands.
- **A typo in a route's permission string now fails CI.** The tool
  registry already guarded this (`test_every_tool_permission_exists`,
  "would otherwise silently always-deny"); routes gate on the same
  strings with no equivalent check, and the consequence is worse — a 403
  for every user, forever, with nothing logged to say the string was the
  problem. The tree is clean today (673 literal call sites, 189 distinct,
  all valid), so `test_route_permissions.py` is purely preventive.
- Migrations are checked against the schema the models declare (#704); a
  slot nobody renders fails CI (#694); six removable modules get
  branch-scoped uninstall round-trips (#646, thanks @lamanji).

## [2.8.0] - 2026-10-07

### Added

- **Same-origin API proxy for split-domain PaaS hosts** (`NUXT_API_PROXY=true`):
  the frontend forwards `/api/v1/**` to `NUXT_API_BASE_URL_SERVER`, so
  deploys on public-suffix hosts (`*.onrender.com`, `*.vercel.app`…) keep
  host-only session cookies without a custom domain. Off by default (#624). Setup in
  `docs/user-manual/{en,es}/operations.md` §1.
- **Telugu (`te`, తెలుగు) locale** (#589 via #617, thanks @tresundios) — core app and every module layer,
  patient email templates (HTML + TXT), PDF labels, and a Telugu demo
  seed (`--lang te`): an India GST clinic in Hyderabad, Telangana
  (state 36) with traditional Telugu patient names. `README.te.md` added.
- **Brazilian Portuguese (`pt-BR`) as a host-only overlay on `pt`** (#509, #521, thanks @dupotey):
  small delta locale file, `fallbackLocale` chain `pt-BR → pt → en`, Nuxt UI
  `pt_br`, communications language + Brazil country preset, PDF Babel `pt_BR`,
  labels reused from `pt`, email templates falling back `pt-BR → pt`.
  Only templates with vocabulary deltas live under `backend/templates/email/pt-BR/`).
- **Orthodontics: installments via plan links** (#578, #270, thanks @lamanji) —
  link a case to a treatment plan item, generate a down payment + monthly
  schedule that replaces the pending sessions (total validated), and collect
  each installment from payments.
- **`imaging_viewer`** — RVG queue tabs per status with live counts
  (#587) and the linked sensor identities list with an unlink action
  (#583), thanks @lamanji.
- **`leads`** — confirmation before rotating the intake key (#510, thanks
  @abdd8433).
- **CI** — `node-image-freshness` job keeps the Dockerfile Node major and
  the CI pins in step (#581, thanks @lamanji).

### Changed

- **Core migration `0009`: one membership per user per clinic** (#619,
  thanks @lamanji). Existing duplicate `clinic_memberships` rows are
  removed, keeping the most recently created one. If you ever had
  duplicates, check each affected user's role after upgrading.
- **Rate limiter on by default** outside test runs (`TESTING=true` opts
  out), `ENVIRONMENT` validated at boot, core migration spine pinned
  (#604, thanks @lamanji).
- **Email** — the production compose files forward every `EMAIL_*`
  setting, and the backend logs an error at startup when production runs
  the `console` provider (#615, #614, thanks @ZoliQua).
- **GDPR** — erasure results carry a `coverage_note` stating that only
  patient-row identity fields are erased (#621, #546, thanks @lamanji).

### Fixed

- **Security** — clinic-scoped clinical getters, sanitized download
  filenames and repaired copilot guardrails (#596); public budget `/meta`
  lookup scoped to the budget's clinic (#592); `/health/ready` no longer
  leaks database error text (#606, thanks @pollychen-lab); CSV exports
  neutralize spreadsheet formulas everywhere (#613, #611, thanks
  @ZoliQua); self-demotion and last-admin demotion refused, user list
  gated on read (#600).
- **Copilot** — redaction tokens salted per conversation (#601);
  re-confirming an approved write replays the stored result instead of
  re-running the tool, and turns have an iteration bound (#603).
- **Memberships** — duplicate rows no longer 500 membership checks (#598,
  #599, thanks @lamanji and @Kshot3000).
- **Module restart** never kills an unsupervised backend (#602).
- **Reports** — soft-deleted plans no longer counted in the pipeline
  (#612, #610, thanks @ZoliQua).
- **`imaging_viewer`** — approving an import whose file vanished marks it
  as failed instead of leaving it stuck pending (#582).
- **`leads`** — intake key "last used" in the UI locale (#575); dead
  availability field and unused keys removed (#618, thanks @abdd8433).
- **Infra** — pip seeded into the backend venv; empty module layers fail
  loudly (#595).

### Docs & tests

- Six permission tables filled and migration docstrings corrected
  (#597); `COOKIE_DOMAIN` cannot be a public suffix (#609); uninstall
  round-trip tests resolve their downgrade targets (#605).

## [2.7.1] - 2026-10-02

### Fixed

- **Login on plain-HTTP installs** — since 2.7.0 the session cookies
  were always `Secure` in production, which browsers drop over
  `http://` on anything but localhost: a LAN install at
  `http://192.168.x.x` logged in and bounced straight back to `/login`.
  `Secure` now follows the scheme the browser used
  (`X-Forwarded-Proto`, else `Origin`); HTTPS deployments are unchanged
  (#594).
- **Copilot** — `date_of_birth` is redacted before it reaches the LLM
  provider (#585, #534, thanks @readyagentsdev).
- **Dev environment** — the frontend container heals a stale
  `node_modules` anonymous volume on start (#588, thanks @lamanji).

### Changed

- **`imaging_viewer`** — RVG folder scans report their counts in a
  summary toast (#580, thanks @lamanji).

### Tests

- Public-route audit with adversarial tenant-scoping pins (#579, thanks
  @lamanji) and a lint that forbids UTC day-slicing in the UI (#576,
  #522, thanks @ZoliQua).

## [2.7.0] - 2026-09-30

### Added

- **Twelve new optional modules** (all manual-install from the admin UI):
  - **`sdi_it`** — Italian FatturaPA/SDI e-invoicing: FPR12 builder,
    B2B gate, PEC transport with IMAP receipt polling, settings and
    records pages and an invoice SDI panel (#410, #418, #435, #436,
    #133, thanks @ZoliQua).
  - **`sistema_ts`** — Sistema Tessera Sanitaria submission of paid
    patient invoices, patient opposition and per-item `tipoSpesa`
    (#437, #442, #134, thanks @ZoliQua).
  - **`payment_gateways`** + **`razorpay`** — a provider-neutral
    gateway contract with Razorpay as the first adapter; test/live mode
    derived from the key prefix (#439, #445, #474, #481, #518, #263,
    thanks @tresundios and @ZoliQua).
  - **`sms_gateway`** — SMS delivery through pluggable providers for
    the notifications SMS channel (#392, #231, thanks @lamanji).
  - **`leads`** — inbound lead capture and pipeline (#476, #568,
    thanks @Valeriooooh and @abdd8433).
  - **`prescriptions`** — clinical prescriptions with compliance hooks
    and a localized PDF (#465, #490, #269, thanks @lamanji).
  - **`imaging_viewer`** — in-app DICOM study viewer (OHIF embed) on
    media documents (#503, #569, thanks @lamanji).
  - **`imaging_ai`** — on-demand AI segmentation jobs over imaging
    studies behind a Runner protocol (#504, #570, thanks @lamanji).
  - **`orthodontics`** — case tracking with monthly controls, slice A
    (#505, #270, thanks @lamanji).
  - **`treasury`** — cash and bank accounts with transfers and
    memo-gated corrections (#463, #491, #502, thanks @lamanji).
  - **`staff_attendance`** — clock in/out, current state and a daily
    report (#462, #492, #501, thanks @lamanji).
  - **`patient_segments`** — clinic-local patient tags for grouping
    and campaigns (#461, thanks @lamanji).
- **HttpOnly cookie sessions** with rotating, reuse-detecting refresh
  tokens and CSRF protection (ADR 0023), a warning when a split-host
  deploy can never receive the cookies, and session refresh for blob
  downloads, media streams and copilot (#394, #449, #451, #457, #353,
  thanks @ZoliQua).
- **Reports**: financial (aging buckets, issued trend, CSV),
  patient-stats and operational families (#385, #434, #230, thanks
  @lamanji).
- **Agenda QR check-in** with signed short-lived tokens and a public
  page, from the appointment quick-actions menu; ADR 0037 sets the
  kiosk self check-in design (#464, #493, #512, thanks @lamanji).
- **Notifications: built-in WebPush channel** with VAPID (#430, #63,
  thanks @lamanji).
- **Sidebar super-sections + Settings super-groups** (#232): module nav
  items self-place under `clinical`, `lab`, `financials`, `inventory`
  and `practice`; the Settings rail groups its categories into five
  labelled super-groups and every settings page gets one back control.
  Presentation only; copilot's standalone sidebar entry is removed
  (#429, #467, #488, thanks @lamanji and @ZoliQua).
- **Settings → Modules**: upgrade/installable signals, text search,
  per-state filter and pagination synced to the URL (#427, #447, #47,
  thanks @lamanji and @BabuBahir).
- **Auth RBAC step 4** (#46): `role_id` writes on membership/user
  endpoints with flag-aware callers; ADR 0029 (#415, #438, thanks
  @lamanji).
- **CSV import** with dry-run for patients and expenses, plus patient
  restore (#431, thanks @lamanji).
- **Ops**: `db backup` CLI and a disaster-recovery runbook (#432);
  opt-in backend error tracking via the Sentry protocol (GlitchTip
  compatible), DSN-gated and PII-free, with tracing as a separate
  opt-in (#466, #498, thanks @lamanji).
- **Copilot**: LLM provider registry (#456, #332, thanks
  @Aryan-coder-student); WRITE-versus-DESTRUCTIVE tool dispatch rule
  codified (#516, thanks @lamanji).
- **Arabic**: email templates and `ar` as a clinic communication
  language with RTL email layout (#508, from #426 by Haider Habeeb,
  @dev-7aider); Arabic for the remaining layers and extracted plural
  rules (#414, #428, #389, thanks @lamanji).
- Backend startup names `.env` keys that are not app settings instead
  of dropping them silently, and tolerates non-app keys (#513, #517,
  thanks @lamanji and @ZoliQua).
- **ADRs** on country billing positions: Portugal 0027 and France 0028
  (#408, #409, #412), Germany (#443), Poland and Brazil (#453), United
  States (#454) and Mexico (#455) (thanks @ZoliQua); 0038 subject export
  registry for GDPR (#574, #475, thanks @lamanji).
- `MAINTAINERS.md` with the review bar and merge criteria (#416) and
  strategy docs (#433, thanks @lamanji).

### Changed

- **License**: Licensor set to Dentared Odontology Services S.L. (#417, #419).
- **Payments**: recording a payment is split from collecting one
  through a gateway (#519, #506, thanks @ZoliQua).
- **Odontogram**: realistic occlusal view and crown profile without
  root (#364, #48, thanks @Mr-Neutr0n).
- Frontend Node engines pinned and LF endings enforced for shell/YAML
  (#478, thanks @lamanji).

### Fixed

- **PDFs render in every UI locale**: invoices (#423, #484, #422),
  budgets, purchase orders and prescriptions (#450, #487, #441, #485)
  and managed documents (#525, #524) (thanks @ZoliQua and @lamanji).
- Hydration mismatches in the settings rail and client-registered slots
  (#425, #458, #424, thanks @ZoliQua).
- Date pickers send the local calendar day, not its UTC rendering
  (#523, #522, thanks @ZoliQua).
- List filters: a cleared filter stays cleared and the Archived filter
  lists archived patients alone (#479, #520, #473, thanks @ZoliQua).
- Odontogram plan dropdown rebuilt on the supported items API (#471,
  #459, thanks @ZoliQua).
- Notifications read treatment names from a single
  `budget_treatments_context` (#528, #527, thanks @ZoliQua).
- Copilot publishes the data-bus namespace after a confirmed write
  (#577).
- Alembic: Windows-safe `version_locations`, guards for leftover dirs
  and for cross-module FKs without `depends_on` (#472, #477, #511,
  #572, #507, thanks @ZoliQua and @lamanji).
- Coolify compose passes the demo flag to backend and frontend (#529).
- Payroll draft delete actions, single error toast on procurement
  pages and documents clean-ups (#413, #496, #497, thanks @lamanji).
- `frontend/modules.json` restored to its canonical form (#584).

## [2.6.0] - 2026-09-07

### Added

- **Six new optional modules** (all manual-install from the admin UI):
  - **`purchase_orders`** — purchase orders with receiving, quality
    checks and PDF export (#369, thanks @lamanji), on top of
    **`supplier_items`** — per-vendor SKU and price links (#368,
    thanks @lamanji).
  - **`inventory_reorder`** — reorder suggestions from stock levels
    and draft PO generation (#377, thanks @lamanji) and
    **`supplier_ratings`** — delivery/quality metrics plus manual 1–5
    ratings (#378, thanks @lamanji). The whole supplier suite
    (roadmap #227) ships a shared five-page frontend layer with
    locales (#379, thanks @lamanji).
  - **`gdpr`** — EU 2016/679 compliance: data-subject requests with a
    30-day SLA, append-only consents, retention policies gating
    erasure, partial erasure with an immutable audit log, breach
    register and portability export (#374, #44, thanks @lamanji).
  - **`payroll`** — admin-only staff payroll with Fernet-encrypted
    bank/tax data, pay periods with a guarded status machine, entries,
    monthly reports and a frontend layer; empty draft periods and
    draft entries can be deleted (#383, #401, #399, #229, #391,
    thanks @lamanji).
  - **`nav_online`** — NAV Online Számla 3.0 real-time invoice
    reporting for Hungary, phase 1: the third `BillingComplianceHook`
    after `verifactu` and `india_gst`, with a queued worker and no
    network in the request path (#395, #341, thanks @ZoliQua).
- **Arabic (`ar`) interface with full RTL support** — core app at exact
  key parity plus every module layer, MSA register with Latin
  clinical/financial glosses, `html[dir]` driven from the active locale,
  Cairo Variable as the Arabic glyph carrier, FDI tooth charts pinned
  LTR, and phone/email/DNI tokens bidi-isolated so `+1 (212) 555-0007`
  no longer reverses (#375, #397, #398, #389, thanks @lamanji).
- **DB-backed, clinic-aware RBAC** (#46): `roles`, `permissions` and
  per-clinic override tables, a roles management API, a seeder and ADR
  0024; resolution stays code-based until `RBAC_FROM_DB` is switched on
  (#400, thanks @lamanji).
- **Notifications: SMS channel core** — `Channel.SMS` resolving to the
  patient's E.164 phone, opt-in preferences, preferred-channel ordering
  with SMS fallback and a per-clinic daily cap; transport arrives with
  the `sms_gateway` module (#384, #231, thanks @lamanji).
- **Payments: gateway prerequisites** — `upi`/`netbanking` methods
  gated on the clinic's server-side country, extension slots for
  gateway modules, an idempotency key on `record_payment` and a
  graceful winner-returns response on the concurrent same-key race
  (#370, #376, #365, thanks @ZoliQua).
- **Security**: Content-Security-Policy middleware with an inventory,
  Report-Only rollout and enforcement under e2e (#382, #355); a
  12-character password floor with ADR 0022 deferring TOTP MFA (#380,
  #354); and ADR 0023 for HttpOnly cookie sessions with rotating,
  revocable refresh tokens (#381, #353, thanks @ZoliQua).
- **ADRs for Italy**: 0025 SDI e-invoicing scope and transport for
  `sdi_it` (#402, #133) and 0026 Sistema Tessera Sanitaria submission
  for `sistema_ts` (#403, #134, thanks @ZoliQua).

### Changed

- **Production frontend builds ship one locale chunk per language**
  instead of one per layer: a local Nuxt module merges every layer's
  locale files at build time (593 → 335 client chunks, 8.1 → 7.6 MB);
  dev mode is untouched and `NUXT_I18N_CONSOLIDATE=0` opts out (#406,
  #322, thanks @ZoliQua).
- **Physical→logical CSS utilities across the core app and all module
  layers** for right-to-left readiness: directional spacing
  (`ml→ms`, `mr→me`, `pl→ps`, `pr→pe`), borders (`border-l/r→s/e`),
  text alignment (`text-left/right→start/end`), inset positioning
  (`left/right-*→start/end-*`) and the inline-style equivalents now
  resolve against the document direction. Identical pixels in LTR;
  mirrored under `dir="rtl"` (#397, thanks @lamanji).
- **Reproducible installs**: Python dependencies locked with `uv.lock`,
  frozen in the Docker image and drift-checked in CI (#371, #356);
  frontend CI runs `npm ci` so a drifted lockfile fails (#393, #388);
  frontend and docs-portal images move to `node:22-alpine` pinned by
  digest (#372, #367, thanks @ZoliQua).
- **CI guards the frontend prod-build memory budget** (6.8 GB RSS)
  and per-layer locale parity; the #322 "move host keys into layers"
  proposal was measured and parked (#330, thanks @ZoliQua).

### Fixed

- Discount-type and state-filter selects crashed on open because an
  item carried an empty-string value; five call sites now use `null`
  (#407).
- External-audit fixes: soft-delete in `patients_clinical`,
  `ajr_0001`/`mc_0001` migrations ordered after core `0001`, a one-time
  startup warning on the `SECRET_KEY` fallback, `ANTHROPIC_API_KEY`
  passed through the prod compose, plus locale and micro-fixes (#386,
  thanks @lamanji).

## [2.5.0] - 2026-09-02

### Added

- **Nine new optional modules** (all manual-install from the admin UI):
  - **`inventory`** — stock list with low-stock alerts (#277), then
    the core upgrade: unit cost tracking, stock movements with an
    audit trail and automatic deduction on completed treatments (#289,
    thanks @lamanji).
  - **`treatment_consumables`** — links catalog treatments to the
    inventory items they consume; feeds the auto-deduction above
    (#280, thanks @lamanji).
  - **`suppliers`** — supplier and procurement base module on top of
    `contacts`; backend-only foundation for the purchasing suite
    (#359, thanks @lamanji).
  - **`medication_catalog`** — clinic-wide medication list (#279,
    thanks @lamanji).
  - **`staff_tasks`** — staff handoff board (#267, thanks @lamanji).
  - **`activity_journal`** — append-only staff activity log with
    resolved actor names (#278, thanks @lamanji).
  - **`documents`** — branded PDF generation module
    (#319, thanks @lamanji).
  - **`whatsapp_webhook`** — WhatsApp via a signed webhook, the
    zero-onboarding adapter for any PBX/automation tool; HMAC signing
    and URL safety moved into `app/core/webhooks` so other adapters
    can share them (#347, #63, thanks @ZoliQua).
  - **`telephony`** — CTI gateway phase 1: HMAC-verified inbound call
    events, E.164 normalization, caller→patient matching, persistent
    call log and a screen-pop toast for ringing calls; the pop poll
    backs off to a 10-minute status probe on unconfigured clinics
    (#349, #366, #64, thanks @ZoliQua).
- **Integrations Phase 2** (#65): eight webhook triggers with a stable
  `event_id`, a token-authenticated public read API with `/public/ping`,
  `last_used_at` stamping on tokens and a structured patient find
  (#345, thanks @lamanji; #358).
- **Notifications: WhatsApp-first channel configuration** with a
  preferred channel per patient, manual send buttons on the patient
  summary and a `GET /notifications/channels` probe so the conversation
  card only renders where WhatsApp is actually available (#310, #287,
  #306, thanks @ZoliQua).
- **Copilot: Anthropic LLM provider adapter**, plus the design brief for
  pluggable free/local providers (#342, #340, #332, thanks @ZoliQua).
- **Polish (`pl`) and Italian (`it`) interfaces** — core app and all 20
  module layers; Polish ships CLDR-exact three-form plural rules (#285,
  #304, #144, #132, thanks @ZoliQua). **German and Hungarian** now cover
  every module layer too (#297, #335), and patient communications
  (email templates, reminders) render in de/hu/pl/it (#344). All nine
  core locales sit at 2489 keys, enforced by a new parity test (#302,
  #312, thanks @lamanji).
- **Flow-continuity batch** (#207): *Confirmar plan* links to its draft
  quote, *Programar cita* preselects the plan's pending treatments, the
  post-appointment dialog can close unmarked treatments and open the
  payment modal in place, and the signature modal prefills the signer
  (#306, thanks @ZoliQua).
- **Onboarding follow-ups** (#205): clinic address in `/setup`, "I see
  patients myself" as a first-class switch, guided mode opens the form
  directly, the guide bar counts the walk and the wizard language
  follows the country preset (#296, thanks @ZoliQua).
- **Agenda: export an appointment as `.ics`** (#282, #129).
- **India GST: GSTIN mod-36 checksum and state-code cross-check**
  (#295, #262).
- **E2E suite runs against a production build in CI** (#294, #259) and
  a country-readiness matrix is tracked in-repo (#339, #146).

### Changed

- **Module system hygiene**: the dependency-debt allowlists are drained
  to empty via provider inversion and seed relocation (#315, #309);
  `appointment_treatments` moved to `treatment_plan` (#338, #337); the
  four import-time registrations moved to `on_activate` with an
  AST-based ADR 0020 guard (#329); five missing module entry points
  declared with a regression guard (#328); Alembic branch-head
  resolution memoized to one walk per process (#336, #323); CI fails
  when a module migrations dir is not registered in `alembic.ini`
  (#346, thanks @lamanji).
- **Baked-but-uninstalled modules stop costing at runtime**: routes
  in `modules.json` plus a module-gate middleware (#333, #326).
- **useApi error contract**: unhandled 4xx responses surface the
  backend's message; silent-failure sweep across error states, input
  preservation and destructive confirms (#317, #311, #101).
- **Accessibility**: aria-labels on all 98 icon-only buttons across
  host and module layers, closing the sweep (#305, #307, #127).
- **Docs**: nine-language READMEs with contributor credits (#313),
  EN/ES user-manual parity (#128), ADR numbering enforced by CI (#303),
  the copilot redaction guarantee stated precisely as pseudonymization
  with a documented free-text gap (#361, #357), Node 22 in CI and BSL
  wording on every README (#363, #352).

### Fixed

- Production deploy hardening (#351): `docker-compose.prod.yml` pulls
  from `ghcr.io/dentalpin/dentalpin-*`, the namespace `release.yml`
  actually publishes to, instead of the stale personal one; the frontend
  image installs with `npm ci` and runs as `node` instead of root; Caddy
  sets HSTS, `X-Content-Type-Options`, `Referrer-Policy` and
  `frame-ancestors 'self'`; `.env.prod.example` pins a release instead of
  `latest` (#362, thanks @lamanji).
- Batch uninstall of a dependency pair no longer strands the dependent
  in `to_remove` (#286): the pending processor now runs removals in
  reverse topological order (dependents first), after installs and
  upgrades, so the dependent's backup runs while its tables still
  exist. Already-dropped tables are detected from the catalog rather
  than `pg_dump`'s stderr (#292, #308).
- Dev compose no longer runs the prod Nitro build, so 4 GB machines boot
  again (#321); the `module_layers` symlink resolves inside the frontend
  container (#293, #261); `frontend/modules.json` is guarded against
  clobbering (#283, #264); Nuxt devtools disabled in e2e (#284).
- Confirmed treatment plans stay schedulable in the appointment
  selector (#301, #108); patient warning flags refresh after saving the
  clinical history (#291, #274); the last local-only full-suite failure
  root-caused and fixed (#316, #188).

## [2.4.0] - 2026-08-24

### Added

- **Eight new optional modules** (all manual-install from the admin UI):
  - **`expenses`** — fixed office cost tracking with date filters,
    pagination and per-role grants (#245, thanks @lamanji).
  - **`lab_orders`** — lab work orders with status tracking; no
    hard-delete, status transitions gated, `received_date` stamped on
    the receive transition (#266, thanks @lamanji).
  - **`medical_reference`** — clinic-managed reference lists for
    allergies, medications, diseases and surgeries, integrated into the
    patient clinical history via slots (#216, thanks @lamanji).
  - **`contacts`** — directory of external labs, suppliers and
    providers (#214, thanks @lamanji).
  - **`patient_relationships`** — patient-to-patient family/guardian
    relationships on the patient summary (#208, thanks @lamanji).
  - **`recall_reminders`** — notifies patients by email when a recall
    is created, with a shipped default template (#189, thanks @lamanji).
  - **`india_gst`** — GST-compliant invoicing for Indian clinics:
    FY-scoped document numbering, turnover-based e-invoice
    applicability, CGST/SGST/IGST breakdown, Tamil PDF output and a
    Tamil Nadu demo fixture (#210, thanks @tresundios).
  - **`integrations`** — outbound webhook subscriptions with outbox
    delivery and API tokens; first trigger is `appointment.completed`
    (#65 Phase 1, PRs #246/#247, thanks @hirad121).
- **German (`de`) and Hungarian (`hu`) interfaces** — full core app,
  2418 keys each, dental-domain terminology reviewed against #131/#275.
  Module-layer keys fall back to English (instead of raw dotted keys)
  until their translations land; the same fallback softens fr/pt/ta
  drift (#276, thanks @ZoliQua).
- **Last-visit smart-card on the patient summary**, fed by a new
  `order=asc|desc` parameter on `GET /appointments` (#182, #251).
- **SSR renders the user's language**: the locale persists in a cookie
  and `Accept-Language` is honoured on first visit (#235, #249).

### Fixed

- **Security: production startup now rejects weak or default
  `SECRET_KEY` values** (GHSA-hcg9-cm67-2g8f, thanks @hirad121).
- **Billing/budget consistency batch**: a treatment plan now owns the
  lines of its linked quote — edits flow one way and conflicting edits
  get a 409 (#176, #177); quotes show and carry net prices per line
  with VAT applied on the discounted base (#181); voiding, deleting or
  crediting an invoice releases the quote lines it consumed (#175); the
  first invoice is no longer blocked for patients with a DNI but no
  billing tax id (#206); invoice PDF footer time, VAT formatting and
  exemption clause corrected (#204); legacy `on_account` allocations
  backfilled into their budget target (#180).
- **Catalog**: price, VAT and status of system treatments are editable
  again (#237), and the treatment modal no longer 422s on mapped
  treatments by sending legacy `visualization_rules`.
- **Reports**: "work completed" derives from fully invoiced quotes
  scoped to the patient (#242); week-glance deltas no longer NaN on
  string decimals (#201).
- **Patients**: `last_visit` counts completed appointments only, and
  the patient list reflects it (#257).
- **UI polish batch** from a fresh-install E2E run (#203) and overlay
  module slots wrapped in `ClientOnly` to stop hydration crashes
  (#258).

## [2.3.1] - 2026-08-20

### Fixed

- **Non-tooth treatments are addable to treatment plans** (#215). Global
  catalog items (limpieza dental, primera visita, radiografía
  panorámica, blanqueamientos, prótesis…) never reached the plan's
  treatment bar: `/catalog/odontogram-treatments` dropped every item
  without an odontogram mapping, and the odontogram service refused to
  create a `Treatment` from unmapped items. The endpoint now returns
  unmapped global-scope items (nullable mapping fields), the service
  falls back to the internal `clinical_type="other"` for global scopes,
  and the "Boca completa" tab groups the ~40 global treatments by
  clinical category with a search filter and an arch picker for
  per-arch items. Demo seeds now write these plan treatments with their
  real scope/arch instead of fake tooth-scoped rows.
- **Patient summary "Diagnoses" card translates clinical types** — it
  pointed at an i18n namespace that never existed, so every label
  rendered as the humanized raw key ("filling composite").

### Added

- **Onboarding: "Treatment catalog" step loads the default catalog inline.**
  The dashboard card's *Set up* opens a dialog with *Load default
  catalog* (VAT, categories and reference treatments for the clinic
  country) or *I will create my own*, instead of only linking to Settings.

## [2.3.0] - 2026-08-18

### Added

- **First-run onboarding redesign** (`/setup`, dashboard "Puesta en
  marcha" card, guided mode, invite links). See
  [`docs/features/onboarding.md`](docs/features/onboarding.md) and
  [ADR 0018](docs/adr/0018-onboarding-seeding-and-state.md).
  - `/setup` asks for the country and derives timezone, currency,
    tax-id format and VAT preset (Spain full preset; generic fallback);
    NIF/CIF checksum warning; UI language switcher in the wizard.
  - `POST /auth/setup` publishes `clinic.created`; catalog, billing,
    agenda and schedules seed their defaults (VAT + catalog, `FAC`/`RECT`
    series, one cabinet, Mon–Fri hours) so the clinic is operative on
    first login.
  - Dashboard card for admins with progress, per-step *Configurar* /
    *Omitir*, inline mini-modals (cabinets, hours, team), optional
    group, *Modo guiado* sticky bar. State stored per clinic in
    `clinic.settings.onboarding` (`PATCH /auth/clinic/settings/onboarding`);
    localStorage dismissal removed.
  - Module getting-started rules: catalog, invoice series, clinic
    hours, SMTP (optional), first patient (optional), VeriFactu
    suggestion for ES (optional).
  - Team invite links without email: `POST /auth/users/{id}/invite-link`
    + public `POST /auth/set-password`; `UserCreate.password` optional;
    `/set-password` page; "access link" row action doubles as an
    admin-driven password reset.
- **Treatment categories can be managed from the UI** (#190).
  Settings → Catalog → *Categorías*: create, rename, reorder,
  deactivate and reactivate. The category CRUD API existed with no
  screen behind it, and the treatment form requires a category, so a
  clinic with none could not create a single treatment.
- **"Load default catalog"** (#190). `POST /catalog/seed` (admin) adds
  the stock VAT types, categories and reference treatments for the
  clinic's country — only what is missing, safe to repeat. Offered in
  the empty state of Settings → Catalog, where the getting-started
  card already sends you. This is the repair path for installs created
  on 2.2.x (which seeded nothing on setup) or where the automatic seed
  failed.
- **Payments: reallocate a collection** from the patient ledger
  ("Asignar a presupuesto…") and pick the destination when recording
  one (`AllocationTargetSelect`), instead of typing a budget UUID (#178).

### Fixed

- **One collection now updates every surface** (#178). Recording a
  payment on an invoice, on a quote or on account converged on
  different tables and never met: invoice payments ignored the
  invoice's budget, quote payments never reached the invoice, refunds
  left the invoice status stale and the patient billing summary
  ignored refunds. Billing now mirrors payment allocations onto the
  budget's open invoices, invoices issued from a quote sweep the
  anticipos already collected (they may be born *paid*), and refunds
  are reflected everywhere. No schema change.
- **Event handlers that silently did nothing** (#183). Handlers that
  opened their own DB session ran before the publisher committed and
  could not see its rows. Two were live production bugs: recall
  auto-link on scheduling had never worked (FK violation swallowed by
  the handler) and the welcome message on patient creation was never
  queued. 23 handlers now run inside the publisher's transaction
  ([ADR 0019](docs/adr/0019-transactional-event-handlers.md)); a CI
  guard fails when a publisher of a transactional event forgets to
  forward its session. Also removes the `SKIP LOCKED` / commit-first
  workarounds that only existed because of the second session, and an
  earned-revenue entry can no longer outlive a treatment whose request
  rolled back.
- **Production frontend image ships every module layer** (#174).
  Modules installed after the image was built (e.g. `accounting_export`
  on the demo) had no page and a raw sidebar label. The prod build now
  bakes all layers; the backend's active-module list decides what is
  visible, and permissions of inactive modules no longer surface
  settings cards.
- **Reactivating a deactivated treatment category** returned 404
  (#190).
- **Nuxt typecheck** of the host app is clean again (8 stale errors);
  the module-layer backlog is tracked in #184.

### Changed

- **Module authoring docs no longer teach "publish after commit"** —
  every module `events.md` states the mode each handler runs in, and
  `creating-modules.md` §6 carries the decision tree and the savepoint
  pattern (#183).

## [2.2.2] - 2026-08-15

### Fixed

- **Quote discounts now reach the treatment plan and the invoice**
  (#167). Reported on the quote → plan → invoice path:
  - Accepting a quote with line and/or global discounts rescales the
    plan's pending sessions to the accepted amounts, so completing a
    session books the discounted price into the patient's earned
    ledger instead of the catalog price. The plan list shows the
    catalog price struck through next to the effective one.
  - Treatments and sessions can no longer be completed while the plan
    is *Draft* or *Pending acceptance* — the API answers 400 and the
    UI hides the action until the plan is *In progress*.
  - Invoices created from a quote now carry the line discount **and**
    the global discount (prorated per line, ex-tax) — the invoice bills
    what the patient signed. Absolute discounts are prorated on partial
    invoicing (no more double charge across two invoices) and can never
    push a line below zero. The from-budget preview matches the
    resulting invoice.
- **Clearing a quote line's discount via the API was ignored.**
  `PUT /budgets/{id}/items/{item_id}` now honours an explicit `null` on
  nullable fields (discount, tooth, surfaces, notes).
- **Appointment hours rendered in the device timezone on mobile.** The
  mobile day view, kanban, home tiles and lists now show clinic
  wall-clock hours on every device, like the desktop grid.

### Added

- **Tamil (ta) UI locale** across the app, email templates and demo
  seeds (#165). Thanks @tresundios.
- **`DEMO_MODE`** — the public demo blocks user edits/removal and module
  install/uninstall/restart so one visitor cannot break it for everyone.

### Changed

- **License**: production use is granted via a standard BSL 1.1
  *Additional Use Grant* (self-hosting and per-client deployments are
  affirmatively permitted; the SaaS restriction is unchanged).

## [2.2.1] - 2026-08-09

### Fixed

- **Plan and quote lifecycles drifted apart on reject/resend/cancel**
  (#162). Three sync gaps reported during functional testing of the
  renegotiation workflow:
  - Reactivating a rejected treatment plan and confirming it again
    never generated a new quote — the plan stayed tied to the old
    rejected one. Re-confirming now provisions a fresh quote and
    relinks the plan (the documented renegotiation flow had the same
    stale-link bug and is fixed too).
  - Accepting a new quote version (the *Resend* flow) did not advance
    the plan: the version chain never carried the plan link. The plan
    now follows the new version, and a plan closed as *rejected by the
    patient* returns to *In progress* automatically when the patient
    accepts the resent quote.
  - Cancelling a quote directly from the Quotes module left the plan
    stuck in *Pending acceptance* forever. The linked plan now returns
    to *Draft*, ready to edit and re-confirm.
- **Reopening a plan whose quote had expired returned a 500.** The
  invalid `expired → cancelled` budget transition is now skipped.
- **Terminal quotes no longer freeze their plan.** Only *sent* or
  *accepted* quotes lock the plan for editing; cancelled, rejected and
  expired ones are history.

### Added

- **"Resend" button on the quote detail page** — clones a rejected,
  expired or cancelled quote into a new draft version (with a fresh
  public link) and navigates to it. Available in all four UI languages.

## [2.2.0] - 2026-08-01

### Added

- **Portuguese (pt-PT) translation.** The fourth UI language after
  Spanish, English and French. Ships the ~2,340-key core locale plus a
  `pt.json` for each of the eleven module layers, so every screen the
  modules contribute is covered too, and the language appears in
  Settings → Account → Language with no further configuration. Patient
  communications can also be switched to Portuguese: the clinic-wide
  communications language accepts `pt` and the full set of transactional
  email templates (appointment confirmation / reminder / cancellation,
  quote sent / accepted, welcome, morning digest, Verifactu alerts) is
  translated. Nuxt UI's own `pt` locale is wired in so date pickers and
  built-in component strings follow. Backend catalog-name resolution
  gained a `pt` fallback, so treatments named in Portuguese resolve on
  invoices, plans, the timeline and the agent tools rather than silently
  falling back to the internal code.

  Not included: the user manual and the demo seed data stay on
  `es/en/fr`, matching how French shipped.

### Fixed

- **Multi-session treatments were charged double.** Completing the last
  step of a multi-session treatment (e.g. an implant with surgery,
  abutment and crown steps) re-recorded the full parent price on top of
  the amounts already charged per session, so a 1,100 € treatment showed
  as 2,200 € owed. Each session now books only its own amount and the
  total always equals the sum of the sessions. The reverse flow is also
  covered: marking the treatment performed from the odontogram charges
  it once in full and auto-cancels its pending sessions. **Upgrading
  repairs affected ledgers automatically** — the migration removes the
  duplicate charges this bug created; no manual action needed.

- Published images were `amd64` only, so `docker compose up` failed at the
  very first command on Apple Silicon and on ARM VPS instances (Hetzner's
  CAX line, the cheapest in Europe and popular with self-hosters) with a
  bare `no matching manifest for linux/arm64/v8`. Each architecture now
  builds on its own native runner and a merge step publishes one manifest
  list per image, verified to carry both before the release is cut.

## [2.1.0] - 2026-07-28

First release cut through the automated pipeline. The eleven modules that
landed since 2.0.0 — payments, copilot, verifactu, recalls, schedules,
notifications, periodontogram, clinical_notes, accounting_export,
migration_import, whatsapp_kapso — are listed per-PR in the generated
release notes and documented in their own module CHANGELOGs; the
narrative version of that work belongs to the next major.

### Added

- **Prebuilt images and a one-command install.** Tagging a release now
  builds and publishes `ghcr.io/dentalpin/dentalpin-backend` and
  `-frontend`, and publishes the GitHub Release with notes taken from
  this file. `docker-compose.prod.yml` runs the stack straight from those
  images with no clone and no build; a Caddy container fronts both
  services on a single origin, so TLS is provisioned automatically from
  `PUBLIC_URL` and there is no CORS to configure. One image serves every
  deployment — Nuxt overrides `runtimeConfig.public.apiBaseUrl` from
  `NUXT_PUBLIC_API_BASE_URL` at boot rather than baking the URL in.

- **First-time setup assistant** (issue #85). A fresh install (no users)
  now bootstraps from the UI: `GET /api/v1/auth/setup/status` reports
  whether the system is initialized, and `POST /api/v1/auth/setup`
  atomically creates the first clinic + admin user + admin membership and
  returns tokens. The endpoint is self-closing (409 once any account
  exists). The frontend redirects unauthenticated visitors of an empty
  system to a 2-step `/setup` wizard (admin account → clinic basics);
  remaining configuration is handled by the existing onboarding checklist.

### Changed

- Removed the public `POST /api/v1/auth/register` endpoint. It created
  orphan users with no clinic membership (unusable, and unused by the UI);
  the first-run setup assistant replaces it.

- Alembic history squashed. The 29-migration main-linear chain
  inherited from Fase A collapsed into one `0001_core_initial` for
  core tables + 11 module-owned initials under
  `backend/app/modules/<name>/migrations/versions/<mod>_0001_initial.py`.
  Each module's initial lives in its own package so community module
  authors can pattern-match their own migrations on the official
  examples. Cross-module FKs live on the "late" side — the only
  circular dep (`appointment_treatments.planned_treatment_item_id`
  → `planned_treatment_items`) is created in `tp_0001` after both
  tables exist. Round-trip `upgrade head → downgrade base → upgrade
  head` is clean and `test_alembic_roundtrip` no longer xfails.

### Fixed

- `docker-compose.yml` hardcoded `http://localhost:8000` as the frontend's
  API base (build arg + runtime env), so the documented `API_BASE_URL` in
  `.env` had no effect and the app was unreachable from any device other
  than the Docker host — the browser resolved `localhost` to itself.
  Both now read `${API_BASE_URL:-http://localhost:8000}`.

- Clinic timezone selector only offered 15 curated European/American
  zones. It now lists the runtime's full IANA set (`Intl.supportedValuesOf`)
  in a searchable `USelectMenu`; the backend already validated against
  `zoneinfo`, so any IANA id was accepted all along.

## [2.0.0] - 2026-04-21

First release on the post-Fase-B module architecture. Covers the
full Fase B refactor (B.1 → B.6), the hardening pass (B.7), and the
Playwright E2E smoke suite (B.8). `main` is stable against the
12-module layout; the `clinical` module is gone.

### Added

- **Module `patients`** (`auto_install: True, removable: False`) —
  Patient identity, demographics, billing info. Endpoints under
  `/api/v1/patients/*`. Permissions under `patients.*`.
- **Module `patients_clinical`** (`auto_install: True, removable: True`)
  — normalized medical history with 7 tables
  (`patients_clinical_medical_context`, `_allergy`, `_medication`,
  `_systemic_disease`, `_surgical_history`, `_emergency_contact`,
  `_legal_guardian`). Endpoints under `/api/v1/patients_clinical/*`.
  Alerts (`/alerts`) now derive from real rows — actual SQL analytics
  over allergies / diseases is possible.
- **Module `agenda`** (`auto_install: True, removable: True`) —
  Appointment, AppointmentTreatment, Cabinet. Cabinets promoted from
  the `clinic.cabinets` JSONB to a real table with FK
  (`appointments.cabinet_id`). Endpoints under `/api/v1/agenda/*`.
- **Module `patient_timeline`** (`auto_install: True, removable: True`)
  — cross-module audit log, populated via event subscriptions.
  Endpoints under `/api/v1/patient_timeline/*`.
- Clinic metadata endpoints moved into core auth:
  `GET/PUT /api/v1/auth/clinics`.
- Nuxt layer support for every official module. Each module now ships
  `<module>/frontend/{pages,components,composables,i18n}` and is
  auto-discovered at boot via `modules.json`.
- New pytest marker `alembic_roundtrip` for the full
  `base → head → base → head` migration-chain check; excluded from
  the default pytest run, executed as a dedicated CI step.
- CI pipeline gains `manifest-consistency` and `frontend-typecheck`
  jobs (Nuxt `prepare` pass that catches broken Vue/TS imports across
  module layers).
- Playwright browser E2E suite under `frontend/tests/e2e/` — 16
  smoke tests covering admin navigation across every module layer,
  patient detail rendering, and per-role sidebar visibility. CI `e2e`
  job boots docker-compose + seeds demo + runs Playwright.
  `./scripts/e2e.sh` wrapper for local runs.

### Changed

- **Breaking — API paths**
  - `GET /api/v1/clinical/patients/*` → `GET /api/v1/patients/*`
  - `.../medical-history`, `.../alerts`, `.../emergency-contact`,
    `.../legal-guardian` → `/api/v1/patients_clinical/patients/{id}/...`
  - `GET /api/v1/clinical/appointments/*` → `/api/v1/agenda/appointments/*`
  - `GET /api/v1/clinical/clinics/*` → `/api/v1/auth/clinics/*`
  - Patient timeline read at `/api/v1/patient_timeline/patients/{id}`
- **Breaking — permissions**
  - `clinical.patients.*` → `patients.*`
  - `clinical.patients.medical.*` → `patients_clinical.medical.*`
  - `clinical.patients.emergency.*` → `patients_clinical.emergency.*`
  - `clinical.appointments.*` → `agenda.appointments.*`
  - `clinical.appointments.cabinets.*` → `agenda.cabinets.*`
- Every official module manifest's `depends` rewritten against the
  real modules (patients / agenda / catalog / budget) instead of the
  now-removed `clinical`.
- `Patient.active_alerts` property removed (alerts compute via
  `PatientsClinicalService.compute_alerts`).
- Dashboard + Settings sidebar entries are host-owned (see
  `frontend/app/utils/moduleRegistry.ts::HOST_NAV`); modules no
  longer publish `/` or `/settings`.
- Auth rate limiter only activates in `ENVIRONMENT=production`.
  Dev + test runs were tripping the 5/min `/login` cap during manual
  reloads and Playwright runs; production semantics unchanged.

### Removed

- **Breaking — module `clinical`** — fully deleted. All downstream
  depends point at the real owning modules.
- `patients.medical_history`, `patients.emergency_contact`,
  `patients.legal_guardian` JSONB columns dropped — data migrated to
  the normalized `patients_clinical_*` tables in
  `w3x4y5z6a7b8_add_patients_clinical_tables.py`.
- `clinic.cabinets` JSONB column dropped — replaced by the `cabinets`
  table in `v2w3x4y5z6a7_add_cabinets_table.py`.

### Frontend layer conventions

- Each layer's `nuxt.config.ts` must register
  `components: [{path: './components', pathPrefix: false}]`; the host
  overrides Nuxt's default auto-scan so this is load-bearing.
- Cross-layer type imports use `~~/app/types` (rootDir-relative, = host
  frontend) instead of `~/types` (srcDir-relative, which would scope
  to the current layer).

### Known gaps (deferred)

- Alembic chain still lives as a single main-linear list. The squash
  that breaks it into per-module branches (one clean initial per
  module) is deferred; `test_alembic_roundtrip` is `xfail` until
  then and exists purely to hold the infrastructure in place.
- Docs (`docs/diagrams/*`, `CLAUDE.md` examples) still reference the
  old `/api/v1/clinical/*` paths in a handful of illustrative spots;
  the primary `docs/technical/creating-modules.md` and `docs/technical/core-api.md` are
  up to date.
