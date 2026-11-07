---
module: treatment_consumables
last_verified_commit: 47983b05
---

# Treatment consumables

Links each catalog treatment to the inventory items it consumes, and
how many of them (e.g. root canal → 2 anesthetic vials). When a linked catalog treatment is marked performed, the linked quantities may be deducted from stock automatically. Link notes are informational; they do not set conditions for deduction.

## Screens

- [Treatment consumables](./screens/index.md): link history with
  search-based pickers into both modules, quantity editing and unlink
  with confirmation.
