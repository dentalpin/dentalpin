"""Public contract vendor gateway modules import — nothing else.

Mirrors ``app.modules.notifications.channels`` (ADR 0016): a stable,
provider-neutral surface (``GatewayAdapter`` protocol + typed request/
result dataclasses) that a vendor module (``razorpay``, and later
``phonepe``/``stripe``) implements and registers into :mod:`.registry`
from its own ``on_activate()``.
"""

from __future__ import annotations

from .base import (
    GatewayAdapter,
    GatewayCheckoutResult,
    GatewayConfirmation,
    GatewayCustomerInfo,
    GatewayRefundInitResult,
    GatewayRefundStatusResult,
    GatewayStatusResult,
    GatewayWebhookEvent,
)
from .registry import gateway_registry

__all__ = [
    "GatewayAdapter",
    "GatewayCheckoutResult",
    "GatewayConfirmation",
    "GatewayCustomerInfo",
    "GatewayRefundInitResult",
    "GatewayRefundStatusResult",
    "GatewayStatusResult",
    "GatewayWebhookEvent",
    "gateway_registry",
]
