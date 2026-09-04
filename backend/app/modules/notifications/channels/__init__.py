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
from .push_adapter import PushAdapter
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
