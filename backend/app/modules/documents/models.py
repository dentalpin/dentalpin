"""SQLAlchemy models for the documents module."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentType(str, enum.Enum):
    """Supported document types."""

    PRESCRIPTION = "prescription"
    MEDICAL_CERTIFICATE = "medical_certificate"
    REFERRAL = "referral"
    RADIOLOGY_REQUEST = "radiology_request"


class DocumentStatus(str, enum.Enum):
    """Document lifecycle status."""

    DRAFT = "draft"
    GENERATED = "generated"
    ARCHIVED = "archived"


class GeneratedDocument(Base):
    """A generated document (prescription, certificate, referral, radiology request)."""

    __tablename__ = "generated_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clinics.id"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(20), server_default="draft"
    )
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_generated_documents_clinic_type",
            "clinic_id",
            "document_type",
        ),
    )
