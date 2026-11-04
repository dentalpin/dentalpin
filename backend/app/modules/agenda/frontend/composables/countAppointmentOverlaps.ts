import type { Appointment } from '~~/app/types'

export interface OverlapQuery {
  /** The appointment being moved; it never overlaps itself. */
  appointmentId: string
  /** `YYYY-MM-DD`, compared with the date part of `start_time`. */
  date: string
  /** `HH:MM` */
  startTime: string
  /** `HH:MM` */
  endTime: string
  professionalId: string
  cabinet: string | null
}

function toMinutes(time: string): number {
  const [hours, minutes] = time.split(':').map(Number)
  return (hours ?? 0) * 60 + (minutes ?? 0)
}

/**
 * Count the active appointments a new placement overlaps, per shared resource.
 *
 * An unassigned appointment (`cabinet` null, see #51) occupies no cabinet, so
 * two unassigned appointments do not compete for one.
 */
export function countAppointmentOverlaps(
  appointments: readonly Appointment[],
  query: OverlapQuery
): { sameProfessional: number, sameCabinet: number } {
  const newStart = toMinutes(query.startTime)
  const newEnd = toMinutes(query.endTime)
  let sameProfessional = 0
  let sameCabinet = 0

  for (const apt of appointments) {
    if (apt.id === query.appointmentId || apt.status === 'cancelled') continue
    if (apt.start_time.split('T')[0] !== query.date) continue

    const aptStart = toMinutes(apt.start_time.split('T')[1]?.substring(0, 5) ?? '00:00')
    const aptEnd = toMinutes(apt.end_time.split('T')[1]?.substring(0, 5) ?? '00:00')
    if (newStart >= aptEnd || newEnd <= aptStart) continue

    if (apt.professional_id === query.professionalId) sameProfessional++
    if (query.cabinet !== null && apt.cabinet === query.cabinet) sameCabinet++
  }

  return { sameProfessional, sameCabinet }
}
