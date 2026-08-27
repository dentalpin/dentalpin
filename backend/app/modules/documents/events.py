"""Event handlers for the documents module.

The module consumes no core events. It publishes
``document.generated`` after successful PDF creation.
"""

from __future__ import annotations

# No event subscriptions — the documents module is a producer only.
# ``document.generated`` is published by DocumentService.generate_pdf()
# and consumed by activity_journal for timeline entries.
