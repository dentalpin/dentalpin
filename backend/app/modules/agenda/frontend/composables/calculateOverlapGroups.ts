import type { Appointment } from '~~/app/types'

/**
 * Group overlapping appointments and return `{ index, total }` per id.
 *
 * Two appointments belong to the same group if their time intervals
 * overlap, transitively. Index/total drive the side-by-side column
 * layout in the day view.
 *
 * Algorithm: sort by start, then a single sweep that union-finds each
 * appointment with the prior groups whose latest end-time is still
 * after this appointment's start. Replaces an earlier O(n⁴)
 * group-merge pass.
 */
export function calculateOverlapGroups(
  profAppointments: Appointment[]
): Map<string, { index: number, total: number }> {
  const result = new Map<string, { index: number, total: number }>()
  if (profAppointments.length === 0) return result

  const items = profAppointments.map(apt => ({
    apt,
    start: new Date(apt.start_time).getTime(),
    end: new Date(apt.end_time).getTime()
  }))
  items.sort((a, b) => a.start - b.start || a.end - b.end)

  // DSU
  const parent = new Array(items.length).fill(0).map((_, i) => i)
  const rank = new Array(items.length).fill(0)
  function find(i: number): number {
    while (parent[i] !== i) {
      parent[i] = parent[parent[i]!]!
      i = parent[i]!
    }
    return i
  }
  function union(a: number, b: number): void {
    const ra = find(a)
    const rb = find(b)
    if (ra === rb) return
    if (rank[ra]! < rank[rb]!) parent[ra] = rb
    else if (rank[ra]! > rank[rb]!) parent[rb] = ra
    else {
      parent[rb] = ra
      rank[ra]!++
    }
  }

  // Active = items whose interval ends after the current item's start.
  // Maintained sorted by `end` ascending so we can drop expired ones.
  const active: number[] = []
  for (let i = 0; i < items.length; i++) {
    const cur = items[i]!
    while (active.length && items[active[0]!]!.end <= cur.start) active.shift()
    for (const j of active) union(i, j)
    active.push(i)
    // Keep `active` sorted by end so the front-prune above stays correct.
    active.sort((x, y) => items[x]!.end - items[y]!.end)
  }

  // Materialize groups, sort each by start, assign index/total.
  const groups = new Map<number, number[]>()
  for (let i = 0; i < items.length; i++) {
    const root = find(i)
    let g = groups.get(root)
    if (!g) {
      g = []
      groups.set(root, g)
    }
    g.push(i)
  }
  for (const g of groups.values()) {
    g.sort((a, b) => items[a]!.start - items[b]!.start)
    const total = g.length
    g.forEach((idx, columnIndex) => {
      result.set(items[idx]!.apt.id, { index: columnIndex, total })
    })
  }

  return result
}
