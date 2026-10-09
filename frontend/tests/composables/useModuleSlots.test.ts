import { describe, expect, it, beforeEach } from 'vitest'
import { defineComponent, isReactive, markRaw, h } from 'vue'
import { PERMISSIONS } from '~/config/permissions'

// Regression: ISSUE-004 — slot components triggered "reactive object"
// warnings because the slot registry stored every registered component
// inside a `useState`-backed reactive map. Components must be wrapped
// with `markRaw` at registration time so Vue's
// `<component :is="entry.component">` rendering path stops complaining.
// Found by /qa on 2026-05-19
// Report: .gstack/qa-reports/qa-report-localhost-2026-05-19.md

describe('useModuleSlots', () => {
  beforeEach(async () => {
    const { clearSlots } = await import('~/composables/useModuleSlots')
    clearSlots()
  })

  it('marks the registered component raw so the slot map can\'t make it reactive', async () => {
    const { registerSlot, resolveSlot } = await import('~/composables/useModuleSlots')

    const Demo = defineComponent({
      name: 'DemoSlotComponent',
      render: () => h('span', 'demo')
    })

    registerSlot('test.slot', { id: 'demo.entry', component: Demo })

    const entries = resolveSlot('test.slot', {}, { can: () => true })
    expect(entries).toHaveLength(1)
    // markRaw skips reactive wrapping — Vue exposes that via isReactive.
    expect(isReactive(entries[0].component)).toBe(false)
  })

  it('does not double-wrap a component that was already markRaw', async () => {
    const { registerSlot, resolveSlot } = await import('~/composables/useModuleSlots')

    const Demo = markRaw(defineComponent({
      name: 'AlreadyRawComponent',
      render: () => h('span', 'raw')
    }))

    registerSlot('test.slot', { id: 'demo.raw', component: Demo })

    const entries = resolveSlot('test.slot', {}, { can: () => true })
    expect(entries[0].component).toBe(Demo)
    expect(isReactive(entries[0].component)).toBe(false)
  })

  it('preserves order and filters by permission gate', async () => {
    const { registerSlot, resolveSlot } = await import('~/composables/useModuleSlots')

    const A = defineComponent({ name: 'A', render: () => h('span', 'a') })
    const B = defineComponent({ name: 'B', render: () => h('span', 'b') })

    registerSlot('ordered.slot', { id: 'b', component: B, order: 20 })
    registerSlot('ordered.slot', { id: 'a', component: A, order: 10, permission: PERMISSIONS.patients.read })

    const all = resolveSlot('ordered.slot', {}, { can: () => true })
    expect(all.map(e => e.id)).toEqual(['a', 'b'])

    const onlyUngated = resolveSlot('ordered.slot', {}, { can: () => false })
    expect(onlyUngated.map(e => e.id)).toEqual(['b'])
  })

  it('drops an entry whose condition rejects the ctx (#506)', async () => {
    const { registerSlot, resolveSlot } = await import('~/composables/useModuleSlots')

    // A gateway rail that only applies to India clinics — razorpay's own
    // gate. The payment modal decides whether to render its "Collect now"
    // group from `resolve()`, not from the registered count, so a Spanish
    // clinic with the module installed must come back empty and get no
    // heading at all.
    const Rail = defineComponent({ name: 'Rail', render: () => h('span', 'rail') })
    registerSlot('payments.create.methods', {
      id: 'gateway.rail',
      component: Rail,
      condition: (ctx: { clinic?: { country?: string } }) => ctx.clinic?.country === 'IN'
    })

    const inIndia = resolveSlot(
      'payments.create.methods', { clinic: { country: 'IN' } }, { can: () => true }
    )
    expect(inIndia.map(e => e.id)).toEqual(['gateway.rail'])

    const elsewhere = resolveSlot(
      'payments.create.methods', { clinic: { country: 'ES' } }, { can: () => true }
    )
    expect(elsewhere).toHaveLength(0)
  })

  it('treats a missing condition as "always" (#506)', async () => {
    const { registerSlot, resolveSlot } = await import('~/composables/useModuleSlots')

    const Plain = defineComponent({ name: 'Plain', render: () => h('span', 'plain') })
    registerSlot('payments.create.methods', { id: 'no.condition', component: Plain })

    const entries = resolveSlot('payments.create.methods', {}, { can: () => true })
    expect(entries.map(e => e.id)).toEqual(['no.condition'])
  })
})
