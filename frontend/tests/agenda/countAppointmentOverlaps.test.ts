import { describe, expect, it } from 'vitest'
import type { Appointment } from '~~/app/types'
import { countAppointmentOverlaps } from '#module-layers/agenda/frontend/composables/countAppointmentOverlaps'

function apt(id: string, overrides: Partial<Appointment> = {}): Appointment {
  return {
    id,
    professional_id: 'other',
    start_time: '2026-05-18T10:00:00Z',
    end_time: '2026-05-18T10:30:00Z',
    status: 'scheduled',
    cabinet: null,
    ...overrides
  } as Appointment
}

const query = {
  appointmentId: 'moved',
  date: '2026-05-18',
  startTime: '10:15',
  endTime: '10:45',
  professionalId: 'pro1',
  cabinet: null as string | null
}

describe('countAppointmentOverlaps', () => {
  it('does not treat two unassigned appointments as sharing a cabinet', () => {
    expect(countAppointmentOverlaps([apt('a')], query).sameCabinet).toBe(0)
  })

  it('does not match an assigned appointment when the moved one is unassigned', () => {
    expect(countAppointmentOverlaps([apt('a', { cabinet: 'Cab 1' })], query).sameCabinet).toBe(0)
  })

  it('counts an overlap in the same named cabinet', () => {
    const result = countAppointmentOverlaps([apt('a', { cabinet: 'Cab 1' })], {
      ...query,
      cabinet: 'Cab 1'
    })
    expect(result.sameCabinet).toBe(1)
  })

  it('ignores another named cabinet', () => {
    const result = countAppointmentOverlaps([apt('a', { cabinet: 'Cab 2' })], {
      ...query,
      cabinet: 'Cab 1'
    })
    expect(result.sameCabinet).toBe(0)
  })

  it('still warns about the professional when neither has a cabinet', () => {
    const result = countAppointmentOverlaps([apt('a', { professional_id: 'pro1' })], query)
    expect(result).toEqual({ sameProfessional: 1, sameCabinet: 0 })
  })

  it('skips the moved appointment, cancelled ones, other days and touching slots', () => {
    const others = [
      apt('moved', { professional_id: 'pro1' }),
      apt('cancelled', { professional_id: 'pro1', status: 'cancelled' }),
      apt('other-day', {
        professional_id: 'pro1',
        start_time: '2026-05-19T10:00:00Z',
        end_time: '2026-05-19T10:30:00Z'
      }),
      apt('touching', {
        professional_id: 'pro1',
        start_time: '2026-05-18T10:45:00Z',
        end_time: '2026-05-18T11:00:00Z'
      })
    ]
    expect(countAppointmentOverlaps(others, query).sameProfessional).toBe(0)
  })
})
