---
module: leads
last_verified_commit: dd2611ce
---

# leads — overview

Inbound enquiries from the clinic external website form, routed two ways.
The module owns three tables, one page (`/leads`), four settings routes and
one public endpoint. Everything else follows from a single rule: **an enquiry
that matches a patient the clinic already has never becomes a lead — it
becomes a recall.**

`leads` is `official`, `auto_install=False`, `removable=True`, and it
`depends = ["patients", "recalls"]`. Because the routing rule is the module
core, leads cannot be installed without recalls: with recalls missing there is
nowhere for a matched enquiry to go and the rule would degrade into creating
the duplicate lead the module exists to prevent.

## The routing rule

Both entry points — the public form and `POST /api/v1/leads/` (manual creation
by the front desk) — call the same method, `LeadIntakeService.route`, so the
rule cannot drift between the website and the front desk.

```text
POST /api/v1/leads/public/intake          POST /api/v1/leads/
  X-Lead-Key: lk_…                        staff JWT + leads.write/patients.read
        │                                          │
        └──────────► LeadIntakeService.route ◄──────┘
                             │
  honeypot `website` filled ......► 201 {received:true}, nothing written
                                    (no lead, no recall — a bot must see success)
  body > LEADS_INTAKE_MAX_BODY_KB ► 413
  key missing/unknown/inactive ...► 401 (one generic message; public path only)
  daily cap reached ..............► 429 + Retry-After: 3600 (counted anyway)
  ──────────────────────────────────────────────────────────────────────────
  match patients by phone OR email (this clinic, status != archived, LIMIT 3)
        │
        ├── no match ──────────────► INSERT lead, status "new"
        │
        └── match(es) ─────────────► NO lead row. For each matched patient:
                                     recall, reason "other", priority "high",
                                     due today
                                     └─ patient.do_not_contact → status
                                        "needs_review"
  ──────────────────────────────────────────────────────────────────────────
  201 {received:true}  — byte-identical in every end state (D12)
```

The **staff** route does not discard the outcome: it returns a union, so the
front desk is never told "saved" when the row went to Recalls instead.

```jsonc
// 201 — new person
{ "outcome": "lead_created", "lead": { … }, "recalled_patient": null }

// 201 — matched an existing patient
{ "outcome": "recall_queued", "lead": null,
  "recalled_patient": { "id": "…", "first_name": "…", "last_name": "…" } }
```

`recalled_patient` is a `PatientBrief` — which is exactly why `POST /leads/`
also requires `patients.read`, and why `/convert` requires `patients.write`.
The public path returns neither.

### Matching (`matching.py`)

- Clinic-scoped and **non-archived only**. An archived chart calling back is a
  reactivation decision, so the enquiry takes the normal lead path.
- Phones are compared by their **trailing 9 digits** (`phone_key`), which is
  what makes `+34 600 111 222`, `600 111 222` and `600111222` one patient. It
  is a heuristic, not a normaliser: numbers shorter than 9 digits compare
  whole, so a short legacy number can false-positive — hence the confirm step
  in the drawer. The SQL twin lives in `find_matching_patients`; the two must
  change together.
- `phone OR email`, never `AND` — a shared family inbox is common.
- `LIMIT 3`, phone match ranked first, most recent first. A family sharing one
  phone or email legitimately matches two or three patients and **every** match
  gets a recall (each one needs a call); truncation is logged at INFO.

### Recall creation (`recall_routing.py`)

- `RecallService.create` is the **only** writer. It dedupes against active
  recalls for the same `(patient, reason)` — a repeat enquiry refreshes the
  existing row instead of stacking a second one — and publishes
  `recall.created` transactionally, with `db=db`, which is what feeds
  `activity_journal` and, when installed, `recall_reminders`. A hand-written
  insert would silently drop both.
- `reason="other"` (already in `recalls.models.REASONS`), `priority="high"`,
  `due_month`/`due_date` = **today in the clinic's timezone** (`_clinic_context`
  → `_local_day`, not `date.today()`: near midnight a server in another timezone
  would write yesterday's or tomorrow's date on a "call today" recall). That is
  what puts the call-back at the top of the call list. On the public path
  `recommended_by` is `None`; on the staff path it is `ctx.user_id`, so the
  recall records who took the enquiry.
