/**
 * Allows the clinic's own website to embed `/p/booking/<clinicId>` in an
 * iframe. Sends an enforced `Content-Security-Policy: frame-ancestors ...`
 * for that route only, whatever `NUXT_CSP_MODE` is (a Report-Only policy
 * cannot enforce `frame-ancestors`). In `enforce` mode `csp.ts` reads the same
 * value from `event.context` and includes it in the full policy. Runs before
 * `csp.ts` (middleware load in file-name order).
 */
import { bookingFrameAncestors } from '../utils/bookingEmbed'

export default defineEventHandler(async (event) => {
  const value = await bookingFrameAncestors(event)
  if (!value) return
  event.context.frameAncestors = value
  setHeader(event, 'Content-Security-Policy', `frame-ancestors ${value}`)
})
