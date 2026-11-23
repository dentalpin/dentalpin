import { describe, expect, it } from 'vitest'
import { createAppointmentDate } from '../../../backend/app/modules/agenda/frontend/utils/createDate'

describe('createAppointmentDate (#1037)', () => {
  const now = new Date(2026, 10, 22)
  const viewed = new Date(2026, 10, 24)

  it('books the viewed day from the day and kanban views', () => {
    expect(createAppointmentDate('day', viewed, now)).toBe(viewed)
    expect(createAppointmentDate('kanban', viewed, now)).toBe(viewed)
  })

  it('books today from the week view', () => {
    expect(createAppointmentDate('week', viewed, now)).toBe(now)
  })

  it('books the day the mobile view asks for, whatever the desktop view mode', () => {
    expect(createAppointmentDate('week', new Date(2026, 10, 1), now, viewed)).toBe(viewed)
  })
})
