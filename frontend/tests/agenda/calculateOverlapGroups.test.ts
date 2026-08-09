import { describe, expect, it } from 'vitest'
import type { Appointment } from '~~/app/types'
// Import directly from the agenda module's frontend layer. Nuxt aliases
// would require the full Nuxt env, so we use a relative path that works
// both locally and in CI (the /module_layers/ symlink only exists in Docker).
import { calculateOverlapGroups } from '../../../backend/app/modules/agenda/frontend/composables/calculateOverlapGroups'

function apt(id: string, start: string, end: string): Appointment {
  return {
    id,
    clinic_id: 'c1',
    patient_id: 'p1',
    professional_id: 'pro1',
    start_time: `2026-05-18T${start}:00Z`,
    end_time: `2026-05-18T${end}:00Z`,
    status: 'scheduled',
    cabinet: null,
    treatment_type: null,
    notes: null,
    confirmation_sent_at: null,
    confirmed_at: null,
    checked_in_at: null,
    completed_at: null,
    cancelled_at: null,
    cancellation_reason: null,
    patient: null,
    professional: null,
    created_at: '2026-05-18T00:00:00Z',
    updated_at: '2026-05-18T00:00:00Z'
  } as Appointment
}

describe('calculateOverlapGroups', () => {
  it('returns empty map for empty input', () => {
    expect(calculateOverlapGroups([]).size).toBe(0)
  })

  it('singletons get index 0 total 1', () => {
    const r = calculateOverlapGroups([apt('a', '09:00', '09:30')])
    expect(r.get('a')).toEqual({ index: 0, total: 1 })
  })

  it('non-overlapping appointments stay in separate groups', () => {
    const r = calculateOverlapGroups([
      apt('a', '09:00', '09:30'),
      apt('b', '10:00', '10:30'),
      apt('c', '11:00', '11:30')
    ])
    expect(r.get('a')).toEqual({ index: 0, total: 1 })
    expect(r.get('b')).toEqual({ index: 0, total: 1 })
    expect(r.get('c')).toEqual({ index: 0, total: 1 })
  })

  it('two overlapping appointments → group size 2', () => {
    const r = calculateOverlapGroups([
      apt('a', '09:00', '10:00'),
      apt('b', '09:30', '10:30')
    ])
    expect(r.get('a')).toEqual({ index: 0, total: 2 })
    expect(r.get('b')).toEqual({ index: 1, total: 2 })
  })

  it('chain transitively merges groups (A↔B↔C)', () => {
    const r = calculateOverlapGroups([
      apt('a', '09:00', '10:00'),
      apt('b', '09:30', '10:30'),
      apt('c', '10:15', '11:00')
    ])
    expect(r.get('a')?.total).toBe(3)
    expect(r.get('b')?.total).toBe(3)
    expect(r.get('c')?.total).toBe(3)
    expect(r.get('a')?.index).toBe(0)
    expect(r.get('b')?.index).toBe(1)
    expect(r.get('c')?.index).toBe(2)
  })

  it('non-transitive: A-B overlap, C separate', () => {
    const r = calculateOverlapGroups([
      apt('a', '09:00', '09:45'),
      apt('b', '09:30', '10:00'),
      apt('c', '11:00', '11:30')
    ])
    expect(r.get('a')?.total).toBe(2)
    expect(r.get('b')?.total).toBe(2)
    expect(r.get('c')).toEqual({ index: 0, total: 1 })
  })

  it('identical start times → grouped, deterministic indices', () => {
    const r = calculateOverlapGroups([
      apt('a', '09:00', '10:00'),
      apt('b', '09:00', '10:00')
    ])
    expect(r.get('a')?.total).toBe(2)
    expect(r.get('b')?.total).toBe(2)
  })

  it('touching endpoints do not overlap (end===start)', () => {
    const r = calculateOverlapGroups([
      apt('a', '09:00', '10:00'),
      apt('b', '10:00', '11:00')
    ])
    expect(r.get('a')).toEqual({ index: 0, total: 1 })
    expect(r.get('b')).toEqual({ index: 0, total: 1 })
  })

  it('handles 20 overlapping items without timing out', () => {
    const items = Array.from({ length: 20 }, (_, i) =>
      apt(`x${i}`, '09:00', '10:00')
    )
    const r = calculateOverlapGroups(items)
    for (const it of items) expect(r.get(it.id)?.total).toBe(20)
  })
})
