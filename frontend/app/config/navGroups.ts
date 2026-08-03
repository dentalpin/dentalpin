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
  { id: 'lab', labelKey: 'nav.groups.lab', order: 2 },
  { id: 'financials', labelKey: 'nav.groups.financials', order: 3 },
  { id: 'inventorySupply', labelKey: 'nav.groups.inventorySupply', order: 4 },
  { id: 'practiceManagement', labelKey: 'nav.groups.practiceManagement', order: 5 }
]

// Lab was previously a subgroup nested inside Practice Management; it's
// now its own top-level group (see NAV_GROUPS above), so its items are
// direct items of that group and no subgroup mapping is needed anymore.
// Left as an empty record (not removed) so SidebarNav.vue's subgroup
// rendering path stays available for any future group that needs it.
export const NAV_SUBGROUPS: Record<string, NavSubgroupDef> = {}

export const NAV_GROUP_MAP: Record<string, NavGroupAssignment> = {
  '/patients': { group: 'clinical' },
  '/treatment-plans': { group: 'clinical' },
  '/recalls': { group: 'clinical' },
  '/documents': { group: 'clinical' },

  '/lab-orders/new': { group: 'lab' },
  '/lab-orders': { group: 'lab' },

  '/budgets': { group: 'financials' },
  '/invoices': { group: 'financials' },
  '/payments': { group: 'financials' },
  '/expenses': { group: 'financials' },
  '/payroll': { group: 'financials' },
  '/accounting-export': { group: 'financials' },

  '/inventory': { group: 'inventorySupply' },
  '/reorder-suggestions': { group: 'inventorySupply' },
  '/purchase-orders': { group: 'inventorySupply' },
  '/contacts': { group: 'inventorySupply' },

  '/reports': { group: 'practiceManagement' },
  '/staff-activity': { group: 'practiceManagement' },
  '/tasks': { group: 'practiceManagement' }
}

// `/treatment-consumables` is deliberately NOT mapped here — it moved
// into Settings → Clinical Configuration and no longer has a sidebar
// entry at all (its module manifest's `navigation` array was emptied
// to match).
