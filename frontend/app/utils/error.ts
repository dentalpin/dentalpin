/**
 * Narrow `unknown` thrown by `useApi` / `$fetch` to a user-facing message.
 * Reads, in order: `.data.detail`, `.data.message`, `.message`. Falls back
 * to the provided default.
 *
 * `.data.detail` is only used when it is a string: FastAPI's own 422
 * handler puts a list of validation objects there, and rendering that
 * yields "[object Object]" — less useful than the caller's fallback.
 */
export function errorMessage(e: unknown, fallback: string): string {
  if (typeof e === 'object' && e !== null) {
    return errorDetail(e) ?? (e as { message?: string }).message ?? fallback
  }
  return fallback
}

/**
 * The server's own explanation, or `undefined` when the failure carries
 * none (network drop, thrown `Error`). Use it as a toast `description`
 * under an already-localized `title`: passing `undefined` leaves the
 * toast exactly as it was before, so a generic title never gains an
 * empty second line.
 */
export function errorDetail(e: unknown): string | undefined {
  if (typeof e !== 'object' || e === null) return undefined
  const obj = e as { data?: { detail?: unknown, message?: unknown } }
  if (typeof obj.data?.detail === 'string') return obj.data.detail
  if (typeof obj.data?.message === 'string') return obj.data.message
  return undefined
}

export function errorStatus(e: unknown): number | undefined {
  if (typeof e === 'object' && e !== null) {
    return (e as { statusCode?: number }).statusCode
  }
  return undefined
}
