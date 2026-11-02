"""Billing compliance hooks for country module extensibility.

This module provides an interface for country-specific compliance modules
(e.g., verifactu-es for Spain, factur-x for France) to integrate with
the billing system without the billing module knowing about specific countries.

The billing module NEVER imports or references any country module directly.
Country modules register themselves via the BillingHookRegistry.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.core.auth.models import Clinic

    from .models import Invoice, InvoiceItem


class BillingComplianceHook(ABC):
    """Interface for country-specific compliance modules.

    Any country compliance module (verifactu-es, factur-x-fr, sdi-it, etc.)
    implements this interface and registers with BillingHookRegistry.
    The billing module does not know which countries exist.

    Example implementation for Spain (in separate module):

        class VerifactuHook(BillingComplianceHook):
            @property
            def country_code(self) -> str:
                return "ES"

            def get_required_fields(self) -> list[str]:
                return ["billing_tax_id"]  # NIF obligatorio

            async def on_invoice_issued(self, invoice, db) -> dict:
                # Generate hash, QR code, etc.
                return {"hash": "...", "qr": "...", "aeat_id": "..."}

            def enhance_pdf_data(self, pdf_data, invoice) -> dict:
                pdf_data["qr_code"] = self._generate_qr(invoice)
                pdf_data["legal_notices"].append("Texto legal España")
                return pdf_data
    """

    @property
    @abstractmethod
    def country_code(self) -> str:
        """ISO country code (ES, FR, IT, PT, DE...).

        This determines which clinic configurations use this hook.
        """
        pass

    @property
    def name(self) -> str:
        """Human-readable name for this compliance module."""
        return f"Compliance module for {self.country_code}"

    async def validate_before_issue(
        self, invoice: "Invoice", db: AsyncSession
    ) -> tuple[bool, str | None]:
        """Validate invoice before issuing.

        Called before transitioning to 'issued' status.
        Use this for country-specific validation rules.

        Args:
            invoice: Invoice being issued
            db: Database session

        Returns:
            (is_valid, error_message): Tuple with validation result.
            If is_valid is False, error_message explains the problem.

        Example:
            # Validate Spanish NIF format
            if not self._validate_nif(invoice.billing_tax_id):
                return False, "Invalid NIF format"
            return True, None
        """
        return True, None  # Default: no validation

    async def on_invoice_issued(self, invoice: "Invoice", db: AsyncSession) -> dict[str, Any]:
        """Hook called after invoice is issued.

        Use this to:
        - Calculate document hash
        - Generate QR code
        - Submit to tax authority
        - Register in chain/ledger

        Args:
            invoice: Issued invoice
            db: Database session

        Returns:
            Dict of compliance data to store in invoice.compliance_data[country_code]
            Returns empty dict if no data to store.

        Example:
            return {
                "hash": "sha256...",
                "previous_hash": "sha256...",
                "qr_data": "https://...",
                "submission_id": "AEAT-123",
                "submitted_at": datetime.now(UTC).isoformat(),
            }
        """
        return {}  # Default: no compliance data

    async def on_credit_note_issued(
        self, credit_note: "Invoice", original_invoice: "Invoice", db: AsyncSession
    ) -> dict[str, Any]:
        """Hook called after a credit note (rectificativa) is issued.

        This hook is called AFTER the credit note transitions to "issued" status.
        Use it for country-specific compliance requirements.

        DEFAULT BEHAVIOR (no hook override):
            - Original invoice: Status UNCHANGED (remains valid)
            - Credit note: Status "issued" with negative balance
            - Both documents coexist as valid fiscal documents
            - Patient balance = sum of all invoice balances

        COUNTRY-SPECIFIC OVERRIDES:
            Some countries require different behavior. Override this hook to:

            1. Cancel the original invoice (Mexico/SAT, Argentina/AFIP):
               ```python
               original_invoice.status = "cancelled"
               ```

            2. Submit to tax authority (TicketBAI, Verifactu, SAT):
               ```python
               return {"tax_id": "...", "qr_code": "..."}
               ```

            3. Link documents in external system:
               ```python
               return {"linked_to": original_invoice.invoice_number}
               ```

        Args:
            credit_note: The newly issued credit note (negative amounts)
            original_invoice: The invoice being rectified (can be modified if needed)
            db: Database session (for any additional queries/updates)

        Returns:
            Dict of compliance data to store in credit_note.compliance_data

        Example (Mexico SAT):
            ```python
            async def on_credit_note_issued(self, credit_note, original_invoice, db):
                # Mexico requires cancelling the original CFDI
                original_invoice.status = "cancelled"

                # Submit to SAT and get response
                sat_response = await self.sat_client.emit_egreso(
                    credit_note, original_invoice
                )
                return {
                    "cfdi_uuid": sat_response.uuid,
                    "related_cfdi": original_invoice.compliance_data.get("cfdi_uuid"),
                }
            ```
        """
        return {}  # Default: no compliance data, no status changes

    async def on_payment_recorded(
        self, invoice: "Invoice", payment_amount: float, db: AsyncSession
    ) -> dict[str, Any]:
        """Hook called after payment is recorded.

        Some countries require reporting payments.

        Args:
            invoice: Invoice receiving payment
            payment_amount: Amount paid
            db: Database session

        Returns:
            Dict of compliance data to merge into invoice.compliance_data
        """
        return {}  # Default: no compliance data

    def enhance_pdf_data(self, pdf_data: dict, invoice: "Invoice") -> dict:
        """Modify PDF data before generation.

        Use this to add:
        - QR codes
        - Country-specific legal text
        - Compliance stamps/watermarks
        - Additional fields required by country

        Args:
            pdf_data: Dict with PDF template data
            invoice: Invoice being rendered

        Returns:
            Modified pdf_data dict

        Example:
            pdf_data["qr_code"] = self._generate_qr(invoice)
            pdf_data["legal_notices"] = pdf_data.get("legal_notices", [])
            pdf_data["legal_notices"].append(
                "Factura generada conforme al RD 1619/2012"
            )
            return pdf_data
        """
        return pdf_data  # Default: no changes

    def get_required_fields(self) -> list[str]:
        """List of required fields for this country.

        Fields are validated before issuing.
        Use dot notation for nested fields: "billing_address.postal_code"

        Returns:
            List of required field paths

        Example for Spain:
            return ["billing_tax_id"]  # NIF required

        Example for France:
            return ["billing_tax_id", "billing_address.postal_code"]
        """
        return []  # Default: no required fields

    def get_pdf_template(self) -> str | None:
        """Optional custom PDF template name for this country.

        Returns:
            Template name or None to use default
        """
        return None  # Default: use standard template

    async def can_edit_billing_party(
        self, invoice: "Invoice", db: AsyncSession
    ) -> tuple[bool, str | None]:
        """Whether the billing party (NIF/name/address) of an issued invoice
        can still be edited under this country's compliance rules.

        Default returns ``(False, ...)`` — most countries treat issued
        invoices as immutable. Verifactu overrides this to allow editing
        when the latest fiscal record is in a correctable state
        (``rejected`` / ``failed_validation``) — AEAT never registered
        the original data so Subsanación with corrected data is legal.
        """

        return False, "Issued invoices are immutable for this country."

    async def regenerate_after_party_change(
        self, invoice: "Invoice", db: AsyncSession
    ) -> dict[str, Any]:
        """Re-render the compliance record after a billing-party edit.

        Called by the billing workflow right after persisting the new
        ``billing_*`` fields. Implementations should re-run their hash
        chain / submission step from the updated invoice. Returns the
        same shape as :meth:`on_invoice_issued` so callers can merge
        the result into ``Invoice.compliance_data``.

        Default: no-op.
        """

        return {}

    async def on_draft_item_deleted(self, item: "InvoiceItem", db: AsyncSession) -> None:
        """Remove this module's own rows for a draft invoice line about to be deleted.

        A module that stores per-line data with an FK to ``invoice_items``
        (India GST's SAC override on a draft) deletes it here, or the line's
        DELETE fails on that FK. Billing calls this on **every** registered
        hook, not only the clinic's country: the per-line row does not
        depend on the country setting (#750).

        Default: no-op.
        """

        return None


class BillingHookRegistry:
    """Registry for compliance hooks.

    Country modules register their hooks here.
    The billing module queries this registry to find applicable hooks.

    Usage by country module (re-attached on every boot the module is
    installed — see ``BaseModule.on_activate``):

        # In verifactu/__init__.py
        class VerifactuModule(BaseModule):
            def on_activate(self) -> None:
                BillingHookRegistry.register(VerifactuHook())
    """

    _hooks: dict[str, BillingComplianceHook] = {}

    @classmethod
    def register(cls, hook: BillingComplianceHook) -> None:
        """Register a compliance hook.

        Args:
            hook: Hook instance to register

        Example:
            BillingHookRegistry.register(VerifactuHook())
        """
        cls._hooks[hook.country_code] = hook

    @classmethod
    def unregister(cls, country_code: str) -> None:
        """Unregister a compliance hook.

        Useful for testing or when module is unloaded.

        Args:
            country_code: ISO country code to unregister
        """
        cls._hooks.pop(country_code, None)

    @classmethod
    def get(cls, country_code: str) -> BillingComplianceHook | None:
        """Get hook by country code.

        Args:
            country_code: ISO country code (ES, FR, etc.)

        Returns:
            Hook instance or None if not registered
        """
        return cls._hooks.get(country_code)

    @classmethod
    def get_for_clinic(cls, clinic: "Clinic") -> BillingComplianceHook | None:
        """Get hook for a clinic based on its configuration.

        Reads the country setting from clinic.settings and returns
        the appropriate hook if one is registered.

        Args:
            clinic: Clinic entity with settings

        Returns:
            Hook instance or None if no hook registered for clinic's country
        """
        settings = clinic.settings or {}
        country = settings.get("country", "")
        return cls._hooks.get(country)

    @classmethod
    def get_all(cls) -> dict[str, BillingComplianceHook]:
        """Get all registered hooks.

        Returns:
            Dict mapping country codes to hooks
        """
        return cls._hooks.copy()

    @classmethod
    def is_registered(cls, country_code: str) -> bool:
        """Check if a country has a registered hook.

        Args:
            country_code: ISO country code

        Returns:
            True if hook is registered
        """
        return country_code in cls._hooks

    @classmethod
    def clear(cls) -> None:
        """Clear all registered hooks.

        Primarily for testing purposes.
        """
        cls._hooks.clear()
