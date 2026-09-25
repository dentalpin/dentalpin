"""imaging_ai module — on-demand AI segmentation jobs (Runner protocol)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule
from app.core.scheduling import ScheduledJob

from .models import AiJob
from .router import router


class ImagingAiModule(BaseModule):
    """AI job queue over imaging studies.

    Default backend ``pano`` runs end to end on single-frame input;
    ``nnunet`` takes a DICOM series volume plus operator weights, both
    behind the ``Runner`` protocol (``runner.py``); torch/CUDA stay out
    of the backend image. Queued jobs execute on the scheduler tick
    (``tasks.py``) — the HTTP route only records them; the agent path
    only proposes them until a clinician confirms.
    """

    manifest = {
        "name": "imaging_ai",
        "version": "0.1.0",
        "summary": "On-demand AI segmentation jobs over imaging studies.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["media", "patients"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["jobs.read", "jobs.write"],
            "hygienist": ["jobs.read"],
            "assistant": ["jobs.read"],
            "receptionist": ["jobs.read"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.imagingAi",
                    "icon": "i-lucide-sparkles",
                    "to": "/imaging-ai",
                    "permission": "imaging_ai.jobs.read",
                    "order": 94,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [AiJob]

    def get_router(self) -> APIRouter:
        return router

    def get_tools(self) -> list:
        from .tools import get_all_tools

        return get_all_tools()

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        from .tasks import scheduled_jobs

        return scheduled_jobs()

    def get_permissions(self) -> list[str]:
        return ["jobs.read", "jobs.write"]
