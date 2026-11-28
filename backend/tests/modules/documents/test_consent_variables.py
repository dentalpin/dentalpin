"""Template variables are filled once, when a consent is created (#1171)."""

from __future__ import annotations

import base64
import io
import shutil
import subprocess
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import settings
from app.core.auth.models import Clinic, User
from app.core.utils.dates import clinic_today
from app.modules.documents.consent_markdown import render_consent_body
from app.modules.documents.consent_variables import (
    BLANK,
    VARIABLE_NAMES,
    build_values,
    escape_markdown_value,
    fill_template_variables,
)
from app.modules.documents.models import ConsentTemplate, GeneratedDocument
from app.modules.patients.models import Patient

FULL = {
    "patient_name": "Ana Synthetic",
    "patient_id_document": "12345678Z",
    "patient_birth_date": "01/02/1990",
    "clinic_name": "Synthetic Dental",
    "professional_name": "Dr. Test",
    "professional_license": "28/1234",
    "date": "26/11/2026",
}


@pytest.fixture(autouse=True)
def synthetic_public_origin(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://clinic.example")


# --- pure substitution -------------------------------------------------------


def test_every_allowlisted_variable_is_substituted():
    assert set(FULL) == set(VARIABLE_NAMES)
    for name, value in FULL.items():
        text, unknown = fill_template_variables("[{{ " + name + " }}]", FULL)
        assert text == f"[{escape_markdown_value(value, line_start=False)}]", name
        assert unknown == []


def test_whitespace_variants_are_equivalent():
    for source in ("{{patient_name}}", "{{ patient_name }}", "{{   patient_name\t}}"):
        assert fill_template_variables(source, FULL)[0] == "Ana Synthetic"


def test_unknown_variables_are_left_verbatim_and_reported_once():
    source = "{{ patient_name }} {{ weight }} {{weight}} {{ nope }}"
    text, unknown = fill_template_variables(source, FULL)
    assert text == "Ana Synthetic {{ weight }} {{weight}} {{ nope }}"
    assert unknown == ["weight", "nope"]


def test_no_expressions_filters_or_attribute_access():
    for source in (
        "{{ patient_name | upper }}",
        "{{ patient.first_name }}",
        "{{ 7*7 }}",
        "{{ patient_name.__class__ }}",
        "{% if x %}y{% endif %}",
        "{{ PATIENT_NAME }}",
    ):
        assert fill_template_variables(source, FULL)[0] == source


def test_missing_values_become_a_visible_blank():
    values = {**FULL, "patient_id_document": None, "professional_license": "   "}
    text, _ = fill_template_variables(
        "ID {{ patient_id_document }} / {{ professional_license }}", values
    )
    assert text == f"ID {BLANK} / {BLANK}"
    assert fill_template_variables("{{ date }}", {})[0] == BLANK


def test_substituted_values_are_not_rescanned():
    values = {**FULL, "patient_name": "{{ clinic_name }}"}
    assert fill_template_variables("{{ patient_name }}", values)[0] == "{{ clinic\\_name }}"


def test_build_values_uses_real_model_fields():
    patient = SimpleNamespace(
        first_name="Ana", last_name="Synthetic", national_id="X1", date_of_birth=date(1990, 2, 1)
    )
    user = SimpleNamespace(first_name="Dr", last_name="Test", professional_id="28/1")
    values = build_values(
        patient=patient, clinic_name="C", user=user, today=date(2026, 11, 26), locale="es"
    )
    assert values == {
        "patient_name": "Ana Synthetic",
        "patient_id_document": "X1",
        "patient_birth_date": "01/02/1990",
        "clinic_name": "C",
        "professional_name": "Dr Test",
        "professional_license": "28/1",
        "date": "26/11/2026",
    }
    patient.date_of_birth = None
    user.professional_id = None
    values = build_values(
        patient=patient, clinic_name="C", user=user, today=date(2026, 11, 26), locale="en"
    )
    assert values["patient_birth_date"] is None and values["professional_license"] is None


# --- Markdown injection ------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "*Ana*",
        "**Ana**",
        "_Ana_",
        "1. Foo",
        "2) Foo",
        "# Heading",
        "- item",
        "+ item",
        "Ana\n\n# Heading",
        "Ana\n- item",
        "back\\slash *x*",
        "<script>x</script>",
    ],
)
def test_markdown_in_a_value_renders_as_literal_text(name):
    source, _ = fill_template_variables(
        "Patient: {{ patient_name }}", {**FULL, "patient_name": name}
    )
    html = render_consent_body(source)
    assert html.startswith("<p>Patient: ") and html.endswith("</p>")
    for tag in ("<strong>", "<em>", "<h2>", "<h3>", "<h4>", "<ul>", "<ol>", "<script"):
        assert tag not in html, (name, html)
    assert html.count("<p>") == 1  # no paragraph or list was injected
    # A newline in a value never breaks the line.
    assert "<br>" not in html


