"""Agent tools for the patients module.

Thin wrappers over :class:`PatientService` — no business logic lives
here. Each tool filters by ``ctx.clinic_id`` (multi-tenancy) and declares
the same RBAC string the HTTP routes use, so an agent can never reach
data the calling user couldn't. PII keys in the returned dicts
(``full_name``, ``phone``, ``email``) are tokenized by the redactor
before any payload leaves the server. See
``docs/technical/copilot-agentic-architecture.md`` §3.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .service import PatientService


class SearchPatientsArgs(BaseModel):
    query: str = Field(
        description=(
            "Search text: full name, partial name, phone, email or national "
            "ID. Multiple words are matched independently against the "
            "patient's name fields, so 'Juan Pérez' (or reversed 'Pérez "
            "Juan') finds the patient — pass the whole name as one query, "
            "don't split it into separate searches."
        )
    )
    limit: int = Field(default=20, ge=1, le=50)


class GetPatientArgs(BaseModel):
    patient_id: UUID


class CreatePatientArgs(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)


class UpdatePatientArgs(BaseModel):
    patient_id: UUID
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)


class ImportPatientsCsvArgs(BaseModel):
    csv_text: str = Field(
        description=(
            "CSV with header first_name,last_name[,phone,email,date_of_birth,"
            "notes,do_not_contact,national_id,national_id_type,billing_name,"
            "billing_tax_id]. Max 1000 rows."
        )
    )
    dry_run: bool = Field(
        default=True,
        description="Validate only when true; create the patients when false.",
    )


def _summary(patient) -> dict:
    return {
        "id": patient.id,
        "full_name": f"{patient.first_name} {patient.last_name}",
        "phone": patient.phone,
        "email": patient.email,
        "status": patient.status,
    }


async def _search_patients(ctx: AgentContext, params: SearchPatientsArgs) -> dict:
    items, total = await PatientService.list_patients(
        ctx.db, ctx.clinic_id, search=params.query, page=1, page_size=params.limit
    )
    return {"total": total, "patients": [_summary(p) for p in items]}


async def _get_patient(ctx: AgentContext, params: GetPatientArgs) -> dict:
    patient = await PatientService.get_patient(ctx.db, ctx.clinic_id, params.patient_id)
    if patient is None:
        return {"error": "not_found"}
    data = _summary(patient)
    data["date_of_birth"] = patient.date_of_birth
    data["do_not_contact"] = patient.do_not_contact
    return data


async def _create_patient(ctx: AgentContext, params: CreatePatientArgs) -> dict:
    patient = await PatientService.create_patient(
        ctx.db, ctx.clinic_id, params.model_dump(exclude_none=True)
    )
    return {"id": patient.id, "full_name": f"{patient.first_name} {patient.last_name}"}


async def _update_patient(ctx: AgentContext, params: UpdatePatientArgs) -> dict:
    patient = await PatientService.get_patient(ctx.db, ctx.clinic_id, params.patient_id)
    if patient is None:
        return {"error": "not_found"}
    data = params.model_dump(exclude_none=True)
    data.pop("patient_id")
    if not data:
        return {"error": "nothing_to_update"}
    patient = await PatientService.update_patient(ctx.db, patient, data)
    return _summary(patient)


async def _import_patients_csv(ctx: AgentContext, params: ImportPatientsCsvArgs) -> dict:
    from .csv_import import CsvImportError, import_patients, validate_patient_csv

    try:
        valid, errors, total = validate_patient_csv(params.csv_text.encode("utf-8"))
    except CsvImportError as exc:
        return {"error": str(exc)}
    created_ids: list = []
    if not params.dry_run and valid:
        patients = await import_patients(ctx.db, ctx.clinic_id, valid)
        created_ids = [p.id for p in patients]
    return {
        "total": total,
        "valid": len(valid),
        "created": created_ids,
        "errors": errors,
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="search_patients",
            description=(
                "Buscar pacientes de la clínica por nombre (completo o "
                "parcial), teléfono, email o DNI/NIE. Pasa el nombre y "
                "apellido juntos en una sola consulta."
            ),
            parameters=SearchPatientsArgs,
            handler=_search_patients,
            permissions=["patients.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="get_patient",
            description="Obtener los datos de un paciente por su id.",
            parameters=GetPatientArgs,
            handler=_get_patient,
            permissions=["patients.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="create_patient",
            description="Crear un paciente nuevo. Requiere confirmación del usuario.",
            parameters=CreatePatientArgs,
            handler=_create_patient,
            permissions=["patients.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="update_patient",
            description=(
                "Actualizar los datos de contacto (tel�fono, email) de un "
                "paciente existente. Requiere confirmaci�n del usuario."
            ),
            parameters=UpdatePatientArgs,
            handler=_update_patient,
            permissions=["patients.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="import_patients_csv",
            description=(
                "Importar pacientes desde un CSV (cabecera first_name,"
                "last_name,...). Valida sin escribir por defecto; crea con "
                "dry_run=false. Requiere confirmaci�n del usuario."
            ),
            parameters=ImportPatientsCsvArgs,
            handler=_import_patients_csv,
            permissions=["patients.write"],
            category=ToolCategory.WRITE,
            exposes_free_text=True,
        ),
    ]
