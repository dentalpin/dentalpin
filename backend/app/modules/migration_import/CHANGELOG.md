# migration_import — changelog

## Unreleased

- i18n: add French locale (`fr.json`) with full UI coverage.

- fix(entity_mappings): widen ``source_canonical_uuid`` from
  ``VARCHAR(36)`` to ``VARCHAR(64)`` (alembic ``mig_0004``). The
  ``appointment_note`` sidecar registers a derived canonical of shape
  ``<uuid>:note`` (~41 chars), which silently overflowed the column
  and aborted every appointment savepoint with
  ``StringDataRightTruncationError`` — turning the entire
  ``appointment`` entity into ``mapper.failed`` warnings (0 of N
  appointments persisted). The widened column leaves room for future
  ``<uuid>:<short_suffix>`` sidecars without another migration.
- feat(recall): new ``RecallMapper`` hydrates Gesdén ``Recalls`` →
  ``recalls.Recall``. Status derived from ``attended`` /
  ``status_code`` / ``scheduled`` / ``contact_date``
  (done / contacted_scheduled / contacted_no_answer / pending).
  ``due_month`` bucketed from ``scheduled_date``; free-text
  ``Comentario`` + ``Observaciones`` land in ``reason_note``.
  Without a master decoder for ``IdMotivo`` the reason falls back to
  ``other`` — the note preserves clinical context. Idempotent via
  the resolver.
- feat(appointment): free-text ``appointment.notes`` in the DPMF
  payload is now routed to a polymorphic ``ClinicalNote`` row
  (``owner_type='appointment'``,
  ``note_type='appointment_administrative'``) instead of the legacy
  ``appointments.notes`` column dropped in ``ag_0005``. Default
  bucket is *administrative* (Gesdén notes typically carry reception
  memos). Idempotent under the synthetic ``appointment_note`` entity
  type so re-runs do not duplicate. ``author_id`` prefers the
  resolved professional; falls back to the import actor (``ctx.created_by``).
- feat(patient): mapper now also hydrates ``phone``, ``email`` and
  ``address`` (JSONB ``{street, postal_code}``) from the DPMF. Patient-level
  fields (dental-bridge ``0.0.3``+ adds them under ``Pacientes.*``) win
  over the client-level fallback. Mobile beats landline; phone is
  defensively truncated to the ``varchar(20)`` column width. ``AceptaSMS``
  set to false also flips ``do_not_contact`` on so SMS-only opt-outs
  propagate. Pre-0.0.3 DPMFs still import — they just leave the new
  columns null because the exporter didn't carry them.
- feat(patient): mapper now hydrates email, billing_name, billing_tax_id,
  do_not_contact and status from the DPMF rather than dropping them.
  Email + legal name + NIF come from the default Gesdén client
  (``Pacientes.IdCliDefec`` → ``IdCliPac`` → ``IdCli`` → ``IdCliTutor``,
  first match wins). Lazy one-pass scan over
  ``ctx.handle.entity_iter('client')`` per job (cache keyed on
  ``job_id``). ``billing_*`` only populated when the client's NIF
  differs from the patient's (third-party/company payer). GDPR/LOPD
  drives ``do_not_contact`` (false consent → opt-out). ``Inactivo`` /
  ``Exitus`` collapse to ``status='archived'`` with a note explaining
  which. ``registered_at`` (FecAlta) is appended to notes. Phone +
  address still missing because dental-bridge v0.0.2 does not export
  Gesdén's ``Telef``/``Movil``/``Domicilio`` — upstream limitation.
- feat(applied_treatment): non-clinical TtosMed rows land as
  ``ClinicalNote(administrative, owner=patient)`` instead of synthetic
  ``Treatment(scope='global_mouth', clinical_type='migrated')`` +
  ``PlannedTreatmentItem``. Two source signals route to the new path:
  ``IdTipoOdg`` in the non-clinical taxonomy (Anotación, Nota
  Económica, Higiene, Panorámica…) **and** ``IdTto`` null (the
  receptionist typed free text without selecting a catalog variant).
  Field impact on a 500-patient subset: ~4 k "migrated" tiles
  disappear from the odontogram BOCA COMPLETA strip and the per-year
  catch-all plan; the same text shows up in the patient Summary feed
  as an administrative note (preserves authorship via
  ``professional_uuid`` when resolvable). ``DebtMapper`` detects the
  reroute via a new ``MappingResolver.mapping_table()`` helper and
  skips the ``PatientEarnedEntry`` when the linked applied_treatment
  resolves to a ClinicalNote (warning code ``debt.no_clinical_target``).
- feat(professional): operator-tunable filtering at execute time.
  Adds four knobs to ``ExecuteRequest`` — ``professional_min_activity_months``
  (default 24), ``professional_exclude_agenda_orphans`` (on),
  ``professional_exclude_inactive_in_source`` (on),
  ``professional_exclude_non_clinical_roles`` (off). Rows that match any
  enabled signal are still imported as Users (so historical FKs from
  appointments / treatments / budgets / payments keep resolving) but
  with ``is_active=False`` and ``ClinicMembership.role='assistant'`` so
  the agenda filters them out. Each filtered row also emits an
  ``info`` ``ImportWarning`` with the trigger reason. Real-world impact
  on a representative Gesdén export: 100 imported staff (60 clinical +
  40 auxiliary) collapses to ~22 active clinicians — close to the
  clinic's actual 10-doctor headcount. Operators can review and
  reactivate individual users from Settings → Users after import.
- feat(preview): the entity preview now carries a
  ``professional_breakdown`` block when the file declares
  ``professional`` rows (deactivated / agenda-orphan / stale-24m /
  no-activity counts plus a per-role tally). Drives the new wizard
  filter panel so operators see how many staff each signal would
  catch before they execute.
- chore(schema): ``migration_import_jobs`` gains a JSONB
  ``execute_options`` column (alembic ``mig_0003``) so future
  operator opt-ins can be added without per-knob migrations.
- fix(fiscal_document): resolve patient via ``client_to_patients`` map
  instead of demanding ``patient_uuid`` on the payload. Gesdén's
  ``DocAdmin`` is keyed on the **client** (payer) — a single invoice
  can cover several family patients — so the canonical layer correctly
  emits ``client_uuid`` only. Mapping path: 1 patient → use it,
  N patients (family billing) → use the first and emit
  ``fiscal_document.family_billing`` warning. End-to-end validated on
  a real 500-patient Gesdén export: invoices imported climbed from
  7 → 554 (547 had been failing as ``mapper.failed``).
