import type { Appointment, AppointmentCreate } from '~~/app/types'

const MS_PER_MINUTE = 60_000

interface AppointmentTiming {
  date: string
  startTime: string
  duration: number
}

interface SavedAppointmentTiming extends AppointmentTiming {
  startIso: string
}

type AppointmentTimes = Pick<AppointmentCreate, 'start_time' | 'end_time'>

export function readAppointmentTiming(
  appointment: Pick<Appointment, 'start_time' | 'end_time'>
): SavedAppointmentTiming {
  return {
    date: appointment.start_time.slice(0, 10),
    startTime: appointment.start_time.slice(11, 16),
    duration: (Date.parse(appointment.end_time) - Date.parse(appointment.start_time)) / MS_PER_MINUTE,
    startIso: appointment.start_time
  }
}

export function appointmentTimes(timing: AppointmentTiming): AppointmentTimes {
  const startTime = `${timing.date}T${timing.startTime}:00`
  // Use UTC for the arithmetic, then send clinic-local wall-clock timestamps.
  const end = new Date(Date.parse(`${startTime}Z`) + timing.duration * MS_PER_MINUTE)
  return { start_time: startTime, end_time: end.toISOString().replace(/(?:\.000)?Z$/, '') }
}

export function editedAppointmentTimes(
  original: SavedAppointmentTiming,
  timing: AppointmentTiming
): Partial<AppointmentTimes> {
  if (timing.date !== original.date || timing.startTime !== original.startTime) {
    return appointmentTimes(timing)
  }
  if (timing.duration === original.duration) return {}

  // Keep the persisted start instant, including its offset and seconds.
  const end = new Date(Date.parse(original.startIso) + timing.duration * MS_PER_MINUTE)
  return { end_time: end.toISOString() }
}
