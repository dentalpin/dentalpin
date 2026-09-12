"""Channel adapter contract + registry (public surface for vendor modules).

Vendors import from here only:

    from app.modules.notifications.channels import (
        channel_registry, ChannelAdapter, Channel, OutboundMessage, AdapterResult, SendStatus,
    )
"""

from .base import (
    AdapterResult,
    Channel,
    ChannelAdapter,
    OutboundMessage,
    SendStatus,
)
from .email_adapter import EmailAdapter
from .registry import ChannelRegistry, channel_registry

__all__ = [
    "AdapterResult",
    "Channel",
    "ChannelAdapter",
    "ChannelRegistry",
    "EmailAdapter",
    "OutboundMessage",
    "PushAdapter",
    "SendStatus",
    "channel_registry",
]


def __getattr__(name: str):
    """Defer the WebPush import to first use (PEP 562).

    ``push_adapter`` hard-imports ``pywebpush`` (locked prod dep, no
    fallback branch by design). Host tooling (manifest/loader gates)
    runs without it, so binding ``PushAdapter`` here would break
    module discovery off-container. ``from .channels import
    PushAdapter`` keeps working everywhere; touching it without the
    dep raises ``ImportError`` loudly instead of degrading silently.
    """
    if name == "PushAdapter":
        from .push_adapter import PushAdapter

        return PushAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
