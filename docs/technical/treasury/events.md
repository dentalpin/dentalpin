---
module: treasury
last_verified_commit: 7f721882
---

# treasury - events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Consumers |
|-------|------|-----------|
| `treasury.transferred` | Paired transfer legs written | activity_journal |
| `treasury.corrected` | Manual correction written | activity_journal |

## Consumed

None.
