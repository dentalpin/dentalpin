"""Alembic environment configuration for async migrations.

Supports Fase A's mixed Alembic layout:

* **Main linear** — the historic chain under ``backend/alembic/versions/``.
  Holds every migration shipped before the module-system refactor plus
  any new migrations of modules that have not been extracted to a branch
  (clinical and the other legacy modules in Fase A).
* **Per-module branches** — brand-new modules keep their migrations
  under ``backend/app/modules/<name>/migrations/versions/`` and declare
  ``branch_labels=('<name>',)`` on the first revision. The directory is
  discovered at env-load time; missing or empty folders are ignored, so
  bootstrap on a fresh database works identically to before.

Discovery is filesystem-based on purpose: querying ``core_module`` from
here would create a circular dependency (the table does not exist
during its own migration and is missing in offline ``--sql`` mode).
"""

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings

# Import all models to register them with Base.metadata
from app.core.agents.models import (  # noqa: F401
    Agent,
    AgentApprovalQueue,
    AgentAuditLog,
    AgentSession,
)
from app.core.auth.models import Clinic, ClinicMembership, User  # noqa: F401
from app.core.plugins.alembic_paths import discover_version_locations
from app.core.plugins.db_models import (  # noqa: F401
    ExternalId,
    ModuleOperationLog,
    ModuleRecord,
)
from app.database import Base
from app.modules.agenda.models import Appointment, AppointmentTreatment, Cabinet  # noqa: F401
from app.modules.billing.models import (  # noqa: F401
    Invoice,
    InvoiceHistory,
    InvoiceItem,
    InvoicePayment,
    InvoiceSeries,
    InvoiceSeriesHistory,
)
from app.modules.budget.models import (  # noqa: F401
    Budget,
    BudgetHistory,
    BudgetItem,
    BudgetSignature,
)
from app.modules.catalog.models import (  # noqa: F401
    TreatmentCatalogItem,
    TreatmentCategory,
    TreatmentOdontogramMapping,
    VatType,
)
from app.modules.media.models import Document, MediaAttachment  # noqa: F401
from app.modules.notifications.models import (  # noqa: F401
    ClinicChannelSettings,
    ClinicNotificationSettings,
    ClinicSmtpSettings,
    CommunicationMessage,
    NotificationPreference,
    NotificationTemplate,
)
from app.modules.odontogram.models import (  # noqa: F401
    OdontogramHistory,
    ToothRecord,
    Treatment,
    TreatmentTooth,
)
from app.modules.patient_timeline.models import PatientTimeline  # noqa: F401
from app.modules.patients.models import Patient  # noqa: F401
from app.modules.patients_clinical.models import (  # noqa: F401
    Allergy,
    EmergencyContact,
    LegalGuardian,
    MedicalContext,
    Medication,
    SurgicalHistory,
    SystemicDisease,
)
from app.modules.payments.models import (  # noqa: F401
    PatientEarnedEntry,
    Payment,
    PaymentAllocation,
    PaymentHistory,
    Refund,
)
from app.modules.recalls.models import (  # noqa: F401
    Recall,
    RecallContactAttempt,
    RecallSettings,
)
from app.modules.schedules.models import (  # noqa: F401
    ClinicOverride,
    ClinicWeeklySchedule,
    ProfessionalOverride,
    ProfessionalWeeklySchedule,
    ScheduleShift,
)
from app.modules.treatment_plan.models import (  # noqa: F401
    PlannedTreatmentItem,
    TreatmentPlan,
)
from app.modules.whatsapp_kapso.models import (  # noqa: F401
    WhatsappKapsoSettings,
    WhatsappKapsoTemplate,
)
from app.modules.documents.models import GeneratedDocument  # noqa: F401

ALEMBIC_DIR = Path(__file__).parent
BACKEND_ROOT = ALEMBIC_DIR.parent
MAIN_LINEAR = ALEMBIC_DIR / "versions"
MODULES_ROOT = BACKEND_ROOT / "app" / "modules"

config = context.config

# Set the database URL from settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Register main linear + discovered branches so Alembic can resolve heads
# across all of them. ``version_path_separator = os`` in alembic.ini, so
# join on ``os.pathsep``.
config.set_main_option(
    "version_locations",
    os.pathsep.join(discover_version_locations(MAIN_LINEAR, MODULES_ROOT)),
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
