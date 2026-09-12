"""payment_gateways — provider-neutral gateway contract, registry, and
the ``PaymentRequest``/``GatewayRefundRequest`` async lifecycle.

Mirrors ``notifications`` (ADR 0016): this module owns the contract
and the registry (:mod:`.adapters`), never a provider implementation.
A provider module (``razorpay``, and later ``phonepe``/``stripe``)
declares ``depends=["payment_gateways"]`` and registers its adapter
from its own ``on_activate()`` — this module never imports a provider.

Declares no permissions of its own: every endpoint reuses
``payments.record.{read,write,refund}`` (see ``router.py`` docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from app.core.plugins import BaseModule

from .constants import TERMINAL_REFUND_STATES, TERMINAL_REQUEST_STATES
from .models import GatewayRefundRequest, PaymentRequest
from .router import router

if TYPE_CHECKING:
    from app.core.plugins.base import ModuleContext

# Table names exercised by the round-trip uninstall test.
PAYMENT_GATEWAYS_TABLES = {"payment_requests", "gateway_refund_requests"}


class PaymentGatewaysModule(BaseModule):
    manifest = {
        "name": "payment_gateways",
        "version": "0.1.0",
        "summary": "Provider-neutral payment gateway contract, registry, and PaymentRequest lifecycle.",
        "author": "DentalPin Core Team",
        "license": "BSL-1.1",
        "category": "official",
        "depends": ["patients", "budget", "payments"],
        "installable": True,
        "auto_install": False,
        "removable": True,
        # No permissions of this module's own (get_permissions() -> []) —
        # every endpoint reuses payments.record.{read,write,refund} (see
        # router.py). Declared anyway so admin keeps its "*" convention
        # if a module-own permission is ever added later.
        "role_permissions": {"admin": ["*"]},
        "frontend": {},
    }

    def get_models(self) -> list:
        return [PaymentRequest, GatewayRefundRequest]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return []

    async def uninstall(self, ctx: ModuleContext) -> None:
        from sqlalchemy import func, select

        # Guard: refuse uninstall while any collection or refund attempt
        # is still in flight — removing the module would orphan a
        # provider-side checkout/refund the clinic (and the patient)
        # are actively waiting on. Terminal-state rows (succeeded,
        # failed, expired, cancelled, completed) never block uninstall;
        # they're just history.
        pending_requests_q = await ctx.db.execute(
            select(func.count())
            .select_from(PaymentRequest)
            .where(PaymentRequest.state.notin_(tuple(TERMINAL_REQUEST_STATES)))
        )
        pending_requests = pending_requests_q.scalar() or 0
        pending_refunds_q = await ctx.db.execute(
            select(func.count())
            .select_from(GatewayRefundRequest)
            .where(GatewayRefundRequest.state.notin_(tuple(TERMINAL_REFUND_STATES)))
        )
        pending_refunds = pending_refunds_q.scalar() or 0
        if pending_requests or pending_refunds:
            raise RuntimeError(
                f"Cannot uninstall payment_gateways: {pending_requests} payment request(s) "
                f"and {pending_refunds} refund request(s) are still in flight. Wait for them "
                "to resolve (succeed/fail/expire/cancel) or cancel them first."
            )
