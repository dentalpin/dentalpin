# Changelog — leads module

## Unreleased

### Fixed

- Convert drawer: the Edit button now requires `leads.write` and Create
  patient `leads.write` + `patients.write`, mirroring the API — a dentist
  (`patients.*`, `leads.read`) no longer clicks into a 403.
- Edit modal success toast no longer shows the "Status" label as its message.

### Changed

- Manifest `category` is `community` and `author` the contributor.

### Added

- `leads` module: inbound enquiries from the clinic external website form,
  mounted at `/api/v1/leads/`, with the `/leads` queue page and the
  Settings → Integrations → "Formulario web" settings page.
- Public, key-gated intake endpoint `POST /api/v1/leads/public/intake`
  (`X-Lead-Key`): honeypot, 8 KB body cap, per-clinic daily cap and identical
  responses in every routing branch (D12).
- Routing rule: an enquiry whose phone **or** email matches a non-archived
  patient of the clinic queues a recall (`reason="other"`, `priority="high"`,
  due today) and writes **no** lead row; `do_not_contact` matches land in
  `needs_review`.
- Repeat enquiries refresh the existing `(patient, "other")` recall and append
  the enquiry note instead of overwriting it (4000-character cap).
- Tables `leads`, `leads_intake_keys` (SHA-256 hash only) and `leads_settings`
  on the module own Alembic branch `leads` (`leads_0001`).
- `manifest.depends = ["patients", "recalls"]` — the module cannot be installed
  without them, because a matched enquiry has nowhere to go otherwise.
- Six agent tools; intake-key rotation and the active toggle are deliberately
  not exposed to agents.
- Publishes no events of its own: the recall it creates publishes
  `recall.created` through the `recalls` module.
- The daily counter is committed before a 429, so a blocked flood keeps showing
  in the gauge instead of being rolled back with the rejected request;
  `tests/modules/leads/test_intake.py` asserts it through a separate
  connection.
- The settings page builds the intake URL from the app's API base
  (`runtimeConfig.public.apiBaseUrl`) instead of the browser origin, so the URL it
  hands the clinic's web developer points at the API — posting to the SPA origin
  answers with a login redirect, not `{"received": true}`.
- Frontend layer with the `/leads` page, the convert drawer, the manual
  create/edit modal and the settings page.
- Localised into all ten UI locales (en, es, fr, de, pt, it, pl, hu, ta, ar) —
  key-identical and placeholder-checked by
  `frontend/tests/i18n/locale-parity.test.ts`. Each language reuses the host locale
  own word for Recalls and its own address register.
- The /leads queue opens filtered to **New** (the status chip reads
  `Status · 1`): converted cards leave the default view as soon as they are
  converted. Deliberate deviation from the original plan (which defaulted to all
  statuses) — the default is a *visible* chip selection and the API still answers
  "no status param = every status", so nothing is hidden server-side and the
  converted history stays reachable by clearing the chip.
- **Availability is structured**: `availability_days` (mon..sun, canonicalised and
  deduplicated) plus an optional `availability_slot`
  (`morning`/`afternoon`/`evening`), replacing the free-text column. The public
  intake contract takes day codes, so the clinic website must send them;
  `leads_0002` drops the old text column (free text cannot be parsed into days,
  and guessing a call window is worse than asking again).
- Lead payloads now reject unknown fields (`extra="forbid"`): a website still
  posting the retired `availability` free-text string receives a 422 naming the
  field instead of having the value silently dropped.
- The lead card was redesigned around the call: **motive** first, the description
  trimmed to a line, and a **week strip** with the days (and time of day) the
  person can be called. Weekday names come from `Intl.DateTimeFormat`, so they
  are correct in all ten locales without per-day translation keys.
- **The motive and the call availability are no longer copied into the patient
  record.** The convert drawer starts with empty notes: they are logistics for
  one call, not patient data. The recall note (the matched-patient path, where no
  lead card exists) carries the motive and description — but not the availability;
  see the Fixed entry below.
- Form validation on both staff forms (`utils/leadValidation.ts`): an invalid email,
  a phone with too few digits, a missing required field or a future date of birth
  is refused **before** it is sent, with the reason shown on the field and a toast
  — every message translated in all ten locales. The rules mirror what pydantic
  accepts (single @, dot in the domain, 6+ digits, the 20-char patient phone
  column), so anything the form accepts is not rejected by the server.
- Copy buttons on the website-form settings page for the intake URL, the intake
  key and the `curl` example (with an explicit error toast when the browser
  denies clipboard access).

### Fixed

- **A matched enquiry's recall note now opens with the identity as submitted**
  (`Web form — submitted as: Name · phone · email`). The matched path drops the
  submitted name/phone/email — the recall hangs off the patient — so a stranger's
  words (or a relative's, or a one-digit typo, or a phone two patients share)
  read as the patient's own and the front desk acted on them. The header is first
  in the note, so the 4000-character cap can never truncate it; the response to
  the submitter is unchanged (D12 still holds).
- **That label is written in the clinic's communication language**, not a fixed
  English string: `clinics.settings["communication_language"]` (the same source
  the budget PDFs and the notifications gateway use; fallback `es`), with labels
  for all ten UI locales in `_IDENTITY_LABELS`. Stored notes have no reader
  locale — the UI language is a browser-local preference that never reaches the
  API and intake has no user session — so the wording is frozen with the note: a
  clinic that switches language keeps earlier blocks in the earlier language.
  `test_routing.py` covers es/en/unknown-language and guards the label key set
  against the host locale list.
- **"Call today" is now the clinic's today, not the server's calendar day.** The
  recall's `due_month`/`due_date` are computed from `Clinic.timezone`, so a server
  in another timezone no longer stamps yesterday's or tomorrow's date on a
  call-back near midnight.
- **`list_leads` no longer returns `motive`/`description`.** They are free text
  typed by anyone on the internet, and an unflagged tool result is sent to the
  cloud LLM — a PHI and prompt-injection surface. `get_lead` still returns them
  (it is flagged `exposes_free_text=True`, which keeps it off the cloud path);
  `tests/modules/leads/test_tools.py` pins the shape so a re-added prose field
  cannot leak through five tools silently.
- **The recall note no longer carries the enquiry's availability** (days / slot).
  Those are a booking window for a first appointment, not part of what the
  patient wanted to say, and the call-back records the second thing. Consequence
  worth stating plainly: a matched enquiry writes no lead row, so its availability
  is now stored nowhere. `test_routing.py` pins the absence so it cannot creep
  back; `recall_routing._format_availability` and its day-code token are gone with
  it.