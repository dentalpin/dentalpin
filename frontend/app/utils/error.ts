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
    const obj = e as { data?: { detail?: unknown, message?: string }, message?: string }
    if (typeof obj.data?.detail === 'string') return obj.data.detail
    return obj.data?.message ?? obj.message ?? fallback
  }
  return fallback
}

export function errorStatus(e: unknown): number | undefined {
  if (typeof e === 'object' && e !== null) {
    return (e as { statusCode?: number }).statusCode
  }
  return undefined
}