def test_value_at_line_start_cannot_become_a_list_or_heading():
    for name in ("1. Foo", "- Foo", "# Foo"):
        html = render_consent_body(
            fill_template_variables("{{ patient_name }}", {**FULL, "patient_name": name})[0]
        )
        assert html == f"<p>{name}</p>"


def test_block_markers_are_only_escaped_at_the_start_of_a_line():
    values = {**FULL, "date": "2026. 11. 27."}
    assert fill_template_variables("Date: {{ date }}", values)[0] == "Date: 2026. 11. 27."
    at_start, _ = fill_template_variables("{{ date }}", values)
    assert render_consent_body(at_start) == "<p>2026. 11. 27.</p>"
    indented, _ = fill_template_variables("Intro\n  {{ date }}", values)
    assert "<ol>" not in render_consent_body(indented)


def test_two_blanks_in_punctuation_stay_visible():
    # A bare "____" would be an underscore delimiter run: two of them between
    # punctuation would pair up as strong emphasis and both blanks would vanish.
    text, _ = fill_template_variables(
        "DNI ({{ patient_id_document }}), fecha ({{ patient_birth_date }})", {}
    )
    html = render_consent_body(text)
    assert "<strong>" not in html and "<em>" not in html
    assert html.count(BLANK) == 2
    assert f"DNI ({BLANK}), fecha ({BLANK})" in html
    assert BLANK == "\u2014" * 4  # not Markdown syntax: the edit box shows what is printed
    assert "\\" not in text


@pytest.mark.parametrize(
    ("template", "value"),
    [
        # A value after a list or heading marker is still at a block start.
        ("- {{ patient_name }}", "1. Foo"),
        ("- {{ patient_name }}", "# Foo"),
        ("1. {{ patient_name }}", "- Foo"),
        ("## {{ patient_name }}", "# Foo"),
        # An all-digit value followed by "." or ")" from the template.
        ("{{ patient_name }}. Firma", "123"),
        ("{{ patient_name }}) Firma", "123"),
        ("- {{ patient_name }}. Firma", "123"),
    ],
)
def test_values_cannot_open_a_block_after_markers_or_before_template_punctuation(template, value):
    # The value must render exactly where a neutral word would, with the
    # template's own structure (its list or heading) and nothing more.
    text, _ = fill_template_variables(template, {"patient_name": value})
    neutral = render_consent_body(template.replace("{{ patient_name }}", "NEUTRALWORD"))
    assert render_consent_body(text) == neutral.replace("NEUTRALWORD", value)


def test_digit_value_mid_line_is_left_alone():
    text, _ = fill_template_variables(
        "Ref {{ patient_id_document }}. Firma", {"patient_id_document": "123"}
    )
    assert text == "Ref 123. Firma"


def test_literal_text_survives_exactly():
    source, _ = fill_template_variables(
        "{{ patient_name }}", {**FULL, "patient_name": "*Ana* _B_ \\C"}
    )
    assert render_consent_body(source) == "<p>*Ana* _B_ \\C</p>"


# --- API ---------------------------------------------------------------------


async def create_consent(client, headers, patient, body, title="Synthetic consent"):
    template = await client.post(
        "/api/v1/documents/consent-templates", headers=headers, json={"title": title, "body": body}
    )
    assert template.status_code == 201, template.text
    created = await client.post(
        "/api/v1/documents/consents",
        headers=headers,
        json={"template_id": template.json()["data"]["id"], "patient_id": str(patient.id)},
    )
    assert created.status_code == 201, created.text
    return template.json()["data"]["id"], created.json()["data"]


BODY = (
    "Patient: {{ patient_name }}, ID {{ patient_id_document }}, born {{ patient_birth_date }}\n"
    "Clinic: {{ clinic_name }}\n"
    "Dr. {{ professional_name }}, licence {{ professional_license }}\n"
    "Date: {{ date }}"
)


@pytest.mark.asyncio
async def test_consent_snapshot_is_filled_and_template_keeps_raw_text(
    client, auth_headers, test_patient, test_clinic, db_session
):
    test_patient.national_id = "12345678Z"
    test_patient.date_of_birth = date(1990, 2, 1)
    user = (await db_session.execute(select(User))).scalars().first()
    user.professional_id = "28/1234"
    await db_session.commit()
    template_id, data = await create_consent(client, auth_headers, test_patient, BODY)
    assert "unknown_variables" not in data
    doc = await db_session.get(GeneratedDocument, data["id"])
    today = clinic_today(test_clinic.timezone).strftime("%d/%m/%Y")
    assert doc.content["text"] == (
        "Patient: Test Patient, ID 12345678Z, born 01/02/1990\n"
        "Clinic: Test Clinic\n"
        "Dr. Test User, licence 28/1234\n"
        f"Date: {today}"
    )
    template = await db_session.get(ConsentTemplate, template_id)
    assert template.body == BODY


