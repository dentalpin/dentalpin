/**
 * Sidebar grouping — purely a display concern for the host layout.
 *
 * Does NOT touch any module's manifest (upstream or custom). Modules keep
 * contributing flat `navigationItems` exactly as before; this file just
 * maps a subset of `to` paths to a group (and optionally a subgroup) so
 * `SidebarNav.vue` can render them under a header. Any `to` path with no
 * entry here renders ungrouped, in its existing position — so a newly
 * installed module with no group mapping degrades gracefully instead of
 * disappearing or erroring.
 */

export interface NavGroupDef {
  id: string
  labelKey: string
  order: number
}

export interface NavSubgroupDef {
  labelKey: string
  order: number
}

export interface NavGroupAssignment {
  group: string
  subgroup?: string
}

export const NAV_GROUPS: NavGroupDef[] = [
  { id: 'clinical', labelKey: 'nav.groups.clinical', order: 1 },
  { id: 'financials', labelKey: 'nav.groups.financials', order: 2 },
  { id: 'practiceManagement', labelKey: 'nav.groups.practiceManagement', order: 3 }
]

export const NAV_SUBGROUPS: Record<string, NavSubgroupDef> = {
  lab: { labelKey: 'nav.groups.lab', order: 1 }
}

export const NAV_GROUP_MAP: Record<string, NavGroupAssignment> = {
  '/patients': { group: 'clinical' },
  '/treatment-plans': { group: 'clinical' },
  '/recalls': { group: 'clinical' },

  '/budgets': { group: 'financials' },
  '/invoices': { group: 'financials' },
  '/payments': { group: 'financials' },
  '/expenses': { group: 'financials' },
  '/accounting-export': { group: 'financials' },

  '/inventory': { group: 'practiceManagement' },
  '/lab-orders/new': { group: 'practiceManagement', subgroup: 'lab' },
  '/lab-orders': { group: 'practiceManagement', subgroup: 'lab' },
  '/contacts': { group: 'practiceManagement' },
  '/reports': { group: 'practiceManagement' },
  '/tasks': { group: 'practiceManagement' }
}

// Deliberately NOT mapped yet (would-be dead-link phases): inventory's
// "New Order (from low stock)" sub-item (Phase 13), Staff Activity
// (Phase 10), Documents sub-items (Phase 14), Medication List (Phase 9).
// Add their `to` paths here once those pages actually exist.