- The note opens with the identity **as submitted** —
  `Web form — submitted as: Somebody Else · 612345678 · stranger@example.com`,
  with the label in the **clinic's communication language**
  (`clinics.settings["communication_language"]`, fallback `es`; e.g.
  `Formulario web — enviado como` for a Spanish clinic). A stored note has no
  reader locale — the UI language is a browser-local preference and intake has
  no user session — so the label is frozen at write time, like every other
  backend-authored string the platform stores (budget PDFs, notifications).
  Then motive / description verbatim, blank-line separated, and **appended** to
  any existing note (skipped if already present, skipped if it would exceed the
  4000-character cap), because `create` overwrites `reason_note` on its dedupe
  path and a staff member may have written their own `other` recall there.
  The header leads because the matched path drops the submitted name, phone and
  email — the recall hangs off the patient — so without it a stranger's words
  (a relative's, a one-digit typo, a shared family phone) read as the patient's
  own and the front desk acts on them. Being first also means the cap can never
  truncate the identity away.
- The submitted **availability is not carried into the note**: days and slot are
  a booking window for a first appointment, not part of what the patient wanted
  to say, and the call-back records the second thing. Because a matched enquiry
  writes no lead row, its availability is consequently not persisted anywhere —
  a deliberate trade, not an oversight (a dedicated recall column is the
  additive way back if a clinic ever needs it).
- `do_not_contact` matches are created in status `needs_review`: the default
  call list filters opted-out patients out, so a `pending` recall for one would
  be invisible and the enquiry would vanish. Outbound contact stays blocked
  independently by the notifications gateway, even with `force_send`.
- **Known, accepted side effect:** with `recall_reminders` installed, the recall
  also queues the patient-facing `recall_reminder` message. Do not bypass
  `RecallService.create` to suppress it — that trades an odd automated message
  for a missing `recall.created`.

## Data model

| Table | One row per | Holds |
|---|---|---|
| `leads` | enquiry that matched nobody | `full_name`, `phone`, `email`, `motive`, `description`, `availability_days` (JSONB, mon..sun), `availability_slot` (`morning`/`afternoon`/`evening`), `status`, `patient_id`, `converted_at` |
| `leads_intake_keys` | clinic (`uq_leads_intake_keys_clinic`) | SHA-256 `key_hash`, `key_prefix`, `is_active` (kill switch), `last_used_at` — never the plaintext |
| `leads_settings` | clinic (`clinic_id` is the **primary key**) | `daily_cap` (default 200, `0` = unlimited), `day_count`, `day_count_date` |

`leads.status` is one of `new`, `contacted`, `converted`, `discarded`;
`discarded` is the only removal path (leads are never hard-deleted).
Conversion goes through `PatientService.create_patient` and sets
`patient_id`, `status="converted"` and `converted_at`; a second conversion is
a 409. `patient_id` is `ON DELETE SET NULL`, so deleting a chart does not
delete the enquiry history that produced it.

The intake key row and the settings row are both **one per clinic** and the
settings row is lazy: `GET /settings` creates it (with the column defaults) so
the page never 404s, but a read never mints an intake key — a key exists only
after an explicit rotate. The counter lives on `leads_settings`, not on the key
row, so cap and count are read and bumped in one atomic statement and the page
works before any key exists.

The attempt is counted **before** the routing decision, and the 429 path
commits that count before it raises: `get_db` rolls back a session whose
handler raised, so an uncommitted increment would vanish and a flood would look
like it never happened. The clinic then sees how big the flood is, not merely
that intake stopped (`tests/modules/leads/test_intake.py` asserts it through a
separate connection).

### Availability is structured, and never becomes patient data

Days live in `availability_days` (canonicalised mon..sun, deduplicated by the
service) with an optional `availability_slot`. Free text was the first design
and was replaced: the front desk needs "which days can we call this person" at a
glance, and the lead card renders a week strip from the codes, localized through
`Intl.DateTimeFormat` rather than 70 i18n keys. The public contract changed with
it — the website now sends `["tue","thu"]`, not a sentence — and `leads_0002`
drops the old text column (it cannot be parsed into days; guessing a call window
is worse than asking again).

Neither the motive nor the availability is copied into the patient record. They
are logistics for one phone call; the chart is built by a human from what belongs
in it. The convert drawer therefore leaves **notes empty**, and the recall note
(the fallback for the matched-patient path, where no lead card exists) is the
only place they are rendered outside the module.

### Why there is no `matched_patient_id` and no `status = "matched"`

A matched enquiry writes **no `leads` row at all** (D8). Its record *is* the
recall: that row already carries the patient, the enquiry note, the priority,
the due date and the dedupe. A second artefact for one enquiry would split the
front desk attention between two queues, and the two views would eventually
disagree. The recall the module created is also not linked back with a
`recall_id` column: the link is `(clinic_id, patient_id, reason)` and the
dedupe lives inside the recalls module, so an FK would buy nothing. If lead
*analytics* ever need matched volume, a `status="matched"` row behind an
explicit flag is the additive way in.

## Abuse controls

The realistic threats, in order: anonymous `curl` without a key, a **leaked
key** (pasted into site JS, committed, shared), someone scripting the real
form, and an actual person double-submitting. The layers, cheapest first:

| Layer | Stops | Honest limit |
|---|---|---|
| Intake key required (`X-Lead-Key`) → one generic 401 | anonymous floods | the key **is** the whole security model — treat it as a secret |
| slowapi `5/minute` per key hash + `30/hour` per IP | lazy scripted floods | disabled unless `ENVIRONMENT=production` and not `TESTING`, and **per-process** (N workers ⇒ N× the budget) |
| **Per-clinic daily cap** in `leads_settings` | leaked-key floods; multi-worker safe | the real ceiling: one atomic `UPDATE … RETURNING` per accepted intake, default 200/day, `0` = unlimited, owned by the clinic |
| 8 KB body cap + `max_length` on every field | memory/storage abuse | a declared-size ceiling, not a streaming read cap |
| Honeypot `website` field | naive bots | free; silently 201s with no write |
| Recall dedupe + 4000-character note cap | spam turning into staff noise | free |
| Rotate the key, or `PATCH /settings/intake-key {is_active:false}` | an *active* flood | instant, no deploy — the operator kill switch |

**Honest limits — read these before trusting a layer:**

- The backend runs `uvicorn … --proxy-headers --forwarded-allow-ips=*`
  (`docker-compose.yml`), so **`X-Forwarded-For` is client-controlled**: an
  attacker rotating that header walks around any IP-keyed limit. The IP limit
  is still worth having (it stops the lazy case); the **per-key** limit and the
  **per-clinic daily cap** are the real bounds — which is why the cap lives in
  Postgres and not in process memory.
- A captcha was considered and deliberately **not** shipped: it is inert without
  external credentials, and the key + per-clinic cap already bound the damage. An
  operator facing distributed spam should put Cloudflare or nginx in front
  (below) rather than expect a third-party dependency to be added here.
- Rotating the key is the *complete* answer to a leaked key: the old key stops
  working immediately and legitimate intake continues with the new one.
  Rotating never resets `day_count` — it stops a flood, it does not hand the
  attacker a fresh daily budget — and it is the reason the operator must paste
  the new key into the website (the form fails until then).
- Operator-level protection belongs in **front of the app**: Cloudflare rate
  rules or nginx `limit_req`. **Do not add a `rate_limit` directive to
  `Caddyfile`** — it is not in stock Caddy (it is a third-party module) and the
  repo ships stock Caddy, so a plan that "adds Caddy rate limiting" breaks the
  prod build.

### Where the cap is configured

**Settings → Integrations → "Formulario web"** (`/settings/integrations/leads`),
backed by the four `/settings` routes. The cap is a `leads_settings` column
edited in the UI — **never an env var**: a clinic has to be able to raise its
own ceiling during a campaign without an admin editing `.env` and restarting
containers. There is no `LEADS_INTAKE_DAILY_CAP`; the column default *is* the
default. One thing stays in the environment, and it is not a business decision:
`LEADS_INTAKE_MAX_BODY_KB`. Lowering the cap below today count blocks intake
immediately — that is the
intended emergency lever, and the page says so.

## Events

The module publishes and subscribes to **nothing of its own** (D7), which is
why there is no `docs/technical/leads/events.md`. The recall it creates does
publish `recall.created` — through the recalls module, whose
`RecallService.create` is the writer. `activity_journal` and (when installed)
`recall_reminders` react to that event, not to anything `leads` emits.

## Related documents

- `backend/app/modules/leads/CLAUDE.md` — agent-facing summary and gotchas.
- [`permissions.md`](./permissions.md) — endpoint-per-permission table.
- `docs/technical/leads-plan.md` — the approved implementation plan (D1–D13).
- `docs/user-manual/en/leads/index.md` — end-user landing page.