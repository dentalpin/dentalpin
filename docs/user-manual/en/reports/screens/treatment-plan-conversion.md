---
module: reports
screen: treatment-plan-conversion
route: /reports/treatment-plan-conversion
related_endpoints:
  - GET /api/v1/reports/treatment-plans/conversion
related_permissions:
  - reports.scheduling.read
related_paths:
  - backend/app/modules/reports/frontend/pages/reports/treatment-plan-conversion.vue
  - backend/app/modules/reports/services/plan_conversion.py
last_verified_commit: 5595761b
---

# Treatment plan conversion

This report follows plans confirmed by a clinician from confirmation through
booking and treatment completion. Open it from **Reports → Treatment plans**.

## Choose a period

The report groups plans by the date they were confirmed, using the clinic's
local timezone. The initial period is the current month. Change **From** and
**To** to compare another period. The start date must be on or before the end
date.

Draft plans and plans confirmed outside the selected period are excluded. This
makes the report a cohort view: later bookings and completed items stay
associated with the date the clinician confirmed the plan.

## Read the metrics

- **Confirmed plans** — plans confirmed during the selected period.
- **Booked plans** — confirmed plans with at least one linked appointment that
  has not been cancelled. A plan counts once even when several items are booked.
- **Completed plans** — plans in the completed or archived state with at least
  one completed item.
- **Treatment item progress** — completed items divided by non-cancelled items
  in the confirmed-plan cohort.

The booking and completion percentages use confirmed plans as their denominator.
Item progress uses treatment items as its denominator. Empty cohorts show zero
percentages rather than an undefined value.

## Access and troubleshooting

The report requires `reports.scheduling.read`. If it is missing, ask a clinic
administrator to grant access through **Settings → Users → Roles**.

- **The report is empty.** Widen the period or confirm that plans were approved
  by a clinician during it. Draft plans do not enter the cohort.
- **A booked plan is not counted.** The appointment must be linked to a plan
  item; cancelled appointments are ignored.
- **Completion is lower than expected.** Mark finished items as completed in
  the treatment plan. Booking an appointment alone does not mark care complete.
