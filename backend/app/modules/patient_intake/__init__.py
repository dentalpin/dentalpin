"""Optional first-visit intake and staff review."""

from fastapi import APIRouter

from app.core.plugins import BaseModule
from app.core.scheduling import ScheduledJob

from .models import ConsentProvenance, FormVersion, Intake
from .router import router
from .service import purge_expired_intakes


class PatientIntakeModule(BaseModule):
    manifest = {
        "name": "patient_intake",
        "version": "0.1.0",
        "summary": "Versioned first-visit forms, review of patient declarations and communication consent.",
        "author": "Clínica Dental Araque",
        "license": "BSL-1.1",
        "category": "community",
        "depends": ["patients", "patients_clinical", "gdpr", "notifications"],
        "installable": True,
        "auto_install": False,
        "removable": False,
        "role_permissions": {
            "admin": ["*"],
            "receptionist": ["issue", "review_admin", "withdraw"],
            "dentist": ["review_clinical"],
        },
    }

    def get_router(self) -> APIRouter:
        return router

    def get_models(self) -> list:
        return [FormVersion, Intake, ConsentProvenance]

    def get_permissions(self) -> list[str]:
        return ["configure", "issue", "review_admin", "review_clinical", "withdraw"]

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        return [
            ScheduledJob(
                id="purge_patient_intake_staging",
                func=purge_expired_intakes,
                trigger="interval",
                trigger_args={"hours": 1},
                name="Purge expired first-visit intake staging",
            )
        ]
