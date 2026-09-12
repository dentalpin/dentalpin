"""Mirror an SDI record into the invoice's ``compliance_data["IT"]``.

The invoice list chip and the detail header read the invoice, not the
record, so every state transition (exported, receipt, requeue, worker)
must write the block back; otherwise the chip says "To send" forever.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import Invoice

from ..models import SdiItRecord


def compliance_block(record: SdiItRecord) -> dict[str, Any]:
    return {
        "sdi": "queued",
        "record_id": str(record.id),
        "tipo_documento": record.tipo_documento,
        "file_name": record.file_name,
        "state": record.state,
    }


async def sync_invoice_state(db: AsyncSession, record: SdiItRecord) -> None:
    """Write ``record``'s block into its invoice. Does not commit."""
    await db.flush()  # a freshly built record gets its id here
    invoice = (
        await db.execute(
            select(Invoice).where(
                Invoice.id == record.invoice_id, Invoice.clinic_id == record.clinic_id
            )
        )
    ).scalar_one_or_none()
    if invoice is None:
        return
    data = dict(invoice.compliance_data or {})
    data["IT"] = compliance_block(record)
    # Reassign: plain JSONB does not track in-place mutation (see #418).
    invoice.compliance_data = data
