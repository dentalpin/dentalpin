"""ImportJobService — orchestrates upload, validate, preview, execute.

The state machine:

    uploaded → validating → validated → previewing → executing → completed
                                                              \\→ failed

Validate, preview and execute all run as BackgroundTasks so the HTTP
endpoints return immediately. Their progress + errors land back in
the ImportJob row, which the UI polls.

Idempotency for ``execute`` is delegated to the mappers via the
:class:`EntityMapping` table — re-running execute on a job that already
completed is a no-op for rows already mapped.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plugins import module_registry
from app.database import async_session_maker

from .dpmf import DpmfHandle, open_dpmf
from .dpmf.crypto import DpmeError
from .dpmf.reader import DpmfFormatError
from .events import (
    publish_entity_persisted,
    publish_job_completed,
    publish_job_failed,
    publish_job_started,
)
from .mappers import (
    FALLBACK_MAPPER,
    MAPPERS,
    MapperContext,
    MappingResolver,
    ProfessionalFilterOptions,
)
from .models import EntityMapping, FileStaging, ImportJob, ImportWarning
from .schemas import (
    EntityPreview,
    FilesManifestSummary,
    PreviewResponse,
    PreviewSample,
    ProfessionalPreviewBreakdown,
    WarningView,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Refuse files whose major exceeds this. v0.1 supports 0.x only.
_SUPPORTED_MAJOR = 0
# Sample rows per entity in the preview response.
_PREVIEW_SAMPLE_SIZE = 5
# Commit every N entities so a restart can resume close to where it
# stopped. Mappers are idempotent so larger batches just waste rework
# on resume, not consistency.
_COMMIT_BATCH = 500


class ImportJobService:
    """All business logic for the DPMF importer."""

    # ---- create / upload --------------------------------------------------

    @staticmethod
    async def create_job(
        db: AsyncSession,
        *,
        clinic_id: UUID,
        user_id: UUID,
        original_filename: str,
        staged_path: Path,
        file_size: int,
    ) -> ImportJob:
        job = ImportJob(
            clinic_id=clinic_id,
            created_by=user_id,
            status="uploaded",
            original_filename=original_filename,
            file_path=str(staged_path),
            file_size=file_size,
        )
        db.add(job)
        await db.flush()
        return job

    @staticmethod
    async def get_job(db: AsyncSession, clinic_id: UUID, job_id: UUID) -> ImportJob | None:
        result = await db.execute(
            select(ImportJob).where(ImportJob.id == job_id, ImportJob.clinic_id == clinic_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_jobs(
        db: AsyncSession, clinic_id: UUID, page: int, page_size: int
    ) -> tuple[list[ImportJob], int]:
        page_size = min(max(page_size, 1), 100)
        page = max(page, 1)
        offset = (page - 1) * page_size
        total = (
            await db.execute(
                select(func.count(ImportJob.id)).where(ImportJob.clinic_id == clinic_id)
            )
        ).scalar() or 0
        rows = await db.execute(
            select(ImportJob)
            .where(ImportJob.clinic_id == clinic_id)
            .order_by(ImportJob.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(rows.scalars().all()), total

    # ---- validate ---------------------------------------------------------

    @staticmethod
    async def validate(db: AsyncSession, job: ImportJob, *, passphrase: str | None) -> ImportJob:
        """Open the file (decrypt/decompress), populate `_meta` columns,
        recompute and compare the integrity hash."""
        job.status = "validating"
        await db.flush()

        try:
            with open_dpmf(Path(job.file_path), passphrase=passphrase) as handle:
                meta = handle.meta
                ImportJobService._fill_meta(job, meta)
                ImportJobService._check_format_version(meta)
                computed = handle.recompute_integrity_hash()
                job.integrity_hash_computed = computed
                declared = handle.declared_integrity_hash()
                if declared and declared != computed:
                    raise DpmfFormatError(
                        f"integrity hash mismatch: declared={declared} computed={computed}"
                    )
                # Populate total_entities for progress UI.
                counts = handle.entity_counts()
                job.total_entities = sum(counts.values())
                job.status = "validated"
        except (DpmeError, DpmfFormatError) as exc:
            job.status = "failed"
            job.error = str(exc)
            logger.warning("DPMF validation failed for job %s: %s", job.id, exc)
        except Exception as exc:
            job.status = "failed"
            job.error = f"unexpected validation error: {exc}"
            logger.exception("Unexpected DPMF validation error for job %s", job.id)
        await db.flush()
        return job

    @staticmethod
    def _fill_meta(job: ImportJob, meta: dict[str, str]) -> None:
        job.source_system = meta.get("source_system")
        job.source_adapter_version = meta.get("source_adapter_version")
        job.exporter_tool = meta.get("exporter_tool")
        job.exporter_version = meta.get("exporter_version")
        job.format_version = meta.get("format_version")
        job.tenant_label = meta.get("tenant_label")
        job.integrity_hash_declared = meta.get("integrity_hash")

    @staticmethod
    def _check_format_version(meta: dict[str, str]) -> None:
        version = meta.get("format_version", "")
        try:
            major = int(version.split(".", 1)[0])
        except (ValueError, IndexError) as exc:
            raise DpmfFormatError(f"missing or invalid format_version: {version!r}") from exc
        if major > _SUPPORTED_MAJOR:
            raise DpmfFormatError(
                f"DPMF format_version {version} not supported (supports {_SUPPORTED_MAJOR}.x)"
            )

    # ---- preview ----------------------------------------------------------

    @staticmethod
    async def preview(
        db: AsyncSession, job: ImportJob, *, passphrase: str | None
    ) -> PreviewResponse:
        """Read entity counts, sample rows, warnings, _files summary.

        Reads the DPMF in read-only mode; no DentalPin rows are created.
        """
        if job.status not in {"validated", "previewing", "completed"}:
            raise ValueError(f"job {job.id} cannot be previewed from status {job.status}")
        job.status = "previewing"
        await db.flush()

        with open_dpmf(Path(job.file_path), passphrase=passphrase) as handle:
            previews = ImportJobService._build_entity_previews(handle)
            warnings = ImportJobService._build_warnings(handle)
            files = ImportJobService._build_files_summary(handle)
            verifactu_detected = _detect_verifactu_data(handle)

        verifactu_installed = module_registry.is_loaded("verifactu")

        from .schemas import ImportJobResponse

        return PreviewResponse(
            job=ImportJobResponse.model_validate(job),
            entities=previews,
            warnings=warnings,
            files=files,
            verifactu_data_detected=verifactu_detected,
            verifactu_module_installed=verifactu_installed,
        )

    @staticmethod
    def _build_entity_previews(handle: DpmfHandle) -> list[EntityPreview]:
        previews: list[EntityPreview] = []
        for entity_type, count in handle.entity_counts().items():
            samples: list[PreviewSample] = []
            breakdown: ProfessionalPreviewBreakdown | None = None
            cutoff_24m = date.today().replace(year=date.today().year - 2)
            if entity_type == "professional":
                breakdown = ProfessionalPreviewBreakdown()
            for i, row in enumerate(handle.entity_iter(entity_type)):
                canonical_uuid, source_id, _src_system, payload_json, _raw, _ts = row
                try:
                    payload = json.loads(payload_json)
                except json.JSONDecodeError:
                    payload = {"_decode_error": True}
                if i < _PREVIEW_SAMPLE_SIZE:
                    samples.append(
                        PreviewSample(
                            canonical_uuid=canonical_uuid,
                            source_id=source_id,
                            payload=payload,
                        )
                    )
                if breakdown is not None:
                    _accumulate_professional_breakdown(
                        breakdown,
                        payload=payload,
                        source_id=source_id,
                        cutoff_24m=cutoff_24m,
                    )
            previews.append(
                EntityPreview(
                    entity_type=entity_type,
                    declared_count=count,
                    samples=samples,
                    professional_breakdown=breakdown,
                )
            )
        return previews

    @staticmethod
    def _build_warnings(handle: DpmfHandle) -> list[WarningView]:
        return [
            WarningView(
                severity=row[2],
                code=row[3],
                message=row[4],
                entity_type=row[0],
                source_id=row[1],
            )
            for row in handle.warnings_iter()
        ]

    @staticmethod
    def _build_files_summary(handle: DpmfHandle) -> FilesManifestSummary:
        total = 0
        with_sha = 0
        for row in handle.files_iter():
            total += 1
            if row[5]:
                with_sha += 1
        return FilesManifestSummary(
            total=total, with_sha256=with_sha, without_sha256=total - with_sha
        )

    # ---- execute ----------------------------------------------------------

    @staticmethod
    async def execute_in_background(
        job_id: UUID,
        clinic_id: UUID,
        *,
        passphrase: str | None,
        import_fiscal_compliance: bool,
        execute_options: dict[str, Any] | None = None,
    ) -> None:
        """Top-level entry point for the BackgroundTask.

        Owns its own DB session so the original request handler's
        session can return immediately. Errors set ``status='failed'``
        and publish ``migration.job.failed`` — they never bubble to the
        client (we are detached from the request).
        """
        async with async_session_maker() as session:
            try:
                # Row-level lock: blocks a concurrent BackgroundTask from
                # transitioning the same job to ``executing`` twice. The
                # status check below runs against the locked snapshot, so
                # only one task can win the race.
                result = await session.execute(
                    select(ImportJob).where(ImportJob.id == job_id).with_for_update()
                )
                job = result.scalar_one_or_none()
                if job is None:
                    logger.error("execute: job %s missing", job_id)
                    return
                # ``executing`` is excluded on purpose — re-entry while
                # another task is mid-pipeline would race against the
                # batch counter and the entity-mapping inserts. We
                # allow ``failed`` so the operator can resume after
                # fixing whatever blocked the previous run; the resolver
                # short-circuits on entities already mapped, so the
                # re-run only does the missing tail.
                if job.status not in {"validated", "previewing", "completed", "failed"}:
                    logger.error("execute: job %s in status %s — refusing", job.id, job.status)
                    return
                if job.clinic_id != clinic_id:
                    logger.error(
                        "execute: clinic mismatch job=%s expected=%s actual=%s",
                        job.id,
                        clinic_id,
                        job.clinic_id,
                    )
                    return

                job.status = "executing"
                job.started_at = datetime.now(UTC)
                job.completed_at = None
                # Re-executing a ``completed`` job restarts the progress
                # counter — mappers are idempotent (resolver short-circuit
                # at the top of each ``apply``), so accumulating the
                # previous run's counter would double-count without doing
                # any actual work.
                job.processed_entities = 0
                job.last_checkpoint = None
                job.import_fiscal_compliance = import_fiscal_compliance
                job.execute_options = execute_options
                job.error = None
                # Drop warnings from the previous run so the audit log
                # shows only the latest execution. Without this prune,
                # every re-run doubles ``non_clinical_entry`` /
                # ``unmapped_tipo_odg`` rows even though mappers were
                # idempotent — the warning emission itself was the only
                # non-idempotent path.
                await session.execute(delete(ImportWarning).where(ImportWarning.job_id == job.id))
                await session.commit()

                await publish_job_started(job.id, job.clinic_id)
                await ImportJobService._run_pipeline(session, job, passphrase=passphrase)

                job.status = "completed"
                job.completed_at = datetime.now(UTC)
                await session.commit()
                warnings_count = (
                    await session.execute(
                        select(func.count(ImportWarning.id)).where(ImportWarning.job_id == job.id)
                    )
                ).scalar() or 0
                await publish_job_completed(
                    job.id, job.clinic_id, job.total_entities, int(warnings_count)
                )
            except Exception as exc:
                await session.rollback()
                logger.exception("execute pipeline crashed for job %s", job_id)
                async with async_session_maker() as failure_session:
                    job = await ImportJobService.get_job_unscoped(failure_session, job_id)
                    if job is not None:
                        job.status = "failed"
                        job.error = str(exc)
                        await failure_session.commit()
                        await publish_job_failed(job.id, job.clinic_id, str(exc))

    @staticmethod
    async def get_job_unscoped(db: AsyncSession, job_id: UUID) -> ImportJob | None:
        result = await db.execute(select(ImportJob).where(ImportJob.id == job_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def _run_pipeline(db: AsyncSession, job: ImportJob, *, passphrase: str | None) -> None:
        """Walk the DPMF in topological order, dispatch to mappers."""
        from .dpmf.iter import ordered_entity_types

        resolver = MappingResolver(db=db, clinic_id=job.clinic_id, job_id=job.id)
        # Bulk-load any pre-existing ``entity_mappings`` for this clinic
        # into the resolver cache so re-executes (or resumes after a
        # failed/killed run) don't pay 1 DB SELECT per already-mapped
        # entity. On a 1.27 M-row Gesdén dataset this collapses the
        # idempotency check from ~5 ms × 1 M to one SELECT + in-memory
        # dict lookups.
        await resolver.preload_cache()
        logger.info(
            "resolver cache preloaded: %d entries (%d skipped sentinels)",
            len(resolver._cache),
            len(resolver._skipped_cache),
        )
        ctx = MapperContext(
            db=db,
            clinic_id=job.clinic_id,
            job_id=job.id,
            resolver=resolver,
            import_fiscal_compliance=job.import_fiscal_compliance,
            created_by=job.created_by,
            professional_filters=_build_filter_options(job.execute_options),
        )

        with open_dpmf(Path(job.file_path), passphrase=passphrase) as handle:
            # Expose the handle to mappers that need a sibling-row
            # pre-pass (e.g. the applied_treatment shadow-pairing
            # logic). Mappers that don't care simply ignore it.
            ctx.handle = handle
            entity_types = ordered_entity_types(list(handle.entity_counts().keys()))

            for entity_type in entity_types:
                mapper = MAPPERS.get(entity_type, FALLBACK_MAPPER)
                processed_in_batch = 0
                for row in handle.entity_iter(entity_type):
                    canonical_uuid, source_id, source_system, payload_json, raw_json, _ts = row
                    try:
                        payload = json.loads(payload_json)
                        raw = json.loads(raw_json)
                    except json.JSONDecodeError as exc:
                        await ImportJobService._record_warning(
                            db,
                            job.id,
                            entity_type,
                            source_id,
                            severity="error",
                            code="payload.decode_error",
                            message=f"JSON decode failed: {exc}",
                        )
                        continue

                    # Savepoint per entity so a half-flushed mapper (e.g.
                    # ``Treatment`` added but ``TreatmentTooth`` flush
                    # crashed) rolls back to a clean snapshot instead of
                    # leaving an orphan row that the next batch commit
                    # would persist. ``begin_nested`` issues a SAVEPOINT;
                    # exiting the ``with`` block with an exception
                    # releases it.
                    try:
                        async with db.begin_nested():
                            await mapper.apply(
                                ctx,
                                entity_type=entity_type,
                                payload=payload,
                                raw=raw,
                                canonical_uuid=canonical_uuid,
                                source_id=source_id,
                                source_system=source_system,
                            )
                    except Exception as exc:
                        # Savepoint already rolled back. One entity blowing
                        # up does not fail the whole job — surface it as a
                        # warning and continue. The op gets a single
                        # "X warnings" badge to act on.
                        logger.warning(
                            "mapper %s failed for %s/%s: %s",
                            mapper.__class__.__name__,
                            entity_type,
                            source_id,
                            exc,
                        )
                        # Recorded on the outer session (still alive after
                        # the savepoint rollback) so the warning survives
                        # the next batch commit.
                        await ImportJobService._record_warning(
                            db,
                            job.id,
                            entity_type,
                            source_id,
                            severity="error",
                            code="mapper.failed",
                            message=str(exc),
                        )

                    processed_in_batch += 1
                    if processed_in_batch >= _COMMIT_BATCH:
                        # Counter bump + checkpoint + commit happen
                        # together, once per batch, in the main session.
                        # The "relaxed counter" semantics in the original
                        # design exploded into 1 fresh-session COMMIT per
                        # entity (~25 ms each) — ~9 h for 1.27 M rows.
                        # Batching lifts throughput to ~200-500 ent/s.
                        job.processed_entities = job.processed_entities + processed_in_batch
                        job.last_checkpoint = {
                            "entity_type": entity_type,
                            "after_canonical_uuid": canonical_uuid,
                        }
                        await db.commit()
                        await publish_entity_persisted(job.id, entity_type, processed_in_batch)
                        processed_in_batch = 0
                # End-of-entity flush: persist the remaining tail counter
                # alongside the natural commit boundary, then emit one
                # progress event covering the trailing rows.
                if processed_in_batch:
                    job.processed_entities = job.processed_entities + processed_in_batch
                await db.commit()
                if processed_in_batch:
                    await publish_entity_persisted(job.id, entity_type, processed_in_batch)

            # Ingest the DPMF's own _files manifest into our staging table.
            # The document mapper already created one staging row per
            # PatientDocument entity; the manifest provides the canonical
            # set of files the sync agent will upload. We persist every
            # row from _files so the sync agent can match by sha256 even
            # for files whose parent we have not mapped yet.
            await ImportJobService._persist_files_manifest(db, job, handle)
            # Ingest the DPMF's own _warnings into our audit log so the
            # operator sees the same issues the extractor surfaced.
            await ImportJobService._persist_dpmf_warnings(db, job, handle)
            await db.commit()

            # Post-pipeline recalculation pass: budget_line mappers
            # defer the budget aggregate refresh to here, so the
            # single recalc per budget runs once over the final set
            # of lines instead of N times during ingest (O(N²) per
            # budget). Same idea would apply to other aggregates if
            # they get added.
            await ImportJobService._finalise_migrated_budgets(db, job)
            # Roles for migrated professionals are best-effort at
            # ingest time: Gesdén's ``IdTipoColab`` is often blank, so
            # everyone lands as ``assistant`` — which the agenda
            # filters out by role. Post-pipeline we promote any
            # imported user who actually appears as the responsible
            # clinician on an appointment or applied treatment to
            # ``dentist``, restoring visibility in the agenda board.
            await ImportJobService._finalise_migrated_professional_roles(db, job)

    @staticmethod
    async def _persist_files_manifest(db: AsyncSession, job: ImportJob, handle: DpmfHandle) -> None:
        for row in handle.files_iter():
            canonical_uuid, parent_type, parent_uuid, rel_path, size, sha, mime = row
            # Skip if we already have it (idempotent re-run).
            existing = await db.execute(
                select(FileStaging).where(
                    FileStaging.job_id == job.id,
                    FileStaging.canonical_uuid == canonical_uuid,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            staging = FileStaging(
                clinic_id=job.clinic_id,
                job_id=job.id,
                canonical_uuid=canonical_uuid,
                parent_entity_type=parent_type,
                parent_canonical_uuid=parent_uuid,
                relative_path=rel_path,
                declared_size_bytes=size,
                sha256=sha,
                mime_hint=mime,
                status="pending" if sha else "missing",
            )
            db.add(staging)
            if not sha:
                await ImportJobService._record_warning(
                    db,
                    job.id,
                    parent_type,
                    canonical_uuid,
                    severity="warn",
                    code="file.sha256_missing",
                    message=f"file {rel_path} has no sha256 — cannot be matched",
                )

    @staticmethod
    async def _finalise_migrated_budgets(db: AsyncSession, job: ImportJob) -> None:
        """Apply deferred budget post-processing once the pipeline is done.

        - **Status promotion**: the ``budget_line`` mapper accumulates
          the set of budgets that had at least one source line carrying
          ``applied_treatment_uuid`` (Gesdén's "the patient acted on
          this presupuesto" signal). Promote those drafts to ``accepted``
          in one UPDATE instead of one per line.
        - **Aggregate recalc**: budget_line mappers skip the per-row
          ``_recalculate_totals`` to keep the ingest loop O(N) instead
          of O(N²) per budget — the price is that
          ``Budget.subtotal``/``discount``/``tax``/``total`` are stale
          until this pass runs. We restrict the recalc to budgets whose
          ``BudgetItem`` rows resolve back to a migration-import
          ``entity_mappings`` row from this job.
        """
        from app.modules.budget.models import Budget, BudgetItem
        from app.modules.budget.service import BudgetService

        # Bulk status promotion before recalc — the totals computation
        # walks BudgetItem regardless of Budget.status, so order is
        # irrelevant for arithmetic, but doing the UPDATE first keeps
        # the SELECT for recalc cheap (no extra status read needed).
        line_mapper = MAPPERS.get("budget_line")
        accept_pending: set = getattr(line_mapper, "_budgets_to_accept", set())
        if accept_pending:
            pending = list(accept_pending)
            for batch_start in range(0, len(pending), 500):
                batch = pending[batch_start : batch_start + 500]
                await db.execute(
                    Budget.__table__.update()
                    .where(
                        Budget.clinic_id == job.clinic_id,
                        Budget.id.in_(batch),
                        Budget.status == "draft",
                    )
                    .values(status="accepted", accepted_via="manual")
                )
            await db.commit()
            logger.info(
                "post-pipeline: promoted %d budgets to accepted (job %s)",
                len(pending),
                job.id,
            )
            accept_pending.clear()

        # Treatment ↔ BudgetItem back-fill. Gesdén overwhelmingly
        # emits the forward link on the budget_line side
        # (``payload.applied_treatment_uuid``), so we collect those
        # pairs during budget_line ingest and resolve them here once
        # the applied_treatment mappings exist.
        pending_links: list = getattr(line_mapper, "_pending_treatment_links", [])
        if pending_links:
            from app.modules.odontogram.models import Treatment as _Treatment
            from app.modules.treatment_plan.models import PlannedTreatmentItem

            patched = 0
            for batch_start in range(0, len(pending_links), 500):
                batch = pending_links[batch_start : batch_start + 500]
                applied_uuids = list({uuid for _, uuid in batch})
                # One round-trip pulls all PlannedTreatmentItem.id +
                # PlannedTreatmentItem.treatment_id for the batch.
                rows = await db.execute(
                    select(
                        EntityMapping.source_canonical_uuid,
                        EntityMapping.dentalpin_id,
                    ).where(
                        EntityMapping.clinic_id == job.clinic_id,
                        EntityMapping.entity_type == "applied_treatment",
                        EntityMapping.source_canonical_uuid.in_(applied_uuids),
                    )
                )
                plan_item_by_uuid = {r[0]: r[1] for r in rows.all()}
                if not plan_item_by_uuid:
                    continue
                pti_rows = await db.execute(
                    select(PlannedTreatmentItem.id, PlannedTreatmentItem.treatment_id).where(
                        PlannedTreatmentItem.id.in_(plan_item_by_uuid.values())
                    )
                )
                treatment_by_plan_item = {r[0]: r[1] for r in pti_rows.all()}
                for budget_item_id, applied_uuid in batch:
                    plan_item_id = plan_item_by_uuid.get(applied_uuid)
                    if plan_item_id is None:
                        continue
                    treatment_id = treatment_by_plan_item.get(plan_item_id)
                    if treatment_id is None:
                        continue
                    await db.execute(
                        BudgetItem.__table__.update()
                        .where(
                            BudgetItem.id == budget_item_id,
                            BudgetItem.clinic_id == job.clinic_id,
                        )
                        .values(treatment_id=treatment_id)
                    )
                    await db.execute(
                        _Treatment.__table__.update()
                        .where(
                            _Treatment.id == treatment_id,
                            _Treatment.clinic_id == job.clinic_id,
                            _Treatment.budget_item_id.is_(None),
                        )
                        .values(budget_item_id=budget_item_id)
                    )
                    patched += 1
            await db.commit()
            logger.info(
                "post-pipeline: linked %d BudgetItem ↔ Treatment pairs (job %s)",
                patched,
                job.id,
            )
            pending_links.clear()

        result = await db.execute(
            select(BudgetItem.budget_id)
            .join(
                EntityMapping,
                (EntityMapping.dentalpin_id == BudgetItem.id)
                & (EntityMapping.entity_type == "budget_line"),
            )
            .where(
                EntityMapping.job_id == job.id,
                EntityMapping.clinic_id == job.clinic_id,
            )
            .distinct()
        )
        budget_ids = [row[0] for row in result.all()]
        if not budget_ids:
            return
        for batch_start in range(0, len(budget_ids), 200):
            batch = budget_ids[batch_start : batch_start + 200]
            budgets = (await db.execute(select(Budget).where(Budget.id.in_(batch)))).scalars().all()
            for budget in budgets:
                await BudgetService._recalculate_totals(db, budget)
            await db.commit()
        logger.info(
            "post-pipeline: recalculated totals for %d budgets (job %s)",
            len(budget_ids),
            job.id,
        )

    @staticmethod
    async def _finalise_migrated_professional_roles(db: AsyncSession, job: ImportJob) -> None:
        """Upgrade migrated users with clinical activity to ``dentist``.

        Why: Gesdén's ``TColabos.IdTipoColab`` is often blank, and many
        clinics drive the agenda through ``TUsuAgd`` columns whose
        canonical professional rows carry no role hint. dental-bridge
        therefore emits ``role=other`` for those users, which DentalPin
        maps to ``assistant``. The agenda's ``/professionals`` endpoint
        only returns ``dentist``/``hygienist`` memberships — assistants
        disappear from the dropdown — so the migrated appointments
        render to nobody and the operator perceives them as "missing".

        Fix: after the pipeline runs, any user that this job mapped AND
        that now owns at least one ``Appointment`` or ``Treatment``
        (i.e. shows up as the responsible clinician) is promoted to
        ``dentist`` in this clinic's ``ClinicMembership``. Admins still
        explicitly assigned roles (``admin``/``hygienist``/``dentist``/
        ``receptionist``) are left untouched — only the ``assistant``
        catch-all is moved up. Idempotent.
        """
        # Local imports so this module stays import-safe in test
        # contexts that may stub out auth.
        from app.core.auth.models import ClinicMembership
        from app.modules.agenda.models import Appointment
        from app.modules.odontogram.models import Treatment

        # Users mapped by this job.
        user_ids_q = await db.execute(
            select(EntityMapping.dentalpin_id).where(
                EntityMapping.job_id == job.id,
                EntityMapping.entity_type.in_(("user", "professional")),
            )
        )
        user_ids = {row[0] for row in user_ids_q.all()}
        if not user_ids:
            return

        # Users that actually appear as the responsible clinician on
        # something post-import.
        appt_users = {
            row[0]
            for row in (
                await db.execute(
                    select(Appointment.professional_id).where(
                        Appointment.clinic_id == job.clinic_id,
                        Appointment.professional_id.in_(user_ids),
                    )
                )
            ).all()
        }
        treat_users = {
            row[0]
            for row in (
                await db.execute(
                    select(Treatment.performed_by).where(
                        Treatment.clinic_id == job.clinic_id,
                        Treatment.performed_by.is_not(None),
                        Treatment.performed_by.in_(user_ids),
                    )
                )
            ).all()
        }
        clinical_users = appt_users | treat_users
        if not clinical_users:
            return

        # Promote only the ``assistant`` rows — never override an
        # explicit clinical role assignment.
        result = await db.execute(
            update(ClinicMembership)
            .where(
                ClinicMembership.clinic_id == job.clinic_id,
                ClinicMembership.user_id.in_(clinical_users),
                ClinicMembership.role == "assistant",
            )
            .values(role="dentist", is_professional=True)
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        promoted = int(result.rowcount or 0)
        if promoted:
            logger.info(
                "post-pipeline: promoted %d assistant→dentist memberships (job %s)",
                promoted,
                job.id,
            )

    @staticmethod
    async def _persist_dpmf_warnings(db: AsyncSession, job: ImportJob, handle: DpmfHandle) -> None:
        for row in handle.warnings_iter():
            entity_type, source_id, severity, code, message, raw_data = row
            raw = None
            if raw_data:
                try:
                    raw = json.loads(raw_data)
                except json.JSONDecodeError:
                    raw = {"_decode_error": True, "raw": raw_data}
            db.add(
                ImportWarning(
                    job_id=job.id,
                    entity_type=entity_type,
                    source_id=source_id,
                    severity=severity,
                    code=f"dpmf.{code}",
                    message=message,
                    raw_data=raw,
                )
            )

    @staticmethod
    async def _record_warning(
        db: AsyncSession,
        job_id: UUID,
        entity_type: str | None,
        source_id: str | None,
        *,
        severity: str,
        code: str,
        message: str,
    ) -> None:
        db.add(
            ImportWarning(
                job_id=job_id,
                entity_type=entity_type,
                source_id=source_id,
                severity=severity,
                code=code,
                message=message,
            )
        )

    # ---- warnings ---------------------------------------------------------

    @staticmethod
    async def list_warnings(
        db: AsyncSession,
        job_id: UUID,
        page: int,
        page_size: int,
        *,
        severity: str | None = None,
        entity_type: str | None = None,
    ) -> tuple[list[ImportWarning], int]:
        page_size = min(max(page_size, 1), 200)
        page = max(page, 1)
        offset = (page - 1) * page_size
        conditions = [ImportWarning.job_id == job_id]
        if severity:
            conditions.append(ImportWarning.severity == severity)
        if entity_type:
            conditions.append(ImportWarning.entity_type == entity_type)
        total = (
            await db.execute(select(func.count(ImportWarning.id)).where(*conditions))
        ).scalar() or 0
        rows = await db.execute(
            select(ImportWarning)
            .where(*conditions)
            .order_by(ImportWarning.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        return list(rows.scalars().all()), total


def _accumulate_professional_breakdown(
    breakdown: ProfessionalPreviewBreakdown,
    *,
    payload: dict[str, Any],
    source_id: str,
    cutoff_24m: date,
) -> None:
    """Tally per-signal counts for one professional payload.

    Called once per row inside :meth:`_build_entity_previews` so the UI
    can show "X total / Y deactivated / Z stale" before the operator
    commits the execute step. The 24-month window is the default; the UI
    can recompute other windows client-side from the sample data, but
    this gross summary is enough to size the slider.
    """
    if bool(payload.get("deactivated")):
        breakdown.deactivated_count += 1
    if source_id.startswith("usuagd:"):
        breakdown.agenda_orphan_count += 1
    last_activity = payload.get("last_activity_at")
    if last_activity is None:
        breakdown.no_activity_count += 1
    else:
        try:
            parsed = date.fromisoformat(str(last_activity)[:10])
        except ValueError:
            parsed = None
        if parsed is None or parsed < cutoff_24m:
            breakdown.stale_24m_count += 1
    role = (payload.get("role") or "other").lower()
    breakdown.by_role[role] = breakdown.by_role.get(role, 0) + 1


def _build_filter_options(execute_options: dict[str, Any] | None) -> ProfessionalFilterOptions:
    """Hydrate :class:`ProfessionalFilterOptions` from the job's JSONB blob.

    Legacy jobs (executed before the column existed) have ``None`` here
    and fall back to safe defaults — same shape as :class:`ExecuteRequest`.
    """
    if not execute_options:
        return ProfessionalFilterOptions()
    return ProfessionalFilterOptions(
        min_activity_months=int(execute_options.get("professional_min_activity_months", 24)),
        exclude_agenda_orphans=bool(
            execute_options.get("professional_exclude_agenda_orphans", True)
        ),
        exclude_inactive_in_source=bool(
            execute_options.get("professional_exclude_inactive_in_source", True)
        ),
        exclude_non_clinical_roles=bool(
            execute_options.get("professional_exclude_non_clinical_roles", False)
        ),
    )


def _detect_verifactu_data(handle: DpmfHandle) -> bool:
    """Scan fiscal_document payloads for Spanish legal hash fields."""
    if "fiscal_document" not in handle.entity_counts():
        return False
    for row in handle.entity_iter("fiscal_document"):
        _uuid, _src, _sys, payload_json, _raw, _ts = row
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            continue
        for key in ("legal_hash", "hash", "hash_control", "atcud", "qr_code"):
            if payload.get(key):
                return True
    return False
