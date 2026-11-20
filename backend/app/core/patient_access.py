"""Staff access audit shared by patient-scoped read routers."""

from datetime import UTC, datetime
from ipaddress import ip_address
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, Request
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.auth.dependencies import ClinicContext, get_clinic_context
from app.database import Base, get_db

Action = Literal["view", "download", "export"]
DEFAULT_RETENTION_YEARS = 5
RETENTION_SETTINGS_KEY = "patient_access_retention_years"
MAX_RETENTION_YEARS = 30


class PatientAccessLog(Base):
    """Access metadata retained independently of optional modules and erasure."""

    __tablename__ = "patient_access_logs"
    __table_args__ = (
        Index(
            "uq_patient_access_view_window",
            "clinic_id",
            "user_id",
            "patient_id",
            "resource",
            "window_start",
            unique=True,
        ),
        Index("ix_patient_access_patient", "clinic_id", "patient_id", "occurred_at", "id"),
        Index("ix_patient_access_user", "clinic_id", "user_id", "occurred_at", "id"),
        Index("ix_patient_access_retention", "clinic_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("clinics.id", ondelete="CASCADE"))
    user_id: Mapped[UUID]
    patient_id: Mapped[UUID]
    action: Mapped[str] = mapped_column(String(12))
    resource: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))


def retention_years(clinic_settings: dict | None) -> int:
    value = (clinic_settings or {}).get(RETENTION_SETTINGS_KEY)
    if type(value) is int and 1 <= value <= MAX_RETENTION_YEARS:
        return value
    return DEFAULT_RETENTION_YEARS


class AccessRecorder:
    def __init__(self, db: AsyncSession, ctx: ClinicContext, request: Request):
        self.db = db
        self.clinic_id = ctx.clinic_id
        self.user_id = ctx.user_id
        self.user_agent = request.headers.get("user-agent", "").replace("\x00", "")[:512] or None
        try:
            self.client_ip = str(ip_address(request.client.host)) if request.client else None
        except ValueError:
            self.client_ip = None

    async def __call__(self, patient_id: UUID, resource: str, *, action: Action = "view") -> None:
        """Record an already authorised read before returning patient data.

        PostgreSQL treats NULL windows as distinct, so repeated downloads
        and exports remain individually auditable.
        """
        now = datetime.now(UTC)
        window = (
            now.replace(minute=now.minute // 10 * 10, second=0, microsecond=0)
            if action == "view"
            else None
        )
        await self.db.execute(
            insert(PatientAccessLog)
            .values(
                clinic_id=self.clinic_id,
                user_id=self.user_id,
                patient_id=patient_id,
                action=action,
                resource=resource,
                occurred_at=now,
                window_start=window,
                client_ip=self.client_ip,
                user_agent=self.user_agent,
            )
            .on_conflict_do_nothing(
                index_elements=["clinic_id", "user_id", "patient_id", "resource", "window_start"]
            )
        )
        await self.db.commit()


def get_access_recorder(
    db: Annotated[AsyncSession, Depends(get_db)],
    ctx: Annotated[ClinicContext, Depends(get_clinic_context)],
    request: Request,
) -> AccessRecorder:
    return AccessRecorder(db, ctx, request)


RecordPatientAccess = Annotated[AccessRecorder, Depends(get_access_recorder)]
