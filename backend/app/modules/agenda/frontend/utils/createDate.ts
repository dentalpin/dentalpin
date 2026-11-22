/**
 * The day a new appointment starts on: the one the caller names (the mobile
 * day view, whose `viewMode` stays `week`), else the one being viewed, else
 * today from the week view, which has no single day (#1037).
 */
export function createAppointmentDate(
  viewMode: 'week' | 'day' | 'kanban',
  viewed: Date,
  today: Date,
  requested?: Date
): Date {
  return requested ?? (viewMode === 'week' ? today : viewed)
}
