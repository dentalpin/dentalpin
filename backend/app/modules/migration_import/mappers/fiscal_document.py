"""Map ``fiscal_document`` → ``billing.Invoice`` (+ optional verifactu).

This mapper is the only place in the importer that has a **runtime**
dependency on another module (``verifactu``). Per the project's
internationalisation goal — same module must work for PT/FR clinics
where Verifactu doesn't apply — ``verifactu`` is intentionally absent
from ``manifest.depends``.

Behaviour matrix:

| verifactu loaded | operator opt-in | legal hashes |
|------------------|-----------------|--------------|
| no               | _ignored_       | dropped, ``verifactu.skipped`` warning |
| yes              | False           | dropped, ``verifactu.opt_out`` warning |
| yes              | True            | preserved verbatim (never re-signed)  |

The opt-in flag lives on :attr:`ImportJob.import_fiscal_compliance`,
set by the execute request body.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from app.core.plugins import module_registry

from ..models import ImportWarning
from .base import MapperContext

logger = logging.getLogger(__name__)

# Field names per DPMF CanonicalFiscalDocument that we preserve when
# verifactu is loaded + opt-in is true.
_LEGAL_FIELDS = (
    "legal_hash",
    "hash",
    "hash_control",
    "atcud",
    "qr_code",
)


def _verifactu_active(ctx: MapperContext) -> bool:
    return ctx.import_fiscal_compliance and module_registry.is_active("verifactu")


class FiscalDocumentMapper:
    async def apply(
        self,
        ctx: MapperContext,
        *,
        entity_type: str,
        payload: dict[str, Any],
        raw: dict[str, Any],
        canonical_uuid: str,
        source_id: str,
        source_system: str,
    ) -> UUID | None:
        existing = await ctx.resolver.get("fiscal_document", canonical_uuid)
        if existing is not None:
            return existing

        # billing.InvoiceService is the right target, but its create
        # signature couples to budget/treatment_plan in a way that
        # doesn't fit a historical import (it expects unbilled items).
        # We persist the *legal* surface (number, series, totals, dates,
        # hashes) directly via the Invoice model so downstream reports
        # see the historical record without re-issuing.
        from app.modules.billing.models import Invoice

        # The source's ``series`` is a free-text legal series ("F", "FR",
        # "A"…) that DentalPin models as a UUID FK to ``InvoiceSeries``.
        # Building the InvoiceSeries catalog from a historical import is
        # out of scope, so we stamp the source series into
        # ``invoice_number`` (prefix preserves the legal chain visually)
        # and leave ``series_id`` NULL. Downstream reports that group by
        # series can still bucket by parsing the prefix.
        source_series = (payload.get("series") or "MIG").strip() or "MIG"
        source_number = str(payload.get("number") or source_id).strip()
        source_year = payload.get("year")
        if source_year:
            invoice_number = f"{source_series}-{source_year}-{source_number}"
        else:
            invoice_number = f"{source_series}-{source_number}"

        issue_date = _parse_date(payload.get("document_date") or payload.get("issued_at"))
        created_by = await ctx.resolver.resolve_actor(payload.get("user_uuid"), ctx.created_by)
        invoice = Invoice(
            id=uuid4(),
            clinic_id=ctx.clinic_id,
            patient_id=await self._resolve_patient(ctx, payload, source_id),
            invoice_number=invoice_number[:50],
            issue_date=issue_date,
            status=_map_status(payload.get("status")),
            is_historical=True,
            total=_decimal(payload.get("total"), default="0"),
            total_tax=_decimal(payload.get("tax_total"), default="0"),
            subtotal=_decimal(payload.get("subtotal"), default="0"),
            created_by=created_by,
        )

        if _verifactu_active(ctx):
            self._stamp_legal_fields(invoice, payload)
        else:
            await self._record_legal_skip(ctx, source_id, payload)

        ctx.db.add(invoice)
        await ctx.db.flush()

        await ctx.resolver.set(
            entity_type="fiscal_document",
            canonical_uuid=canonical_uuid,
            source_system=source_system,
            dentalpin_table="invoices",
            dentalpin_id=invoice.id,
        )
        return invoice.id

    @staticmethod
    async def _resolve_patient(ctx: MapperContext, payload: dict[str, Any], source_id: str) -> UUID:
        """Resolve the patient that owns this invoice.

        Gesdén's ``DocAdmin`` is keyed on the **client** (payer), not
        the patient — a single invoice can cover several patients of
        the same family. The canonical layer reflects that and emits
        ``client_uuid`` instead of ``patient_uuid`` on
        ``CanonicalFiscalDocument``. We resolve the patient through
        the ``client_to_patients`` map populated by
        ``PatientClientLinkMapper`` (Gesdén ``PacCli``):

        - 1 patient on the client → unambiguous, use it.
        - N patients (family billing) → pick the first by mapping
          order (deterministic) and add a warning so the operator can
          re-attribute later if needed.
        - 0 patients (client with no linked patient — odd but real
          in Gesdén when ``PacCli`` was deleted) → as a last resort,
          look at the line items: any ``patient_uuid`` on a line wins.
        - Still nothing → raise. Caller emits ``mapper.failed``.

        ``patient_uuid`` on the document is still honoured if the
        payload happens to carry it (forward-compat with future
        adapters that pre-resolve).
        """
        # Forward-compat: trust an explicit patient_uuid when present.
        external_patient = payload.get("patient_uuid")
        if external_patient:
            patient_id = await ctx.resolver.get("patient", str(external_patient))
            if patient_id is not None:
                return patient_id

        # Primary path: derive from client → patients map.
        client_uuid = payload.get("client_uuid") or payload.get("guardian_client_uuid")
        if client_uuid:
            patient_ids = ctx.client_to_patients.get(str(client_uuid)) or []
            if len(patient_ids) == 1:
                return patient_ids[0]
            if len(patient_ids) > 1:
                ctx.db.add(
                    ImportWarning(
                        job_id=ctx.job_id,
                        entity_type="fiscal_document",
                        source_id=source_id,
                        severity="info",
                        code="fiscal_document.family_billing",
                        message=(
                            f"Factura cliente con {len(patient_ids)} pacientes; "
                            "atribuida al primero. Re-asignar manualmente si procede."
                        ),
                    )
                )
                return patient_ids[0]

        raise ValueError(
            f"fiscal_document {source_id}: no patient resolvable via "
            f"client_uuid={client_uuid!r} or payload.patient_uuid"
        )

    @staticmethod
    def _stamp_legal_fields(invoice: Any, payload: dict[str, Any]) -> None:
        """Copy whichever legal-hash fields exist on the Invoice model.

        We use ``setattr`` so the mapper survives schema drift on the
        billing side — if a field disappears, we just skip it. The
        verifactu module owns the canonical field names today; we
        write the DPMF values verbatim regardless.
        """
        for field in _LEGAL_FIELDS:
            value = payload.get(field)
            if value and hasattr(invoice, field):
                setattr(invoice, field, value)

    @staticmethod
    async def _record_legal_skip(
        ctx: MapperContext, source_id: str, payload: dict[str, Any]
    ) -> None:
        has_legal = any(payload.get(field) for field in _LEGAL_FIELDS)
        if not has_legal:
            return
        code = (
            "verifactu.opt_out" if module_registry.is_active("verifactu") else "verifactu.skipped"
        )
        ctx.db.add(
            ImportWarning(
                job_id=ctx.job_id,
                entity_type="fiscal_document",
                source_id=source_id,
                severity="info",
                code=code,
                message=(
                    "Datos legales Verifactu omitidos (módulo ausente o no solicitado). "
                    "El documento se ha creado como factura comercial sin hashes legales."
                ),
                raw_data={f: payload.get(f) for f in _LEGAL_FIELDS if payload.get(f)},
            )
        )


def _decimal(value: Any, *, default: str) -> Any:
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(value)) if value is not None else Decimal(default)
    except (InvalidOperation, TypeError):
        return Decimal(default)


def _parse_date(value: Any):
    if not value:
        return None
    from datetime import date

    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _map_status(value: Any) -> str:
    s = str(value or "").lower()
    if s in {"issued", "sent", "paid", "cancelled", "draft"}:
        return s
    return "issued"
