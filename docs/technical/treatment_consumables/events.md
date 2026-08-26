# treatment_consumables — events

The module emits and consumes **no events**.

It is a pure mapping table: nothing else needs to react to link
lifecycle asynchronously. Stock deduction driven by completed
treatments is explicitly out of scope here — when the inventory core
upgrade (#226) adds it, it will subscribe to treatment events from *its*
own module rather than this junction writing stock.
