import { test as base, expect, type Page } from '@playwright/test'

/**
 * Credentials for the seeded demo users (`./scripts/seed-demo.sh`).
 * All share the password `demo1234`.
 */
export const ROLES = {
  admin: 'admin@demo.clinic',
  dentist: 'dentist@demo.clinic',
  hygienist: 'hygienist@demo.clinic',
  assistant: 'assistant@demo.clinic',
  receptionist: 'receptionist@demo.clinic'
} as const

export type Role = keyof typeof ROLES

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'

/**
 * Log in via direct API call + cookie set.
 *
 * We bypass the browser form for two reasons:
 * 1. Chromium's preflight interaction with Nuxt's client-side fetch
 *    flakes in Playwright (the form works fine in a real browser).
 * 2. Auth state lives in a ``useCookie`` named ``access_token``;
 *    setting it directly is the same thing the login handler does.
 *
 * After this, a regular ``page.goto(...)`` hits the auth middleware
 * with the token already present and skips the redirect to ``/login``.
 */
export async function login(page: Page, role: Role): Promise<void> {
  const ctx = page.context()

  const form = new URLSearchParams({
    username: ROLES[role],
    password: 'demo1234'
  })
  const response = await ctx.request.post(`${API_BASE}/api/v1/auth/login`, {
    data: form.toString(),
    headers: { 'content-type': 'application/x-www-form-urlencoded' }
  })
  if (!response.ok()) {
    throw new Error(`login failed: ${response.status()} ${await response.text()}`)
  }
  const body = (await response.json()) as { access_token: string }

  // Mirror Nuxt's useCookie: default scope is the whole site, plain
  // serialization, not httpOnly (so client JS can read it).
  const origin = page.url() !== 'about:blank' ? new URL(page.url()).origin : 'http://localhost:3000'
  await ctx.addCookies([
    {
      name: 'access_token',
      value: body.access_token,
      url: origin
    },
    {
      // Pin the UI language. SSR and hydration then agree from the
      // first paint, so text locators never race a post-hydration
      // language switch — the race that blocked prod-build e2e, where
      // lazy locale messages arrive as a hashed chunk after hydration
      // (#259). Pinned to `en` because the suite's locators are
      // authored against the English chrome (e.g. /New payment/i);
      // seeded *data* (patient and treatment names) stays Spanish
      // either way.
      name: 'dentalpin_locale',
      value: 'en',
      url: origin
    }
  ])

  // Prime the session by landing on the dashboard.
  await page.goto('/')
  await page.waitForURL(url => url.pathname === '/', { timeout: 10_000 })
}

type RoleFixture = {
  role: Role
  loggedIn: Page
}

export const test = base.extend<RoleFixture>({
  role: ['admin', { option: true }],
  loggedIn: async ({ page, role }, use) => {
    await login(page, role)
    await use(page)
  }
})

export { expect }
