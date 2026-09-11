// @vitest-environment node
import { describe, expect, it } from 'vitest'
import type { NavigationItem } from '~/types'
import { groupNavigationItems } from '~/utils/navigation'

/**
 * Sidebar section grouping (issue #232). Pure helper — no Nuxt needed.
 * Items without a `section` stay flat; the rest group by key in
 * first-seen order. Grouping always runs after the permission filter,
 * so empty groups cannot occur.
 */
function item(to: string, section?: string): NavigationItem {
  return { label: to, icon: 'i-x', to, ...(section ? { section } : {}) }
}

describe('groupNavigationItems', () => {
  it('keeps section-less items flat in order', () => {
    const { flat, groups } = groupNavigationItems([item('/a'), item('/b')])
    expect(flat.map(i => i.to)).toEqual(['/a', '/b'])
    expect(groups).toEqual([])
  })

  it('groups by key in first-seen order', () => {
    const { flat, groups } = groupNavigationItems([
      item('/a'),
      item('/x1', 'clinical'),
      item('/y1', 'financials'),
      item('/x2', 'clinical')
    ])
    expect(flat.map(i => i.to)).toEqual(['/a'])
    expect(groups.map(g => g.key)).toEqual(['clinical', 'financials'])
    expect(groups[0].items.map(i => i.to)).toEqual(['/x1', '/x2'])
    expect(groups[1].items.map(i => i.to)).toEqual(['/y1'])
  })

  it('handles an empty list', () => {
    expect(groupNavigationItems([])).toEqual({ flat: [], groups: [] })
  })
})
