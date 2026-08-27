# Changelog — odontogram module

## Unreleased

- fix(#101): treatment delete asks for confirmation (names the treatment and tooth); the edit modal stays open with the user's edits when a save fails, and surface edits are actually included in the update payload (they were silently dropped).

- feat: global treatments from unmapped catalog items are creatable —
  `TreatmentService._resolve_clinical_type` falls back to the
  server-internal type `"other"` for `global_mouth`/`global_arch` scopes
  when the catalog item has no odontogram mapping (mirrors the
  `"migrated"` precedent; still rejected as explicit API input; tooth
  scopes still require a mapping or explicit type). `TreatmentBar`'s
  "Boca completa" tab now groups items by clinical category with
  localized subheaders, shows prices in tooltips, and adds a name filter
  when the list exceeds 12 items; neutral `other` icon added.
- fix: `DiagnosesCard` translates clinical types via the real i18n
  namespace `odontogram.treatments.types` (it pointed at a
  `treatmentTypes` namespace that never existed, so every label fell
  back to the humanized raw key — "filling composite", "other").

- fix(#184): the layer type-checks clean under `nuxt typecheck`. Real bugs behind the errors: treatment colour dots read `TREATMENT_COLORS` (a `{light,dark}` config) as a hex string — they now go through `getTreatmentColor()`; the toast undo action used the v3 `click` key (v4: `onClick`), `UPopover :ui.width` is `content`; `TreatmentBar` emitted a possibly-undefined fallback status; touch drags on the timeline guard an empty `touches` list. Tooth-position lookups are typed by `ToothPosition` (1–8) instead of `|| MAP[1]` fallbacks.
- fix(#183): `TreatmentService.perform` publishes with `db=` so the payments earned ledger and the plan-item completion run in its transaction (ADR 0019).
- feat(events): `TreatmentService.perform` accepts `publish_price=False`
  to emit `odontogram.treatment.performed` with `unit_price: null` —
  the caller declares the revenue already attributed elsewhere
  (treatment_plan per-session billing). Default behaviour unchanged.

- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- fix(frontend): render an error state with retry when the odontogram
  fetch fails, instead of falling through to a fabricated all-healthy
  32-tooth chart (audit S5, #95). Adds `odontogram.messages.loadError`.

- feat(ux): ``DiagnosisMode`` now publishes a ``treatmentsToothById`` map
  and an ``onTeethHover`` callback through the
  ``odontogram.diagnosis.sidebar`` slot ctx, so the clinical-notes
  sidebar can pulse the matching tooth on the chart when the user
  hovers/focuses a note. Reuses the existing ``hoveredTeeth`` →
  ``highlightedTeethProp`` plumbing on ``OdontogramChart``.
- feat(treatments): add ``crown_on_implant`` and
  ``provisional_crown_on_implant`` clinical types. Both render on the
  lateral view as a solid prosthetic fill on the crown path (same code
  path as ``bridge``) — the diagonal-stripes pattern used by regular
  ``crown`` looked too sparse / artificial for implant-supported
  restorations. The two new types appear in ``TreatmentPicker`` under
  the Restauradora category, and count as ``hasReplacementTreatment``
  so the underlying ``missing`` / ``extraction`` state stops fading
  the tooth.
- fix(ToothDualView): when a tooth carrying ``missing`` /
  ``extraction_indicated`` / ``extraction`` state receives a
  prosthetic replacement (implant, bridge, crown, pontic,
  bridge_abutment, overlay, inlay, unerupted), render the tooth at
  full opacity — the restoration supersedes the extracted state.
  Also suppress the dashed/solid X overlays (occlusal + lateral) on
  those teeth, so the X no longer paints over the implant/crown.
  Previously, SVG-level opacity (and the wrapper ``.transparent``
  0.4 dim) faded both the natural anatomy and every overlay, so a
  newly placed implant on an extracted tooth rendered almost
  invisible. Opacity now applies only to natural-anatomy paths and
  only when no replacement is present.
- fix(DiagnosisMode): hide treatments whose
  ``source_module === 'migration_import'`` from the Diagnóstico panel.
  Migrated patients arrived with their entire chart history (often
  decades of crowns, fillings and extractions) flooding the active
  diagnosis workflow. The artefacts remain visible on the odontogram
  via ``ToothRecord.general_condition``, and the historical record
  stays in the History tab + the auto-generated treatment plans.
- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast in ``useTreatments`` now that ``useApi`` accepts ``object`` payloads.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- Issue #60: `DiagnosisMode.vue` exposes a right-rail
  `odontogram.diagnosis.sidebar` slot (with mobile slideover) and
  `ConditionsList.vue` exposes a per-treatment
  `odontogram.condition.actions` slot. The clinical_notes module fills
  both — odontogram itself does not depend on it.

## 0.3.0 — initial documented version

- Per-tooth state with surface granularity, JSONB-backed.
- Tooth treatment workflow with `added` / `status_changed` /
  `performed` / `deleted` events.
- Drives budget + treatment_plan sync via `odontogram.treatment.performed`.
