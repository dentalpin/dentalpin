"""Registry-driven scheduler job declaration (ADR 0014 import-coupling fix).

Modules declare periodic jobs via ``BaseModule.get_scheduled_jobs()``;
the scheduler iterates the registered modules instead of importing task
functions directly. These are pure unit tests — no DB, no APScheduler
start.
"""

from __future__ import annotations

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.scheduler import _build_trigger
from app.core.scheduling import ScheduledJob
from app.modules.budget import BudgetModule
from app.modules.copilot import CopilotModule
from app.modules.integrations import IntegrationsModule
from app.modules.notifications import NotificationsModule
from app.modules.treatment_plan import TreatmentPlanModule
from app.modules.verifactu import VerifactuModule


def test_modules_declare_their_jobs() -> None:
    expected = {
        NotificationsModule: {
            "appointment_reminders",
            "notifications_dispatch_outbox",
            "notifications_stuck_reaper",
        },
        IntegrationsModule: {"integrations_dispatch_outbox", "integrations_stuck_reaper"},
        BudgetModule: {"expire_budgets", "send_budget_reminders", "purge_budget_access_logs"},
        TreatmentPlanModule: {"auto_close_expired_plans"},
        CopilotModule: {"copilot_morning_digests"},
        # Declared, not self-registered from install() — so the jobs exist
        # on every boot the module is installed, and never otherwise (#91).
        VerifactuModule: {
            "verifactu_submissions",
            "verifactu_stuck_reaper",
            "verifactu_cert_expiry",
        },
    }
    for module_cls, ids in expected.items():
        jobs = module_cls().get_scheduled_jobs()
        assert {j.id for j in jobs} == ids
        for job in jobs:
            assert callable(job.func)
            assert job.trigger in ("cron", "interval")


def test_base_module_default_is_no_jobs() -> None:
    # A module that doesn't override the hook contributes nothing — the
    # whole point of decoupling the scheduler from module imports.
    from app.modules.patients import PatientsModule

    assert PatientsModule().get_scheduled_jobs() == []


def test_build_trigger_maps_spec_to_apscheduler() -> None:
    cron = _build_trigger(
        ScheduledJob(id="x", func=lambda: None, trigger="cron", trigger_args={"hour": 2}, name="x")
    )
    assert isinstance(cron, CronTrigger)

    interval = _build_trigger(
        ScheduledJob(
            id="y", func=lambda: None, trigger="interval", trigger_args={"minutes": 5}, name="y"
        )
    )
    assert isinstance(interval, IntervalTrigger)
