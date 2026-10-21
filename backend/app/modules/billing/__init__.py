"""Billing module - invoice management and payment tracking."""

from fastapi import APIRouter

from app.core.erasure.types import ErasureContributor
from app.core.plugins import BaseModule
from app.core.settings.spec import SettingSpec

from .models import Invoice, InvoiceHistory, InvoiceItem, InvoicePayment, InvoiceSeries
from .router import router


class BillingModule(BaseModule):
    """Billing module providing invoice management and payment tracking.

    Features:
    - Invoice creation from budgets or manual
    - Partial invoicing support
    - Multiple payment methods
    - Credit notes (rectificativas)
    - Invoice series with numbering control
    - PDF generation
    - Extensible hooks for country compliance modules
    """

    manifest = {
        "name": "billing",
        "version": "0.1.0",
        "summary": "Invoices, payments, credit notes, PDF billing.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "catalog", "budget", "payments"],
        "installable": True,
        "auto_install": True,
        "removable": False,
        "role_permissions": {
            "admin": ["*"],
            "dentist": ["*"],
            "hygienist": ["read"],
            "assistant": ["read", "write"],
            "receptionist": ["read", "write"],
        },
        "frontend": {
            "layer_path": "frontend",
            "navigation": [
                {
                    "label": "nav.invoices",
                    "section": "financials",
                    "icon": "i-lucide-receipt",
                    "to": "/invoices",
                    "permission": "billing.read",
                    "order": 50,
                },
            ],
        },
    }

    def get_models(self) -> list:
        return [InvoiceSeries, Invoice, InvoiceItem, InvoicePayment, InvoiceHistory]

    def get_tools(self) -> list:
        from . import tools

        return tools.get_tools()

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return [
            "read",  # View invoices
            "write",  # Create/update invoices, record payments
            "admin",  # Manage series, settings, void invoices
        ]

    def get_settings(self) -> list[SettingSpec]:
        return [
            SettingSpec(
                key="default_payment_term_days",
                type="integer",
                default=30,
                permission="billing.read",
                write_permission="billing.admin",
                label_key="billingSettings.fields.defaultPaymentTermDays.label",
                description_key="billingSettings.fields.defaultPaymentTermDays.description",
                min_value=0,
                max_value=365,
            ),
            SettingSpec(
                key="invoice_footer_text",
                type="string",
                default=None,
                nullable=True,
                multiline=True,
                permission="billing.read",
                write_permission="billing.admin",
                label_key="billingSettings.fields.invoiceFooterText.label",
                description_key="billingSettings.fields.invoiceFooterText.description",
            ),
            SettingSpec(
                key="bank_account_info",
                type="string",
                default=None,
                nullable=True,
                multiline=True,
                permission="billing.read",
                write_permission="billing.admin",
                label_key="billingSettings.fields.bankAccountInfo.label",
                description_key="billingSettings.fields.bankAccountInfo.description",
            ),
        ]

    def get_event_handlers(self) -> dict:
        # ``budget.completed`` was never actually published; the handler
        # was orphaned. Removed alongside the ``BudgetWorkflowService.complete_budget``
        # path. Re-add a subscription here when invoices need to react
        # to budget lifecycle events again.
        from app.core.events import EventType

        from .events import on_clinic_created, on_payment_allocated, on_payment_refunded

        return {
            # Transactional handlers (ADR 0019): run inside the payments
            # module's session. Budget allocations are mirrored onto the
            # budget's invoices; refunds recompute invoice status.
            EventType.PAYMENT_ALLOCATED: on_payment_allocated,
            EventType.PAYMENT_REFUNDED: on_payment_refunded,
            # Fresh clinic → default FAC/RECT series.
            EventType.CLINIC_CREATED: on_clinic_created,
        }

    def get_erasure_contributors(self) -> list[ErasureContributor]:
        from .erasure import BillingErasureContributor

        return [BillingErasureContributor()]