- feat(catalog_item): new generic dispatcher mapper. Handles
  ``catalog_item`` (DPMF) → DentalPin. Today only ``kind=chair``
  produces real rows: Gesdén ``TBoxes`` entries land as
  :class:`agenda.Cabinet` so imported appointments resolve a real
  ``cabinet_id`` instead of always landing on the DentalPin demo
  cabinets. Other kinds (country, province, payment_method, …)
  archive to :class:`RawEntity` for forward-compat. The
  ``AppointmentMapper`` now resolves ``chair_uuid`` through the new
  mapper's resolver (was a TODO).
- feat(catalog): bidirectional subset-token rule inside the category
  filter. When the mapper has a confirmed category (from
  ``IdTipoODG``) and one seed candidate's tokens are a strict subset
  of the source tokens (or vice versa), accept the link even below
  the 0.7 threshold — but only when a single candidate wins. Catches
  the common Gesdén pattern where the label appends a detail token
  ("OBTURACION COMPOSITE PERMANENTE" vs ``Obturación composite``) or
  drops one ("RECONSTRUCCION ESTETICA" vs ``Reconstrucción estética
  con composite``). Validated on a real 189-row Gesdén ``Tratamientos``
  export: auto-link rate climbed from ~13 % → ~20 % without
  introducing new false positives beyond what operator review
  surfaces.
- feat(catalog): smarter Gesdén catalog mapper. The IdTipoODG signal
  (46-value ``TTipoOdg`` master) now drives a per-category fuzzy
  search instead of a flat global one, with a looser 0.7 threshold
  inside the right bucket and the existing 0.8 elsewhere. A curated
  abbreviation alias map (``OBTUR``→``obturacion``, ``MC``→``metal
  ceramica``, ``IMPL TI``→``implante titanio``, …) expands the
  Gesdén short labels before scoring so they reach the seed entries
  they obviously match. When no match exists, the new item lands in
  the inferred category (instead of always ``Importado de Gesdén``)
  with inferred ``treatment_scope``, ``requires_surfaces`` and
  ``odontogram_treatment_type`` — so migrated rows now paint on the
  odontogram. All Gesdén-specific tables live in the new
  ``mappers/_gesden_catalog.py`` module to keep the global catalog
  schema untouched.
- feat(proposals): new ``MappingDecision`` entity + four endpoints —
  ``POST /jobs/{id}/proposals`` builds the per-row mapping proposals
  in a dry-run pass, ``GET`` lists them paginated, ``PATCH``
  ``/jobs/{id}/proposals/{canonical_uuid}`` records an operator
  override (accept / relink / create-new / ignore), and ``POST
  /jobs/{id}/proposals/bulk_accept`` accepts every high-confidence
  match (default ≥ 0.9). Execute consults the table first and falls
  back to the automatic matcher when no decision exists
  (backward-compatible). Migration ``mig_0002`` adds the table on the
  module's branch; uninstall round-trip drops it.
- feat(applied_treatment): shared the 46-value ``IdTipoODG`` →
  ``TreatmentType`` lookup with the catalog mapper via
  ``mappers/_gesden_catalog`` so both stay in sync. Removes the
  partial 14-entry duplicate that used to live inside
  ``applied_treatment.py``.
- fix(catalog): match Gesdén ``Tratamientos`` against the DentalPin
  seed even when the source label uses abbreviations/dots
  ("OBTUR. COMP.", "ENDODONCIA UNI."). The previous matcher required a
  lower-cased exact hit on ``names->>'es'`` so practically every
  source row fell into "Importado de Gesdén" and the odontogram +
  plan view ended up showing "migrated" instead of the real
  treatment name. The new matcher normalises both sides (accent
  strip, punctuation→whitespace, whitespace collapse), then falls
  back to a ``difflib`` similarity ratio ≥ 0.88 when the exact form
  misses. Single best match wins; ties or sub-threshold scores fall
  through to the create path. Fuzzy hits emit a
  ``catalog.fuzzy_matched`` info warning so ops can spot-check.
- feat(debt): new ``DebtMapper`` (``mappers/debt.py``) makes
  Gesdén's ``DeudaCli`` table the only source of truth for the
  patient ledger. One non-anulado / non-uncollectible debt row with
  ``Adeudo > 0`` produces one ``PatientEarnedEntry`` with
  ``amount = Adeudo``, idempotently keyed by a uuid5-derived
  ``source_session_id`` so multi-phase billings on the same
  treatment land cleanly. ``AppliedTreatmentMapper`` no longer
  writes earned entries from ``TtosMed.Importe`` — that signal was
  the catalog reference price (~76% of realised treatments in real
  exports have no matching ``DeudaCli`` and were therefore booking
  phantom debt). The clinical history is unchanged: Treatment,
  PlannedTreatmentItem, TreatmentTooth, ToothRecord general
  conditions and ClinicalNote keep coming from
  ``AppliedTreatmentMapper`` regardless of billing — patients with
  realised work but no debt see their odontogram and plan with
  balance = 0.
- feat(debt): sidecar resolver entry ``applied_treatment_record`` →
  ``treatments.id`` set inside ``AppliedTreatmentMapper`` so
  ``DebtMapper`` can recover the destination Treatment row (for
  catalog_item_id / professional_id / performed_at snapshots and
  for the ledger uniqueness constraint). Shadow planned twins
  inherit the redirect along with the existing
  ``applied_treatment`` mapping so a ``DeudaCli`` pointing at the
  planned row still lands on the realised twin.
- feat(payment): negative ``PagoCli`` rows now create
  ``payments.Refund`` rows tied to a DentalPin ``Payment`` instead
  of being skipped. ``_resolve_refund_target`` tries three
  canonical-space signals in order: (1) explicit chain via
  ``related_payment_uuid`` (``IdPagoCliRelacionado``), (2) first
  positive ``PagoCli`` booked against the same
  ``applied_treatment_uuid``, (3) most recent positive ``PagoCli``
  for the same ``client_uuid`` whose source ``Pagado`` equals the
  refund's ``abs(amount)``. The third signal anchors on the
  canonical source amount so family-split downstream Payments
  don't break the match. No date window — migration data often has
  multi-year gaps between an original payment and its refund row
  (post-hoc reconciliations), and the
  ``Σ Refund.amount ≤ Payment.amount`` invariant prevents over-
  refunding regardless. Refunds with none of the three signals
  emit ``payment.refund_unmappable`` and drop. The previous
  ``amount <= 0 → skip`` branch is split into
  ``payment.zero_amount`` for true zeros and the refund branch for
  negatives.
