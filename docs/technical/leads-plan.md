# Leads module — implementation plan

> **Status:** implemented — kept as the design record (see "Shipped in
> `85e5bffa`" below for where reality diverged).
> **Audience:** the agent/model implementing the `leads` module.
> **Scope of this document:** everything needed to ship the module green
> against CI, in the order it should be built.
> **Revision 2:** adds the match→recall routing (D8–D12, §3.1–§3.3) and the
> abuse-control layers (§3.4). Read §3 before writing any code — it is what
> makes `leads` depend on `recalls`.
> **Revision 3:** the daily cap is a **per-clinic setting edited on a module
> settings page** (§5.6), not an env var — and the intake key moves there
> with it.
>
> **Shipped in `85e5bffa`.** This document is the *pre-implementation design*;
> the line of record for behaviour is `backend/app/modules/leads/CLAUDE.md`
> and `docs/technical/leads/`. Three points changed during implementation and
> the text below still describes the original:
>
> 1. **Availability is structured** — `availability_days` (canonical mon..sun
>    codes) + `availability_slot` (`morning`/`afternoon`/`evening`), not the
>    free-text string of D3. `leads_0002` drops the old text column, and the
>    payloads use `extra="forbid"`, so a website still posting the retired
>    `availability` string gets a **422 naming the field** rather than a
>    silent drop.
> 2. **Captcha was not shipped** (the optional layer in §3.4). The abuse
>    budget is the key + IP limits, the per-clinic daily cap, the body cap,
>    the honeypot and the recall/lead dedupe. There is no captcha env var and
>    no `captcha_token` field.
> 3. **The convert drawer opens with `notes` empty** — motive and
>    availability are logistics for one call, not chart data, so they are not
>    copied into the patient record.
>
> Everything else (§3.1 routing, §3.2 recall reuse, §4.x file layout, §5.6
> settings page, §10 gotchas) landed as written.

`leads` captures inbound enquiries from an external website/form, then
routes each one two ways: an enquiry that matches a patient the clinic
already has becomes a **recall** (the staff call list) — no lead is
created — while a genuinely new person becomes a **lead** card on a new
`/leads` page, convertible into a `patients` record through a right-side
drawer pre-filled from the lead.

---

## 1. Locked decisions (do not re-litigate)

| # | Decision | Rationale |
|---|---|---|
| D1 | **Conversion target is a patient** (`patients.id`), created through `PatientService.create_patient`. | The `contacts` module is a directory of external labs/suppliers, not people. Reception's real workflow is opening a patient chart. |
| D2 | **Intake auth = one per-clinic intake key** (`lk_…`), sent as `X-Lead-Key`. Not the `integrations` `dp_` token, not a bare slug route. | The form is outside the app; a key is self-contained, revocable, and needs no cross-module dependency. |
| D3 | **`availability` is free text**, stored verbatim. | The external form owns its own wording ("mornings", "weekdays after 17:00"). |
| D4 | **Page scope:** card list + status filter + convert drawer, **plus** manual lead creation and editing. | Front desk must be able to fix a typo'd phone taken over the phone. |
| D5 | Intake is **key-gated only** (a second, staff-authenticated path is not built). | Keeps the surface small; staff work goes through `POST /leads`. |
| D6 | Converting **keeps the lead** (`status="converted"`, `patient_id` set). | Lead history is marketing data; never hard-delete. |
| D7 | No events published or consumed by this module in v1. | Nothing needs to react to a lead yet; adding events later is additive. The recall it creates *does* publish `recall.created` — that is the recalls module's existing contract, not something we add. |
| D8 | **A matched enquiry never becomes a lead.** Intake matches `phone` **or** `email` against the clinic's patients; on a match, the matched patient(s) get a recall and **no `leads` row is written.** | A returning patient does not need a lead card; they need a phone call. Two artefacts for one enquiry would also split the front desk's attention. |
| D9 | Matching is clinic-scoped, **non-archived only**. Matches on `do_not_contact` patients become recalls in status `needs_review`. Archived-only matches are treated as no match. | `patients/CLAUDE.md`: opted-out patients must stay out of active call lists and surface in a needs-review bucket. An archived chart calling back is a reactivation decision, not an automatic recall. |
| D10 | Recall creation **reuses `RecallService.find_pending_for` + `RecallService.create`** — never a hand-written insert. | `create` already dedupes per `(patient, reason)` against active recalls and publishes `recall.created` transactionally. Duplicating it would drop the event (activity journal) and the dedupe. |
| D11 | Abuse controls: key + IP rate limits, a **per-clinic daily cap** (default 200, `0` = unlimited — configured on the module settings page, **not** an env var), an 8 KB body cap, the honeypot field, and recall/lead dedup. Captcha is **wired but inert** until `LEADS_CAPTCHA_PROVIDER`/`_SECRET` are set. | See §3.4 — the honest limits (spoofable `X-Forwarded-For`, per-process slowapi) are why the DB-backed cap is the real ceiling. |
| D12 | The intake response is byte-identical whether the enquiry matched a patient or not. | An unauthenticated caller must not be able to probe "is this phone a patient of this clinic?". |
| D13 | **The cap is clinic data, not process config.** It lives in `leads_settings` (one row per clinic), edited on a registered settings page at **Settings → Integrations → *Formulario web***, with `leads.settings.read` (see it) / `leads.settings.write` (change it, rotate the key) permissions. The intake-key UI moves off the Leads page into that same page. | A clinic must be able to raise its own ceiling during a campaign without an admin editing `.env` and restarting containers. Precedent: `whatsapp_webhook` (per-clinic secret on an Integrations settings page) and `schedules.clinic_hours.read/write`. |

**Deliberate deviation to know about:** the intake schema requires
`full_name`, `phone`, `email`, `motive` and `availability`, matching the
requested payload (only `description` is optional). If the clinic's site
would rather not lose leads with a typo'd email, relax `email` to
`EmailStr | None` in `LeadIntakeCreate` — a one-line change; the column is
nullable either way.

---

## 2. Contract summary

| Item | Value |
|---|---|
| Module name | `leads` |
| Backend mount | `/api/v1/leads/` |
| Permission namespace | `leads.read`, `leads.write`, `leads.settings.read`, `leads.settings.write` |
| Tables | `leads`, `leads_intake_keys`, `leads_settings` |
| Frontend layer | `backend/app/modules/leads/frontend/` |
| Page route | `/leads` |
| Settings page | registered at **`/settings/integrations/leads`** (category `integrations`, permission `leads.settings.read`) |
| Nav | label `leads.nav.leads` (module's own i18n), icon `i-lucide-inbox`, `section: "practice"`, `order: 86` |
| Alembic branch | label `leads`, first revision `leads_0001`, `down_revision="0001"`, `depends_on=("pat_0003",)` |
| Manifest policy | `category: "official"`, `auto_install: False`, `removable: True`, `depends: ["patients", "recalls"]` |

`order: 86` places the entry inside the **Practice** sidebar section
between *Reports* (60) and *Staff tasks* (91). `practice` is correct per
the canonical-section table in `docs/technical/creating-modules.md` §4 — a
lead queue is practice-management work, not clinical data.

### Data model

`leads`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `default=uuid4` |
| `clinic_id` | UUID FK `clinics.id`, indexed | mandatory multi-tenant column |
| `full_name` | String(200), not null | the external form sends **one** name field |
| `phone` | String(32), not null | store as typed, trimmed |
| `email` | String(255), nullable | required by the intake schema, nullable for staff-created rows |
| `motive` | String(200), not null | "motive of call" |
| `description` | Text, nullable | optional free text |
| `availability` | String(200), nullable | free text (D3) |
| `status` | String(20), not null, default `"new"` | `new` / `contacted` / `converted` / `discarded` |
| `patient_id` | UUID FK `patients.id` `ondelete="SET NULL"`, nullable, indexed | set on conversion (D6) |
| `converted_at` | DateTime(tz), nullable | set on conversion |
| `created_at`, `updated_at` | from `TimestampMixin` | |

`Index("ix_leads_clinic_status_created", "clinic_id", "status", "created_at")` —
the list page's default query shape (filter by status, sort by created_at).

`leads_intake_keys` — exactly **one row per clinic**:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `clinic_id` | UUID FK `clinics.id`, indexed | `UniqueConstraint("clinic_id", name="uq_leads_intake_keys_clinic")` |
| `key_hash` | String(64), unique, indexed | SHA-256 hex of `lk_…` (same reasoning as `integrations.ApiToken.token_hash`) |
| `key_prefix` | String(12) | e.g. `lk_AbC12` — shown in the UI so a clinic can tell keys apart after rotation |
| `is_active` | Boolean, not null, default `True` | soft revoke (the kill switch) |
| `last_used_at` | DateTime(tz), nullable | touched on every accepted intake |
| `created_at`, `updated_at` | `TimestampMixin` | |

Never store the plaintext key: it is returned **once** from
`POST /settings/intake-key/rotate` and never again.

`leads_settings` — exactly **one row per clinic** (the D13 home for the cap
and its counter):

| Column | Type | Notes |
|---|---|---|
| `clinic_id` | UUID FK `clinics.id`, **primary key** | one row per clinic — the `recalls.recall_settings` shape |
| `daily_cap` | Integer, not null, `server_default="200"` | `0` = unlimited; validated `0..5000` at the API edge |
| `day_count` | Integer, not null, `server_default="0"` | attempts accepted today, including matched (recall) ones — the flood gauge |
| `day_count_date` | Date, nullable | the day `day_count` belongs to; a new day resets it |
| `updated_at` | DateTime(tz), not null | `server_default=func.now()`, `onupdate=func.now()` |

The counter lives here rather than on the key row so that cap + count are
read and bumped in **one** atomic statement (§4.3), and so the settings page
works before any key exists. Rotating the key must **not** reset
`day_count` — rotation stops a flood, it does not hand the attacker a fresh
daily budget.

Note what is **absent** from `leads`: there is no `matched_patient_id`, no
`status = "matched"`, no "matched enquiry" audit row. A matched enquiry
leaves no trace in this module — its record is the recall (§3.1). If lead
*analytics* ever need it, a `status="matched"` row behind a boolean is the
additive way in (§11).

### Endpoints

Staff (all require the clinic JWT context and filter by `ctx.clinic_id`):

| Method | Path | Permission | Notes |
|---|---|---|---|
| `GET` | `/api/v1/leads/` | `leads.read` | paginated; `status`, `search`, `page`, `page_size`, `sort` |
| `GET` | `/api/v1/leads/{lead_id}` | `leads.read` | 404 on unknown/other-clinic id |
| `POST` | `/api/v1/leads/` | `leads.write` **and** `patients.read` | manual creation (201). Returns an outcome union: `lead_created` **or** `recall_queued` (§3.1). `patients.read` is required because the matched-patient branch discloses a patient (§4.5) |
| `PATCH` | `/api/v1/leads/{lead_id}` | `leads.write` | all-optional body + `exclude_unset` (PATCH semantics, as in `patient_segments`) |
| `POST` | `/api/v1/leads/{lead_id}/convert` | `leads.write` **and** `patients.write` | body = patient fields; creates the patient + links the lead atomically |
| `GET` | `/api/v1/leads/settings` | `leads.settings.read` | `{daily_cap, day_count, day_count_date, intake_url, key: {configured, key_prefix, is_active, last_used_at}}` — never the key |
| `PATCH` | `/api/v1/leads/settings` | `leads.settings.write` | `{daily_cap}`; validated `0..5000` (`0` = unlimited) |
| `POST` | `/api/v1/leads/settings/intake-key/rotate` | `leads.settings.write` | creates or rotates; returns `key` plaintext **once**. Does not reset `day_count` |
| `PATCH` | `/api/v1/leads/settings/intake-key` | `leads.settings.write` | `{is_active: bool}` |

Public (no clinic context — the key *is* the auth, same shape as
`notifications/public_router.py`):

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/leads/public/intake` | header `X-Lead-Key`; 201 `{data: {received: true}}`; 401 on missing/unknown/inactive key; 422 on validation; 413 on an oversized body; 429 over a limit or the daily cap |

**Path traps — pin these exactly.** Modules are mounted at
`/api/v1/<name>` and the app runs with `redirect_slashes=False`. Declare
the collection routes as `@router.get("/")` / `@router.post("/")` (the
`contacts` / `staff_tasks` convention) and call them from the frontend as
`/api/v1/leads/` **with** the trailing slash. `/api/v1/leads` will 404.
Sub-paths (`/public/intake`, `/settings/intake-key/rotate`) carry no
trailing slash.

Settings and intake-key routes live under `/settings/…` rather than at the
module root: one prefix, one permission pair, and the frontend URL
(`/settings/integrations/leads`) mirrors the API shape.

### Intake request/response

```jsonc
// POST /api/v1/leads/public/intake
// X-Lead-Key: lk_xxxxxxxx...
{
  "full_name": "Marta Ruiz",
  "phone": "+34 600 111 222",
  "email": "marta@example.com",
  "motive": "Presupuesto de ortodoncia",
  "description": "Le llaman por la mañana, viene de Instagram.",
  "availability": "Tardes a partir de las 17:00",
  "website": "",           // honeypot — must be empty, never stored
  "captcha_token": null    // only meaningful when LEADS_CAPTCHA_PROVIDER is set
}

// 201
{ "data": { "received": true }, "message": null }
```

The response echoes **nothing** back (no id, no clinic name, no
"you're already our patient") — the caller must learn nothing it did not
already know, mirroring `PushSubscribed`/`redeem_push_subscribe_token`.
That is a hard rule, not styling: the endpoint is unauthenticated and the
clinic's patient list is not public (D12).

---

## 3. Intake routing and abuse controls

Both entry points — the public form and `POST /api/v1/leads/` — call **one**
service method (`LeadIntakeService.route`) so the rule cannot drift between
them. Build this section before the CRUD; everything else depends on it.

### 3.1 The routing rule

```
payload: full_name, phone, email, motive, description, availability

  honeypot filled .............................► 201 {received:true}, nothing written
  body > LEADS_INTAKE_MAX_BODY_KB .............► 413
  key missing/unknown/inactive (public only) ..► 401 (one generic message)
  captcha configured and failing ..............► 403
  daily cap reached ...........................► 429 (counted, surfaced in the UI)
  ──────────────────────────────────────────────────────────────────────────
  match patients by phone OR email (this clinic, status != archived)
        │
        ├── no match ─────────────────────────► INSERT lead (status "new")
        │
        └── match(es) ────────────────────────► NO lead row. For each matched
                                               patient: recall, reason "other",
                                               priority "high", due today
                                               └─ do_not_contact → status "needs_review"
  ──────────────────────────────────────────────────────────────────────────
  201 {received:true}  — identical body in both end states
```

Matching details (implement in `LeadService.find_matching_patients`):

```python
digits = re.sub(r"\D", "", phone or "")
phone_key = digits[-9:] if len(digits) >= 9 else digits      # "+34 600 111 222" → "600111222"

select(Patient).where(
    Patient.clinic_id == clinic_id,                 # mandatory — never omit
    Patient.status != "archived",
    or_(
        func.right(func.regexp_replace(func.coalesce(Patient.phone, ""), r"\D", "", "g"), 9)
            == phone_key,                            # phone match wins
        func.lower(Patient.email) == (email or "").strip().lower(),
    ),
).order_by(match_is_phone.desc(), Patient.created_at.desc()).limit(3)
```

- The trailing-9-digits comparison is what makes `+34 600 111 222`,
  `600 111 222` and `600111222` one patient. It is a **heuristic**: numbers
  shorter than 9 digits compare whole, so a short legacy number can
  false-positive. Documented, tested (§6.1), and the reason the drawer still
  lets a human confirm.
- `LIMIT 3` bounds the fan-out. A family sharing one phone/email legitimately
  matches two or three patients, so **all** matches get a recall (each needs
  a call). Log at INFO when the limit truncates.
- Archived patients are excluded from matching: the enquiry then takes the
  normal lead path, which is where a reactivation decision belongs.

### 3.2 Recall creation (reuse, never re-implement)

```python
existing = await RecallService.find_pending_for(db, clinic_id, patient.id, "other")
note = _compose_enquiry_note(payload)               # motive / description / availability
if existing and existing.reason_note:
    if note not in existing.reason_note and len(existing.reason_note) < _NOTE_CAP:
        note = f"{existing.reason_note}\n\n---\n\n{note}"   # append, never overwrite
recall, created = await RecallService.create(
    db,
    clinic_id,
    {
        "patient_id": patient.id,
        "due_month": date.today(),        # service normalises to day-1
        "due_date": date.today(),         # "call today"
        "reason": "other",
        "priority": "high",               # call list sorts high first
        "reason_note": note,
        "assigned_professional_id": None,
    },
    recommended_by=None,                  # public path; ctx.user_id on the staff path
)
if patient.do_not_contact:                # D9 — applies to both branches: an opted-out
    recall.status = "needs_review"        # patient must never sit in the active call list
```

Why each piece:

- **`RecallService.create` is the only writer.** It dedupes against active
  recalls for the same `(patient, reason)` — a repeat enquiry refreshes the
  existing row instead of stacking a second one — and it publishes
  `recall.created` with `db=db`, which feeds `activity_journal` and, when
  installed, `recall_reminders`. A hand-written insert would silently drop
  both.
- **The note is appended, not replaced**, because `create` *overwrites*
  `reason_note` on the dedupe path (it is designed for a single call this
  way) — and a staff member may have written their own `other` recall for
  that patient. Append preserves both; the substring check plus a
  4000-character cap keeps a flood from growing one row without bound.
- **`reason = "other"`** exists in `recalls.models.REASONS` already. A
  dedicated `lead_callback` reason would filter better but means editing
  another module's enum, its reason-interval defaults, its picker and ten
  locale files — that is a follow-up, not part of this module (§11).
- **`priority = "high"` + `due_month`/`due_date` = today** is what makes the
  recall land at the top of the call list: `recalls/service.py:152-159`
  orders by priority bucket, then `due_month`, then `created_at`.
- **`do_not_contact` → `needs_review`** matches `patients/CLAUDE.md` and
  keeps the patient out of the default call list
  (`recalls/service.py:112-113` excludes opted-out patients). Outbound
  contact is independently blocked: the notifications gateway hard-refuses
  `do_not_contact` on every channel, even with `force_send`
  (`notifications/gateway.py:92-102`) — so the opt-out holds even though a
  recall row exists.
- **Known, accepted side effect:** with `recall_reminders` installed, the
  recall also queues the patient-facing `recall_reminder` message. Do **not**
  bypass `RecallService.create` to suppress it — that trades a slightly odd
  automated message for a missing `recall.created` (activity journal, and
  any future consumer). The lever a clinic has is the notifications
  template/preference; a dedicated "we received your enquiry" notification
  type is a follow-up (§11). Write this into the module `CLAUDE.md`.

### 3.3 Staff-path outcome

`POST /api/v1/leads/` returns the same union the routing produces, so the
front desk is never told "saved" when the row went to Recalls instead:

```jsonc
// 201 — new person
{ "data": { "outcome": "lead_created", "lead": { /* LeadResponse */ },
            "recalled_patient": null } }

// 201 — matched an existing patient
{ "data": { "outcome": "recall_queued", "lead": null,
            "recalled_patient": { "id": "…", "first_name": "…", "last_name": "…" } } }
```

`recalled_patient` is a `PatientBrief` — which is exactly why this route
also requires `patients.read` (§4.5): it discloses which patient matched.
The public path returns neither (§3.1, D12).

### 3.4 Anti-abuse layers

The realistic threats are, in order: (1) anonymous `curl` without a key,
(2) a **leaked key** — pasted into site JS, committed, or shared,
(3) someone filling the real form with a script, (4) an actual person
double-submitting. The layers below are aimed at those, cheapest first.

| Layer | Stops | Cost / honest limit |
|---|---|---|
| Key required (`X-Lead-Key`) → generic 401 | anonymous floods (1) | free; the key is the whole security model, so treat it as a secret |
| slowapi `5/minute` + `30/hour`, keyed **by key-hash and by IP** | lazy scripted floods (2, 3) | disabled unless `ENVIRONMENT=production` and not `TESTING`; **per-process** (N workers ⇒ N× the budget); IP is spoofable (below) |
| **Per-clinic daily cap** in `leads_settings`, edited at Settings → Integrations → *Formulario web* | leaked-key floods (2), multi-worker-safe (3) | one atomic `UPDATE … RETURNING` per accepted intake; default 200/day, `0` = unlimited; the clinic owns the number (D13) |
| 8 KB body cap + `max_length` on every field | memory/storage abuse (1–3) | free |
| Honeypot `website` field | naive bots | free; silently 201s with no write |
| Recall dedupe + note cap (§3.2) | spam turning into staff noise | free |
| Optional captcha (`LEADS_CAPTCHA_PROVIDER` + `_SECRET`, Turnstile or hCaptcha) | distributed bot spam (3) | inert unless configured; one outbound verify call with a 5 s timeout, **fail-closed** when configured |
| `PATCH /settings/intake-key {is_active:false}` + rotate | an *active* flood | instant, no deploy — the operator's kill switch, on the settings page next to the volume gauge |

Honest limits — put these in the docs rather than discovering them live:

- The backend runs `uvicorn … --proxy-headers --forwarded-allow-ips=*`
  (`docker-compose.yml:50`), so **`X-Forwarded-For` is client-controlled**:
  an attacker rotating that header walks around any IP-keyed limit. The
  IP limit is still worth having (it stops the lazy case); the **per key**
  limit and the **per-clinic daily cap** are the real bounds, which is why
  the cap lives in Postgres and not in process memory.
  `_client_ip()` (`app/core/auth/router.py:291-295`) has the same caveat.
- Captcha raises the price of distributed spam; it does not make it
  impossible. Off by default keeps self-hosters working with no third-party
  dependency — turn it on for a clinic that is actually being targeted.
- Rotating the key is the *complete* answer to a leaked key: the old key
  stops working immediately and legit intake continues with the new one.
  Say so on the settings page, right next to the rotate button, so nobody's
  first instinct is to disable intake for the day (and nobody has to find
  an admin to edit `.env`).
- Operator-level protection belongs in front of the app: Cloudflare rate
  rules or nginx `limit_req`. **Do not add a `rate_limit` directive to
  `Caddyfile`** — it is not in stock Caddy (third-party module) and the
  repo ships stock Caddy. A plan that "adds Caddy rate limiting" would
  break the prod build.

### 3.5 Env vars

Only two things stay in the environment, and neither is a business
decision: the request size ceiling and the optional captcha credentials.
**The daily cap is deliberately *not* here** (D13) — it is a
`leads_settings` column the clinic edits in the UI.

Add to `backend/app/config.py` (and to `.env.example` / `.env.prod.example`
with comments):

```python
LEADS_INTAKE_MAX_BODY_KB: int = 8
LEADS_CAPTCHA_PROVIDER: str = ""       # "" | "turnstile" | "hcaptcha"
LEADS_CAPTCHA_SECRET: str = ""
```

If captcha is not wanted at all, delete `captcha_token` from
`LeadIntakeCreate`, the `_verify_captcha` helper and these two vars —
nothing else in the design depends on them.

---

## 4. Backend — files to create

```
backend/app/modules/leads/
├── CLAUDE.md                      # from docs/checklists/module-claude-template.md
├── CHANGELOG.md                   # starts at "## Unreleased"
├── __init__.py                    # LeadsModule + manifest + entry point
├── models.py                      # Lead, LeadIntakeKey
├── schemas.py                     # staff CRUD + intake + intake-key schemas
├── service.py                     # LeadService, LeadIntakeService, LeadIntakeKeyService
├── matching.py                    # phone/email normalisation + find_matching_patients
├── recall_routing.py              # route_matched_enquiry → recalls (D8–D10)
├── router.py                      # staff HTTP surface
├── public_router.py               # POST /public/intake (no clinic context)
├── tools.py                       # agent tools wrapping LeadService
├── migrations/__init__.py
├── migrations/versions/leads_0001_initial.py
└── frontend/…                     # §5
```

`matching.py` and `recall_routing.py` are separate files on purpose: the
matching heuristic and the recall routing are the two things a reviewer must
be able to read in isolation, and both are unit-testable without HTTP.

Plus three registrations outside the module directory (§4.7).

### 4.1 `__init__.py`

```python
class LeadsModule(BaseModule):
    manifest = {
        "name": "leads",
        "version": "0.1.0",
        "summary": "Inbound leads from external forms: new enquiries become leads, known patients become recalls.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        # recalls: matched enquiries are routed to the call list (D8).
        #   leads cannot be installed without recalls installed.
        # patients: FK + PatientService.create_patient on conversion.
        "depends": ["patients", "recalls"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": [],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "leads.nav.leads",
                    "section": "practice",
                    "icon": "i-lucide-inbox",
                    "to": "/leads",
                    "permission": "leads.read",
                    "order": 86,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [Lead, LeadIntakeKey]

    def get_router(self) -> APIRouter:
        # Compose authenticated + public sub-routers under one mount
        # (budget / notifications precedent).
        combined = APIRouter()
        combined.include_router(router)
        combined.include_router(public_router)
        return combined

    def get_permissions(self) -> list[str]:
        # Namespaced by the registry → leads.read, leads.write,
        # leads.settings.read, leads.settings.write.
        # settings.* are admin-only (via "admin": ["*"]), exactly like
        # whatsapp_webhook: the key is a secret and rotating it breaks the
        # clinic's website until a human pastes the new one in.
        return ["read", "write", "settings.read", "settings.write"]

    def get_tools(self) -> list:
        from . import tools
        return tools.get_tools()
```

The manifest validator rejects a nav `permission` that is not namespaced
(`NAV_PERM_NOT_NAMESPACED`), rejects `role_permissions` entries not
returned by `get_permissions()` (`UNKNOWN_PERMISSION`), and rejects
`removable=True` unless the Alembic branch is isolated
(`REMOVABLE_BRANCH_NOT_ISOLATED`).

`settings.read` / `settings.write` are returned by `get_permissions()` but
granted to **no role except admin** (through `"admin": ["*"]`) — the
`whatsapp_webhook` shape. `test_module_manifests_consistency.py` is happy
with that: it checks that every manifest grant exists in
`get_permissions()`, not the reverse. Do not add `settings.write` to
`receptionist` to "make floods easier to handle" — rotation silently breaks
the integration until the site is updated, so it belongs to whoever owns
the website.

Nav label `leads.nav.leads` is namespaced inside the module's **own**
locale files (the `payroll.nav.*` pattern) — do **not** add a `nav.leads`
key to the ten host locale files.

### 4.2 `service.py`

`LeadService` — static methods, no HTTP imports except `HTTPException`
where a status code is the contract (the `patient_segments` precedent):

- `list_leads(db, clinic_id, *, status=None, search=None, page=1, page_size=20, sort=None) -> tuple[list[Lead], int]`
  — always `.where(Lead.clinic_id == clinic_id)`; `status != "discarded"`
  is **not** the default (the page filters explicitly); `search` does a
  case-insensitive `ILIKE` over `full_name`, `phone`, `email`; sort goes
  through `app.core.list_query.apply_sort` with allow-list
  `{"created_at", "full_name", "status"}` and default `created_at:desc`.
- `get_lead(db, clinic_id, lead_id) -> Lead | None` — id **and** clinic_id
  in the same `WHERE`.
- `create_lead(db, clinic_id, data: dict) -> Lead` — the *only* place a lead
  row is inserted. Nothing may call it without going through `route()` first
  (§4.2.1).
- `update_lead(db, lead, data: dict) -> Lead` — callers pass
  `model_dump(exclude_unset=True)`.
- `convert(db, clinic_id, lead, patient_data: dict) -> tuple[Lead, Patient]`
  — calls `PatientService.create_patient(db, clinic_id, patient_data)`
  (it flushes and publishes `patient.created` with `db=db`, so
  timeline/notifications/webhooks fire exactly as a normal creation),
  then sets `lead.patient_id`, `lead.status = "converted"`,
  `lead.converted_at = datetime.now(UTC)`, flushes. **Never re-implement
  patient creation.** Raises `HTTPException(409)` if the lead is already
  converted.
- `count_today(db, clinic_id) -> int` — not needed as a separate method:
  `LeadSettingsService.get_or_create` already returns `day_count` for the
  gauge (§4.5).

`LeadSettingsService`:

- `get_or_create(db, clinic_id) -> LeadSettings` — lazy row with column
  defaults (`daily_cap=200`), the `RecallSettingsService.get_or_create`
  shape. Race-safe via `pg_insert(...).on_conflict_do_nothing()`, not
  select-then-insert.
- `update(db, clinic_id, data: dict) -> LeadSettings` — only `daily_cap`
  today; callers pass `model_dump(exclude_unset=True)`. **Never touch
  `day_count`/`day_count_date` here.**
- `consume_daily_quota(db, clinic_id) -> tuple[int, int]` — the upsert +
  atomic counter bump from §4.3, returning `(day_count, daily_cap)`. Keep it
  in this service (not in the router) so the public handler stays thin and
  the logic is unit-testable without HTTP.

#### 4.2.1 `LeadIntakeService.route` — the single entry point

```python
@dataclass
class IntakeOutcome:
    outcome: Literal["lead_created", "recall_queued"]
    lead: Lead | None = None
    recalled_patients: list[Patient] = field(default_factory=list)
```

```python
async def route(
    db, clinic_id, data: dict, *, recommended_by: UUID | None
) -> IntakeOutcome:
    """Route one enquiry: new person → lead, known patient → recall."""
    matched = await find_matching_patients(db, clinic_id, data["phone"], data.get("email"))
    if not matched:
        return IntakeOutcome("lead_created", lead=await LeadService.create_lead(db, clinic_id, data))
    recalled = await route_matched_enquiry(db, clinic_id, matched, data, recommended_by)
    return IntakeOutcome("recall_queued", recalled_patients=recalled)
```

Both the public handler and `POST /api/v1/leads/` call **this**, so the
routing rule cannot diverge between the form and the front desk. The
`recalled_patients` list is what the staff route turns into
`recalled_patient` (§3.3) and what the public route deliberately discards
(D12).

`matching.py`:

- `phone_key(raw: str) -> str` — digits only, trailing 9 (or fewer).
- `find_matching_patients(db, clinic_id, phone, email) -> list[Patient]` —
  the single query in §3.1; clinic-scoped, non-archived, phone-match first,
  `LIMIT 3`. Pure function + one query = unit-testable without HTTP.

`recall_routing.py`:

- `_compose_enquiry_note(data: dict) -> str` — motive / blank / description /
  blank / availability, verbatim, **no invented labels** (the note is data
  the staff reads, in the patient's own words).
- `route_matched_enquiry(db, clinic_id, patients, data, recommended_by)` —
  the loop from §3.2: `find_pending_for` → append-or-compose note →
  `RecallService.create(..., recommended_by=recommended_by)` →
  `needs_review` when `patient.do_not_contact`. Returns the recalls it
  touched. Imports `RecallService` from `app.modules.recalls.service`
  (legal: `recalls` is in `depends`).

`LeadIntakeKeyService`:

- `get_key(db, clinic_id) -> LeadIntakeKey | None`
- `rotate(db, clinic_id) -> tuple[LeadIntakeKey, str]` — plaintext is
  `"lk_" + secrets.token_urlsafe(32)`; stores
  `key_hash = hashlib.sha256(plaintext.encode()).hexdigest()` and
  `key_prefix = plaintext[:12]`; upserts the single row per clinic
  (insert when absent, update `key_hash`/`key_prefix`/`is_active=True`
  when present). Mirrors `integrations/service.py::_hash_token`.
- `resolve_clinic_id(db, plaintext: str) -> UUID | None` — look up by
  `key_hash`, require `is_active`, then `UPDATE … SET last_used_at = now()`.
  Return `None` for both "unknown" and "inactive" so the router cannot
  leak which one it was.
- `set_active(db, clinic_id, is_active: bool) -> LeadIntakeKey`

### 4.3 `public_router.py` — the intake endpoint

```python
public_router = APIRouter(prefix="/public")

@public_router.post("/intake", response_model=ApiResponse[LeadIntakeAck], status_code=201)
@limiter.limit("5/minute")
@limiter.limit("30/hour")
async def intake_lead(
    data: LeadIntakeCreate,
    request: Request,                      # slowapi needs it
    db: Annotated[AsyncSession, Depends(get_db)],
    x_lead_key: Annotated[str | None, Header(alias="X-Lead-Key")] = None,
) -> ApiResponse[LeadIntakeAck]:
    ...
```

Rules for this handler, **in this order** (cheapest rejection first):

1. Honeypot first: if `data.website` is non-empty, return
   `ApiResponse(data=LeadIntakeAck(received=True))` **without writing
   anything** — not even a recall. Bots must see success.
2. Body size: a dependency that rejects `Content-Length` (and a read cap,
   the `read_upload_limited` pattern at
   `patients/csv_import.py:62-67`) above `LEADS_INTAKE_MAX_BODY_KB` with
   `413`.
3. Missing key → `401`; `resolve_clinic_id` returns `None` → `401`
   (one generic detail, `"Invalid intake key"`, for unknown *and* inactive).
4. Captcha, only when `LEADS_CAPTCHA_PROVIDER` is set: verify
   `data.captcha_token` with a 5 s timeout; failure or provider error → `403`
   (fail-closed, logged). Inert otherwise.
5. Daily cap. Read the cap and bump the counter in **one** atomic statement
   against `leads_settings`, with a race-free upsert first (two concurrent
   intakes for a clinic whose settings row does not exist yet must not both
   try to insert it):

   ```python
   from sqlalchemy.dialects.postgresql import insert as pg_insert

   # 1. Ensure the row exists (no-op when it does). Defaults come from the
   #    column server_defaults.
   await db.execute(
       pg_insert(LeadSettings)
       .values(clinic_id=clinic_id)
       .on_conflict_do_nothing(index_elements=["clinic_id"])
   )

   # 2. Count this attempt and read the cap in the same statement.
   row = (
       await db.execute(
           update(LeadSettings)
           .where(LeadSettings.clinic_id == clinic_id)
           .values(
               day_count=case(
                   (LeadSettings.day_count_date == func.current_date(),
                    LeadSettings.day_count + 1),
                   else_=1,
               ),
               day_count_date=func.current_date(),
           )
           .returning(LeadSettings.day_count, LeadSettings.daily_cap)
       )
   ).one()

   day_count, daily_cap = row
   if daily_cap and day_count > daily_cap:
       raise HTTPException(
           status_code=429,
           detail="Daily intake limit reached for this clinic",
           headers={"Retry-After": "3600"},
       )
   ```

   Counting *before* the write is deliberate: blocked attempts stay visible
   in `day_count`, so the clinic sees how big the flood is rather than only
   that intake stopped. One statement, no read-then-write race, and it
   survives multi-worker restarts (which the in-process slowapi store does
   not). The cap itself is edited by the clinic on the settings page
   (D13) — lowering it below today's count blocks intake immediately, which
   is the intended emergency behaviour; say that in the settings page copy.
6. Route: `await LeadIntakeService.route(db, clinic_id, data, recommended_by=None)`,
   then **discard the outcome** and always answer
   `ApiResponse(data=LeadIntakeAck(received=True))` (D12). Let `get_db`
   commit.
7. Import `limiter` from `app.core.auth.router` (`from app.core.auth.router import limiter`).
   It is **disabled unless `ENVIRONMENT=production` and not `TESTING`**
   (`_limiter_enabled` at `app/core/auth/router.py:83`), so no test can
   assert a 429 — do not write one. Key it by key-hash *and* IP:

   ```python
   @limiter.limit("5/minute", key_func=_by_lead_key)   # sha256 of X-Lead-Key
   @limiter.limit("30/hour")                            # get_remote_address
   ```

   Never use the raw header as the bucket name — hash it (`_hash_token`
   precedent) so the secret is not sitting in limiter state.
8. No `get_clinic_context`, no `require_permission`, no clinic id in the
   path or body. The key is the only auth.
9. Do not log the plaintext key. Log `key_prefix` + `clinic_id` at most, and
   log the routing branch ("lead created" / "N patients recalled") — that is
   the audit trail a matched enquiry leaves in this module, since it writes
   no lead row.

**CORS note for the README/CLAUDE.md:** the intended integration is a
server-side POST from the clinic's website/host (WordPress handler,
Webflow form action, Zapier/n8n). A browser `fetch()` straight from the
clinic's site additionally needs that origin in `ALLOWED_ORIGINS`
(`backend/app/config.py:51`, comma-separated) — mention it in the docs, do
not change CORS code.

### 4.4 `schemas.py`

- `LeadStatus = Literal["new", "contacted", "converted", "discarded"]`
- `LeadCreate` — `full_name` (1..200), `phone` (1..32), `email: EmailStr | None`,
  `motive` (1..200), `description: str | None`, `availability: str | None`,
  `status: LeadStatus = "new"`; `field_validator` trims and rejects blank
  `full_name`/`phone`/`motive` (copy the `_strip_name` validator shape from
  `patient_segments/schemas.py`).
- `LeadUpdate` — every field optional (`PATCH` + `exclude_unset=true`).
- `LeadResponse` — all columns + `patient_id`, `converted_at`,
  `created_at`, `updated_at`, `model_config = ConfigDict(from_attributes=True)`.
- `LeadIntakeCreate` — `full_name`, `phone`, `email: EmailStr`, `motive`,
  `description: str | None = None`, `availability: str`,
  `website: str = ""` (honeypot; `max_length=200`),
  `captcha_token: str | None = None` (`max_length=4096`).
  Every string carries a `max_length` — that plus the body cap is the
  storage-abuse floor.
- `LeadIntakeAck` — `received: bool` (the only field ever returned publicly).
- `LeadSubmitOutcome = Literal["lead_created", "recall_queued"]`.
- `LeadSubmitResponse` — `{outcome: LeadSubmitOutcome, lead: LeadResponse | None,
  recalled_patient: PatientBrief | None}` — the staff-path union (§3.3).
- `LeadConvertRequest` — the patient payload the drawer submits:
  `first_name` (1..100), `last_name` (1..100), `phone: str | None`,
  `email: EmailStr | None`, `date_of_birth: date | None`,
  `national_id: str | None`, `notes: str | None`.
- `LeadConvertResponse` — `{lead: LeadResponse, patient: PatientBrief}`.
  Import `PatientBrief` from `app.modules.patients.schemas` (legal:
  `patients` is in `depends`).
- `LeadIntakeKeyStatus` — `{configured, key_prefix, is_active, last_used_at}`
  (never the key, never the hash).
- `LeadSettingsResponse` — `{daily_cap, day_count, day_count_date, intake_url,
  key: LeadIntakeKeyStatus}`; `intake_url` is the path
  `/api/v1/leads/public/intake` (the frontend prefixes its own origin — the
  backend does not guess hostnames). One GET feeds the whole settings page.
- `LeadSettingsUpdate` — `{daily_cap: int = Field(ge=0, le=5000)}`. The
  bound is the point: `0` means unlimited, but `10_000_000` does not, and a
  cap the clinic can defeat in one field is not a cap.
- `IntakeKeyRotated` — `{key: str, key_prefix: str}` (returned once).
- `IntakeKeyUpdate` — `{is_active: bool}`.

### 4.5 `router.py` (staff surface)

Copy the shape of `backend/app/modules/patient_segments/router.py`:
`Annotated[ClinicContext, Depends(get_clinic_context)]` +
`Annotated[None, Depends(require_permission("leads.read"))]` +
`Annotated[AsyncSession, Depends(get_db)]` on every route, `ApiResponse` /
`PaginatedApiResponse` wrappers, `status_code=201` on POST, `200` on
PATCH, and a private `_ensure_lead(db, clinic_id, lead_id)` helper that
raises 404.

The convert route:

```python
@router.post("/{lead_id}/convert", response_model=ApiResponse[LeadConvertResponse])
async def convert_lead(
    lead_id: UUID,
    data: LeadConvertRequest,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.write"))],
    __: Annotated[None, Depends(require_permission("patients.write"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadConvertResponse]:
```

Two permission dependencies are intentional: `leads.write` owns the
action, `patients.write` guarantees the caller may create a patient.
`patients` is in `depends`, so this is a legal cross-module reference.

The manual-create route carries the same idea for a different reason:

```python
@router.post("/", response_model=ApiResponse[LeadSubmitResponse], status_code=201)
async def submit_lead(
    data: LeadCreate,
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    _: Annotated[None, Depends(require_permission("leads.write"))],
    __: Annotated[None, Depends(require_permission("patients.read"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LeadSubmitResponse]:
    result = await LeadIntakeService.route(db, ctx.clinic_id, data.model_dump(), recommended_by=ctx.user_id)
    ...
```

`patients.read` is required because the `recall_queued` branch returns
`recalled_patient` — a matched patient's name (§3.3). **Principle worth
keeping in every future endpoint here: cross-module disclosure or write ⇒
that module's permission too.** `/convert` needs `patients.write` for the
write, `/` (POST) needs `patients.read` for the disclosure.

`recommended_by=ctx.user_id` is the one difference from the public path:
the recall records which staff member took the enquiry
(`ClinicContext.user_id`, `app/core/auth/dependencies.py:73`).

The settings surface (D13) — four routes, two permissions, no clinic
context mix-ups:

| Route | Permission | Handler shape |
|---|---|---|
| `GET /settings` | `leads.settings.read` | `LeadSettingsService.get_or_create(db, ctx.clinic_id)` + key status → `LeadSettingsResponse` |
| `PATCH /settings` | `leads.settings.write` | `LeadSettingsService.update(db, clinic_id, data.model_dump(exclude_unset=True))` |
| `POST /settings/intake-key/rotate` | `leads.settings.write` | `LeadIntakeKeyService.rotate` → plaintext once |
| `PATCH /settings/intake-key` | `leads.settings.write` | `LeadIntakeKeyService.set_active` |

`get_or_create` mirrors `RecallSettingsService.get_or_create` (lazy row, so
the page never 404s and no install-time hook is needed). The laziness applies
to the **settings row only**: a read must never mint an intake key (a key
appears only through `rotate`), and `GET /settings` must report
`key.configured = false` rather than creating one to fill the response.

Rotating must not touch `day_count` / `day_count_date`, and
`PATCH /settings` must not reset them either: the gauge is a fact about
today, not a property of the config. The only thing that resets the counter
is the date rolling over.

### 4.6 `tools.py`

Follow `docs/technical/creating-modules.md` §12 exactly: each tool wraps a
`LeadService` method (never duplicates logic), filters by `ctx.clinic_id`,
returns native values (UUID/datetime — no `str()`/`.isoformat()`), and
carries the same permission string as the HTTP route.

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_leads` | `READ` | `LeadService.list_leads` | `leads.read` |
| `get_lead` | `READ` | `LeadService.get_lead` | `leads.read` |
| `create_lead` | `WRITE` | **`LeadIntakeService.route`** | `leads.write` |
| `update_lead` | `WRITE` | `LeadService.update_lead` | `leads.write` |
| `convert_lead_to_patient` | `WRITE` | `LeadService.convert` | `leads.write` |
| `update_intake_settings` | `WRITE` | `LeadSettingsService.update` | `leads.settings.write` |

**Never expose key rotation or the key toggle as a tool.** An LLM that
decides to "fix intake" by rotating the intake key silently breaks the
clinic's website form until a human updates it — an irreversible
side effect on an external system with no undo. If a tool is ever needed
for the kill switch, it belongs in `DESTRUCTIVE`, but the right answer here
is not to expose it at all. Say this explicitly in the module `CLAUDE.md`,
because "expose every service method" is the general rule and this is a
deliberate exception.

Note `create_lead`: the tool must route, not insert blindly, or the copilot
would create the duplicate lead a human is not allowed to create. Its result
is therefore the `IntakeOutcome` union (`lead_created` / `recall_queued`) —
describe the recall branch in the tool's docstring so the agent tells the
user "they're already a patient, I've queued a call-back" instead of
"created" (a wrong answer here is a lie about the clinic's data).

Keep the PII keys redactor-friendly (`full_name`, `phone`, `email` — all in
the redactor's known-key set), so they tokenize before any cloud LLM
call. Set `exposes_free_text=True` on any tool whose result is prose
(none of the five is, as long as they return Pydantic models).

### 4.7 The three registrations outside the module

1. **`backend/pyproject.toml`** → append to
   `[project.entry-points."dentalpin.modules"]`:
   `leads = "app.modules.leads:LeadsModule"`.
   `test_entry_point_parity.py` fails without it.
2. **`backend/alembic.ini`** → append
   `:app/modules/leads/migrations/versions` to the single-line
   `version_locations` (line 11). **Mandatory**: the Alembic CLI resolves
   the revision graph from that static list, and
   `test_every_module_migrations_dir_is_registered_in_alembic_ini` fails
   the manifest gate without it. Skip it and the uninstall round-trip
   fails with "tables missing after upgrade heads".
3. **`frontend/modules.json`** → regenerate (see §5.1).

### 4.8 Migration `leads_0001_initial.py`

```python
revision: str = "leads_0001"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = ("leads",)
depends_on: str | Sequence[str] | None = ("pat_0003",)
```

`depends_on=("pat_0003",)` pins the patients chain before the `patients.id`
FK is created — same reasoning as `pseg_0001`
(`patient_segments/migrations/versions/pseg_0001_initial.py`). Generate
with autogenerate, then hand-check:

```bash
cd backend && alembic revision --autogenerate \
  -m "initial leads schema" \
  --version-path app/modules/leads/migrations/versions \
  --branch-label leads --head 0001
```

`upgrade()` creates **three** tables + indexes + constraints; `downgrade()`
drops them in reverse order (`leads_settings`, `leads_intake_keys`,
`leads`). Follow the `pseg_0001` file as the template for
column/index/constraint syntax.

Three things to hand-check after autogenerate:

1. `leads_settings` exists with `clinic_id` as the **primary key** (not a
   surrogate id), `daily_cap` (`Integer`, `server_default="200"`,
   `nullable=False`), `day_count` (`Integer`, `server_default="0"`,
   `nullable=False`), `day_count_date` (`Date`, nullable) and `updated_at`.
   Autogenerate gets these only if the model declares the server defaults.
2. `leads_intake_keys` has **no** counter columns — they live on
   `leads_settings` (§4.3). If autogenerate leaves them here, the cap check
   reads a row that does not exist and every intake 500s.
3. **No FK to `recalls`.** The recall is written at runtime through the
   recalls module's own tables; `leads` stores nothing about it, so
   `depends_on` stays pinned to the patients chain only. Adding a
   `recall_id` column "to link them" would (a) create an FK the module never
   reads, and (b) break the dedupe model in §3.2, which is keyed on
   `(patient, reason)` inside the recalls module.

---

## 5. Frontend layer — files to create

```
backend/app/modules/leads/frontend/
├── nuxt.config.ts                            # components path + 10-locale i18n block
├── plugins/settings.client.ts                # registerSettingsPage (D13)
├── composables/useLeads.ts                   # leads CRUD + convert
├── composables/useLeadsSettings.ts           # settings page state
├── pages/leads/index.vue                     # the /leads page
├── components/leads/LeadConvertDrawer.vue
├── components/leads/LeadEditModal.vue        # manual create + edit
├── components/settings/LeadsIntakeSettingsPage.vue   # Settings → Integrations → Formulario web
└── i18n/locales/{en,es,fr,de,pt,it,pl,hu,ta,ar}.json
```

### 5.1 `nuxt.config.ts`

Copy `recalls/frontend/nuxt.config.ts` (it ships components **and** i18n):

```ts
export default defineNuxtConfig({
  components: [{ path: './components', pathPrefix: false }],
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' }, { code: 'es', file: 'es.json' },
      { code: 'fr', file: 'fr.json' }, { code: 'de', file: 'de.json' },
      { code: 'pt', file: 'pt.json' }, { code: 'it', file: 'it.json' },
      { code: 'pl', file: 'pl.json' }, { code: 'hu', file: 'hu.json' },
      { code: 'ta', file: 'ta.json' }, { code: 'ar', file: 'ar.json' }
    ],
    langDir: 'locales'
  }
})
```

Ten locale files with **identical key sets** — `frontend/tests/i18n/locale-parity.test.ts`
fails on any missing or orphan key, and on placeholder drift vs `en.json`.
Non-English files may fall back to the English string for a first pass,
but every key must exist in every file.

Then regenerate the layer registry (CI diffs it):

```bash
cd frontend && node scripts/modules-json.mjs ../backend/app/modules --prefix /module_layers
```

`/api/v1/modules/-/active` only lists a module whose layer is in
`modules.json`, so a skipped regeneration makes `/leads` unreachable in
Docker builds.

### 5.2 `composables/useLeads.ts`

Mirror `staff_tasks/frontend/composables/useStaffTasks.ts`: exported
types (`LeadStatus`, `Lead`, `LeadCreatePayload`, `LeadUpdatePayload`,
`LeadConvertPayload`) and a `useLeads()` factory over `useApi()`.

```ts
list(filters)      → api.get('/api/v1/leads/?…')            // PaginatedResponse<Lead>
get(id)            → api.get(`/api/v1/leads/${id}`)
create(payload)    → api.post('/api/v1/leads/', payload)     // LeadSubmitResponse union
update(id, patch)  → api.patch(`/api/v1/leads/${id}`, patch)
convert(id, body)  → api.post(`/api/v1/leads/${id}/convert`, body)
```

`useLeadsSettings.ts` (used only by the settings page, D13):

```ts
getSettings()          → api.get('/api/v1/leads/settings')
updateSettings({daily_cap}) → api.patch('/api/v1/leads/settings', …)
rotateIntakeKey()      → api.post('/api/v1/leads/settings/intake-key/rotate')
setIntakeKeyActive(active)  → api.patch('/api/v1/leads/settings/intake-key', { is_active: active })
```

Pass `{ errorToast: false }` on `create`/`update`/`convert` (the page
toasts its own message, as `useStaffTasks` does).

### 5.3 `/leads` page anatomy

Follow `lists-redesign.md`: `DataListLayout` (title + toolbar +
loading/empty/error + `PaginationBar`) + `FilterBar` with one
`FilterChipMulti` (status) + `SearchBar` (debounced, `search` param). Use
the host `useListQuery` composable for URL-synced filters/page/sort with
`defaults = { q: '', status: [], sort: 'created_at:desc' }`.

Status semantics, fixed here so the backend and the chip agree: **no
`status` query param means all four statuses**, ordered `created_at desc`.
With `FilterChipMulti` an empty selection *is* the "All" state, so it
simply omits the param — no sentinel needed. (The `'all'` sentinel value
shows up only if you use a single `USelect` instead, as
`staff_tasks/frontend/pages/tasks/index.vue` does, because `USelect` has no
empty option.) Do not make the backend exclude `discarded` by default —
"hidden rows with no filter visible" is exactly the confusion the leads
queue cannot afford.

Each row (`DataListItem` with `row` slot for md+, `card` slot for <md):

- `leading`: `UAvatar` with the lead's initials, tinted by status.
- `title`: `full_name` + `StatusBadge` (`new` → info, `contacted` →
  warning, `converted` → success, `discarded` → neutral).
- `subtitle`: `phone` · `motive` (truncated).
- `meta`: `availability` (md+ only) and a relative "received" date.
- `actions`: the arrow — `<UIcon name="i-lucide-chevron-right" aria-hidden="true" class="text-subtle" />`.
  Render it as a **plain icon, not a `UButton`**, and make the whole row
  the control (`ListRow :clickable="true"` → it already applies
  `role="button"`, `tabindex=0` and Enter/Space handling, and shows
  hover/focus rings). A nested button inside the row's `role="button"`
  would be an a11y violation.
- Clicking a row opens `LeadConvertDrawer` for that lead (`@click` → set
  `selected = lead; drawerOpen = true`).

Header actions (`#actions` slot):
- **Manual lead** (`UButton` icon `i-lucide-plus`, gated on
  `PERMISSIONS.leads.write`) → `LeadEditModal` in create mode.
- **Formulario web** (`UButton` variant outline, icon `i-lucide-globe`,
  gated on `PERMISSIONS.leads.settingsRead`) → **navigates** to
  `/settings/integrations/leads`. It is a link out, not a modal: the cap,
  the key and the volume gauge live on the settings page (§5.6), and having
  the key rotatable from two places is how two UIs drift.
- A `ModuleSlot` if you want extensibility (`leads.list.toolbar`) — only
  add a slot if a second module will actually fill it; otherwise skip it.

Empty state: `EmptyState` copy that also explains the routing rule, because
a clinic that just wired the form and sees an empty list will otherwise
think it is broken: "No new enquiries. Enquiries from people who are
already patients go straight to Recalls — check there before assuming the
form is not working." A link to `/recalls` in that sentence is worth more
than the paragraph.

**The page never shows matched enquiries** (D8) — it lists what is in
`leads`, and a matched enquiry writes no row there. Do not add a "matched"
tab, badge or counter to this page: the recall is the artefact, and
duplicating it in two places is how the two views start disagreeing.

Page spine (copy `staff_tasks/frontend/pages/tasks/index.vue`):

```vue
<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useLeads } from '../../composables/useLeads'

definePageMeta({ middleware: ['auth'] })

const { can } = usePermissions()
if (!can(PERMISSIONS.leads.read)) await navigateTo('/')
</script>
```

Imports inside the layer use **relative** paths for siblings and `~~/app/…`
for host code. Never `~/composables/…`: Vite rewrites `~` to the layer but
`vue-tsc` maps it to the host frontend root, so it type-checks against a
file that does not exist.

### 5.4 `LeadConvertDrawer.vue` — the right-side panel

```vue
<USlideover
  v-model:open="open"
  side="right"
  :title="t('leads.convert.title')"
  :ui="{ content: 'w-[560px] max-w-[95vw] bg-surface' }"
>
  <template #content> … </template>
</USlideover>
```

API confirmed against the only existing usage in the repo
(`frontend/app/components/HelpButton.vue:52-59`): `USlideover` takes
`v-model:open` / `:open`, `side="right"`, `:title`, `:ui="{ content }"`,
and slots `#content` (there is no `#body` slot in this version).

Drawer contents, top to bottom:

1. **Lead context panel** (read-only, muted): motive, description,
   availability, phone, email, received date. This is why the drawer
   exists — the receptionist fills the patient form while seeing what the
   lead asked for.
2. **Duplicate warning** (rendered only when it applies): on open, call
   `GET /api/v1/patients?search=<phone>&page_size=5` and compare
   normalised phones (strip spaces/dashes). On a hit show a `UAlert`
   ("A patient with this phone already exists") with a link to
   `/patients/<id>`. Do not block conversion — two patients with one
   phone number is legal (families share a phone).
3. **Patient form** — exactly the fields of the creation modal in
   `patients/frontend/pages/patients/index.vue`: `first_name`*,
   `last_name`*, `phone`, `email`, `national_id`, `date_of_birth`,
   `notes`. Same labels via the host `patients.*` i18n keys where they
   already exist.

Pre-fill map (autofill is the point of the feature):

| Lead | Patient field | Rule |
|---|---|---|
| `full_name` | `first_name`, `last_name` | split at the **first** whitespace: first token → `first_name`, remainder → `last_name`; a single-token name puts everything in `first_name` and leaves `last_name` empty (the form requires it, so the user completes it) |
| `phone` | `phone` | verbatim |
| `email` | `email` | verbatim |
| `motive` + `description` + `availability` | `notes` | one composed block: motive label + value, blank line, description, availability label + value — editable before saving. Build the two labels with `t('leads.notes.motive')` / `t('leads.notes.availability')` (never hardcode "Motivo:"/"Disponibilidad:" in code) |
| — | `national_id`, `date_of_birth` | empty |

Document the split heuristic in the module `CLAUDE.md` "Gotchas" — it is
the one piece of guessing in the flow, and the form lets staff correct it
before anything is written.

4. **Footer**: Cancel + *Crear paciente* (`:loading`, disabled until
   `first_name` and `last_name` are non-empty). On success: toast, refresh
   the list, and show the success state inside the drawer with an "Open
   patient" link to `/patients/<id>` (do not navigate away automatically —
   the next lead is usually one click behind).
5. **Already-converted branch**: when `lead.status === 'converted'`,
   replace sections 2–4 with a banner + *Open patient* link, and keep the
   context panel. Never re-convert (the backend answers 409 anyway).

### 5.5 `LeadEditModal.vue` — manual create / edit

`UModal` + `UCard`, like the create modal in
`patients/frontend/pages/patients/index.vue`. Fields: `full_name`*,
`phone`*, `email`, `motive`*, `description` (textarea), `availability`,
and — edit mode only — a `USelect` for `status`
(`new | contacted | converted | discarded`). *Marking a lead `converted`
by hand is allowed but does **not** create a patient* — say that in the
module docs so nobody expects it.

**The create path is not a plain save** (§3.3). `POST /leads/` returns
`lead_created` or `recall_queued`, and the modal must branch:

- `lead_created` → close, toast "lead added", refresh the list.
- `recall_queued` → close, and toast a *different* message naming the
  matched patient, with an action link to `/recalls`: "Marta Ruiz is
  already a patient — a call-back was added to Recalls." The list will
  **not** contain the enquiry; if the modal said "saved" here, the front
  desk would file a card that does not exist.

Do not show the `status` select in create mode (`status` starts `new`; a
brand-new enquiry is not yet `contacted`).

`LeadEditModal` is also where the front desk marks a lead as `contacted`
or `discarded` after calling.

### 5.6 `LeadsIntakeSettingsPage.vue` — the module settings page (Settings → Integrations)

This is where the daily cap lives (D13), together with the intake key it
protects. Register it the way `whatsapp_webhook` does — the closest
precedent (per-clinic secret + an Integrations settings page):

```ts
// plugins/settings.client.ts
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'leads',
    category: 'integrations',
    labelKey: 'leads.settings.title',
    descriptionKey: 'leads.settings.description',
    icon: 'i-lucide-inbox',
    permission: 'leads.settings.read',
    component: () => import('../components/settings/LeadsIntakeSettingsPage.vue'),
    searchKeywords: ['leads', 'contactos', 'formulario', 'web', 'website', 'intake', 'limite', 'cap'],
    order: 52
  })
})
```

Route: **`/settings/integrations/leads`** (the host's dynamic
`/settings/[category]/[page].vue` mounts it). `order: 52` follows
`whatsapp_kapso`/`whatsapp_webhook` (51) in the Integrations group.

The page (a normal component, no `definePageMeta` — the host owns the
route) contains, in reading order:

1. **Cap** — `UFormField` + `UInput type="number"` bound to `daily_cap`,
   hint: "Maximum enquiries accepted per day. 0 = no limit." Save button
   calls `PATCH /settings`, disabled without `leads.settings.write` (render
   the value read-only in that case rather than hiding the field — the cap
   is the number behind the behaviour staff are seeing). Client-side clamp
   to `0..5000` to match the server's `Field(ge=0, le=5000)`; let the server
   be the authority and toast its 422. Today only `admin` holds either
   `settings.*` permission, so the read-only branch is latent — keep it
   anyway, since the RBAC map is slated to become a DB-driven
   custom-roles-per-clinic store (`core/auth/permissions.py`).
2. **Today's gauge** — "37 of 200 today" from `day_count` / `daily_cap`,
   switching to a `UAlert` warning at the cap ("intake is paused until
   tomorrow"). When `daily_cap === 0`, show the count with no denominator.
   One line must say what lowering the cap below today's count does
   (blocks immediately) — that is the emergency lever, and it should not be
   discovered by accident.
3. **Intake key** — `configured`, `key_prefix`, `is_active`, `last_used_at`;
   **Generate / rotate** (plaintext shown **once** in a callout, kept only
   in local state); **active toggle**; and one sentence of operational copy
   next to rotate: *"Rotating stops a leaked key immediately. Remember to
   paste the new key into your website — the form will fail until you do."*
   That second sentence is the whole reason rotation is gated on
   `leads.settings.write` (admin-level) rather than `leads.write`.
4. **Intake URL** — `intake_url` copyable (`UInput readonly` + copy button).
5. **Integration example** — the `curl` and a server-side snippet (the
   deliverable the clinic's web developer actually needs). Include the
   routing note from §3.1: *"Enquiries whose phone or email already belongs
   to a patient don't create a lead — they are added to Recalls for a
   call-back."* Mention the captcha field only if `LEADS_CAPTCHA_PROVIDER`
   is configured.
6. **Empty state** (no key yet): intake is closed until a key exists; the
   cap field still works, because the settings row is created on read
   (§4.5).

Render the whole page behind `leads.settings.read` (the registry already
filters the card by permission; still guard the component so a direct URL
does not render an empty shell for a role that lacks it).

### 5.7 i18n keys (module namespace `leads.*`)

Under one top-level `"leads"` object, at minimum:

```
leads.nav.leads
leads.title  leads.subtitle  leads.empty  leads.emptyHint
leads.searchPlaceholder  leads.filterStatus  leads.status.{new,contacted,converted,discarded}
leads.receivedAt  leads.availability  leads.motive  leads.description
leads.open  leads.newLead  leads.websiteForm
leads.fields.{fullName,phone,email,motive,description,availability,status}
leads.actions.{edit,save,cancel,discard,markContacted}
leads.convert.{title,subtitle,createPatient,created,openPatient,alreadyConverted,duplicateWarning,duplicateOpen}
leads.notes.{motive,availability}          # labels used when pre-filling patient notes
leads.routing.{explainer,recallQueued,openRecalls,emptyHint}
leads.settings.{title,description,capLabel,capHint,capSave,capSaved,volume,unlimited,atLimit,capLoweredWarning,keyTitle,keyConfigured,keyMissing,keyPrefix,keyActive,keyInactive,lastUsed,rotate,rotateWarning,rotateCopyOnce,copied,intakeUrl,example,captchaNote}
leads.errors.{load,save,convert,settingsLoad,settingsSave}
```

`leads.settings.title` / `leads.settings.description` are the card labels
the settings registry renders — they are required, not optional, or the
card shows a raw key on `/settings/integrations`.

Reuse host keys for generic chrome (`common.save`, `common.cancel`,
`common.error`, `common.success`) — do not invent module duplicates.

### 5.8 `frontend/app/config/permissions.ts`

Add next to the other module entries:

```ts
leads: {
  read: 'leads.read',
  write: 'leads.write',
  settingsRead: 'leads.settings.read',
  settingsWrite: 'leads.settings.write'
},
```

---

## 6. Tests

### 6.1 Backend — `backend/tests/modules/leads/`

`__init__.py`, `test_leads.py`, `test_routing.py`, `test_intake.py`,
`test_settings.py`, `test_uninstall_roundtrip.py`. The routing tests are the
ones worth writing first — they encode D8/D9, the requirement most likely to
regress.

`test_leads.py` (fixtures: `client`, `auth_headers`, `db_session`,
`test_clinic`, `test_patient` from `tests/conftest.py`):

- CRUD round-trip through HTTP against a **phone/email that matches nobody**:
  create → assert `outcome == "lead_created"` → list (assert it appears) →
  PATCH status → GET detail.
- Multi-tenancy: a lead created in clinic A is invisible to a user of
  clinic B (create a second clinic like
  `tests/modules/patient_segments/test_patient_segments.py` does, and
  assert `404` on the cross-clinic id, not just an empty list). Repeat the
  assertion for `/convert`.
- Convert: returns `200`, the patient exists in `patients` with the
  posted fields, the lead is `converted` with `patient_id` set and
  `converted_at` non-null; a second convert returns `409`.
- Convert permission: a user without `patients.write` gets `403` (use a
  role/token that holds only `leads.write`).
- `PATCH` with an empty body must not wipe fields (`exclude_unset`).
- Status filter and `search` (by phone and by name).

`test_routing.py` — the matching + recall contract (§3.1, §3.2). Use
`db_session` + the services directly for the matrix, plus one HTTP case per
branch:

- **New person** → `leads` row created, `recalls` untouched.
- **Phone match** (`+34 600 111 222` vs a patient stored as `600111222`) →
  no `leads` row, one `Recall` for that patient with `priority == "high"`,
  `reason == "other"`, `status == "pending"`, `due_month`/`due_date` today,
  and the enquiry text in `reason_note`.
- **Email match** (different phone) → same recall outcome. Confirms `OR`,
  not `AND`.
- **Both match, different patients** (shared family phone) → one recall per
  matched patient, capped at 3.
- **`do_not_contact` patient** → recall created with
  `status == "needs_review"` (and therefore absent from the default call
  list, which filters opted-out patients — assert that too).
- **Archived patient only** → treated as no match: a lead row **is**
  created.
- **Repeat match** → still exactly one recall for `(patient, "other")`
  (the `find_pending_for` dedupe), and the note has the new block appended,
  not replaced; a third submission whose note would exceed the cap leaves
  the note unchanged.
- **Staff pre-existing `other` recall** for that patient → the enquiry note
  is appended to it rather than overwriting the staff's text.
- **Public response is identical** in the matched and unmatched cases
  (byte-compare the two response bodies) — the D12 anti-enumeration rule.
- **Staff outcome union**: `POST /leads/` with a matching phone returns
  `outcome == "recall_queued"`, `lead is None`, `recalled_patient` present;
  without `patients.read` the same call is `403`.

`test_intake.py` (service + HTTP):

- Valid key → `201`, row created with the right clinic, key
  `last_used_at` and `day_count` touched.
- Missing header → `401`; unknown key → `401`; inactive key → `401`
  (identical response, no distinguishing detail).
- Honeypot filled → `201` and **no row** — assert no lead *and* no recall.
- Validation failure (missing `motive`) → `422`.
- Oversized body → `413`.
- Response body contains only `{"data": {"received": true}}` — assert no
  lead id, no clinic id, no patient name leaks.
- Two clinics, two keys: each enquiry lands in the right clinic — including
  the match case (a patient in clinic A must never be recalled by clinic
  B's key: seed the same phone in both clinics and assert B gets a lead).
- Daily cap: `PATCH /settings {"daily_cap": 2}`, exhaust it, assert `429` +
  `Retry-After`, and that `day_count` kept counting past the cap. **The
  slowapi 429 itself is untestable** (limiter is disabled outside
  production) — do not write that test; the cap is the testable ceiling.
- Captcha: with `LEADS_CAPTCHA_PROVIDER` set and the provider call
  monkeypatched to fail → `403`; unset → the field is ignored and the same
  request succeeds.

`test_settings.py` (D13):

- `GET /settings` on a clinic with no row → `200`, `daily_cap == 200`
  (server default), `key.configured is False`, and the row now exists
  (lazy create) — while **no intake key row** is created.
- `PATCH /settings {"daily_cap": 0}` → unlimited: the cap check never
  trips. `{"daily_cap": 5001}` → `422`. `{"daily_cap": -1}` → `422`.
- Permission split: a receptionist-shaped token gets `403` on `GET
  /settings`, `PATCH /settings` and the key routes (admin-only), while
  `leads.read` still works. This is the test that keeps the secret out of
  front-desk hands.
- `POST /settings/intake-key/rotate` twice → two different `key_prefix`
  values, the first key stops working (`401`), `day_count` is **unchanged**
  across the rotation.
- `PATCH /settings/intake-key {"is_active": false}` → intake `401`.
- Cross-tenant: clinic B's settings/`day_count` are untouched by clinic A's
  `PATCH`.
- Tool surface: assert the copilot tool registry exposes no intake-key or
  rotation tool for this module (the deliberate exception in §4.6) — a
  one-line guard that fails the moment someone "completes" the tool set.

`test_uninstall_roundtrip.py`: copy
`backend/tests/modules/patient_segments/test_uninstall_roundtrip.py`
verbatim, with `LEAD_TABLES = {"leads", "leads_intake_keys",
"leads_settings"}` and the downgrade target `leads@-1`. Mark it
`pytest.mark.alembic_roundtrip`. Assert explicitly that `recalls`,
`recall_contact_attempts` and `recall_settings` survive the downgrade — this
module depends on the recalls branch and must never take it down with it.

### 6.2 Frontend

- Optional vitest for the pure helpers if you extract any (e.g. the
  name-split + notes-composition functions into
  `backend/app/modules/leads/frontend/utils/leadAutofill.ts` — recommended
  precisely so they can be unit-tested without mounting a component, and
  so the drawer stays thin). A vitest file under `frontend/tests/` imports
  it through the `module_layers` symlink, same as the existing
  `frontend/tests/india_gst/*` tests.
- No new e2e spec is required by CI. If you add one, add
  `leads` to the "Install optional modules covered by e2e" step in
  `.github/workflows/ci.yml` — an `auto_install=False` module is absent
  from a fresh boot, so a spec that assumes `/leads` exists will fail
  without it.

---

## 7. Documentation (CI-enforced)

| File | Why |
|---|---|
| `backend/app/modules/leads/CLAUDE.md` | `test_module_docs.py` requires ≥ 12 non-blank lines; use `docs/checklists/module-claude-template.md` (purpose, public API, dependencies, permissions, tools table, lifecycle, gotchas, ADRs, changelog) |
| `backend/app/modules/leads/CHANGELOG.md` | `test_module_docs.py` requires ≥ 5 non-blank lines; start with `## Unreleased` |
| `docs/technical/leads/overview.md` | required by `check_docs_coverage.py --strict` for every discovered module |
| `docs/technical/leads/permissions.md` | required because the module returns permissions; one row per endpoint under its gating permission, including the four `settings.*` routes |
| `docs/user-manual/en/leads/index.md` + `docs/user-manual/es/leads/index.md` | module landing page in both locales |
| `docs/user-manual/en/leads/screens/leads.md` + `docs/user-manual/es/leads/screens/leads.md` | required per Nuxt page — `route: /leads` in frontmatter must match the page, or the strict check errors |
| `docs/user-manual/en/leads/screens/intake-settings.md` + ES twin | the settings page, following `docs/user-manual/en/whatsapp_kapso/screens/connect.md`: frontmatter `route: /settings/integrations/leads`. The strict checker only *warns* when a `route` matches no module page (`check_docs_coverage` fails on errors only), so this is convention-compliant and CI-safe |
| `docs/glossary.md` | append the ES↔EN term: **Lead / Contacto entrante** (or *Solicitud de cita*, matching whatever the UI says). Also the routing vocabulary: *matched enquiry → recall* |
| `docs/modules-catalog.md` | regenerated, not hand-edited |

Content the module docs must carry (beyond the template's sections):

- `backend/app/modules/leads/CLAUDE.md`: the routing rule in two sentences,
  `depends = ["patients", "recalls"]` **and why** (a matched enquiry writes
  a recall), the note-append/dedupe behaviour, the
  `recall.created` → `recall_reminders` side effect, the `do_not_contact` →
  `needs_review` rule, the phone heuristic, the "leads cannot be installed
  without recalls" consequence, and the two configuration surfaces: the cap
  is a `leads_settings` column edited at Settings → Integrations, and
  `settings.write` is admin-only on purpose.
- `docs/technical/leads/overview.md`: §3.1 decision tree (a fenced block —
  it is the fastest way to explain this module to a human), a short
  "Abuse controls" subsection with the honest limits from §3.4 (spoofable
  `X-Forwarded-For`, per-process slowapi, the DB cap as the real ceiling),
  and where the cap is configured (UI, not env).
- `docs/user-manual/{en,es}/leads/index.md`: state plainly that enquiries
  from existing patients appear in **Recalls**, not in Leads. This is the
  sentence staff will otherwise file a bug about. Point at Settings →
  Integrations → *Formulario web* for the daily limit and the key.
- `docs/user-manual/{en,es}/leads/screens/leads.md`: the card/arrow/drawer
  flow, the convert autofill behaviour, the manual create outcome union.
- `docs/user-manual/{en,es}/leads/screens/intake-settings.md`: the cap
  (including what `0` means and what lowering it below today's count does),
  the volume gauge, and rotate-vs-disable with the "update your website
  first" warning.

`docs/technical/leads/events.md` is **not** needed while D7 holds — the
checker only demands it when events flow either way. Worth a one-line note
in `overview.md` regardless: this module publishes nothing of its own, but
the recall it creates publishes `recall.created` through the recalls
module.

Screen-doc frontmatter (the contract in `documentation-portal.md` §2,
verified against `docs/user-manual/en/contacts/screens/list.md`):

```yaml
---
module: leads
screen: leads
route: /leads
related_endpoints:
  - GET /api/v1/leads/
  - POST /api/v1/leads/
  - PATCH /api/v1/leads/{lead_id}
  - POST /api/v1/leads/{lead_id}/convert
  - POST /api/v1/leads/public/intake
related_permissions:
  - leads.read
  - leads.write
related_paths:
  - backend/app/modules/leads/router.py
  - backend/app/modules/leads/frontend/pages/leads/index.vue
last_verified_commit: <sha>
---
```

`last_verified_commit` must be a real commit sha (the check only warns when
it is empty, but the repo convention is a real one — use `git rev-parse --short HEAD`).
`screenshots:` and the `![...]` image line are **optional**: include them
only if you actually commit a PNG under `docs/screenshots/leads/`, because
a markdown link to a missing image is a portal-build hazard. EN and ES file
sets must match exactly (same slugs) or `test_module_docs.py` fails.

Regenerate the catalogs last:

```bash
cd backend && python scripts/generate_catalogs.py
```

---

## 8. Green path — run in this order

```bash
# 1. backend static
cd backend && ruff check . && ruff format .        # then: ruff format --check .

# 2. docs + catalog gates (fast, catches layout/coverage mistakes early)
python scripts/generate_catalogs.py
python scripts/check_docs_coverage.py --strict
python scripts/check_docs_layout.py

# 3. layer registry (must be committed; CI diffs it)
cd ../frontend && node scripts/modules-json.mjs ../backend/app/modules --prefix /module_layers

# 4. tests (needs the db; use docker compose exec backend … if the stack is up)
cd ../backend && python -m pytest -v
python -m pytest -m alembic_roundtrip tests/modules/leads -v
alembic upgrade heads && alembic downgrade leads@-1 && alembic upgrade heads

# 5. frontend
cd ../frontend && npm run lint
npm run test                    # locale parity + unit tests
npm run typecheck:layers        # stop the dev frontend container first; modules.json is auto-restored
git checkout -- modules.json    # typecheck:layers rewrites it
```

Note: `frontend/node_modules` is empty in this workspace — run
`npm ci --no-audit --no-fund` in `frontend/` before the frontend steps.

---

## 9. End-to-end verification (do this before calling it done)

```bash
# 1. install the module (auto_install=False). recalls is a declared dependency,
#    so it must already be installed — `modules install leads` resolves the
#    chain transitively if it is not.
docker compose exec -T backend python -m app.cli modules install leads
docker compose restart backend

# 2. mint an intake key (staff JWT required; grab a session cookie from the app)
curl -s -X POST http://localhost:8000/api/v1/leads/settings/intake-key/rotate \
  -H "Authorization: Bearer <staff-jwt>" | jq .
# → { "data": { "key": "lk_…", "key_prefix": "lk_…" } }

# 3. post an enquiry from someone who is NOT a patient yet → it becomes a lead
curl -s -X POST http://localhost:8000/api/v1/leads/public/intake \
  -H "Content-Type: application/json" \
  -H "X-Lead-Key: lk_…" \
  -d '{"full_name":"Marta Ruiz","phone":"+34 600 111 222",
       "email":"marta@example.com","motive":"Ortodoncia",
       "description":"Instagram","availability":"Tardes"}' | jq .
# → { "data": { "received": true } }

# 4. same body, but with the phone of a patient the demo clinic already has
#    (find one: SELECT phone FROM patients LIMIT 1)
#    → same 201 body, and a recall appears instead of a lead
curl -s -X POST http://localhost:8000/api/v1/leads/public/intake \
  -H "Content-Type: application/json" -H "X-Lead-Key: lk_…" \
  -d '{"full_name":"Cualquiera","phone":"<existing patient phone>",
       "email":"x@example.com","motive":"Presupuesto","availability":"Mañanas"}' | jq .

# 5. wrong key must be a bare 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  http://localhost:8000/api/v1/leads/public/intake \
  -H "Content-Type: application/json" -H "X-Lead-Key: lk_nope" \
  -d '{"full_name":"x","phone":"1","email":"a@b.co","motive":"m","availability":"a"}'
# → 401

# 6. the cap: open Settings → Integrations → Formulario web (D13), set the
#    daily limit to 2, save, then send a third enquiry → 429, and the page's
#    gauge shows "3 of 2 today". Log in as a receptionist-shaped user and
#    confirm the page/card is not reachable (settings.* is admin-only).
```

Then in the UI, in this order:

1. Log in as `admin@demo.clinic`, open **Leads** (Practice section).
2. The step-3 enquiry is a card; click the arrow → the drawer opens with the
   name split into first/last and notes pre-filled from
   motive/description/availability → *Crear paciente* → the drawer shows
   *Open patient* and the row flips to `converted`.
3. **The step-4 enquiry is not on this page.** Open **Recalls**: that patient
   has a `high`-priority recall due today with the enquiry text in its note
   (`other` reason). This is the D8 behaviour end to end — if the recall is
   missing, the routing never ran.
4. Manual create with an existing patient's phone → the modal says
   "already a patient — added to Recalls", and no card appears.
5. Re-post the step-4 body twice more → still exactly one recall, note
   appended once (not two duplicates).
6. Open **Settings → Integrations → Formulario web**: the cap field, today's
   gauge, the intake URL, rotate and the active toggle. Change the cap there
   and confirm the change takes effect on the next intake without a restart
   — that is D13's whole point.

---

## 10. Gotchas — the traps that will bite

1. **`alembic.ini` registration is mandatory** (§4.7.2): append
   `:app/modules/leads/migrations/versions` to the existing
   `version_locations` line — not a new key, not a whole new line.
2. **`branch_labels = ("leads",)` on the first revision only**; later
   revisions use `None`. An isolated branch is what makes
   `removable=True` legal and the uninstall round-trip pass.
3. **`redirect_slashes=False`**: pin the collection routes to `/` and call
   `/api/v1/leads/` from the layer. A mismatch is a silent 404.
4. **Never touch `ctx.clinic_id`-less queries**; every staff query filters
   by clinic, including inside `tools.py`, the settings row and the
   intake-key lookups.
5. **The intake endpoint is the one route with no clinic context.** Do not
   add `get_clinic_context` "for consistency" — it would require a JWT the
   website does not have.
6. **slowapi is disabled outside production** (`ENVIRONMENT=production`
   and not `TESTING`), so rate limits are untestable here; do not assert
   a 429 (and do not remove the decorators — they are the production
   guard).
7. **Rotate returns the plaintext exactly once.** Never store it, never
   return it from `GET /settings`, never log it.
8. **Layer i18n needs ten files with identical keys** — parity is a
   vitest guard, not a convention.
9. **`modules.json` must be regenerated** after the layer exists, or the
   module will be baked but never mounted in Docker builds.
10. **Do not `import ~/composables/...`** inside the layer: use relative
    paths for siblings, `~~/app/...` for host code, or `typecheck:layers`
    fails.
11. **Reuse `PatientService.create_patient`** for conversion. Hand-writing
    the insert would skip `patient.created` and break the timeline,
    notifications, and `integrations` webhooks.
12. **Two permission dependencies on `/convert`** (`leads.write` +
    `patients.write`) — dropping one lets a `leads.write`-only role create
    patients.
13. **The name split is a heuristic.** Make `last_name` editable in the
    drawer and keep the copy in the module CLAUDE.md honest about it.
14. **Demo mode**: no module endpoint uses `block_in_demo` today, so do not
    add it here. But do not mint an intake key on the public demo instance
    in the e2e/pilot steps.
15. **One insert path for leads, ever** (D8). `LeadService.create_lead` is
    called only from `LeadIntakeService.route`. Any second caller — a new
    endpoint, the copilot tool, a seed script — silently re-creates exactly
    the duplicate lead this module exists to prevent.
16. **Never hand-write the `Recall` insert.** `RecallService.create` carries
    the `(patient, reason)` dedupe *and* publishes `recall.created`; a raw
    `Recall(...)` would stack duplicate call-backs and drop the activity
    journal entry. If you need something `create` does not do, change
    `create` (and its CHANGELOG), don't route around it.
17. **`do_not_contact` matches must be `needs_review`.** The calls call list
    filters opted-out patients out (`recalls/service.py:112-113`), so a
    `pending` recall for one is invisible — the enquiry would vanish. The
    gateway's hard block (`notifications/gateway.py:92-102`) is what keeps
    the opt-out safe on the outbound side.
18. **Phones are compared by trailing 9 digits, never by equality.** That is
    what makes `+34 600 111 222` match `600111222`. Implement it once in
    `matching.py::phone_key` and use that function in the query builder and
    in the tests — a second copy of the rule is how matching drifts.
19. **No `recall_id` on `leads`.** The recall is the recalls module's row;
    the link is `(clinic_id, patient_id, reason)`, and the dedupe lives
    there. Adding an FK buys nothing and couples the two branches.
20. **`depends` includes `recalls` — that is a real install constraint.**
    Leads cannot be installed without recalls, and the uninstall order is
    leads first. Do not "soften" it to an optional import: a matched enquiry
    with recalls uninstalled has nowhere to go, and the module's core rule
    would silently degrade to "create a duplicate lead".
21. **The intake response never varies by branch** (D12). No different
    status, body, wording or obvious timing between "new lead", "recall
    queued" and "matched an opted-out patient" — otherwise the endpoint
    becomes an unauthenticated oracle for "is this phone your patient?".
22. **Do not add a `rate_limit` directive to `Caddyfile`**, and do not treat
    IP limits as the security boundary: `--forwarded-allow-ips=*`
    (`docker-compose.yml:50`) lets a client set its own
    `X-Forwarded-For`. The per-key limit and the DB daily cap are the real
    bounds.
23. **The note append is bounded, and never destructive.** Substring-check
    before appending, cap the total, and never overwrite an existing
    `reason_note` — a staff member's own `other` recall can be sitting on
    that row.
24. **The daily cap counts before it writes.** Do not "fix" it to count only
    successful inserts: blocked attempts must keep counting so the clinic can
    see the size of a flood, not just that intake stopped.
25. **The cap is per-clinic data, never an env var** (D13). There is no
    `LEADS_INTAKE_DAILY_CAP`. Adding one back — even as a "default" — creates
    two sources of truth and guarantees a support call where the UI says 200
    and the process says 50. The column default *is* the default.
26. **`leads_settings` is created with `INSERT … ON CONFLICT DO NOTHING`, not
    select-then-insert.** Two concurrent intakes on a clinic whose settings
    row does not exist yet is a real race (the row is lazy), and the loser
    would 500 on a unique violation.
27. **Never reset `day_count` from the settings page, rotation, or a toggle.**
    Rotating the key stops a flood; wiping the counter would hand the
    attacker a fresh 200 for the day and hide the evidence. Only the date
    rolling over resets it.
28. **Do not expose intake-key rotation or the toggle as an agent tool**
    (§4.6). It is the one deliberate exception to "expose every mutating
    service method": an LLM rotating the key breaks the clinic's website with
    no undo, and the clinic would not know why the form went quiet.
29. **`settings.write` stays admin-only.** It is the key's permission as much
    as the cap's. If the front desk needs to *see* the URL during setup, read
    `leads.settings.read` — do not hand out write to make a demo easier.

---

## 11. Out of scope (explicitly deferred)

- Per-source intake keys / "which form did this come from" attribution
  (single key per clinic is deliberate for v1).
- Notification or staff-task creation when a lead arrives.
- Publishing `lead.created` / `lead.converted` on the event bus.
- Linking a lead to an **existing** patient (`POST /convert` with
  `existing_patient_id` instead of a patient body) — the duplicate warning
  in the drawer is the v1 answer.
- Agenda shortcut ("book an appointment for this lead") — belongs to the
  agenda module.
- Lead scoring, funnel analytics, UTM capture, spam heuristics beyond the
  honeypot.
- Hard deletion of leads: `discarded` is the only removal path.
- Per-clinic *captcha* configuration on the settings page. Captcha stays an
  operator-level env switch: it needs external credentials, and a clinic
  without a Turnstile/hCaptcha account should not see a field it cannot
  fill. Revisit if more than one clinic asks.
- Alerting when intake hits the cap (email/notification to the admin). The
  settings page shows the gauge; pushing it is a notifications-module job.
- A dedicated `lead_callback` reason in the `recalls` enum. It would filter
  better than `reason = "other"`, but it means editing another module's
  `REASONS`, its `reason_intervals` defaults, its reason picker and ten
  locale files — a change that should come with its own PR and CHANGELOG
  entry, not as a side effect of this one.
- Suppressing or rewriting the patient-facing `recall_reminder` that
  `recall_reminders` queues when the recall is created (§3.2). The honest
  workarounds today: don't install `recall_reminders`, or adjust the
  notification template/preferences.
- An audit trail for matched enquiries (a `leads` row with
  `status="matched"` behind an explicit flag). Deliberately not in v1 —
  D8 says the recall *is* the record; this is the additive way in if lead
  analytics ever need the matched volume by source.
- De-duplicating *leads* by phone within a time window. A person who
  double-submits gets two cards today; the daily cap and the recall dedupe
  bound the damage, and suppressing repeats risks dropping a second
  family member's genuine enquiry.
- Hard-blocking `/convert` when the submitted phone already exists (family
  phones make it a false positive; the drawer warns and lets a human decide).
- Parsing `availability` into bookable slots. It is free text by decision
  (D3); any slot suggestion belongs to the agenda module.
