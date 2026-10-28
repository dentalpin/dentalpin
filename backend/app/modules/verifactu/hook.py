"""Verifactu implementation of ``BillingComplianceHook``.

Wired in :func:`VerifactuModule.install` via
``BillingHookRegistry.register(VerifactuHook())``. The billing module
discovers it through the registry — no direct import.

Flow on ``on_invoice_issued``:

1. Look up :class:`VerifactuSettings` for the clinic. If missing or
   ``enabled=False`` we return ``{}`` (the module is installed but the
   clinic hasn't activated it).
2. Pessimistically lock the settings row (``SELECT ... FOR UPDATE``)
   to read ``last_huella`` without racing other concurrent issues.
3. Determine the ``TipoFactura`` (F1/F2/R1) and build the XML payload.
4. Compute the ``Huella`` for the chain.
5. Insert a :class:`VerifactuRecord` in ``state="pending"`` with the
   full XML pre-rendered (it will be sent to AEAT by the worker).
6. Update settings ``last_huella``, ``last_record_id`` so the next
   record chains off this one. **Note:** these become the chain head
   immediately even before AEAT confirms — if AEAT rejects we'll need
   ``Subsanación`` resubmits, which use the same hash. This matches
   the AEAT spec (the chain is monotonically growing as records are
   produced, not as records are accepted).
7. Return preliminary compliance data ``{huella, qr_url, state, record_id}``
   to be merged into ``Invoice.compliance_data['ES']``. ``csv`` and
   ``submitted_at`` arrive later when the worker drains the queue.

Subsanación (regenerate_record):

When AEAT rejects a record (``state="rejected"`` / ``"failed_validation"``)
we recompute the XML from current Clinic + Invoice + Settings data and
overwrite the record in place. The previous XML/huella are preserved in
``verifactu_record_attempts`` (RD 1007/2023 art. 8 trazabilidad). The
chain hash invariant is preserved because:

- ``huella_anterior`` is NOT recomputed (still points to the previous
  accepted/produced record).
- ``settings.last_huella`` is updated to the new huella IF the record
  is the chain head — guaranteed by ``validate_before_issue`` which
  blocks issuing new invoices while a rejected record exists.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import Clinic
from app.modules.billing.hooks import BillingComplianceHook

from .models import VerifactuRecord, VerifactuRecordAttempt, VerifactuSettings
from .services import (
    hash_chain,
    iva_classifier,
    qr,
    sistema_informatico,
    vat_mapping,
    xml_builder,
)
from .services.severity import severity_for

if TYPE_CHECKING:
    from app.modules.billing.models import Invoice

logger = logging.getLogger(__name__)

_TZ = ZoneInfo("Europe/Madrid")


@dataclass
class _ComposedRecord:
    payload: xml_builder.RegistroAltaPayload
    xml: str
    huella: str
    huella_anterior: str
    is_first: bool
    qr_url: str
    tipo_factura: str
    tipo_rectificativa: str | None
    serie_numero: str
    fecha_expedicion: Any
    fecha_hora_huso: datetime
    cuota_total: Decimal
    importe_total: Decimal


def _now_madrid() -> datetime:
    return datetime.now(_TZ)


async def _get_or_create_settings(db: AsyncSession, clinic_id) -> VerifactuSettings:
    result = await db.execute(
        select(VerifactuSettings)
        .where(VerifactuSettings.clinic_id == clinic_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = VerifactuSettings(
            clinic_id=clinic_id,
            enabled=False,
            environment="test",
            numero_instalacion=str(uuid4()),
        )
        db.add(settings)
        await db.flush()
    return settings


async def _load_emisor(db: AsyncSession, clinic_id) -> tuple[str, str]:
    """Read clinic identity used as fiscal issuer.

    Returns ``(nif_emisor, nombre_razon_emisor)`` derived from
    ``clinics.tax_id`` and ``clinics.legal_name`` (falling back to
    ``clinics.name`` when no separate legal name is set). Both values
    are normalised: NIF uppercased without whitespace, razón social
    stripped.
    """

    result = await db.execute(
        select(Clinic.tax_id, Clinic.legal_name, Clinic.name).where(Clinic.id == clinic_id)
    )
    row = result.first()
    if row is None:
        return "", ""
    tax_id, legal_name, name = row
    nif = (tax_id or "").strip().upper()
    razon = (legal_name or name or "").strip()
    return nif, razon


def _format_amount(d: Decimal | float) -> Decimal:
    """Round to the cent the way the invoice row itself was rounded.

    ``ROUND_HALF_UP`` (half away from zero) is what PostgreSQL applies
    when it stores a ``NUMERIC(_, 2)`` column, so a half-cent lands on
    the same cent here as it did in ``invoices.total``. The ``Decimal``
    default, ``ROUND_HALF_EVEN``, rounds 9.085 down to 9.08 where the
    stored total is 9.09 — a one-cent gap between the libro fiscal and
    the invoice, inside a hash chain that cannot be rewritten once AEAT
    accepts it. It is also the mode every other fiscal builder in the
    tree already passes explicitly (``sdi_it``, ``nav_online``,
    ``sistema_ts``, ``india_gst``).
    """

    if not isinstance(d, Decimal):
        d = Decimal(str(d))
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _build_desglose(
    invoice: Invoice,
    overrides: dict | None = None,
) -> tuple[list[xml_builder.DesgloseLine], Decimal, Decimal]:
    """Group line items and produce ``DetalleDesglose``.

    Items are grouped by AEAT classification (``CalificacionOperacion``
    + optional ``CausaExencion``) so each desglose entry maps cleanly
    to one AEAT row. ``overrides`` is the per-clinic
    ``{vat_type_id: ClassificationOverride}`` map loaded by
    :func:`vat_mapping.load_overrides`; lines without an override fall
    back to the rate-based heuristic.
    """

    overrides = overrides or {}

    classified: list[tuple[iva_classifier.DesgloseClassification, Decimal, Decimal]] = []
    for item in invoice.items or []:
        vat_rate = Decimal(str(item.vat_rate or 0))
        override = overrides.get(item.vat_type_id) if item.vat_type_id else None
        if override is not None:
            cls = vat_mapping.apply_override(vat_rate=vat_rate, override=override)
        else:
            is_exento = bool(item.vat_exempt_reason) and vat_rate == 0
            cls = iva_classifier.classify(vat_rate=vat_rate, is_exento_sanitario=is_exento)
        line_base = Decimal(str(item.line_subtotal or 0)) - Decimal(str(item.line_discount or 0))
        line_cuota = Decimal(str(item.line_tax or 0))
        classified.append((cls, line_base, line_cuota))

    groups: dict[
        tuple[str, str | None, Decimal | None],
        dict[str, Decimal | iva_classifier.DesgloseClassification],
    ] = {}
    for cls, base, cuota in classified:
        key = (
            cls.calificacion_operacion or "EXENTO",
            cls.causa_exencion,
            cls.tipo_impositivo,
        )
        bucket = groups.setdefault(
            key,
            {"base": Decimal("0"), "cuota": Decimal("0"), "cls": cls},
        )
        bucket["base"] = bucket["base"] + base  # type: ignore[operator]
        bucket["cuota"] = bucket["cuota"] + cuota  # type: ignore[operator]

    lines: list[xml_builder.DesgloseLine] = []
    for bucket in groups.values():
        cls = bucket["cls"]  # type: ignore[assignment]
        is_no_quota = cls.operacion_exenta or cls.calificacion_operacion in ("N1", "N2")
        lines.append(
            xml_builder.DesgloseLine(
                impuesto=cls.impuesto,
                clave_regimen=cls.clave_regimen,
                base_imponible=_format_amount(bucket["base"]),  # type: ignore[arg-type]
                calificacion_operacion=cls.calificacion_operacion,
                operacion_exenta=cls.operacion_exenta,
                causa_exencion=cls.causa_exencion,
                tipo_impositivo=cls.tipo_impositivo,
                cuota_repercutida=None if is_no_quota else _format_amount(bucket["cuota"]),  # type: ignore[arg-type]
            )
        )

    cuota_total = sum((b["cuota"] for b in groups.values()), Decimal("0"))  # type: ignore[misc]
    importe_total = _format_amount(Decimal(str(invoice.total or 0)))
    return lines, _format_amount(cuota_total), importe_total


async def _resolve_id_factura_anterior(
    db: AsyncSession,
    settings: VerifactuSettings,
    nif_emisor: str,
    is_first: bool,
) -> xml_builder.IDFacturaRef | None:
    if is_first or not settings.last_record_id:
        return None
    prev = await db.execute(
        select(VerifactuRecord).where(VerifactuRecord.id == settings.last_record_id)
    )
    prev_rec = prev.scalar_one_or_none()
    if prev_rec is None:
        return None
    return xml_builder.IDFacturaRef(
        nif=nif_emisor,
        num_serie=prev_rec.serie_numero,
        fecha=f"{prev_rec.fecha_expedicion:%d-%m-%Y}",
    )


async def _compose_payload(
    db: AsyncSession,
    *,
    invoice: Invoice,
    settings: VerifactuSettings,
    is_credit_note: bool,
    huella_anterior: str,
    is_first: bool,
    subsanacion: bool = False,
    rechazo_previo: bool = False,
) -> _ComposedRecord:
    """Pure builder: composes the XML payload + huella from inputs.

    Does NOT mutate the database. Used by both the initial issue path
    and the regenerate path.
    """

    nif_emisor, nombre_razon_emisor = await _load_emisor(db, invoice.clinic_id)
    if not nif_emisor:
        raise ValueError(
            "La clínica no tiene CIF/NIF configurado; imposible firmar el registro Verifactu."
        )

    importe_total_raw = Decimal(str(invoice.total or 0))
    tipo_factura = iva_classifier.determine_tipo_factura(
        has_credit_note_for=is_credit_note,
        billing_tax_id=invoice.billing_tax_id,
        importe_total=importe_total_raw,
    )

    overrides = await vat_mapping.load_overrides(db, invoice.clinic_id)
    desglose, cuota_total, importe_total_q = _build_desglose(invoice, overrides)
    fecha_expedicion = invoice.issue_date or _now_madrid().date()
    fecha_hora_huso = _now_madrid()

    huella = hash_chain.fingerprint_alta(
        nif_emisor=nif_emisor,
        num_serie=invoice.invoice_number,
        fecha_expedicion=fecha_expedicion,
        tipo_factura=tipo_factura,
        cuota_total=cuota_total,
        importe_total=importe_total_q,
        huella_anterior=huella_anterior,
        fecha_hora_huso_gen_registro=fecha_hora_huso,
    )

    id_factura_anterior = await _resolve_id_factura_anterior(db, settings, nif_emisor, is_first)

    destinatario = None
    if invoice.billing_tax_id:
        destinatario = xml_builder.Destinatario(
            nombre_razon=invoice.billing_name or "",
            nif=invoice.billing_tax_id,
        )

    facturas_rectificadas: list[xml_builder.IDFacturaRef] = []
    tipo_rectificativa = None
    if is_credit_note:
        tipo_rectificativa = "I"
        original = getattr(invoice, "_verifactu_original", None)
        if original is not None:
            facturas_rectificadas.append(
                xml_builder.IDFacturaRef(
                    nif=nif_emisor,
                    num_serie=original.invoice_number or "",
                    fecha=(f"{original.issue_date:%d-%m-%Y}" if original.issue_date else ""),
                )
            )

    si = sistema_informatico.from_settings(settings)
    payload = xml_builder.RegistroAltaPayload(
        nif_emisor=nif_emisor,
        nombre_razon_emisor=nombre_razon_emisor,
        serie_numero=invoice.invoice_number or "",
        fecha_expedicion=fecha_expedicion,
        tipo_factura=tipo_factura,
        descripcion_operacion=(
            "Servicios odontológicos" if not is_credit_note else "Rectificativa"
        ),
        desglose=desglose,
        cuota_total=cuota_total,
        importe_total=importe_total_q,
        sistema_informatico=si,
        fecha_hora_huso_gen_registro=fecha_hora_huso,
        huella=huella,
        huella_anterior=huella_anterior,
        is_first_record=is_first,
        id_factura_anterior=id_factura_anterior,
        destinatario=destinatario,
        tipo_rectificativa=tipo_rectificativa,
        facturas_rectificadas=facturas_rectificadas,
        subsanacion=subsanacion,
        rechazo_previo=rechazo_previo,
    )

    xml = xml_builder.render_registro_alta(payload)
    qr_url = qr.build_qr_url(
        environment=settings.environment,
        nif=nif_emisor,
        num_serie=invoice.invoice_number or "",
        fecha_expedicion=fecha_expedicion,
        importe_total=importe_total_q,
    )

    return _ComposedRecord(
        payload=payload,
        xml=xml,
        huella=huella,
        huella_anterior=huella_anterior,
        is_first=is_first,
        qr_url=qr_url,
        tipo_factura=tipo_factura,
        tipo_rectificativa=tipo_rectificativa,
        serie_numero=invoice.invoice_number or "",
        fecha_expedicion=fecha_expedicion,
        fecha_hora_huso=fecha_hora_huso,
        cuota_total=cuota_total,
        importe_total=importe_total_q,
    )


async def regenerate_record(
    db: AsyncSession,
    record: VerifactuRecord,
) -> VerifactuRecord:
    """Recompute XML + huella for a rejected record from current data.

    Used to subsanate a rejected record after the user fixed the
    underlying data (clinic NIF, billing party, line items, etc.).
    Sends ``Subsanacion=S`` + ``RechazoPrevio=X`` per AEAT spec.

    Preconditions:
        - ``record.state`` in ``{"rejected", "failed_validation"}``
        - Record is the chain head for its clinic. Enforced by the
          rejected-pending block in :meth:`validate_before_issue`.

    Side effects:
        - Snapshots the previous ``xml_payload`` / ``huella`` to
          ``verifactu_record_attempts`` (RD 1007/2023 art. 8).
        - Mutates the record in place: new XML, new huella, state back
          to ``"pending"``, attempt counter reset.
        - Updates ``settings.last_huella`` if record is chain head.
        - Updates ``Invoice.compliance_data['ES']`` and sets
          ``Invoice.pdf_stale=True``.
    """

    from app.modules.billing.models import Invoice as InvoiceModel

    # Accept rejected, failed_validation, AND failed_transient when the
    # error code points at a business issue (-2 SOAP fault or any 4xxx
    # AEAT validation code). Plain transport failures (-1, 103, -904)
    # are auto-retried by the worker and should not be regenerated
    # manually — same XML still good. Only when AEAT actually pushed
    # back on the data do we re-render.
    code = record.aeat_codigo_error or 0
    is_business_transient = record.state == "failed_transient" and (code == -2 or code >= 1000)
    if record.state not in ("rejected", "failed_validation") and not is_business_transient:
        raise ValueError(
            f"regenerate_record solo aplica a registros rechazados, no a state={record.state!r}"
        )

    invoice_q = await db.execute(
        select(InvoiceModel)
        .where(InvoiceModel.id == record.invoice_id)
        .options(selectinload(InvoiceModel.items))
    )
    invoice = invoice_q.scalar_one_or_none()
    if invoice is None:
        raise ValueError("La factura asociada al registro Verifactu no existe.")

    settings = await _get_or_create_settings(db, record.clinic_id)
    if not settings.enabled:
        raise ValueError("El módulo Verifactu está desactivado para esta clínica.")

    # Snapshot previous attempt for art. 8 trazabilidad. ``attempt_no``
    # debe derivarse del histórico — NO de ``record.submission_attempt``,
    # que se resetea a 0 en cada regenerate y colisionaría con números
    # ya usados por intentos previos.
    if record.xml_payload:
        from sqlalchemy import func as sa_func

        max_q = await db.execute(
            select(sa_func.coalesce(sa_func.max(VerifactuRecordAttempt.attempt_no), 0)).where(
                VerifactuRecordAttempt.record_id == record.id
            )
        )
        attempt_no = (max_q.scalar_one() or 0) + 1
        attempt = VerifactuRecordAttempt(
            record_id=record.id,
            attempt_no=attempt_no,
            xml_payload=record.xml_payload,
            huella=record.huella,
            state=record.state,
            aeat_codigo_error=record.aeat_codigo_error,
            aeat_descripcion_error=record.aeat_descripcion_error,
            aeat_response_xml=record.aeat_response_xml,
            created_at=datetime.now(UTC),
        )
        db.add(attempt)

    is_credit_note = record.record_type == "alta" and record.tipo_rectificativa is not None
    composed = await _compose_payload(
        db,
        invoice=invoice,
        settings=settings,
        is_credit_note=is_credit_note,
        huella_anterior=record.huella_anterior or "",
        is_first=record.is_first_record,
        subsanacion=True,
        rechazo_previo=True,
    )

    is_chain_head = settings.last_record_id == record.id and settings.last_huella == record.huella

    record.xml_payload = composed.xml
    record.huella = composed.huella
    record.tipo_factura = composed.tipo_factura
    record.tipo_rectificativa = composed.tipo_rectificativa
    record.serie_numero = composed.serie_numero
    record.fecha_expedicion = composed.fecha_expedicion
    record.cuota_total = composed.cuota_total
    record.importe_total = composed.importe_total
    record.fecha_hora_huso_gen_registro = composed.fecha_hora_huso.astimezone(UTC)
    record.subsanacion = True
    record.rechazo_previo = True
    record.state = "pending"
    record.submission_attempt = 0
    record.last_attempt_at = None
    record.aeat_csv = None
    record.aeat_estado_envio = None
    record.aeat_estado_registro = None
    record.aeat_codigo_error = None
    record.aeat_descripcion_error = None
    record.aeat_timestamp_presentacion = None
    record.aeat_response_xml = None

    if is_chain_head:
        settings.last_huella = composed.huella

    cd = dict(invoice.compliance_data or {})
    es = dict(cd.get("ES") or {})
    es.update(
        {
            "huella": composed.huella,
            "qr_url": composed.qr_url,
            "state": "pending",
            "tipo_factura": composed.tipo_factura,
            "csv": None,
            "submitted_at": None,
            "error_code": None,
            "error_message": None,
            "severity": severity_for("pending", None),
        }
    )
    cd["ES"] = es
    invoice.compliance_data = cd
    invoice.pdf_stale = True

    await db.flush()
    return record


class VerifactuHook(BillingComplianceHook):
    @property
    def country_code(self) -> str:
        return "ES"

    def get_required_fields(self) -> list[str]:
        # We handle NIF/F1-F2 logic ourselves in validate_before_issue.
        return []

    async def validate_before_issue(self, invoice, db) -> tuple[bool, str | None]:
        settings = await db.execute(
            select(VerifactuSettings).where(VerifactuSettings.clinic_id == invoice.clinic_id)
        )
        s = settings.scalar_one_or_none()
        if s is None or not s.enabled:
            return True, None
        nif_emisor, _ = await _load_emisor(db, invoice.clinic_id)
        if not nif_emisor:
            return (
                False,
                "Configura el CIF/NIF de la clínica antes de emitir con Verifactu.",
            )
        if not s.producer_nif or not s.producer_name:
            return (
                False,
                "Configura el productor del SIF en Verifactu antes de emitir.",
            )
        if s.declaracion_responsable_signed_at is None:
            return (
                False,
                "Falta firmar la declaración responsable del productor del SIF.",
            )

        # F2 cap: simplified invoices ≤ 400 €. >400 € requires NIF (F1).
        if not invoice.credit_note_for_id and not invoice.billing_tax_id:
            if Decimal(str(invoice.total or 0)) > Decimal("400"):
                return (
                    False,
                    "Facturas > 400 € requieren NIF del destinatario para Verifactu (F1).",
                )

        # Block issuing new invoices while a prior record is rejected
        # OR while a transient failure carries a business error code
        # (-2 SOAP fault wrapping a validation error, or any 4xxx
        # AEAT validation code). Guarantees the broken record stays as
        # chain head so regenerate_record never has to re-sign
        # downstream records. Pure transport failures (-1, 103, -904)
        # don't block — the worker retries them automatically and the
        # XML is fine.
        from sqlalchemy import or_

        blocked_q = await db.execute(
            select(VerifactuRecord.id)
            .where(
                VerifactuRecord.clinic_id == invoice.clinic_id,
                or_(
                    VerifactuRecord.state.in_(("rejected", "failed_validation")),
                    (VerifactuRecord.state == "failed_transient")
                    & (
                        (VerifactuRecord.aeat_codigo_error == -2)
                        | (VerifactuRecord.aeat_codigo_error >= 1000)
                    ),
                ),
            )
            .limit(1)
        )
        if blocked_q.scalar_one_or_none() is not None:
            return (
                False,
                "Hay registros Verifactu rechazados sin resolver. Corrígelos en "
                "Configuración → Verifactu → Cola antes de emitir nuevas facturas "
                "(evita romper la cadena de huellas).",
            )

        return True, None

    async def on_invoice_issued(self, invoice, db) -> dict[str, Any]:
        return await self._build_record(invoice, db, is_credit_note=False)

    async def on_credit_note_issued(self, credit_note, original_invoice, db) -> dict[str, Any]:
        # Rectificativas use R1 + FacturasRectificadas. We pass original
        # via a side channel attribute so _build_record can look it up.
        credit_note._verifactu_original = original_invoice  # noqa: SLF001
        try:
            return await self._build_record(credit_note, db, is_credit_note=True)
        finally:
            try:
                del credit_note._verifactu_original
            except AttributeError:
                pass

    async def can_edit_billing_party(self, invoice, db: AsyncSession) -> tuple[bool, str | None]:
        """Allow editing only when the latest record is rejected.

        AEAT never registered the original data in that case, so
        Subsanación con datos modificados is canonical (per AEAT FAQs
        + RD 1007/2023). For ``accepted`` records the libro fiscal is
        immutable and the user must emit a credit note (R1) instead.
        """

        rec_q = await db.execute(
            select(VerifactuRecord)
            .where(VerifactuRecord.invoice_id == invoice.id)
            .order_by(VerifactuRecord.created_at.desc())
            .limit(1)
        )
        record = rec_q.scalar_one_or_none()
        if record is None:
            return (
                False,
                "La factura aún no tiene registro Verifactu asociado.",
            )
        code = record.aeat_codigo_error or 0
        is_business_transient = record.state == "failed_transient" and (code == -2 or code >= 1000)
        if record.state in ("rejected", "failed_validation") or is_business_transient:
            return True, None
        return (
            False,
            "Solo se pueden editar los datos del cliente cuando el "
            "registro Verifactu está rechazado. Si la factura ya fue "
            "aceptada por la AEAT, emite una factura rectificativa.",
        )

    async def regenerate_after_party_change(self, invoice, db: AsyncSession) -> dict[str, Any]:
        """Re-render the latest fiscal record after a billing-party edit."""

        rec_q = await db.execute(
            select(VerifactuRecord)
            .where(VerifactuRecord.invoice_id == invoice.id)
            .order_by(VerifactuRecord.created_at.desc())
            .limit(1)
        )
        record = rec_q.scalar_one_or_none()
        if record is None:
            return {}
        code = record.aeat_codigo_error or 0
        is_business_transient = record.state == "failed_transient" and (code == -2 or code >= 1000)
        if record.state not in ("rejected", "failed_validation") and not is_business_transient:
            return {}
        await regenerate_record(db, record)
        # ``regenerate_record`` already mutated ``invoice.compliance_data``
        # in place — return empty so the workflow does not double-merge.
        return {}

    def enhance_pdf_data(self, pdf_data: dict, invoice) -> dict:
        cd = (invoice.compliance_data or {}).get("ES") or {}
        if cd.get("qr_url"):
            pdf_data = dict(pdf_data)
            qr_png_b64 = qr.render_png_base64(cd["qr_url"])
            # Generic key consumed by ``billing.pdf`` so the billing
            # module stays country-agnostic.
            pdf_data["compliance_qr_png_b64"] = qr_png_b64
            pdf_data["compliance_qr_label"] = "VERI*FACTU"
            # Legacy/specific keys kept for any consumer that knew the
            # AEAT-specific name.
            pdf_data["verifactu_qr_png_b64"] = qr_png_b64
            pdf_data["verifactu_huella"] = cd.get("huella")
            pdf_data["verifactu_csv"] = cd.get("csv")
            notices = list(pdf_data.get("legal_notices", []))
            notices.append("Factura verificable en VERI*FACTU (AEAT)")
            pdf_data["legal_notices"] = notices
        return pdf_data

    async def _build_record(
        self, invoice, db: AsyncSession, *, is_credit_note: bool
    ) -> dict[str, Any]:
        settings = await _get_or_create_settings(db, invoice.clinic_id)
        if not settings.enabled:
            return {}

        is_first = settings.last_huella is None or settings.last_huella == ""
        huella_anterior = settings.last_huella or ""

        composed = await _compose_payload(
            db,
            invoice=invoice,
            settings=settings,
            is_credit_note=is_credit_note,
            huella_anterior=huella_anterior,
            is_first=is_first,
        )

        record = VerifactuRecord(
            clinic_id=invoice.clinic_id,
            invoice_id=invoice.id,
            record_type="alta",
            tipo_factura=composed.tipo_factura,
            tipo_rectificativa=composed.tipo_rectificativa,
            serie_numero=composed.serie_numero,
            fecha_expedicion=composed.fecha_expedicion,
            cuota_total=composed.cuota_total,
            importe_total=composed.importe_total,
            huella=composed.huella,
            huella_anterior=composed.huella_anterior or None,
            is_first_record=is_first,
            fecha_hora_huso_gen_registro=composed.fecha_hora_huso.astimezone(UTC),
            xml_payload=composed.xml,
            state="pending",
        )
        db.add(record)
        await db.flush()

        # Advance chain head BEFORE AEAT confirmation. Subsanación
        # regenerates this same head with new data + new huella; the
        # rejected-pending block in validate_before_issue prevents a
        # second invoice from chaining off a not-yet-final huella.
        settings.last_huella = composed.huella
        settings.last_record_id = record.id

        return {
            "ES": {
                "record_id": str(record.id),
                "huella": composed.huella,
                "qr_url": composed.qr_url,
                "tipo_factura": composed.tipo_factura,
                "state": "pending",
                "severity": severity_for("pending", None),
                "environment": settings.environment,
            }
        }