- refactor(applied_treatment): removed ``_ensure_paid_index`` /
  ``_paid_index`` (now driven from ``DeudaCli``, not ``PagoCli``
  reverse lookup) and both ``PatientEarnedEntry`` creation blocks.
  ``_maybe_record_non_clinical_earned`` renamed
  ``_record_non_clinical_treatment`` — it no longer touches the
  ledger; it just lands Treatment + PlannedTreatmentItem so the
  plan view keeps showing radiografías / TACs / Bonos / primera
  visita. The ``applied_treatment.earned_skipped_no_payment_signal``
  warning is retired (superseded by the ``DeudaCli`` model).
- fix(applied_treatment): shadow-dedup of planned→performed twins now
  groups by ``(patient_uuid, IdPresuTto)`` whenever both rows carry a
  budget-line link. ``IdPresuTto`` is Gesdén's authoritative join
  between a presupuesto line and the realised TtosMed (per
  ``PresuTto.IdTtoMedOrig``), so this catches pairs the previous
  key — ``(patient, IdTto, IdTipoOdg, sorted_teeth)`` — missed when
  the tariff was edited between plan-creation and execution
  (observed on real exports). The legacy key is kept as a fallback
  for rows without budget linkage, and the early ``continue`` that
  dropped null-``IdTipoOdg`` rows from
  the pre-pass is removed so legacy-keyed groups see every row.

- perf(resolver): bulk-preload the entity_mappings cache at the start
  of ``_run_pipeline``. Re-executes that hit short-circuits for every
  row used to do 1 DB SELECT per entity (1.27 M SELECTs on a real
  Gesdén dataset); now one SELECT populates the in-memory dict and
  subsequent ``get`` calls resolve from RAM. Combined with the
  ``cache_warm`` flag, cache misses skip the DB read entirely — the
  preload is authoritative for "this entity has never been mapped".
- perf(budget_line): bypass ``BudgetItemService.create_item``. The
  service did ``db.get(TreatmentCatalogItem)`` + ``db.get(VatType)`` +
  two post-insert refreshes per row — four round-trips on top of the
  INSERT. The mapper now writes the ``BudgetItem`` directly with the
  line totals computed inline (mirrors
  ``_calculate_line_totals``), caches VAT info per
  ``catalog_item_id`` (200 catalog items × 385 K lines = 99.95%
  cache hit), and skips the post-insert refresh entirely (no
  response object needed). Throughput on real Gesdén data went from
  ~250 entities/s to ~830 entities/s.
- perf(budget_line): defer budget status promotion + total recalc to
  one post-pipeline pass (``service._finalise_migrated_budgets``).
  The previous code did one ``db.get(Budget)`` + status check per
  budget_line (~385 K lookups) and called
  ``BudgetService._recalculate_totals`` per row — O(N²) per budget
  for the recalc. The new pass does one bulk ``UPDATE`` for status
  promotion and one recalc per budget at the end.
- feat(budget_line ↔ treatment): post-pipeline back-fill of
  ``BudgetItem.treatment_id`` ↔ ``Treatment.budget_item_id`` driven
  by the budget_line side of the link. Verified on a real Gesdén
  export: 95% of ``budget_line`` rows carry ``applied_treatment_uuid``
  while only 0.9% of ``applied_treatment`` rows carry the reverse
  ``budget_line_uuid``, so the budget_line side is what we resolve.
  The mapper accumulates ``(budget_item_id, applied_treatment_uuid)``
  pairs during ingest; the post-pipeline pass resolves them in
  batches of 500 via two SELECTs (entity_mappings →
  ``PlannedTreatmentItem.id`` → ``Treatment.id``) and applies the
  two-direction UPDATE.
- feat(service): allow re-executing a job in ``status='failed'``.
  Operators routinely fix a downstream issue (DB out of space,
  catalogue gap…) and resume the same job. Mappers stay idempotent
  via the resolver short-circuit + savepoint pattern.
- fix(applied_treatment): gate ``PatientEarnedEntry`` creation on
  ``is_realised`` (formal-done **or** heuristic age/notes promotion)
  instead of ``formal_done`` alone. The previous gate left an
  inconsistency: heuristic-promoted rows landed with
  ``Treatment.status='performed'`` and
  ``PlannedTreatmentItem.status='completed'`` (plan tab shows the
  work done) yet skipped the earned-ledger row — the pagos tab then
  claimed the patient had a huge credit against work the UI told
  them was finished. The ``completed_by_age`` /
  ``completed_by_notes`` warnings remain in place so ops can review
  the heuristic classifications. Same gate applied to the
  non-clinical earned path.
- feat(dpmf/iter): move ``budget`` + ``budget_line`` from level 5 to
  level 3.5, before ``applied_treatment``. The reorder lets
  ``applied_treatment`` resolve ``budget_line_uuid`` to a real
  ``BudgetItem`` and group its plan by source presupuesto (instead
  of falling through to the per-year catch-all). Without this the
  Plan tab listed migrated treatments under "Migrado — 2025"
  disconnected from the presupuesto that originated them, even when
  budget.status had been correctly promoted to ``accepted``.
- fix(applied_treatment): back-fill the symmetric
  ``BudgetItem.treatment_id`` ↔ ``Treatment.budget_item_id`` link
  when an applied_treatment carries a ``budget_line_uuid``. The
  Presupuesto tab now shows each accepted line connected to the
  imported Treatment row (FK to ``treatments.id``); the Plan tab can
  navigate back to the source budget.
- feat(user): new ``UserMapper`` for standalone Gesdén users
  (administradoras, recepción, contabilidad…). Maps
  ``CanonicalUser`` → ``auth.User`` + ``ClinicMembership(role='receptionist')``.
  Non-loginable password hash (matches professional mapper pattern)
  so the admin must send a reset before the imported person signs
  in. Without this, ``user`` rows fell to ``RawEntity`` and every
  ``user_uuid`` reference in the DPMF was silently ignored.
- feat(resolver): new ``resolve_actor`` helper on ``MappingResolver``
  that resolves a DPMF ``user_uuid`` to a destination ``users.id``
  with a fallback (typically ``ctx.created_by``). Used by budget /
  payment / fiscal_document mappers to preserve the original
  Gesdén author/cashier/issuer when available — falls back to the
  migration admin only when the source row had no user link or
  the referenced user wasn't imported.
- fix(catalog): extend the display-label fallback chain to include
  ``patient_facing_description`` and ``name`` before falling through
  to ``code``. The previous chain stopped at ``agenda_description``
  and any DPMF whose adapter wrote a generic ``name`` field landed
  with internal codes (``COD004``, ``COD007``…) as the UI label.
  Treatments and budgets inherited the wrong label transitively. The
  canonical v0.1 spec doesn't define ``name`` but we accept it
  defensively so non-Gesdén adapters render correctly.
