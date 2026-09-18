---
module: mcp
last_verified_commit: d9d8ad97
---

# mcp — events

The module emits and consumes **no events**.

The MCP surface is synchronous RPC (initialize / list / call) over HTTP;
there is nothing in the tool lifecycle the rest of the tree needs to
react to asynchronously, and the bus's event types are untouched — the
module only routes existing tools to a new transport.

## Indirect event exposure

`tools/call` flows through the **same handlers** the event-driven
modules publish from, so executing `search_patients` /
`get_patient` never generates events; only the *write* tools would
(and they are deliberately excluded until a write token scope exists).