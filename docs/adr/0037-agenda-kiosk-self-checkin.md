# 0037 — Agenda kiosk self check-in: identification and the confirm-before-submit rule

- **Status:** proposed
- **Date:** 2026-09-26
- **Deciders:** maintainers (@martinezsalmeron)
- **Tags:** agenda, security, tokens, kiosk

## Context

Issue #464 added QR check-in where staff mint a 15-minute token per
appointment and show the code to the patient. It works, but reception has
to open each appointment and press a button, so the value of self
check-in is lost whenever nobody is at the desk. Issue #480 asks for a
kiosk: a fixed QR on the counter, or a tablet at the entrance, that a
patient uses alone.

The hard part is identification. A per-appointment token *is* the
identification, but a fixed clinic QR is not, so the patient has to tell us
who they are on a public endpoint without that endpoint becoming an oracle
for "who has an appointment today". #480 sets the non-negotiables: tenant
binding from the signed token rather than user input, a response to a
failed identification indistinguishable from "no appointment today", a
clinic-local day window, revocability without a redeploy, and per-IP plus
per-token rate limits.

One property of the existing code decides the shape of this ADR. The
public page from #464 checks in on load:
`agenda/frontend/pages/p/check-in/[token].vue` runs
`onMounted(async () => { ... method: 'POST' ... state.value = 'done' })`.
That is correct for a code scanned at a counter and wrong for a link
inside a reminder, because corporate mail security (Microsoft Defender Safe
Links, Proofpoint URL Defense, Mimecast) follows links at delivery time and
the sandboxing variants render them in a real browser, so they run that
`onMounted`. Messenger link previews fetch URLs too. A patient on
Microsoft 365 would be checked in when the reminder *arrives*, putting a
phantom `checked_in` on the reception kanban hours before they arrive.

## Decision

We adopt option B first (a personal link in the reminder), keep the
staff-minted per-appointment QR, and defer presence proof and tablet entry
to a later phase. Identification option A (date of birth plus phone digits)
is **not** shipped on the open web: it is roughly 28 bits of entropy on two
nullable `Patient` fields, so it is brute-forceable without draconian limits
*and* unusable for part of the population, which would need a fallback path
anyway. Scoped to an enrolled kiosk tablet it becomes acceptable, so A is
kept as the fallback for patients whose reminder never arrives.

Because the pre-fetch hazard is real, **GET and page load never change
state; a deliberate user action does.** We express that with a `source`
claim minted into the check-in token, so the page branches instead of
guessing:

| `source` | Page behaviour | Why |
|---|---|---|
| `counter` | auto-submits on load | a human scanned it in the clinic, presence is proven |
| `reminder` | renders "I'm here", POSTs on press | a scanner pre-fetch only loads an inert page |
| `kiosk` | renders the identifier form, no transition | a clinic-scoped row, not an appointment |
| `absent` | renders "I'm here", POSTs on press | legacy or incomplete tokens must fail safe, so missing `source` cannot auto-submit |

The invariant is therefore **only a token explicitly carrying `source: counter` auto-submits**. A token with no `source` is treated as `reminder`, so the safe behaviour is the default rather than the permissive one.

The token is the existing signed JWT. `agenda/checkin.py` already mints a
`payload` carrying `exp`, `appointment_id`, `clinic_id` and
`type: "checkin"`, and `verify_checkin_token` already rejects on
`payload.get("type") != "checkin"`, so a `source` key is one extra entry on
an existing dict plus a branch in the existing verifier. No new crypto, no
new configuration, and no change to `manifest.depends`.

## Consequences

### Good

- A mailed link cannot check a patient in, because opening it does
  nothing. This also removes a class of support report that would have been
  very hard to diagnose from the kanban.
- The same public page serves both flows, so there is one check-in surface
  with one rule rather than two pages with two behaviours.
- The `start_time` window lands as a side effect and closes the missing
  date guard noted on #464. With a tap step, "too early, your appointment is
  at 16:30" becomes a message on the page instead of a silent 422.
- Chords and the cheatsheet are unaffected; this only governs the public
  surface.

### Bad

- A patient can check in from home. We bound it with same-day validity plus
  a pre-start window, so the worst case is someone checking in from the
  car park, which reception already handles by calling names.
- One extra claim in the token, so the reminder and counter tokens become
  distinguishable. A token minted before this ships has no `source` and is
  therefore treated as `reminder`. The only tokens in flight are 15-minute
  counter QRs, so the worst case is one manual tap; a future mint path or
  refactor that drops the claim degrades to manual confirmation rather than
  auto-submit.
- Nothing here proves presence. That is option C, deliberately deferred; it
  bolts onto B without changing the token model.

### Neutral

- Reminders reach patients through the event bus or a slot, never by
  importing `notifications`, so the module boundary is unchanged.
- Check-ins continue to move through the canonical status machine with
  `changed_by=NULL` and `note="kiosk-checkin"`, distinct from `qr-checkin`,
  so kanban, timeline and events behave as they do today.
- Phase 2 is an entrance presence code and enrolled tablets. Tablets must
  never display names or lists on a shared screen.

## Non-goals

No patient portal or accounts, no payments, forms or consent signing at
the kiosk, and no geofencing.

## Open follow-ups

- The clinic-scoped kiosk row is revocable by an admin without a redeploy,
  which means a database row rather than a bare JWT, matching the fixed-QR
  pattern. Its issuance and revocation endpoints are part of phase 1.
- `docs/technical/country-readiness.md` and the module docs are updated by
  the implementation PR, not by this ADR.

## References

- Issue #480, and #464 for the existing QR check-in it builds on.
- `backend/app/modules/agenda/frontend/pages/p/check-in/[token].vue` (the
  auto-submit on load that motivates the `source` claim)
- `backend/app/modules/agenda/checkin.py` (`mint_checkin_token`,
  `verify_checkin_token`)
- `backend/app/modules/billing/hooks.py` (the
  `BillingComplianceHook` / `BillingHookRegistry` seam this module pattern
  follows)
- `backend/app/modules/agenda/service.py` (`public_checkin`, the
  `transition(..., note=...)` call that stays authoritative)
