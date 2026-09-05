"""Agent tools for the reports module.

Thin wrappers over the report services — no business logic here.
Clinic-scoped; RBAC via the existing ``reports.*`` strings.

**Off-books boundary (project rule):** the billing tools expose the
*invoice axis only* (gross invoiced amounts). They never return settled,
pending / overdue / remainder figures, because those equal the
single-axis difference that clinics keep off-record. The
payments module owns the collection axis (see ``payments/tools.py``); the
two axes are deliberately kept apart and the copilot system prompt
forbids surfacing their difference.
"""

from __future__ import annotations

from datetime import date as date_cls

from pydantic import BaseModel, Field

from app.core.agents import AgentContext, Tool, ToolCategory

from .services import (
    BillingReportService,
    FinancialReportService,
    SchedulingReportService,
)


class PeriodArgs(BaseModel):
    date_from: date_cls = Field(description="Inicio del periodo (YYYY-MM-DD).")
    date_to: date_cls = Field(description="Fin del periodo (YYYY-MM-DD).")


class TopClientsArgs(BaseModel):
    year: int = Field(ge=2000, le=2100)
    limit: int = Field(default=10, ge=1, le=50)


async def _billing_report(ctx: AgentContext, params: PeriodArgs) -> dict:
    summary = await BillingReportService.get_summary(
        ctx.db, ctx.clinic_id, params.date_from, params.date_to
    )
    # Invoice axis only — drop settled / pending / overdue (the off-books diff).
    return {
        "date_from": params.date_from,
        "date_to": params.date_to,
        "total_invoiced": summary.get("total_invoiced", 0),
        "invoice_count": summary.get("invoice_count", 0),
    }


async def _top_clients_by_billing(ctx: AgentContext, params: TopClientsArgs) -> dict:
    rows = await BillingReportService.top_clients_by_billing(
        ctx.db,
        ctx.clinic_id,
        date_cls(params.year, 1, 1),
        date_cls(params.year, 12, 31),
        params.limit,
    )
    return {"year": params.year, "clients": rows}


async def _scheduling_report(ctx: AgentContext, params: PeriodArgs) -> dict:
    return await SchedulingReportService.get_summary(
        ctx.db, ctx.clinic_id, params.date_from, params.date_to
    )


async def _financial_report(ctx: AgentContext, params: PeriodArgs) -> dict:
    # Invoice axis only — aging buckets + issued trend carry issued
    # totals on their own axis, nothing else.
    buckets = await FinancialReportService.aging_buckets(ctx.db, ctx.clinic_id)
    trend = await FinancialReportService.issued_trend(
        ctx.db, ctx.clinic_id, params.date_from, params.date_to
    )
    return {
        "date_from": params.date_from,
        "date_to": params.date_to,
        "aging": [
            {"bucket": b["label"], "total": b["total"], "invoices": b["count"]} for b in buckets
        ],
        "issued_trend": [
            {"month": p["month"], "total": p["total"], "invoices": p["count"]} for p in trend
        ],
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="billing_report",
            description=(
                "Resumen de facturación de un periodo: total facturado y nº de facturas. "
                "Solo eje factura (no incluye cobros ni pendiente)."
            ),
            parameters=PeriodArgs,
            handler=_billing_report,
            permissions=["reports.billing.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="top_clients_by_billing",
            description="Ranking de pacientes por importe facturado en un año (eje factura).",
            parameters=TopClientsArgs,
            handler=_top_clients_by_billing,
            permissions=["reports.billing.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="scheduling_report",
            description="Resumen de actividad de agenda de un periodo (citas, completadas, canceladas).",
            parameters=PeriodArgs,
            handler=_scheduling_report,
            permissions=["reports.scheduling.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="financial_report",
            description=(
                "Antigüedad de saldos por tramos e issued mensual de un periodo. "
                "Solo eje factura (importes emitidos, nunca cobros ni diferencias)."
            ),
            parameters=PeriodArgs,
            handler=_financial_report,
            permissions=["reports.financial.read"],
            category=ToolCategory.READ,
        ),
    ]
