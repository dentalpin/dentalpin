/**
 * Check-in window failure parser (agenda, ADR 0037).
 *
 * The backend answers 422 with a machine-stable string the global HTTP
 * handler passes through untouched: `too_early:<HH:MM>` or
 * `window_closed`. Split on the FIRST colon only: the time itself
 * contains a colon, and splitting on every colon drops the minutes
 * (review round on #667: "Your appointment is at 09." for 09:30).
 */
export interface CheckinWindowFailure {
  code: 'too_early' | 'window_closed' | 'unknown'
  time: string
}

export function parseCheckinResult(message: string): CheckinWindowFailure {
  const sep = message.indexOf(':')
  if (sep === -1) {
    if (message === 'too_early' || message === 'window_closed') {
      return { code: message, time: '' }
    }
    return { code: 'unknown', time: '' }
  }
  const code = message.slice(0, sep)
  const time = message.slice(sep + 1)
  if (code === 'too_early' || code === 'window_closed') {
    return { code, time }
  }
  return { code: 'unknown', time: '' }
}
