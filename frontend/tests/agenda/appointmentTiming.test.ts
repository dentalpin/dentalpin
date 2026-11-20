import { describe, expect, it } from 'vitest'
import {
  editedAppointmentTimes,
  readAppointmentTiming
} from '../../../backend/app/modules/agenda/frontend/utils/appointmentTiming'

const appointment = {
  patient_id: 'alex-example',
  start_time: '2026-12-10T12:00:00+01:00',
  end_time: '2026-12-10T13:15:00+01:00'
}
const original = readAppointmentTiming(appointment)

describe('appointment timing when editing', () => {
  it('keeps the stored 75 minutes when only the patient changes', () => {
    expect(original.duration).toBe(75)
    const update = { patient_id: 'sam-example', ...editedAppointmentTimes(original, original) }
    expect(update).toEqual({ patient_id: 'sam-example' })
    expect({ ...appointment, ...update }).toEqual({ ...appointment, patient_id: 'sam-example' })
  })

  it('updates the end time when another duration is selected', () => {
    const change = editedAppointmentTimes(original, { ...original, duration: 45 })

    expect(change).toEqual({ end_time: '2026-12-10T11:45:00.000Z' })
  })

  it('keeps the 75 minutes when only the start time changes across midnight', () => {
    const change = editedAppointmentTimes(original, { ...original, startTime: '23:30' })

    expect(change).toEqual({
      start_time: '2026-12-10T23:30:00',
      end_time: '2026-12-11T00:45:00'
    })
  })

  it('retains the stored precision when recalculating only the end time', () => {
    const withSeconds = readAppointmentTiming({
      start_time: '2026-12-10T12:00:23.500+01:00',
      end_time: '2026-12-10T13:15:53.500+01:00'
    })

    expect(withSeconds.duration).toBe(75.5)
    expect(editedAppointmentTimes(withSeconds, { ...withSeconds, duration: 60 }))
      .toEqual({ end_time: '2026-12-10T12:00:23.500Z' })
  })
})