@pytest.mark.asyncio
async def test_missing_values_leave_blanks_and_unknown_names_are_reported(
    client, auth_headers, test_patient
):
    _, data = await create_consent(
        client,
        auth_headers,
        test_patient,
        "ID {{ patient_id_document }} born {{ patient_birth_date }} lic {{ professional_license }} {{ mystery }}",
    )
    assert data["unknown_variables"] == ["mystery"]
    detail = await client.get(f"/api/v1/documents/{data['id']}", headers=auth_headers)
    assert (
        detail.json()["data"]["content"]["text"]
        == f"ID {BLANK} born {BLANK} lic {BLANK} {{{{ mystery }}}}"
    )


@pytest.mark.asyncio
async def test_filled_text_remains_editable_while_unsigned(client, auth_headers, test_patient):
    _, data = await create_consent(
        client, auth_headers, test_patient, "ID {{ patient_id_document }}"
    )
    edit = await client.patch(
        f"/api/v1/documents/{data['id']}",
        headers=auth_headers,
        json={"content": {"text": "ID 99999999R"}},
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["data"]["content"]["text"] == "ID 99999999R"


@pytest.mark.asyncio
async def test_patient_name_cannot_inject_formatting_through_the_api(
    client, auth_headers, test_patient, db_session
):
    test_patient.first_name = "*Ana*"
    test_patient.last_name = "_Foo_"
    await db_session.commit()
    _, data = await create_consent(client, auth_headers, test_patient, "{{ patient_name }}")
    doc = await db_session.get(GeneratedDocument, data["id"])
    assert render_consent_body(doc.content["text"]) == "<p>*Ana* _Foo_</p>"


@pytest.mark.asyncio
async def test_variables_use_the_letterhead_name_and_clinic_language(
    client, auth_headers, test_patient, test_clinic, db_session
):
    test_clinic.settings = {
        **(test_clinic.settings or {}),
        "communication_language": "hu",
        "documents": {"letterhead": {"name": "Letterhead Name"}},
    }
    await db_session.commit()
    _, data = await create_consent(
        client, auth_headers, test_patient, "{{ clinic_name }} {{ date }}"
    )
    doc = await db_session.get(GeneratedDocument, data["id"])
    today = clinic_today(test_clinic.timezone)
    assert (
        doc.content["text"] == f"Letterhead Name {today.year}. {today.month:02d}. {today.day:02d}."
    )


@pytest.mark.asyncio
async def test_other_clinic_data_is_never_used(client, auth_headers, test_patient, db_session):
    foreign = Clinic(id=uuid4(), name="Other synthetic clinic", tax_id="B87654321")
    db_session.add(foreign)
    await db_session.flush()
    stranger = Patient(
        id=uuid4(), clinic_id=foreign.id, first_name="Foreign", last_name="Synthetic"
    )
    db_session.add(stranger)
    await db_session.commit()
    template = await client.post(
        "/api/v1/documents/consent-templates",
        headers=auth_headers,
        json={"title": "T", "body": "{{ patient_name }}"},
    )
    response = await client.post(
        "/api/v1/documents/consents",
        headers=auth_headers,
        json={"template_id": template.json()["data"]["id"], "patient_id": str(stranger.id)},
    )
    assert response.status_code == 404
    assert "Foreign" not in response.text


def _signature() -> str:
    image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    ImageDraw.Draw(image).line((2, 2, 35, 16), fill="black", width=2)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@pytest.mark.asyncio
async def test_signed_pdf_contains_the_substituted_values(
    client, auth_headers, test_patient, db_session
):
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext is required to verify rendered PDF text")
    test_patient.national_id = "12345678Z"
    await db_session.commit()
    _, data = await create_consent(
        client,
        auth_headers,
        test_patient,
        "Patient {{ patient_name }} ID {{ patient_id_document }} Clinic {{ clinic_name }}",
    )
    link = await client.post(
        f"/api/v1/documents/consents/{data['id']}/links?purpose=sign", headers=auth_headers
    )
    token = link.json()["data"]["token"]
    signed = await client.post(
        "/api/v1/documents/public/consents/current/sign",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "signer_name": "Synthetic patient",
            "relationship_to_patient": "patient",
            "signature": _signature(),
        },
    )
    assert signed.status_code == 200, signed.text
    pdf = await client.get(
        f"/api/v1/documents/consents/{data['id']}/evidence/sign/download", headers=auth_headers
    )
    text = " ".join(
        subprocess.run(["pdftotext", "-", "-"], input=pdf.content, capture_output=True, check=True)
        .stdout.decode()
        .split()
    )
    assert "Patient Test Patient ID 12345678Z Clinic Test Clinic" in text
    assert "{{" not in text and "____" not in text
