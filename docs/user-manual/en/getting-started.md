# Getting started: first-run setup and the "Getting started" card

This guide covers what happens the first time you open a fresh DentalPin installation and how the dashboard helps you finish configuring the clinic without external support.

## 1. First-run setup (`/setup`)

The first visit to a fresh installation opens the setup wizard. It takes about two minutes.

1. **Administrator account** — your name, email and a password (8+ characters with letters and numbers). This is the clinic administrator. The **"I attend patients myself"** switch (on by default) marks you as a bookable professional — leave it on if you work alone, turn it off if you only manage the clinic.
2. **Clinic** — clinic name, **country** and tax id. The country sets timezone, currency and VAT for you (you can still change them under *Timezone and currency*). For Spain the wizard checks the NIF/CIF format and warns if the checksum looks wrong. The optional **Clinic address** block (street, postal code, city) fills in the address printed on budgets and invoices — filling it here checks off the *Clinic details* step right away.

Press **Create my clinic**. DentalPin creates for you:

- the treatment catalog and VAT types (Spain: exempt / 10 % / 21 %; other countries: a single exempt rate you can edit),
- an invoice series (`FAC`) and a credit-note series (`RECT`),
- one room ("Room 1"),
- a Monday–Friday schedule (Spain: 09–14 and 16–20; elsewhere 09–18).

Everything can be changed later under *Settings*.

> Use the language selector at the top of the wizard to switch the interface language at any time. Until you touch it, the wizard follows the language of the country you pick — selecting Spain switches to Spanish automatically.

## 2. The "Getting started" card

After logging in, administrators see a **Getting started** card at the top of the dashboard with a progress bar and the steps left:

| Step | What it means | Where it takes you |
|---|---|---|
| Clinic details | Name, tax id and street address printed on budgets and invoices | *Settings → General → Clinic* |
| Rooms | At least one room so the agenda can book appointments | Inline dialog |
| Clinic hours | Your real opening hours (a fresh install may still be "open 24/7") | Inline dialog with presets |
| Your team | Add the professionals who see patients, or flag yourself as professional if you work alone | Inline dialog |
| Treatment catalog | Treatments to budget, plan and bill | Inline dialog: **Load default catalog** (VAT, categories and reference treatments for your country) or *I will create my own* → *Settings → Clinical → Catalog* |
| Invoice series | Needed to issue the first invoice | *Settings → Billing → Invoice series* |
| Optional: VeriFactu (Spain), Email sending, First patient | Suggested next steps | Modules / Notifications / Patients |

- **Set up** opens the step (an inline dialog when available, otherwise the settings page).
- **Skip** (eye icon) hides a step you don't need; **Undo** brings it back.
- **Hide** removes the card for the whole clinic; steps still resolve themselves as data appears.
- When the last required step is done the card collapses to a one-line "all set" state with a **Close** button (the optional steps stay reachable until you close it).

Steps are checked against real data: if you delete your last room, the step reappears.

## 3. Guided mode

**Guided mode** walks you through the pending steps one page at a time. A bar under the header shows *Step N of M* — counting only the steps left, so with four of six already done it reads *Step 1 of 2* — with **Next** (re-checks and jumps to the next pending step) and **Exit**. On the last step, **Finish** returns to the dashboard.

Two steps open ready to act: *Clinic details* lands directly on the edit form, and *Your team* shows an **"I attend patients myself"** switch above the user list if you are not marked as a professional yet — flip it and the step resolves without creating a second user.

## 4. Adding colleagues without email

In *Your team* (or *Settings → People → Users*), create the user and **leave the password empty**. DentalPin shows a one-time **access link** you can **copy** or **send via WhatsApp**. Your colleague opens it, chooses a password and is signed in. The link works once and expires after seven days.

The link icon on any user row generates a new access link — useful when someone forgot their password.

> Treat the link like a password: anyone who has it can sign in to that account until it is used.
