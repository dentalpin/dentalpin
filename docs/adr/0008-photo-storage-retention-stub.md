# 0008 — Photo storage retention is documented but not enforced (yet)

- **Status:** accepted
- **Date:** 2026-05-02
- **Deciders:** martinezsalmeron
- **Tags:** modules, media, storage, compliance

## Context

The new patient photo gallery (issue #55) lets clinics upload arbitrary
intraoral / extraoral / X-ray imagery. At scale (~hundreds of clinics
× hundreds of patients × dozens of photos each, plus three precomputed
thumbnail sizes) storage growth becomes a real cost and a compliance
question.

Today the only storage backend is `LocalStorageBackend` (a Docker
volume). Object lifecycle / glacier-style tiering is not feasible
locally — it's a feature of S3-class backends. A future
`media_s3` module is on the roadmap and will extend `StorageBackend`
without changing the contract.

> **Superseded (T6)**: `media` now also ships the S3 backend
> (`storage/s3.py`, `STORAGE_BACKEND=s3`, boto3 via `asyncio.to_thread`),
> so S3-class lifecycle features are feasible; the "future media_s3
> module" landed inside `media`.

Building a custom retention loop on local disk now would be premature
infrastructure (cron + tombstones + restore UI) for a feature nobody
needs at the current scale.

## Decision

Document the retention policy here and stop. **No active enforcement
loop, no archival cron, no UI for "moved to cold storage".** Photos
live alongside other documents and are deleted only via the existing
soft-delete (`Document.status='archived'`).

When S3-class storage first ships (lifecycle rules themselves remain
unimplemented; the backend is live at `media/storage/s3.py`), the
policy below applies:

1. Map "archived" documents to S3 `STANDARD_IA` after 30 days via
   bucket lifecycle rule.
2. Map archived documents older than 1 year to `GLACIER_DEEP`.
3. Patient-level export keeps full quality from the live tier.
4. Hard-delete remains forbidden (legal retention obligations differ
   per jurisdiction; we let clinics move their data, not lose it).

## Consequences

### Good

- Zero infrastructure investment until the cost matters.
- Lifecycle rules ride on S3 native features when we get there — no
  custom cron, no tombstone bookkeeping.
- Policy is captured in writing today so the storage extension
  doesn't have to reinvent it.

### Bad / accepted trade-offs

- Local-disk clinics keep paying for full-quality storage indefinitely.
  Acceptable for v1.
- "Archived" documents on local backend are still served at full
  quality if someone replays a download URL.

## Alternatives considered

- **Implement an archival cron now (local backend).** Rejected:
  premature, and the local backend has no cold tier to move to.
- **Hard-delete after N days.** Rejected: hostile to clinics, opens
  legal exposure.

## How to verify the rule still holds

- `grep "archive_patient_documents" backend/app/modules/media/service.py`
  — soft-delete-only path remains the single archive entry point.
- The S3 backend shipped inside `media` (`storage/s3.py`), not as a
  separate `media_s3` module, and implements no lifecycle rules; this
  ADR remains the record for that unimplemented policy.

## References

- `backend/app/modules/media/storage/base.py` — backend contract
- `backend/app/modules/media/service.py:archive_patient_documents`
- Issue #55
