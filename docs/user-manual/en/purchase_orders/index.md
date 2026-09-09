---
module: purchase_orders
---

# Procurement

Suppliers, vendor items, purchase orders, reorder suggestions and
supplier ratings for the clinic. The five sidebar entries under
Procurement share one backend suite (#227): suppliers and vendor links
feed reorder suggestions, which generate draft purchase orders, whose
receipt history feeds the ratings.

## Screens

- [Suppliers](./screens/suppliers.md): vendor contacts, terms, preferred flag.
- [Vendor items](./screens/items.md): which supplier sells which inventory item.
- [Purchase orders](./screens/orders.md): lifecycle, receiving, PDFs.
- [Reorder](./screens/reorder.md): computed suggestions, draft generation.
- [Ratings](./screens/ratings.md): delivery/quality metrics and manual scores.
