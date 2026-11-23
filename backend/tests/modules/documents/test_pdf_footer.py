"""The footer never prints over the document's text (#1039)."""

from types import SimpleNamespace as N

from weasyprint import HTML

from app.modules.documents.pdf import DocumentPDFService


def _boxes(box):
    yield box
    for child in getattr(box, "children", None) or []:
        yield from _boxes(child)


def test_footer_stays_below_the_text_on_every_page():
    clinic = N(
        name="Example Dental Clinic",
        address=None,
        phone="",
        email="",
        tax_id="",
        settings={},
        timezone="UTC",
    )
    patient = N(first_name="Fictional", last_name="Patient", id="TEST-123", date_of_birth=None)
    text = "\n".join(f"Clause {i}: the patient accepts the risks." for i in range(1, 151))
    document = N(document_type="informed_consent", title="Synthetic", content={"text": text})
    html = DocumentPDFService._generate_html(document, clinic, patient, "en", "Test Doctor")

    pages = HTML(string=html).render().pages
    assert len(pages) > 1
    for number, page in enumerate(pages, start=1):
        root = page._page_box
        footers = [
            box
            for box in _boxes(root)
            if getattr(box, "element", None) is not None
            and "footer" in (box.element.get("class") or "").split()
            # On the page it is declared on, the fixed box sits in a placeholder.
            and type(box).__name__ in ("BlockBox", "AbsolutePlaceholder")
        ]
        assert footers, f"no footer on page {number}"
        top = footers[0].border_box_y()
        in_footer = {id(box) for box in _boxes(footers[0])}
        lowest = max(
            box.position_y + box.height
            for box in _boxes(root)
            if type(box).__name__ == "LineBox" and id(box) not in in_footer
        )
        assert lowest <= top, f"page {number}: text ends at {lowest}, footer starts at {top}"
        assert top + footers[0].border_height() <= root.margin_height()
