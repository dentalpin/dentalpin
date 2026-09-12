"""Adapter registry behavior — mirrors notifications' channel_registry tests."""

from __future__ import annotations

from app.modules.payment_gateways.adapters import gateway_registry
from app.modules.razorpay import RazorpayModule
from app.modules.razorpay.adapter import RazorpayAdapter

from .conftest import FakeAdapter


def test_register_and_get():
    adapter = FakeAdapter()
    gateway_registry.register(adapter)
    try:
        assert gateway_registry.get("fake") is adapter
        assert "fake" in gateway_registry.available_providers()
    finally:
        gateway_registry.unregister("fake")


def test_unregister_removes_adapter():
    adapter = FakeAdapter()
    gateway_registry.register(adapter)
    gateway_registry.unregister("fake")
    assert gateway_registry.get("fake") is None
    assert "fake" not in gateway_registry.available_providers()


def test_get_unknown_provider_returns_none():
    assert gateway_registry.get("does_not_exist") is None


def test_register_is_idempotent_on_reimport():
    a1 = FakeAdapter()
    gateway_registry.register(a1)
    try:
        a2 = FakeAdapter()  # a *different instance*, same class -> idempotent no-op
        gateway_registry.register(a2)
        assert gateway_registry.get("fake") is a1
    finally:
        gateway_registry.unregister("fake")


def test_razorpay_module_on_activate_registers_adapter():
    """The exact hook the loader calls for every installed module on boot
    (ADR 0020) — never at import time. Explicitly unregister first: the
    app process this test runs in may already have activated razorpay
    at its own startup if the module happens to be installed, so
    "not registered by mere import" isn't something this test can
    assert about *global* state — only that on_activate() itself does
    the registering, which the explicit reset+call below proves."""
    gateway_registry.unregister("razorpay")
    assert gateway_registry.get("razorpay") is None
    module = RazorpayModule()
    module.on_activate()
    try:
        adapter = gateway_registry.get("razorpay")
        assert adapter is not None
        assert isinstance(adapter, RazorpayAdapter)
        assert adapter.provider_key == "razorpay"
        assert set(adapter.supported_methods) == {"upi", "qr", "card", "payment_link"}
    finally:
        gateway_registry.unregister("razorpay")


async def test_razorpay_module_uninstall_unregisters_adapter():
    module = RazorpayModule()
    module.on_activate()
    assert gateway_registry.get("razorpay") is not None

    class _Ctx:
        db = None

    await module.uninstall(_Ctx())
    assert gateway_registry.get("razorpay") is None
