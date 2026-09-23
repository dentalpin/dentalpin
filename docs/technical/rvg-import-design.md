# RVG auto-import design (imaging_viewer increment, T1)

> Idea source: apexo-flutter 0.14.x DICOM/RVG hardening (GPL-3.0 —
> ideas only, clean-room reimplementation in DentalPin module patterns).
> Compliant with `docs/technical/compliance-posture.md` §3.

## Flow

1. **Watch.** `get_scheduled_jobs()` declares `rvg_watch_tick` (interval,
   90s). The tick scans `<DENTALPIN_RVG_WATCH_DIR>/<clinic_id>/` per clinic
   (per-clinic subdir = isolation by layout; a clinic without a dir is
   skipped). A manual `POST /rvg/scan` covers setups without the scheduler.
2. **Fingerprint.** Every file is hashed (SHA-256). A row with the same
   `(clinic_id, content_hash)` is never re-imported — re-scans are no-ops,
   failed files stay discoverable with their error and can be retried.
3. **Identify.** Identity tags are extracted (PatientID, PatientName
   `LAST^FIRST`, PatientBirthDate, StudyInstanceUID, Modality, StudyDate).
   Unparsable files or files with no identity at all → `failed`, kept
   visible, never crash the tick (best-effort per file).
4. **Match.** An approved `RvgLink` on the DICOM PatientID auto-imports
   immediately (the link creator's user id attributes the upload — see §5).
   Otherwise candidates are scored (national_id +60, DOB +25, name-token
   overlap up to +30); best ≥ 40 becomes the suggestion, ties stay
   suggestion-less (`ambiguous`), everything lands in the approval queue.
5. **Approve (human).** Creates the media `Document` (xray/xray, DICOM mime —
   thumbnail-safe via the `is_thumbnailable` gate), indexes the study
   (publishes the existing `imaging.study_indexed`), and upserts the
   `RvgLink` so future files from that DICOM identity auto-import.
   Reject keeps the row for audit with an optional reason.

## Decisions

- **No auto-link on first sight.** A never-seen DICOM identity always needs
  one human approval; only the stored link auto-imports afterwards.
- **Attribution without a request user.** Scheduler ticks have no actor, so
  auto-imports attribute the media upload to the link creator (the human who
  approved the identity binding). Manual scans attribute the caller.
- **No new bus event.** Approval funnels through `index_study`, which already
  publishes `imaging.study_indexed` — consumers (timeline, AI) see RVG
  studies exactly like uploaded ones.
- **409, not 500.** Approving/rejecting an already-decided row answers 409
  (L6); unknown patient on approve answers 404; both are state checks, not
  race-prone uniqueness paths.
- **Retention/erasure interplay.** RVG rows reference patients; the existing
  `patient.archived` handler is extended to also reject pending RVG imports
  and drop links of that patient (links to a blanked identity must stop
  matching). No hard deletes of clinical rows — same soft-delete rule.
