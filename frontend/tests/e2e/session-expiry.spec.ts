import { test, expect } from './_fixtures'

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'

/**
 * ADR 0023: reloading a deep link after the access cookie expired must
 * land on that URL, refreshed server-side, with no detour through /login.
 * Expiry is simulated by dropping `dp_access` from the context's jar while
 * `dp_refresh` and `dp_csrf` stay — exactly what the browser sends once the
 * 15-minute cookie is gone.
 */
test.describe('session expiry', () => {
  test.use({ role: 'admin' })

  test('reload of a deep link after access-cookie expiry stays on the page', async ({ loggedIn }) => {
    const ctx = loggedIn.context()
    await ctx.clearCookies({ name: 'dp_access' })
    const before = await ctx.cookies()
    expect(before.some(c => c.name === 'dp_access')).toBe(false)
    expect(before.some(c => c.name === 'dp_refresh')).toBe(true)
    const csrfBefore = before.find(c => c.name === 'dp_csrf')?.value

    const visited: string[] = []
    loggedIn.on('framenavigated', (frame) => {
      if (frame === loggedIn.mainFrame()) visited.push(new URL(frame.url()).pathname)
    })

    await loggedIn.goto('/patients')
    await expect(loggedIn.getByRole('heading', { level: 1 })).toBeVisible()
    expect(new URL(loggedIn.url()).pathname).toBe('/patients')
    expect(visited).not.toContain('/login')

    // SSR refreshed the session: a new access cookie, a rotated refresh
    // cookie, and the CSRF token unchanged (per family, not per token).
    const after = await ctx.cookies()
    expect(after.some(c => c.name === 'dp_access')).toBe(true)
    expect(after.find(c => c.name === 'dp_refresh')?.value).not.toBe(before.find(c => c.name === 'dp_refresh')?.value)
    expect(after.find(c => c.name === 'dp_csrf')?.value).toBe(csrfBefore)

    // The rotated session keeps working for a mutation from this page.
    const res = await loggedIn.request.patch(`${API_BASE}/api/v1/auth/clinic/settings/communications`, {
      headers: { 'X-CSRF-Token': csrfBefore || '' },
      data: {}
    })
    expect([200, 422]).toContain(res.status())
  })
})
