"""NAV Online Számla 3.0 ``InvoiceData`` XML from a billing invoice.

Schema: ``http://schemas.nav.gov.hu/OSA/3.0/data`` (+ base/common). Only
the subset a dental clinic's invoices need:

* ``invoiceCategory`` NORMAL, ``currencyCode`` HUF, ``exchangeRate`` 1.
* Customer: ``PRIVATE_PERSON`` when the invoice has no tax id (patients),
  ``DOMESTIC`` with ``customerVatData`` when it has a Hungarian adószám.
* Lines: ``lineAmountsNormal``; VAT either ``vatPercentage`` (e.g. 0.27)
  or ``vatExemption`` case ``TAM`` for the 0 % lines — humán-egészségügyi
  szolgáltatás is exempt under Áfa tv. 85. § (1) b)/c), which is the
  normal case for treatments; cosmetic work carries 27 %.
* Summary: ``summaryNormal`` grouped by VAT rate + gross totals.
* STORNO (credit note): same document, ``invoiceReference`` to the
  original number with ``modifyWithoutMaster`` false and negative lines.

Amounts are rendered with two decimals; ``*HUF`` mirrors (rate 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from app.modules.billing.models import Invoice

NS_DATA = "http://schemas.nav.gov.hu/OSA/3.0/data"
NS_COMMON = "http://schemas.nav.gov.hu/NTCA/1.0/common"
NS_BASE = "http://schemas.nav.gov.hu/OSA/3.0/base"

DEFAULT_EXEMPTION_REASON = "Áfa tv. 85. § (1) b) — humán-egészségügyi szolgáltatás"

_Q = Decimal("0.01")


def _money(value: Decimal | float | int | str | None) -> str:
    return str(Decimal(str(value or 0)).quantize(_Q, rounding=ROUND_HALF_UP))


def _rate(value: float | Decimal) -> str:
    # 27 → "0.27"; NAV wants the fraction with up to 4 decimals.
    return str((Decimal(str(value)) / Decimal(100)).quantize(Decimal("0.0001")).normalize())


@dataclass(frozen=True)
class HungarianTaxNumber:
    taxpayer_id: str  # 8 digits
    vat_code: str | None = None  # 1 digit — optional in the XSD
    county_code: str | None = None  # 2 digits — optional in the XSD

    @classmethod
    def parse(cls, raw: str | None) -> HungarianTaxNumber | None:
        compact = "".join(c for c in (raw or "") if c not in "- ")
        if not compact.isdigit():
            return None  # a NIF/CIF-style id is not an adószám
        digits = compact
        if len(digits) == 11:
            return cls(digits[:8], digits[8], digits[9:])
        if len(digits) == 8:
            return cls(digits)  # bare törzsszám: vatCode/countyCode are optional, don't guess
        return None

    def xml(self, tag: str) -> str:
        parts = [f"<base:taxpayerId>{self.taxpayer_id}</base:taxpayerId>"]
        if self.vat_code:
            parts.append(f"<base:vatCode>{self.vat_code}</base:vatCode>")
        if self.county_code:
            parts.append(f"<base:countyCode>{self.county_code}</base:countyCode>")
        return f"<{tag}>{''.join(parts)}</{tag}>"


@dataclass
class InvoiceDataResult:
    xml: str
    invoice_number: str
    gross_amount: Decimal


def _address_xml(tag: str, address: dict[str, Any] | None, fallback_country: str = "HU") -> str:
    a = address or {}
    return (
        f"<{tag}><base:simpleAddress>"
        f"<base:countryCode>{escape(str(a.get('country_code') or a.get('country') or fallback_country))[:2].upper()}</base:countryCode>"
        f"<base:postalCode>{escape(str(a.get('postal_code') or '0000'))}</base:postalCode>"
        f"<base:city>{escape(str(a.get('city') or '-'))}</base:city>"
        f"<base:additionalAddressDetail>{escape(str(a.get('street') or '-'))}</base:additionalAddressDetail>"
        f"</base:simpleAddress></{tag}>"
    )


def _payment_method(invoice: Invoice) -> str:
    # Billing has no payment-method snapshot on the invoice; TRANSFER is
    # NAV's catch-all for "not cash at issue time".
    return "TRANSFER"


def build_invoice_data(
    invoice: Invoice,
    *,
    supplier_tax_number: HungarianTaxNumber,
    supplier_name: str,
    supplier_address: dict[str, Any] | None,
    original_invoice_number: str | None = None,
) -> InvoiceDataResult:
    """Render ``InvoiceData`` for ``invoice``.

    ``original_invoice_number`` set ⇒ the document is a STORNO of that
    invoice (credit note): lines and totals are negated and an
    ``invoiceReference`` is emitted.
    """
    is_storno = original_invoice_number is not None
    sign = Decimal("-1") if is_storno else Decimal("1")
    issue_date = invoice.issue_date.isoformat() if invoice.issue_date else ""
    number = invoice.invoice_number or ""

    customer_tax = HungarianTaxNumber.parse(invoice.billing_tax_id)
    if customer_tax:
        customer_xml = (
            "<customerInfo><customerVatStatus>DOMESTIC</customerVatStatus>"
            f"<customerVatData>{customer_tax.xml('customerTaxNumber')}</customerVatData>"
            f"<customerName>{escape(invoice.billing_name or '')}</customerName>"
            f"{_address_xml('customerAddress', invoice.billing_address)}"
            "</customerInfo>"
        )
    else:
        customer_xml = (
            "<customerInfo><customerVatStatus>PRIVATE_PERSON</customerVatStatus></customerInfo>"
        )

    reference_xml = ""
    if is_storno:
        reference_xml = (
            "<invoiceReference>"
            f"<originalInvoiceNumber>{escape(original_invoice_number)}</originalInvoiceNumber>"
            "<modifyWithoutMaster>false</modifyWithoutMaster>"
            "<modificationIndex>1</modificationIndex>"
            "</invoiceReference>"
        )

    lines_xml: list[str] = []
    by_rate: dict[str, dict[str, Decimal]] = {}
    net_total = Decimal("0")
    vat_total = Decimal("0")
    for idx, item in enumerate(invoice.items or [], start=1):
        # Net after the line discount — billing keeps unit_price*quantity in
        # line_subtotal and the discount apart; NAV wants the taxable base.
        net = (Decimal(str(item.line_subtotal or 0)) - Decimal(str(item.line_discount or 0))) * sign
        rate = Decimal(str(item.vat_rate or 0))
        vat = (net * rate / Decimal(100)).quantize(_Q, rounding=ROUND_HALF_UP)
        gross = net + vat
        if rate > 0:
            rate_key = _rate(rate)
            vat_xml = f"<lineVatRate><vatPercentage>{rate_key}</vatPercentage></lineVatRate>"
        else:
            rate_key = "TAM"
            reason = escape((item.vat_exempt_reason or DEFAULT_EXEMPTION_REASON)[:200])
            vat_xml = (
                "<lineVatRate><vatExemption><case>TAM</case>"
                f"<reason>{reason}</reason></vatExemption></lineVatRate>"
            )
        bucket = by_rate.setdefault(rate_key, {"net": Decimal("0"), "vat": Decimal("0")})
        bucket["net"] += net
        bucket["vat"] += vat
        net_total += net
        vat_total += vat
        qty = Decimal(str(item.quantity or 1))
        unit_price = (net / qty).quantize(_Q, rounding=ROUND_HALF_UP) if qty else net
        lines_xml.append(
            "<line>"
            f"<lineNumber>{idx}</lineNumber>"
            "<lineExpressionIndicator>true</lineExpressionIndicator>"
            "<lineNatureIndicator>SERVICE</lineNatureIndicator>"
            f"<lineDescription>{escape((item.description or '')[:512])}</lineDescription>"
            f"<quantity>{qty}</quantity><unitOfMeasure>PIECE</unitOfMeasure>"
            f"<unitPrice>{_money(unit_price)}</unitPrice>"
            "<lineAmountsNormal>"
            f"<lineNetAmountData><lineNetAmount>{_money(net)}</lineNetAmount>"
            f"<lineNetAmountHUF>{_money(net)}</lineNetAmountHUF></lineNetAmountData>"
            f"{vat_xml}"
            f"<lineVatData><lineVatAmount>{_money(vat)}</lineVatAmount>"
            f"<lineVatAmountHUF>{_money(vat)}</lineVatAmountHUF></lineVatData>"
            f"<lineGrossAmountData><lineGrossAmountNormal>{_money(gross)}</lineGrossAmountNormal>"
            f"<lineGrossAmountNormalHUF>{_money(gross)}</lineGrossAmountNormalHUF></lineGrossAmountData>"
            "</lineAmountsNormal>"
            "</line>"
        )

    summary_rates: list[str] = []
    for rate_key, amounts in by_rate.items():
        if rate_key == "TAM":
            rate_xml = (
                "<vatRate><vatExemption><case>TAM</case>"
                f"<reason>{escape(DEFAULT_EXEMPTION_REASON)}</reason></vatExemption></vatRate>"
            )
        else:
            rate_xml = f"<vatRate><vatPercentage>{rate_key}</vatPercentage></vatRate>"
        gross = amounts["net"] + amounts["vat"]
        summary_rates.append(
            "<summaryByVatRate>"
            f"{rate_xml}"
            f"<vatRateNetData><vatRateNetAmount>{_money(amounts['net'])}</vatRateNetAmount>"
            f"<vatRateNetAmountHUF>{_money(amounts['net'])}</vatRateNetAmountHUF></vatRateNetData>"
            f"<vatRateVatData><vatRateVatAmount>{_money(amounts['vat'])}</vatRateVatAmount>"
            f"<vatRateVatAmountHUF>{_money(amounts['vat'])}</vatRateVatAmountHUF></vatRateVatData>"
            f"<vatRateGrossData><vatRateGrossAmount>{_money(gross)}</vatRateGrossAmount>"
            f"<vatRateGrossAmountHUF>{_money(gross)}</vatRateGrossAmountHUF></vatRateGrossData>"
            "</summaryByVatRate>"
        )
    gross_total = net_total + vat_total

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<InvoiceData xmlns="{NS_DATA}" xmlns:common="{NS_COMMON}" xmlns:base="{NS_BASE}">'
        f"<invoiceNumber>{escape(number)}</invoiceNumber>"
        f"<invoiceIssueDate>{issue_date}</invoiceIssueDate>"
        "<completenessIndicator>false</completenessIndicator>"
        "<invoiceMain><invoice>"
        f"{reference_xml}"
        "<invoiceHead>"
        "<supplierInfo>"
        f"{supplier_tax_number.xml('supplierTaxNumber')}"
        f"<supplierName>{escape(supplier_name)}</supplierName>"
        f"{_address_xml('supplierAddress', supplier_address)}"
        "</supplierInfo>"
        f"{customer_xml}"
        "<invoiceDetail>"
        "<invoiceCategory>NORMAL</invoiceCategory>"
        f"<invoiceDeliveryDate>{issue_date}</invoiceDeliveryDate>"
        "<currencyCode>HUF</currencyCode><exchangeRate>1</exchangeRate>"
        f"<paymentMethod>{_payment_method(invoice)}</paymentMethod>"
        "<invoiceAppearance>ELECTRONIC</invoiceAppearance>"
        "</invoiceDetail>"
        "</invoiceHead>"
        f"<invoiceLines><mergedItemIndicator>false</mergedItemIndicator>{''.join(lines_xml)}</invoiceLines>"
        "<invoiceSummary>"
        f"<summaryNormal>{''.join(summary_rates)}"
        f"<invoiceNetAmount>{_money(net_total)}</invoiceNetAmount>"
        f"<invoiceNetAmountHUF>{_money(net_total)}</invoiceNetAmountHUF>"
        f"<invoiceVatAmount>{_money(vat_total)}</invoiceVatAmount>"
        f"<invoiceVatAmountHUF>{_money(vat_total)}</invoiceVatAmountHUF>"
        "</summaryNormal>"
        f"<summaryGrossData><invoiceGrossAmount>{_money(gross_total)}</invoiceGrossAmount>"
        f"<invoiceGrossAmountHUF>{_money(gross_total)}</invoiceGrossAmountHUF></summaryGrossData>"
        "</invoiceSummary>"
        "</invoice></invoiceMain>"
        "</InvoiceData>"
    )
    return InvoiceDataResult(xml=xml, invoice_number=number, gross_amount=gross_total.quantize(_Q))
