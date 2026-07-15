# Changelog — periodontogram module

## Unreleased

- i18n: add French locale (`fr.json`) with full UI coverage.

- fix(frontend): call `api.del` instead of the non-existent `api.delete`
  when discarding a draft (audit frontend #1, #95). `useApi` exposes
  `del`, so `discardDraft` threw a TypeError before any request fired —
  and the one-draft-per-patient unique index then blocked starting any
  new session for that patient.

- feat(ui): dark mode support across the whole periodontogram surface.
  SEPA profile strip, tooth silhouettes, implant fixture, site
  markers, arch tables, indices banner, history banner and empty
  state now read from CSS tokens (`--perio-*`, `--odontogram-*`) or
  use `dark:` Tailwind variants — no hardcoded hex / `rgb()` colours
  left in templates or scoped styles.
- refactor(indices): denominator anchored to `6 × present teeth` so
  half-finished exams no longer report inflated BoP/PI percentages;
  unmeasured sites count as "no finding" instead of dropping out of
  the bucket. Frontend live computation in `PeriodontogramChart`
  mirrors the backend formula exactly.
- feat(ui): session actions (Cerrar sesión / Descartar borrador)
  inlined into `PerioIndicesBanner` and the standalone
  `PerioSessionActions.vue` component removed. Keeps the
  periodontogram aligned with the rest of the patient file's "main
  actions live up top" convention.
- fix(ui): pastel site-marker palette — probing-depth tones now use
  soft fills + accent ring + dark readable text (emerald / amber /
  orange / rose), matching the calm-design tonal scale used on status
  badges elsewhere. Replaces the saturated 500/600 fills that were
  dominating the SEPA chart visually.
- fix(ui): SEPA chart visual alignment — common tooth view widened
  (VIEW_H 130 → 150) so every tooth's crown bottom now fits inside the
  cell without cropping in either vestibular or palatal/lingual rows,
  effectively shrinking the rendered tooth by ~13 % to match the
  4 px/mm scale of the profile strip. Red gum-line curve removed from
  the tooth silhouettes; the strip's CEJ gridline now doubles as the
  gum line. Site markers on inner rows (palatal upper, vestibular
  lower) render above the tooth instead of below, so both markers
  bands cluster between the two tooth rows and the arch block reads
  symmetrically around the SEPA midline. Strip overlay offsets
  recomputed for the new gum cellY (perio-profile-anchor--top 24→17,
  --bottom 28→61).
- feat(indices): `close_snapshot` now computes the SEPA bundle
  (BoP %, PI %, mean CAL, deep-pocket count) over the snapshot's
  sites, persists it on the row as JSONB, and publishes the new
  `periodontogram.snapshot.closed` event for downstream subscribers.
  A new `GET /snapshots/{id}/indices` endpoint serves the frozen
  bundle on closed snapshots and a live-computed bundle on drafts.
- feat(coupling): draft creation reads tooth state from the
  `odontogram` module via `OdontogramService` — missing teeth come
  out as `is_present=False` and performed implants flip
  `is_implant=True` on the seeded perio rows. Read-only; no FK.
- feat(lifecycle): full draft→closed snapshot service +
  `/api/v1/periodontogram/` router. Idempotent draft creation
  pre-seeds 32 permanent teeth, PATCH endpoints support partial
  payloads with closed-state 409 guards, timeline lists closed
  snapshots with site-completeness `change_count`.
- feat(skeleton): initial module skeleton — manifest, models
  (`PeriodontogramSnapshot`, `PeriodontogramTooth`, `PeriodontogramSite`),
  Alembic branch `periodontogram` with `perio_0001_initial`. Empty
  router; service/indices stubs. Optional + removable (`installable=True`,
  `auto_install=False`, `removable=True`). Branch-scoped uninstall test
  added under `backend/tests/test_uninstall_roundtrip.py`.
