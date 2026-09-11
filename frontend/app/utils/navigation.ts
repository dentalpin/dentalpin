import type { NavigationItem } from '~/types'

export interface NavigationGroup {
  key: string
  items: NavigationItem[]
}

export interface GroupedNavigation {
  /** Items without a `section`, in input order. */
  flat: NavigationItem[]
  /** Groups in first-seen order. Never empty: grouping runs after the
   * permission filter, so a group with zero visible items cannot exist. */
  groups: NavigationGroup[]
}

/**
 * Split permission-filtered, sorted nav items into flat entries plus
 * collapsible sections (issue #232). Pure — unit-tested without Nuxt.
 */
export function groupNavigationItems(items: NavigationItem[]): GroupedNavigation {
  const flat: NavigationItem[] = []
  const groups: NavigationGroup[] = []
  const byKey = new Map<string, NavigationGroup>()
  for (const item of items) {
    if (!item.section) {
      flat.push(item)
      continue
    }
    let group = byKey.get(item.section)
    if (!group) {
      group = { key: item.section, items: [] }
      byKey.set(item.section, group)
      groups.push(group)
    }
    group.items.push(item)
  }
  return { flat, groups }
}
