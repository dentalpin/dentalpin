"""IVA classification correctness for dental scenarios."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.verifactu.services import iva_classifier


def test_standard_rate_yields_s1():
    c = iva_classifier.classify(vat_rate=Decimal("21"), is_exento_sanitario=False)
    assert c.calificacion_operacion == "S1"
    assert not c.operacion_exenta
    assert c.tipo_impositivo == Decimal("21")
    assert c.clave_regimen == "01"


def test_zero_rate_no_exento_yields_n1():
    c = iva_classifier.classify(vat_rate=Decimal("0"), is_exento_sanitario=False)
    assert c.calificacion_operacion == "N1"
    assert not c.operacion_exenta
    # AEAT validation 1237: N1/N2 must NOT carry TipoImpositivo.
    assert c.tipo_impositivo is None


def test_exento_sanitario_yields_e1():
    c = iva_classifier.classify(vat_rate=Decimal("0"), is_exento_sanitario=True)
    assert c.operacion_exenta is True
    assert c.causa_exencion == "E1"
    assert c.calificacion_operacion is None
    assert c.tipo_impositivo is None


def test_unsupported_rate_raises():
    with pytest.raises(ValueError):
        iva_classifier.classify(vat_rate=Decimal("7"), is_exento_sanitario=False)


def test_determine_tipo_factura_credit_note_is_r1():
    assert (
        iva_classifier.determine_tipo_factura(
            has_credit_note_for=True, billing_tax_id="B1", importe_total=Decimal("50")
        )
        == "R1"
    )


def test_determine_tipo_factura_simplified_credit_note_is_r5():
    # AEAT FAQ: the rectification of a simplified invoice is R5 whatever the reason (#1049).
    assert (
        iva_classifier.determine_tipo_factura(
            has_credit_note_for=True, billing_tax_id=None, importe_total=Decimal("-72.60")
        )
        == "R5"
    )


def test_determine_tipo_factura_with_nif_is_f1():
    assert (
        iva_classifier.determine_tipo_factura(
            has_credit_note_for=False, billing_tax_id="B1", importe_total=Decimal("50")
        )
        == "F1"
    )


def test_determine_tipo_factura_no_nif_under_400_is_f2():
    assert (
        iva_classifier.determine_tipo_factura(
            has_credit_note_for=False, billing_tax_id=None, importe_total=Decimal("400")
        )
        == "F2"
    )


def test_determine_tipo_factura_no_nif_over_400_raises():
    with pytest.raises(ValueError):
        iva_classifier.determine_tipo_factura(
            has_credit_note_for=False,
            billing_tax_id=None,
            importe_total=Decimal("400.01"),
        )
