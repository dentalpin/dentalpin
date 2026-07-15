"""Static catalog of clinical-note templates by treatment category.

The pre-fill shown in the completion-nudge modal and the per-treatment note
composer is picked from this table based on the ``treatment.clinical_type``
of the item being completed. Bodies are plain text (newline-separated
labels) since the note editors are plain ``<textarea>`` — the clinician
edits the skeleton in place.

No DB. No admin UI. Adding a template = edit this file.
"""

from __future__ import annotations

from typing import Final, TypedDict


class NoteTemplate(TypedDict):
    id: str
    i18n_key: str
    body_i18n_key: str
    body: str


NOTE_TEMPLATES: Final[dict[str, list[NoteTemplate]]] = {
    "endodontics": [
        {
            "id": "endo_single_visit",
            "i18n_key": "clinicalNotes.templates.endo.singleVisit",
            "body_i18n_key": "clinicalNotes.templateBodies.endo_single_visit",
            "body": (
                "Diagnóstico: \n"
                "Anestesia: \n"
                "Conductos localizados: \n"
                "Longitud de trabajo: \n"
                "Obturación: \n"
                "Post-op: "
            ),
        },
        {
            "id": "endo_multi_visit",
            "i18n_key": "clinicalNotes.templates.endo.multiVisit",
            "body_i18n_key": "clinicalNotes.templateBodies.endo_multi_visit",
            "body": (
                "Sesión: \nConductos trabajados: \nMedicación intraconducto: \nPróxima cita: "
            ),
        },
    ],
    "periodontics": [
        {
            "id": "perio_scaling",
            "i18n_key": "clinicalNotes.templates.perio.scaling",
            "body_i18n_key": "clinicalNotes.templateBodies.perio_scaling",
            "body": (
                "Cuadrantes tratados: \n"
                "Profundidad de sondaje: \n"
                "Sangrado al sondaje: \n"
                "Indicaciones higiene: "
            ),
        },
    ],
    "implantology": [
        {
            "id": "implant_placement",
            "i18n_key": "clinicalNotes.templates.implant.placement",
            "body_i18n_key": "clinicalNotes.templateBodies.implant_placement",
            "body": (
                "Implante (marca / diámetro / longitud): \n"
                "Torque final (Ncm): \n"
                "Estabilidad primaria: \n"
                "Injerto: \n"
                "Post-op: "
            ),
        },
    ],
    "diagnosis": [
        {
            "id": "diagnosis_caries",
            "i18n_key": "clinicalNotes.templates.diagnosis.caries",
            "body_i18n_key": "clinicalNotes.templateBodies.diagnosis_caries",
            "body": (
                "Hallazgo: caries \nProfundidad: \nSíntomas: \nPrueba de vitalidad: \n"
                "Tratamiento sugerido: "
            ),
        },
        {
            "id": "diagnosis_periapical",
            "i18n_key": "clinicalNotes.templates.diagnosis.periapical",
            "body_i18n_key": "clinicalNotes.templateBodies.diagnosis_periapical",
            "body": (
                "Lesión periapical \nDiente: \nRadiografía: \n"
                "Pruebas (percusión, palpación): \nDiagnóstico: "
            ),
        },
    ],
    "administrative": [
        {
            "id": "admin_phone_call",
            "i18n_key": "clinicalNotes.templates.admin.phoneCall",
            "body_i18n_key": "clinicalNotes.templateBodies.admin_phone_call",
            "body": "Llamada del paciente: \nMotivo: \nAcción tomada: \nSeguimiento: ",
        },
        {
            "id": "admin_reschedule",
            "i18n_key": "clinicalNotes.templates.admin.reschedule",
            "body_i18n_key": "clinicalNotes.templateBodies.admin_reschedule",
            "body": "Solicita cambio de cita: \nFecha actual: \nNueva propuesta: ",
        },
    ],
    "general": [
        {
            "id": "general_follow_up",
            "i18n_key": "clinicalNotes.templates.general.followUp",
            "body_i18n_key": "clinicalNotes.templateBodies.general_follow_up",
            "body": "Hallazgos: \nProcedimiento realizado: \nIndicaciones al paciente: ",
        },
    ],
}


def list_templates(category: str | None = None) -> list[NoteTemplate]:
    """Return templates for a category, or all of them flat when no category."""
    if category:
        return list(NOTE_TEMPLATES.get(category, ()))
    out: list[NoteTemplate] = []
    for bucket in NOTE_TEMPLATES.values():
        out.extend(bucket)
    return out
