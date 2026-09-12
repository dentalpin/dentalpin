# Booking UX build-similar — design record (Stream 3, design-first)

> Local-only design. No code copied from any Group D repo (most are
> unlicensed; MIT ones usable only with notice — see `../technical/external-repos-sweep.md`).
> Everything below is reimplemented ideas mapped onto existing DentalPin
> modules. Requires maintainer product decision before code.

## Patterns mined (ideas only)

1. **Public slot grid** (Denpointment/Nacre-style): week view of bookable
   chairs, hold-and-confirm (10-min hold token) → confirm via link.
2. **Reminder cascade** (dentrx-style): T-48h + T-2h nudges through the
   existing notifications gateway (no new vendor).
3. **Front-desk triage queue**: unconfirmed online requests land in a manual
   review list (mirrors the approval pattern in `app/core/agents`).

## Mapping onto our modules (no new module)

- Slot grid + hold tokens → `agenda` (new endpoints, own migration branch).
- Reminder cascade → `recall_reminders` + `notifications` events (no new tables).
- Triage queue → `agenda` status extension (`pending_online`).
- Permissions: `agenda.appointments.write` reuse; public grid is
  unauthenticated-by-design like the budget public link (signed token, TTL).

## Non-goals

No patient portal accounts, no online payments for booking, no vendor
datepicker components copied in.

## Ship shape (later)

Tight `agenda`/`recalls` gap-close PR on its own branch, en/es screen
docs, e2e smoke on the hold→confirm flow.

## Code mining result (2026-09-03) — no code gap, S3 stays design-only

Mined `acevedo-daniel/dms-demo` (MIT) at code level: overlap exclusion
(GiST), transition map, confirm button, status badge. Verdict per pattern:

- Overlap guard: **ours is stronger** — partial unique slot index
  (`ag_0004`, active-status-only) + app-level detection + IntegrityError→409.
  Replacing it with GiST EXCLUDE is migration risk for zero user-visible gain.
- Status machine: ours has `transition` + VALID_TRANSITIONS + agent
  self-correction; theirs is a static map. Covered.
- Confirm button / status badge: trivial PATCH-status components; our agent
  tools + slots cover the flows. Nothing to port.
- Only unbuilt piece is the **public hold-and-confirm link** (signed token +
  TTL, budget public-link precedent) — a product decision, not a mining
  task. S3 ships if/when the maintainer wants online booking.