- feat(pharmacological_history): map ``TTratamientos`` rows into
  ``patients_clinical.Medication`` so the patient clinical sidebar
  shows the imported medication list. Previously the rows fell into
  ``RawEntity`` audit-only and the sidebar opened blank even when the
  source had a full prescription history.
- fix(applied_treatment): non-clinical Gesdén rows now register their
  synthetic PlannedTreatmentItem in the resolver (when the row is
  formal-done and billed) or drop a ``mark_skipped`` sentinel (when
  it's a no-op). Re-executes used to duplicate the synthetic
  ``Treatment(scope='global_mouth')`` + ``PatientEarnedEntry`` +
  ``PlannedTreatmentItem`` every run because the non-clinical path
  returned ``None`` without touching the resolver.
- fix(applied_treatment_phase): drop a skipped sentinel when the phase
  is rejected for missing/unmapped parent, so re-executes don't
  re-emit ``phase.unmapped_parent`` / ``phase.no_parent`` warnings.
- feat(MappingResolver): new ``mark_skipped`` / ``was_skipped``
  primitives backed by a ``<entity>.__skipped__`` sidecar in
  ``entity_mappings``. ``get`` ignores the sidecar so downstream FK
  resolution still falls back to ``None`` for skipped rows; the
  sidecar exists only to make the mapper-level short-circuit
  persistent across re-executes.
- fix(service): delete prior ``ImportWarning`` rows when transitioning
  a re-executed job back to ``executing``. Without the prune,
  warnings accumulated every run (236 → 472 → 708…) even though the
  same canonical entities short-circuited at the resolver.
- fix(fiscal_document): use real ``Invoice`` column names
  (``invoice_number``, ``issue_date``, ``total_tax``, ``created_by``)
  instead of the legacy ``series``/``number``/``issued_at``/``tax_total``
  payload. The previous mapper crashed with ``'str' object has no
  attribute '_sa_instance_state'`` when stamping the source legal
  series onto ``Invoice.series`` (a relationship to ``InvoiceSeries``,
  not a free-text column) — every imported fiscal document failed
  silently and the new ``fiscal_document_line`` mapper had no parent
  invoice to point at. The source series is now preserved as a prefix
  in ``invoice_number`` (e.g. ``F-2024-073``) and ``series_id`` stays
  ``NULL`` until the operator wires up an ``InvoiceSeries`` catalog.
- feat(fiscal_document_line): map ``LinAdmin`` rows into ``InvoiceItem``
  so imported invoices carry their concept lines instead of falling
  into ``RawEntity``. Without this mapper the header showed the right
  totals but reports that cross factura↔tratamiento returned empty.
  ``catalog_item_id`` is resolved through the
  ``applied_treatment_uuid`` chain when available; otherwise the line
  stays unlinked. Mapper bypasses ``InvoiceItemService`` consistently
  with the fiscal-document header path (historical billed snapshot,
  not an unbilled treatment context).
- fix(service): row-level lock on ``ImportJob`` before transitioning
  to ``executing`` and drop ``executing`` from the allowed entry
  states. A concurrent re-execute now blocks at the SELECT FOR UPDATE
  and finds the job already running, returning without spawning a
  second pipeline. Earlier behaviour let two BackgroundTasks race on
  the same job, corrupting the progress counter and emitting
  duplicate ``migration.entity.persisted`` events.
- fix(service): reset ``processed_entities`` and ``last_checkpoint``
  on transition to ``executing``. Re-executing a completed job
  short-circuits at the per-mapper resolver but still incremented the
  batch counter, so a re-run of a 100/100 job left
  ``processed_entities=200`` — the UI badge stuck at "completed" with
  nonsensical numbers. Mappers stay idempotent at the entity-mapping
  level, so we lose no data by starting the counter at zero.
- fix(service): wrap every ``mapper.apply`` in a savepoint
  (``db.begin_nested()``) so a half-flushed mapper rolls back to a
  clean snapshot. Earlier behaviour caught the exception, recorded a
  warning, and continued — but anything already flushed (e.g.
  ``Treatment`` added before ``TreatmentTooth`` blew up) survived the
  next batch commit as an orphan row. Reports and odontogram views
  rendered against those orphans drifted from reality.
- fix(applied_treatment): emit
  ``applied_treatment.unmapped_variant`` warning when a Gesdén row
  carries a ``treatment_variant_uuid`` that the variant mapper did
  not import (catalogue out of scope, variant suppressed, etc.).
  Previously the treatment landed silently with ``catalog_item_id =
  NULL`` and the UI showed "Sin catálogo" without any audit trail.
- fix(appointment): stamp ``Appointment.created_by`` with the admin
  who triggered the migration (``ctx.created_by``) instead of
  ``None``. Other mappers (patient, professional, budget) already
  preserved this; appointments were the only entity that lost the
  audit trail.
- fix(applied_treatment): resolve the destination ``catalog_item_id``
  for migrated non-clinical billed services too, so the BOCA COMPLETA
  chip strip / plan list render the real service name
  (Mantenimiento periodontal, Panorámica, Bono ortodoncia…) instead
  of the generic ``migrated`` ``clinical_type`` fallback. Previously
  only the per-tooth path looked up the variant; the global_mouth
  shadow left ``catalog_item_id=NULL`` so the UI label-lookup chain
  fell straight to the enum value.
- feat(payment): split a Gesdén ``PagoCli`` across every patient
  linked to its payer client. The mapper used to attribute the whole
  amount to the first patient mapped, inflating that patient's credit
  while leaving family members in apparent debt. Now
  ``PatientClientLinkMapper`` exposes the full M:N graph through
  ``ctx.client_to_patients``; the payment mapper splits each amount
  proportionally to each linked patient's existing ``earned`` ledger
  (or evenly when nobody has earned activity yet). The resolver
  maps the source canonical_uuid to the first split share; the rest
  are unmapped audit rows. Emits a ``payment.split_across_family``
  warning per split for the operator to spot-check.
- fix(applied_treatment): allow negative earned amounts (credit-note
  corrections from Gesdén's ``Nota Económica`` rows). The
  ``ck_earned_amount_nonneg`` check was lifted in ``pay_0003`` so the
  ledger sums net out correctly against the matching payments;
  publishers still emit positive amounts in normal flow.
- fix(applied_treatment): mirror billable non-clinical Gesdén entries
  (hygiene, panoramic X-rays, fluorisation, "Bonos", first-visit
  consultations, generic services — ``IdTipoOdg`` in
  ``_NON_CLINICAL_TIPO_ODG``) into the destination as
  ``Treatment(scope='global_mouth', clinical_type='migrated')`` +
  ``PlannedTreatmentItem`` (on the per-year catch-all plan) +
  ``PatientEarnedEntry``. Earlier passes only wrote the ledger row,
  so the pagos tab showed services that didn't appear in plans or
  budgets — the user couldn't trace what they were being billed for.
  ``global_mouth`` keeps the odontogram chart clean (no tooth paint)
  while the plan list now enumerates every billed service.
- feat(budget): preserve the source budget number. The mapper now
  composes ``PRES-YYYY-NNNN`` from ``CanonicalBudget.number`` +
  ``quote_date.year`` (with a ``S{n}`` middle segment for non-default
  series) instead of letting the destination renumber every historic
  presupuesto into the current year. On collision with an existing
  row in the destination the auto-generator takes over and a
  ``budget.number_collision`` warning is emitted. Required a one-line
  contract change in ``BudgetService.create_budget`` to honour
  ``data['budget_number']`` when supplied.
- fix(applied_treatment): drop budget-shadow planned rows whose
  performed counterpart was created as a *new* TtosMed entry.
  Gesdén never updates ``StaTto`` 3→5 in place — when a budgeted
  line gets executed the clinician adds a second row at
  ``StaTto=5`` and the original sits at ``StaTto=3`` forever, so
  importing both flooded the odontogram with planned/performed
  twins. A single DPMF pre-pass groups by
  ``(patient, IdTto, IdTipoOdg, teeth)`` and pairs each performed
  with the nearest earlier planned inside a 24-month window; the
  planned twin is skipped and its ``canonical_uuid`` redirected
  via the resolver to the performed's ``PlannedTreatmentItem`` so
  any ``budget_line`` / ``applied_treatment_phase`` that referred
  to the planned still resolves cleanly. Clinics that update
  ``StaTto`` in place have only one row per treatment → the
  pairing never matches → no behavioural change for them.
- feat(patient): pipe ``Pacientes.Notas`` (new in dental-bridge
  adapter 0.0.2) through the same classifier that handles
  ``AlertPac.Texto``. Lines parse into ``Allergy`` / ``Medication`` /
  ``SystemicDisease`` / ``MedicalContext`` flags / administrative
  ``ClinicalNote`` rows; the unclassified remainder appends to
  ``Patient.notes``. Reuses ``PatientAlertMapper.dispatch_freetext``
  so a single rule change propagates to both sources.
- feat(applied_treatment): mirror ``TtosMed.Notas`` into the
  ``clinical_notes`` module as ``note_type='treatment'`` rows owned by
  the imported ``Treatment``. The mapper had been storing the body on
  ``Treatment.notes`` only; the patient-detail clinical feed and the
  diagnosis sidebar both read from the polymorphic ``clinical_notes``
  table, so migrated patients showed an empty clinical history even
  though ~99 % of Gesdén treatments carry narrative
  (composite shade, implant lot, anaesthetic, outcome…).
  ``created_at`` is anchored to the treatment's effective date so the
  feed renders chronologically; ``author_id`` resolves to the
  professional's User row (or the importer admin if unmapped).
- fix(applied_treatment): set ``ToothRecord.general_condition`` for
  realised treatments that leave an observable artefact
  (extraction → missing, crown/bridge/veneer/post → crown,
  implant → implant, fillings/inlays/overlays → filling,
  root canals → root_canal, sealant → sealant). Last write by
  ``end_date`` (or ``start_date`` if absent) wins; ties broken by
  precedence so an implant beats a prior extraction on the same
  tooth. Without this, the imported odontogram chart rendered
  uniformly ``healthy`` even for patients with decades of restorative
  history. Paired with the frontend filter below, the Diagnóstico
  panel stays clear and the chart actually reflects the mouth.
- fix(applied_treatment): hide migrated treatments from the
  Diagnóstico tab. Bulk-importing a patient's full history flooded
  the active diagnosis panel with hundreds of historical artefacts,
  making the "what am I diagnosing today?" workflow unusable.
  ``DiagnosisMode`` now filters
  ``source_module !== 'migration_import'``; the migrated record stays
  visible in the History tab and as PlannedTreatmentItems on the
  imported plans.
- fix(professional): map canonical role ``doctor`` → DentalPin
  ``dentist`` (was silently falling through to ``assistant``, so every
  Gesdén dentist landed as auxiliar), and create the imported User
  with ``is_active=True`` so the Users page shows them as active.
  Login stays blocked by the ``!migration_disabled:`` sentinel hash
  until the admin sends a password reset. The mapper also honours the
  canonical ``deactivated`` flag when present.
- fix(applied_treatment): only formal-done treatments enter the
  patient earned ledger. The first ledger pass counted every
  ``is_realised`` treatment (including the ones rescued by the
  age/notes heuristic), which silently inflated the clinic's
  apparent revenue and erased legitimate patient credit on
  in-progress plans. The earned ledger now gates strictly on
  ``formal_done`` (Gesdén ``StaTto ∈ {5, 6}`` or ``FecFin`` set in
  the source); heuristic-promoted treatments continue to surface as
  "completed" in the UI plan list so the clinician can review them,
  but they don't generate revenue. Validated against la paciente de ejemplo
  three-way: 16,135 € paid · 14,305 € earned-formal · 14,090 € sum
  of accepted budgets → 1,830 € patient credit, matching the
  expected up-front payment for the in-progress implant plan.
- fix(applied_treatment): write the patient earned-ledger entry
  directly. The patient balance UI reads from
  ``patient_earned_entries`` (treatments performed → money the
  clinic has earned), which is normally populated by the payments
  module's event handlers reacting to
  ``odontogram.treatment.performed`` /
  ``treatment_plan.item_session_completed``. The migration bypasses
  the services to avoid spurious notifications for historic data,
  so those events never fire and the ledger stays empty — every
  imported patient appears to be in massive credit because their
  payments are recorded but the treatments they paid for aren't
  counted. ``AppliedTreatmentMapper`` now inserts a
  ``PatientEarnedEntry`` row for every completed treatment with
  ``source_event='migration_import'`` and
  ``source_session_id=NULL`` (matches the
  ``odontogram.treatment.performed`` non-session path; our migrated
  sessions carry ``amount=0`` so the per-session ledger path would
  add nothing). Validated on una paciente de ejemplo: 39
  performed treatments × prices = 32,645 €. With 16,135 € of payments
  recorded, the balance flips from −16,135 (clinic owes the
  patient) to +16,510 (patient still owes the clinic) — which
  matches the operative reality of an in-progress implant /
  prosthesis plan.
- fix(budget): stamp the source ``FecPresup`` onto ``Budget.created_at``
  and ``Budget.updated_at`` so the UI shows the real budget date
  rather than the import-run timestamp. ``TimestampMixin`` was
  seeding both columns from ``func.now()`` because the mapper never
  overwrote them, so every migrated budget read "creado hoy" on the
  patient page regardless of whether it was quoted in 2017 or 2024.
  ``updated_at`` advances to the latest lifecycle event
  (``rejected_date`` > ``accepted_date`` > ``quote_date``) so the
  budget pipeline UI keeps sorting recently-updated entries on top
  as before.
- fix(budget): rescue ``Budget.status`` from the
  ``PresuTto.IdTtoMedOrig`` back-reference. Gesdén keeps a Presu↔TtosMed
  double link (forward in ``TtosMed.IdPresuTto``, backward in
  ``PresuTto.IdTtoMedOrig`` — exposed canonically as
  ``budget_line.applied_treatment_uuid``). Clinics with poor hygiene
  rarely fill ``Presu.FecAcepta`` even when the patient clearly
  acted on the budget, so 88 % of the live export ends up with
  Estado=0 (draft). The back-reference holds because every applied
  treatment must point at its budget line to bill correctly —
  ``BudgetLineMapper`` now promotes the parent budget from ``draft``
  to ``accepted`` (one-way) the first time it sees a line with
  ``applied_treatment_uuid`` set. Verified on una paciente de ejemplo: 8/18 budgets correctly accepted (the 2019-2024
  ones backed by 661 applied treatments, totalling 14,090 €), 10/18
  stay draft (the 2017 alternative quotes that never had work
  done).
- feat(mappers): new ``PatientAlertMapper`` materialises Gesdén
  ``AlertPac`` rows (free-text medical history) into structured
  ``patients_clinical`` records — historical empty "Historial médico"
  on every imported patient was directly caused by ``patient_alert``
  falling through to the ``RawEntity`` catch-all.
  The classifier (``_alert_classifier.py``) routes each free-text
  alert through a cascade of Spanish medical regex rules and
  dispatches into the right destination row:
  - ``allergy``        → ``patients_clinical.Allergy`` (one row per
                          listed allergen, ``ALERGIA:`` prefix
                          recognised)
  - ``medication``     → ``patients_clinical.Medication`` (``MEDICACION:``
                          prefix + bare ``DRUG <DOSE>`` heuristic;
                          ``MG/MCG/G/ML/UI`` dose tokens stripped into
                          the ``dosage`` column)
  - ``disease``        → ``patients_clinical.SystemicDisease`` (covers
                          hipertensión / diabetes / hepatitis / cancer
                          / cardiopatía / Parkinson / Alzheimer /
                          asma / epilepsia / depresión / trastornos /
                          sinusitis / psoriasis / glaucoma /
                          osteoporosis / anemia / fibromialgia /
                          tiroides …)
  - ``anesthesia``     → ``MedicalContext.adverse_reactions_to_anesthesia``
                          + ``anesthesia_reaction_details``
  - ``smoking``        → ``MedicalContext.is_smoker`` + ``smoking_frequency``
  - ``pregnancy`` / ``lactating`` → ``MedicalContext`` flags
  - ``anticoagulant``  → ``Medication`` row + flips
                          ``MedicalContext.is_on_anticoagulants``
                          (Sintrom / Pradaxa / Adiro / Plavix /
                          Clopidogrel / Xarelto / Eliquis / Heparina /
                          Warfarina / Aldocumar)
  - ``bruxism``        → ``MedicalContext.bruxism``
  - ``administrative`` → ``clinical_notes.ClinicalNote`` with
                          ``note_type='administrative'`` attached to
                          the patient (``PRESU.``, ``DTO``,
                          ``COBRAR``, ``ENVIAR FACTURA``,
                          ``VIENE REFERIDO`` …) — preserves the
                          info in the reception-friendly notes panel
                          instead of dropping it on the floor
  - ``general``        → falls back to ``Patient.notes`` so the
                          clinician sees the original text in
                          context
  Rules are case- and accent-insensitive and ordered by precedence
  (pregnancy / lactation before generic disease, anticoagulant
  before generic medication, etc.). ``MedicalContext`` is lazily
  upserted per patient so a patient with multiple flag-style alerts
  (smoking + pregnancy + anesthesia + …) ends up with one row that
  accumulates every flag.
  Manifest grows ``patients_clinical`` in ``depends``. Validated on
  200 random alerts: 82 % routed into structured clinical buckets,
  18 % marked administrative or falling back to notes (matches the
  intuition for free-text leftover noise like "CALCIO" or "NO TIENE
  VESICULA").
- feat(applied_treatment): rescue completion status for treatments
  Gesdén left as ``StaTto=3`` despite being long done. In the live
  export ~26 k clinical treatments sit at ``StaTto=3`` (planned)
  with ``FecFin`` null — 87 % of them are 2+ years old and 55 % are
  5+ years old, which is implausible for genuinely-unstarted work.
  Investigation of the Gesdén schema found no reliable signal in
  this clinic's data (DCitasTto + TtosMed_PagoCli are empty,
  Pendiente is 0 for every row regardless of state, FechaValida /
  IdColValida / NumDocUnico / SesRealiz are all null). The clinic
  simply never updates ``StaTto`` after performing a treatment.
  The mapper now applies a heuristic on top of the formal signals:
  formal "done" (StaTto ∈ {5, 6} or FecFin set), plus
  ``FecIni`` older than 5 years (age alone), plus ``FecIni`` older
  than 2 years AND notes longer than the 40-char catalog-name floor
  (age + clinical detail). Every heuristic hit emits an audit
  warning (``completed_by_age`` / ``completed_by_notes``) so the
  operator can spot-check the reclassification. Validated on the
  una paciente de ejemplo record: 25 stale "planned" items
  collapse to 5 (the recent 2024 entries and one 2021 short-note
  case), with the other 20 promoted to completed.
- fix(applied_treatment): migrated plans land in ``active`` instead of
  ``draft``. Gesdén plans are historical, post-acceptance records —
  leaving them in DentalPin's pre-confirmation state forced the
  operator to manually confirm every imported plan before any
  consumer (budgets, payments, reports) treated it as real. ``active``
  is the natural post-acceptance state in the plan machine and is
  set directly on the model (bypassing the ``draft → pending →
  active`` event chain that would fire spurious notifications for
  historic data).
- fix(applied_treatment): treat ``StaTto`` codes ``{5, 6}`` as
  realised, not just ``5``. Code 6 is a low-volume variant that also
  carries ``FecFin`` in the source and corresponds to a completed
  treatment. The previous "code 5 only" rule made a handful of
  finished items show as pending.
- fix(applied_treatment_phase): mirror the parent ``PlannedTreatmentItem``
  status when the source phase row doesn't carry a realised
  ``StaTto`` itself. In the observed Gesdén export every phase row
  stays at ``StaTto`` 1 or 3 even when its parent treatment is
  finished — Gesdén tracks completion at the ``TtosMed`` level, not
  per ``TtosMedFases``. Without the inheritance, sessions of
  completed items stayed ``pending`` and dragged item-level
  earned-ledger semantics off.
- feat(applied_treatment): map Gesdén ``IdTipoOdg`` to DentalPin's
  ``TreatmentType`` enum (implant / crown / bridge / extraction /
  filling_composite / root_canal_full / veneer / sealant / band /
  bracket / post / apicoectomy …) instead of hard-coding
  ``"migrated"`` on every imported treatment. The UI now surfaces
  real labels; the catalog item name follows via the existing
  ``catalog_item_id`` link.
- feat(applied_treatment): skip non-clinical Gesdén timeline entries
  (Anotación, Nota Económica, Primera Visita, Higiene, Panorámicas,
  Teleradio, Fluorización, Genérico, tooth-state codes). They aren't
  tooth treatments and were polluting the migrated plan with empty
  line items. A ``applied_treatment.non_clinical_entry`` warning
  records each skip; the canonical row still lands in
  ``RawEntity`` for audit.
- feat(applied_treatment): group migrated plans by source budget
  (one plan per ``Migrado — <budget_number>``) when
  ``budget_line_uuid`` resolves; fall back to per-year buckets
  ("Migrado — 2017") when the source carries no budget link, so a
  patient with twenty years of history no longer ends up with a
  single 131-item mega-plan. The ``TreatmentPlan.budget_id`` link is
  also set so the budget detail sidebar reflects the migration.
- fix(applied_treatment): bypass ``TreatmentPlanService.create``
  because its ``count(*)``-based ``plan_number`` generator collides
  any time historic plans leave gaps in the sequence (and the
  per-budget split creates many plans per patient in one session).
  Use deterministic synthetic numbers (``MIG-<budget_number>`` or
  ``MIG-<patient_short>-<year>``) — unique by construction, idempotent
  on re-run.
- feat(applied_treatment): create per-tooth ``TreatmentTooth`` rows
  from the new ``payload["teeth"]`` field that dental-bridge emits
  (FDI numbers decoded from Gesdén's ``PiezasAdu`` / ``PiezasLec``
  bit-masks). ``ToothRecord`` rows are lazily created per ``(clinic,
  patient, tooth_number)`` so subsequent treatments on the same tooth
  reuse the same record. Surfaces remain ``None`` until the source
  ``ZonasPieza`` encoding is field-validated.
- feat(budget_line): write the first decoded FDI tooth into
  ``BudgetItem.tooth_number``; the remaining teeth (e.g. bridge
  members) land in the line ``notes`` field so the operator can split
  the budget line manually if their workflow expects a per-tooth row.
- fix(payment): the historical Payment mapper was producing rows that
  violated three NOT NULL columns on ``payments.Payment``:
  ``currency`` (snapshot of ``Clinic.currency``), ``recorded_by`` (FK
  to ``users``), and ``payment_date`` when the source row had no
  parseable date. ``currency`` is now resolved once per clinic and
  cached, ``recorded_by`` defaults to ``ctx.created_by`` (the admin
  who launched the job), and the date falls back to today with the
  notes field carrying the migration provenance. While here, fix two
  field-name regressions: the canonical payload exposes ``paid_on``
  (not ``paid_at``) and a numeric ``payment_kind`` code (not the
  English string ``method``); both are now read and the Gesdén
  ``Tipo`` code is decoded against ``_PAYMENT_KIND_MAP`` so real
  ``cash``/``card``/``bank_transfer`` etc. land in DentalPin instead
  of every payment defaulting to ``other``.
- feat(mappers): new ``PatientClientLinkMapper`` plus client→patient
  resolution in ``PaymentMapper``. In Gesdén ``DCobros`` references
  the *client* (payer), not the patient — DentalPin's flat
  ``Payment.patient_id`` couldn't be derived from the canonical row
  alone. The new mapper walks ``patient_client_link`` payloads and
  writes a secondary ``patient_for_client`` mapping (one row per
  client, ON CONFLICT DO NOTHING so the first patient registered per
  client wins) plus its primary ``patient_client_link`` mapping for
  idempotent re-runs. ``PaymentMapper`` now resolves
  ``client_uuid → patient_id`` via that sidecar before falling back
  to a direct ``patient_uuid``. Ambiguous clients (multiple patients
  linked) emit a ``patient_client_link.ambiguous_payer`` info
  warning so the operator can reconcile manually.
- feat(catalog): reuse existing DentalPin catalog items when the
  imported Spanish name matches an active item (1:1, case- and
  whitespace-normalised). On a unique match the resolver mapping
  points at the existing row and a ``catalog.matched_existing``
  info warning is emitted; ambiguous or missing matches still fall
  through to the "Importado de Gesdén" create path. This preserves
  pricing strategy, session template, VAT and odontogram mapping for
  treatments the clinic already had configured.
- perf(pipeline): batch the ``processed_entities`` counter update.
  Previously every persisted entity emitted
  ``migration.entity.persisted``, which a subscriber consumed in a
  *fresh* DB session — that meant a separate ``BEGIN ... UPDATE ...
  COMMIT`` round-trip per row (~25 ms each on local Postgres), so a
  1.27 M-row import projected to ~9 h. The counter is now bumped on
  the main session once per ``_COMMIT_BATCH`` (every 500 entities),
  alongside the checkpoint write and the natural batch commit. The
  ``MIGRATION_ENTITY_PERSISTED`` event is still emitted once per
  batch (now carrying the batch ``count``) for any external
  subscriber that wants progress signals; the importer itself no
  longer subscribes. Benchmarked locally: 10 000-entity RawEntity
  slice goes from ~5 min to ~4 s (~2 600 ent/s), projecting a full
  1.27 M run to ~8 min instead of ~9 h.
- feat(mappers): new ``AppliedTreatmentMapper`` materialises DPMF
  ``applied_treatment`` into a three-table cascade — one lazy
  ``treatment_plan.TreatmentPlan`` per patient (titled
  ``"Migrado de Gesdén"``, cached for the job), one
  ``odontogram.Treatment`` per applied treatment (clinical_type
  ``migrated``, with the source price snapshotted on
  ``price_snapshot``), and the linking
  ``treatment_plan.PlannedTreatmentItem``. Tooth/surface detail is
  skipped — the canonical ``odontogram_raw`` bit-mask isn't decoded
  upstream yet.
- feat(mappers): new ``AppliedTreatmentPhaseMapper`` attaches DPMF
  ``applied_treatment_phase`` rows as
  ``PlannedTreatmentItemSession`` children of the imported plan
  item. Per-session amount is left at zero (DentalPin sessions carry
  an absolute amount; the canonical ``percent_to_bill`` is exposed
  in the session label instead — clinics can rebalance manually).
- chore(manifest): add ``odontogram`` to ``depends`` (used by
  AppliedTreatmentMapper to construct Treatment rows directly).
- feat(mappers): new ``CatalogItemMapper`` materialises DPMF
  ``treatment_catalog_item`` rows into ``catalog.TreatmentCatalogItem``.
  Items land under a lazy-created ``TreatmentCategory`` keyed
  ``"migrado_gesden"`` so the clinic can re-classify them later
  without touching the original taxonomy. ``internal_code`` is
  synthesised from the canonical UUID (``MIG-xxxxxxxx``) to dodge
  ``uq_catalog_item_clinic_code`` collisions when the source carries
  duplicate codes across tariff variants.
- feat(mappers): new ``CatalogVariantMapper`` resolves
  ``treatment_catalog_variant`` to the parent
  ``treatment_catalog_item`` (pipe-through). DentalPin's catalog
  doesn't model a per-tariff axis, so the variant's canonical UUID
  resolves to the same DentalPin row as its parent; pricing
  differences survive as ``budget_line.unit_amount`` snapshots.
- feat(mappers): new ``BudgetMapper`` + ``BudgetLineMapper`` materialise
  DPMF ``budget`` / ``budget_line`` into ``budget.Budget`` /
  ``budget.BudgetItem`` via the corresponding services. Budget header
  status is derived from ``accepted_date`` / ``rejected_date`` presence
  (canonical ``status_code`` is source-opaque). Line items resolve
  ``treatment_uuid`` → ``treatment_variant_uuid`` as the catalog FK
  fallback chain. Each line triggers ``_recalculate_totals`` on the
  parent budget so the header subtotal/total stay in sync.
- chore(base): add ``created_by: UUID`` to ``MapperContext`` (populated
  from ``ImportJob.created_by``) — required by the budget mapper and
  any future mapper whose target service tracks the acting user.
- chore(manifest): add ``catalog`` and ``budget`` to ``depends``. Both
  are real ORM imports by the new mappers, so the declaration is
  required by the modular-architecture contract.
- feat(mappers): new ``AppointmentMapper`` materialises DPMF
  ``appointment`` entities into ``agenda.Appointment`` rows. Resolves
  ``patient_uuid``/``professional_uuid`` via the
  :class:`MappingResolver`, combines ``scheduled_date`` +
  ``scheduled_time`` into a UTC ``start_time`` (computes ``end_time``
  from ``duration_minutes``, default 30), maps ``coarse_status`` →
  DentalPin's 7-state status enum, and emits warnings under
  ``appointment.{missing_actor,unmapped_actor,no_schedule,unparseable_datetime}``
  when an entity has to be skipped instead of silently dropped. Chair
  resolution is deferred until a ``catalog_item`` mapper exists.
- chore(manifest): add ``agenda`` to ``depends`` (used by the new
  appointment mapper). ``schedules`` stays as a forward-compat
  declaration even though no mapper touches it yet.
- fix(routing): correct the route prefix used by the frontend wizard and
  by the inline docs/CLAUDE.md/user-manual frontmatter. FastAPI mounts
  the router under ``/api/v1/migration_import/`` (the manifest name,
  with the underscore), but the Vue page, the docstrings and the
  ``related_endpoints`` frontmatter referenced
  ``/api/v1/migration-import/``. The settings wizard was therefore
  silently 404'ing on every step; only ``curl`` against the real path
  worked. All five callers in ``DataMigrationPage.vue`` plus
  ``binaries/ingest.py``, ``router.py``, ``CLAUDE.md`` and both locale
  user-manual files are now aligned.
- fix(lifecycle): default ``_staging_root()`` to
  ``{STORAGE_LOCAL_PATH}/migration-import`` instead of
  ``/var/lib/dentalpin/migration-import``. The previous hardcoded path
  was outside any volume the backend container can write to (running
  as ``appuser``), so installing the module failed with ``[Errno 13]
  Permission denied`` on a stock docker-compose setup. The
  ``MIGRATION_IMPORT_STAGING_DIR`` override is unchanged.
- refactor(perms): migrate hardcoded ``can('migration_import.job.execute')`` in ``DataMigrationPage`` to ``PERMISSIONS.migrationImport.jobExecute``.
- refactor(errors): switch ``catch (err: any)`` to ``catch (err: unknown)`` + shared ``errorMessage`` helper in the upload flow.
- perf(lists): drop the ``select_from(query.subquery())`` count
  anti-pattern in ``ImportJobService.list_jobs``,
  ``list_warnings`` and the warnings-count after each execute. All
  counts now run directly over the indexed filter set.
- chore(events): publisher helpers (``publish_job_started``,
  ``publish_job_completed``, ``publish_job_failed``,
  ``publish_binary_resolved``, ``publish_entity_persisted``) are now
  ``async`` and await the bus inline. Callers in the mapper pipeline
  and binary ingest endpoint were updated to ``await``.
- chore(events): subscribe to ``migration.entity.persisted`` via
  ``EventType.MIGRATION_ENTITY_PERSISTED`` instead of a string
  literal.
- Initial version of the DPMF importer (issue #78).
  - Accepts `.dpm`, `.dpm.zst`, `.dpm.enc`, `.dpm.zst.enc`.
  - Parses 32 canonical entity types per DPMF v0.1 spec.
  - Idempotency table (`entity_mappings`) keyed by
    `(clinic_id, source_system, canonical_uuid, entity_type)` so
    re-imports are no-ops.
  - Binary ingestion endpoint (`POST /jobs/{id}/binaries`) for the
    out-of-band sync agent. Resolves by sha256 against the `_files`
    manifest and hands off to `media.DocumentService`.
  - `verifactu` integration is runtime-tolerant — the fiscal-document
    mapper skips legal-hash preservation when verifactu is not
    installed or the operator opts out.
  - Five real mappers (patient, professional, document, payment,
    fiscal_document); everything else lands in `raw_entities` until a
    dedicated mapper is added.
