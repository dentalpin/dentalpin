/** Failed public booking call; `status` is the HTTP status, or 0 for a network failure. */
export class PublicBookingError extends Error {
  constructor(public status: number) {
    super(`request failed (${status})`)
  }
}
