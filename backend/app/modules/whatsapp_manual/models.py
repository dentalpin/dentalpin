"""Staff declarations of manual WhatsApp delivery."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ManualDeliveryDeclaration(Base):
    """Audit metadata stored separately from the redactable message context."""

    __tablename__ = "whatsapp_manual_delivery_declarations"

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("communication_messages.id", ondelete="CASCADE"), primary_key=True
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id"), index=True)
    marked_by_user_id: Mapped[UUID]
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
