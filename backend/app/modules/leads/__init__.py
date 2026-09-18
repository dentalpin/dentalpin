"""leads — inbound enquiries from an external form, routed two ways.

An enquiry that matches an existing patient (phone **or** email, same
clinic, non-archived) never becomes a lead: it queues a recall in the
recalls module. A genuinely new person becomes a lead card on /leads,
convertible into a patient through a drawer pre-filled from the lead.

``depends`` includes recalls because that routing is the module's core
rule, not an optional extra: with recalls uninstalled a matched enquiry
would have nowhere to go and the rule would silently degrade into "create
a duplicate lead". ``patients`` is required for the FK and for
``PatientService.create_patient`` on conversion.

The daily intake cap is clinic data (a ``leads_settings`` column edited
at Settings → Integrations → *Formulario web*), deliberately not an env
var — a clinic must be able to raise its own ceiling during a campaign
without an admin editing .env and restarting containers.

See ``CLAUDE.md`` and ``docs/technical/leads/overview.md``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .models import Lead, LeadIntakeKey, LeadSettings
from .public_router import public_router
from .router import router

# Table names exercised by the round-trip uninstall test.
LEAD_TABLES = {"leads", "leads_intake_keys", "leads_settings"}


class LeadsModule(BaseModule):
    """Inbound leads: new enquiries become leads, known patients become recalls."""

    manifest = {
        "name": "leads",
        "version": "0.1.0",
        "summary": (
            "Inbound leads from external forms: new enquiries become leads, "
            "known patients become recalls."
        ),
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        # recalls: a matched enquiry is routed to the call list (D8), so
        #   leads cannot be installed without recalls installed.
        # patients: FK + PatientService.create_patient on conversion.
        "depends": ["patients", "recalls"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["read"],
            "hygienist": [],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "leads.nav.leads",
                    "section": "practice",
                    "icon": "i-lucide-inbox",
                    "to": "/leads",
                    "permission": "leads.read",
                    "order": 86,
                }
            ],
        },
    }

    def get_models(self) -> list:
        return [Lead, LeadIntakeKey, LeadSettings]

    def get_router(self) -> APIRouter:
        # One mount, two surfaces: the authenticated staff router and the
        # key-gated public intake (budget / notifications precedent).
        combined = APIRouter()
        combined.include_router(router)
        combined.include_router(public_router)
        return combined

    def get_permissions(self) -> list[str]:
        # Namespaced by the registry -> leads.read, leads.write,
        # leads.settings.read, leads.settings.write.
        #
        # settings.* are granted to no role except admin (through
        # "admin": ["*"]). The key is a secret and rotating it breaks the
        # clinic's website until a human pastes the new one in — so it
        # belongs to whoever owns the website, not to the front desk.
        return ["read", "write", "settings.read", "settings.write"]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()
