"""Render a synthetic signed budget and check the repeated footer's bounds."""

import base64
import shutil
import subprocess
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace as N
from xml.etree import ElementTree

import pytest
from PIL import Image, ImageDraw

from app.modules.budget.pdf import BudgetPDFService


def _signature_png():
    image = Image.new("RGB", (600, 180), "white")
    ImageDraw.Draw(image).line(
        [
            (65, 140),
            (125, 35),
            (153, 126),
            (230, 63),
            (275, 106),
            (310, 55),
            (350, 104),
            (478, 85),
            (535, 116),
        ],
        fill="#1e40af",
        width=9,
        joint="curve",
    )
    stream = BytesIO()
    image.save(stream, format="PNG")
    return "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def _signed_budget(line_count):
    amount = Decimal("50")
    timestamp = datetime(2026, 10, 1, 10, 30, tzinfo=UTC)
    item = N(
        catalog_item=N(names={"es": "Tratamiento de prueba", "en": "Synthetic treatment"}),
        tooth_number=None,
        surfaces=None,
        notes=None,
        quantity=1,
        unit_price=amount,
        line_subtotal=amount,
        line_discount=Decimal("0"),
        line_total=amount,
        vat_rate=Decimal("0"),
    )
    total = amount * line_count
    return (
        N(
            budget_number="PDF-SYNTH-001",
            version=1,
            status="accepted",
            created_at=timestamp,
            valid_from=date(2026, 10, 1),
            valid_until=date(2026, 12, 31),
            global_discount_type=None,
            global_discount_value=None,
            items=[item] * line_count,
            patient=N(first_name="Ficticia", last_name="Paciente"),
            assigned_professional=None,
            subtotal=total,
            total=total,
            total_tax=Decimal("0"),
            total_discount=Decimal("0"),
            patient_notes=None,
        ),
        N(
            name="Clínica de prueba",
            timezone="Europe/Madrid",
            currency="EUR",
            address=None,
            phone=None,
            email=None,
        ),
        N(
            signature_data={"png": _signature_png()},
            signed_at=timestamp,
            signature_method="drawn",
            signed_by_name="Firma Ficticia",
            document_hash="0123456789abcdef" * 4,
        ),
    )


def render_signed_budget():
    budget, clinic, signature = _signed_budget(49)
    html = BudgetPDFService._generate_html(
        budget, clinic, is_preview=False, locale="es", signature=signature
    )
    return BudgetPDFService._html_to_pdf(html)


def test_signature_and_multipage_content_clear_repeated_footer():
    if not shutil.which("pdftotext"):
        pytest.skip("poppler pdftotext is not installed")

    pdf = render_signed_budget()
    assert pdf.startswith(b"%PDF")
    output = subprocess.run(
        ["pdftotext", "-bbox-layout", "-", "-"], input=pdf, capture_output=True, check=True
    ).stdout
    pages = ElementTree.fromstring(output).findall(".//{*}page")
    assert len(pages) >= 2

    signature_pages = []
    for index, page in enumerate(pages):
        blocks = page.findall(".//{*}block")
        (footer,) = [
            block
            for block in blocks
            if [word.text for word in block.findall(".//{*}word")][:3]
            == ["Generado", "por", "DentalPin"]
        ]
        other_blocks = [block for block in blocks if block is not footer]
        footer_top = float(footer.attrib["yMin"])
        assert all(float(block.attrib["yMax"]) < footer_top for block in other_blocks), index + 1

        words = [word.text or "" for word in page.findall(".//{*}word")]
        if any(word.startswith("0123456789abcdef") for word in words):
            signature_pages.append(index)
            joined = " ".join(words)
            assert "Firma del Paciente" in joined
            assert "Firma de la Clínica" in joined

    assert signature_pages == [len(pages) - 1]
