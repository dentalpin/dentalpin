# Changelog — gdpr module

## Unreleased

- fix(#779): the retention window is measured from the clinic's day, not the server's UTC day.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- fix(#679): the `list_gdpr_requests` agent tool types `status` and
  `request_type` with the module's own `RequestStatus` / `RequestType`
  aliases — the ones `GET /requests` has always used — so an unrecognized
  value is rejected by name instead of filtering the register down to
  `{"total": 0}`. Both parameters also gained the description they were
  missing: the agent was being shown a bare string with no vocabulary at
  all. `create_gdpr_request.request_type` is typed the same way, moving its
  failure from the service to the chokepoint.
- fix(#677): the tool parameter `patient_id` is typed `UUID` instead of
  `str` on all four tools that take it.
  The tool schema now advertises `format: uuid`, and a malformed id is
  rejected by `tool_registry.call`'s validation step naming the parameter,
  rather than reaching the handler and raising `badly formed hexadecimal
  UUID string`, which named nothing.

- fix(#562 S2): the consent ledger answers "what is the state now", the
  breach register carries the Art. 34 record, and the filters stop
  accepting free text.
  - `GET /consents/current?patient_id&purpose` returns the latest row for
    one pair, ordered `created_at DESC, id DESC` - the same ordering
    `list_consents` uses, so the two can never disagree (CONS-04).
  - Consent purposes are canonicalized on write (strip + lowercase), so
    `"SMS"`, `"sms "` and `"sms"` are one purpose instead of three
    (CONS-05).
  - `gdpr_0004` backfills rows written before that rule: purposes holding
    the original casing or padding (`"Marketing"`, `"sms "`) are
    canonicalized in place, so a withdrawal stored pre-canonical is
    reachable under the key a later grant uses (CONS-05). The backfill can
    merge rows that the raw string kept distinct — that collapse is the
    intended single-purpose semantics, not a side effect.
  - The `gdpr.consent.granted` / `gdpr.consent.withdrawn` events publish the
    canonical purpose (the stored key), not the raw client string, so a
    subscriber keyed on `purpose` sees the value the ledger stores (CONS-05).
  - A blank purpose (`" "`) is 422: it passes `min_length=1` but normalizes
    to `""`, which would otherwise store an empty key (CONS-05).
  - Purposes stay an open vocabulary (clinics invent processors); only the
    spelling is canonical, so no legitimate purpose is ever rejected.
  - Recording a grant without the shown text is 422: without the text
    there is no record of what was consented to (Art. 4(11), CONS-07).
  - `status` / `request_type` filters are closed vocabularies, so a typo
    is a 422 instead of an empty list (QUAL-11).
  - `data_breaches` gains `notified_subjects_at` + `notified_subjects_count`
    (`gdpr_0003`): the register tracked authority notification only, with
    nowhere to record whether affected people were told. Both nullable,
    set explicitly; no auto-stamp rule (that scope decision is parked)
    (SEC-02).
  - Breach list ordering gets the same `id DESC` tiebreak, so pagination
    stays stable when two breaches share a second (CONS-04).
  - `report_breach` / `list_breaches` agent tools, both clinic-scoped
    and wrapping the existing service methods (SEC-06).
  - `reported -> not_reportable` is documented: it covers an authority
    ruling the report below the threshold after notification, and the
    authority/report latches deliberately stay set, because the
    notification did happen (review round on #664).

- fix(#562 S1): consent writes do a clinic-scoped patient lookup first
  (unknown/foreign ids: 404 on HTTP, error on the tool); creating a
  retention policy supersedes active same-category policies (reactivation
  is not a path) with a partial unique index backstop (`gdpr_0002`,
  concurrent twins answer 409); breach status follows a transition table
  (illegal moves 422) with the authority timestamp stamped only by
  reporting; record fields correctable, explicit nulls on required fields
  ignored; empty `data_involved` rejected.

- refactor(#657): the four interim retained coverage rows
  (`patient_timeline`, `budget`, `billing`, `clinical`) are gone;
  `ErasureService._interim_retained_coverage` is deleted. Every coverage
  row now comes from the module that owns the data, so the registry's
  own guarantee holds for all of them: uninstall a module and its row
  disappears instead of `gdpr` claiming coverage for data that is no
  longer there. The `clinical` row became three (`clinical_notes`,
  `documents`, `media`) — there is no `clinical` module to own it.

- feat(#546, ADR 0038): erasure pulls a core contributor registry instead of
  event-bus fan-out. `gdpr` calls every registered contributor
  (`get_erasure_contributors()`, collected from active modules like
  `get_tools()`) inside the erasure transaction and assembles the
  per-scope coverage list (`ErasureCoverage`: `patient_record` plus each
  contributor's own row) from their answers — a scope with no contributor
  produces no row, so an uninstalled module is never reported as erased.
  `gdpr.erasure.executed` is now a post-commit announcement.
  `patient_timeline`/`budget`/`billing`/`clinical` rows stay hardcoded as
  interim retained entries until their contributors land. A failing
  announcement is logged, never raised (the erasure is already committed);
  interim rows defer to any contributor answering the same scope.
- Maintainer-review fixes (PR #374, part of #44): closed erasure
  vocabulary `ErasureCategory` (`email | phone | identity`, 422 on anything
  else) in the schema and tool args so an erasure can never report a
  category it cannot blank; erasure of unknown/other-clinic patients
  returns `None` (404 upstream, tool error) before touching the audit
  table; retention windows run from the patient's `updated_at` anchor
  (`0` = no age hold, else N years); consents are append-only (one row per
  event, latest per purpose is current); dropped `DELETE /requests/{id}`
  (DSRs are Art. 5(2) accountability records); `datetime.now(UTC)`
  everywhere; deleted dead `ExportService.record_export`; dropped the
  `definition_year` leftover; docs state the v1 scope (ticket tracker, no
  Art. 21 objection yet, export = identity+consents+DSRs, no frontend).
- Initial module (issue #44): GDPR (EU 2016/679) compliance for a clinic.
- Added 5 models on their own Alembic branch (`gdpr`): `gdpr_requests`
  (DSR, Art. 15-20), `patient_consents` (Art. 7-8), `retention_policies`
  (Art. 5(1)(e)), `gdpr_erasure_audit_logs` (Art. 17 accountability),
  `data_breaches` (Art. 33-34).
- DSRs carry a 30-day SLA (`deadline_at` from `received_at` via
  `SlaCalculator`); status transitions auto-stamp `resolved_at`.
- Consents are append-only: every grant/withdraw inserts a row, so the
  full trail (including withdrawals) survives; a withdrawal is never
  destructive.
- Partial erasure (Art. 17) blanks patient identity/PII fields once the
  governing retention policy allows; the patient row is never hard-deleted.
  Every run writes an immutable `ErasureAuditLog` and publishes
  `gdpr.erasure.executed`.
- Portability export endpoint (`GET /gdpr/export/{patient_id}`, Art. 20)
  returns a machine-readable identity + consents + DSR snapshot.
- Six new `EventType` values published by the services:
  `gdpr.request.created`, `gdpr.request.status_changed`,
  `gdpr.consent.granted`, `gdpr.consent.withdrawn`,
  `gdpr.erasure.executed`, `gdpr.breach.reported`.
- RBAC: `gdpr.requests.read/write`, `gdpr.consents.read/write`,
  `gdpr.retention.read/write`, `gdpr.audit.read`, `gdpr.breaches.read/write`;
  admin wildcard, therapist read-only, front-desk read/write for DSRs/consents.
- Agent tools exposed: `create_gdpr_request`, `list_gdpr_requests`,
  `record_gdpr_consent`, `list_gdpr_consents`, `create_retention_policy`,
  `execute_partial_erasure` (wrapping the GDPR services, `ctx.clinic_id`-filtered).
- Migration `gdpr_0001_initial` on own Alembic branch (`gdpr`), depending on
  `patients@pat_0003`.
- `removable=True` — supports full uninstall with roundtrip tests.
- Registered `app/modules/gdpr` in `backend/alembic.ini` `version_locations`
  so the Alembic CLI graph (heads/upgrade) resolves `gdpr_0001` (CI parity).
- Registered `gdpr` in `pyproject.toml` module entry points so the module is
  discoverable in production (`DENTALPIN_DEV_MODULE_SCAN=False`); closes the
  entry-point parity gap reported by `tests/test_entry_point_parity.py`.