"""IVA classification for Veri*Factu ``DetalleDesglose`` blocks.

Dental clinical services are typically exempt under article 20.uno.3º
LIVA (asistencia sanitaria), but cosmetic dentistry, dental products
and some prosthesis are subject to IVA at the standard / reduced /
super-reduced rate. The reference open-source project
EduardoRuizM/verifactu-api-python hardcodes ``CalificacionOperacion=S1``
when ``vat>0`` and ``N1`` when ``vat==0`` — that's wrong for clinics.
This module fixes that.

Inputs:
    - ``vat_rate`` (Decimal): the IVA rate of the line (0, 4, 10, 21).
    - ``is_exento_sanitario`` (bool): true when the line is clinical
      assistance exempt under art. 20 LIVA. Default False.

Output: a small dataclass usable directly by the XML template.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DesgloseClassification:
    """Classification of an invoice line for the AEAT ``DetalleDesglose``.

    Attributes:
        impuesto: ``01`` for IVA. (``02`` IPSI, ``03`` IGIC, ``05`` otros.)
        clave_regimen: ``01`` régimen general (default for dental).
        calificacion_operacion: ``S1``/``S2``/``N1``/``N2``. ``None``
            when the line is exempt — in that case ``operacion_exenta``
            and ``causa_exencion`` are populated instead.
        operacion_exenta: ``True`` for exempt lines (art. 20 etc.).
        causa_exencion: ``E1``..``E6`` per AEAT catalogue. ``E1`` =
            art. 20 LIVA exemption (covers asistencia sanitaria).
        tipo_impositivo: rate as a ``Decimal`` (0 / 4 / 10 / 21). For
            exempt lines this is omitted in the XML.
    """

    impuesto: str
    clave_regimen: str
    calificacion_operacion: str | None
    operacion_exenta: bool
    causa_exencion: str | None
    tipo_impositivo: Decimal | None


_VALID_VAT_RATES = (Decimal("0"), Decimal("4"), Decimal("10"), Decimal("21"))


def classify(
    *,
    vat_rate: Decimal,
    is_exento_sanitario: bool = False,
) -> DesgloseClassification:
    """Map a DentalPin invoice line to its Veri*Factu classification."""

    if vat_rate not in _VALID_VAT_RATES:
        raise ValueError(f"Unsupported VAT rate {vat_rate}; expected one of {_VALID_VAT_RATES}")

    if is_exento_sanitario:
        return DesgloseClassification(
            impuesto="01",
            clave_regimen="01",
            calificacion_operacion=None,
            operacion_exenta=True,
            causa_exencion="E1",
            tipo_impositivo=None,
        )

    if vat_rate == 0:
        # Operación no sujeta (N1). AEAT validation 1237 forbids
        # ``TipoImpositivo``, ``CuotaRepercutida``,
        # ``TipoRecargoEquivalencia`` and ``CuotaRecargoEquivalencia``
        # when CalificacionOperacion is N1 or N2 with IVA — the line
        # only carries ``BaseImponibleOimporteNoSujeto``.
        return DesgloseClassification(
            impuesto="01",
            clave_regimen="01",
            calificacion_operacion="N1",
            operacion_exenta=False,
            causa_exencion=None,
            tipo_impositivo=None,
        )

    return DesgloseClassification(
        impuesto="01",
        clave_regimen="01",
        calificacion_operacion="S1",
        operacion_exenta=False,
        causa_exencion=None,
        tipo_impositivo=vat_rate,
    )


def determine_tipo_factura(
    *,
    has_credit_note_for: bool,
    billing_tax_id: str | None,
    importe_total: Decimal,
) -> str:
    """Decide ``F1``/``F2``/``R1``/``R5`` for a DentalPin invoice.

    Rules:

    * Rectificativa of a simplified invoice (no NIF) → ``R5``, whatever
      the reason (AEAT FAQ). ``R1`` needs a destinatario (#1049).
    * Any other rectificativa (credit note) → ``R1`` (rectificación por
      error fundado en derecho, art. 80.1/80.2 LIVA — the most common case
      for dental clinics).
    * With NIF destinatario → ``F1``.
    * No NIF and total ≤ 400 € → ``F2`` (factura simplificada).
    * No NIF and total > 400 € → ``ValueError`` (caller must surface a
      validation error to the user before issuing).
    """

    if has_credit_note_for:
        return "R1" if billing_tax_id else "R5"
    if billing_tax_id:
        return "F1"
    if importe_total <= Decimal("400"):
        return "F2"
    raise ValueError(
        "Facturas sin NIF de destinatario y total > 400 € no son "
        "válidas para Verifactu. Captura el NIF del paciente o reduce "
        "el importe."
    )
