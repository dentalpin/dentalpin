import { test, expect } from './_fixtures'

/**
 * Team invite link: admin creates a user without a password, gets a
 * one-time link; the invitee sets a password in a fresh context and
 * lands on the dashboard signed in.
 */
const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'
const EMAIL = `invitee-${Date.now()}@e2e.clinic`

test.describe('invite link', () => {
  test.use({ role: 'admin' })

  test('create user without password → link → set password → signed in', async ({ loggedIn, browser }) => {
    await loggedIn.goto('/settings/people/users')
    await loggedIn.getByRole('button', { name: /nuevo usuario|new user/i }).click()

    const dialog = loggedIn.getByRole('dialog')
    await dialog.getByRole('textbox', { name: /^nombre$|first name/i }).fill('Invitada')
    await dialog.getByRole('textbox', { name: /apellidos|last name/i }).fill('E2E')
    await dialog.getByRole('textbox', { name: /email|correo/i }).fill(EMAIL)
    await dialog.getByRole('button', { name: /crear y generar enlace|create and generate link/i }).click()

    const linkInput = dialog.locator('input[readonly]')
    await expect(linkInput).toBeVisible()
    const url = await linkInput.inputValue()
    expect(url).toContain('/set-password?token=')

    // Invitee in a clean context
    const ctx = await browser.newContext()
    const page = await ctx.newPage()
    await page.goto(url)
    await page.waitForLoadState('networkidle') // hydrate before typing
    await page.locator('input[name="password"]').fill('Invitee12345')
    await page.locator('input[name="passwordConfirm"]').fill('Invitee12345')
    await page.getByRole('button', { name: /guardar y entrar|save and sign in/i }).click()
    await page.waitForURL(u => u.pathname === '/', { timeout: 15_000 })
    await expect(page.getByRole('heading', { level: 1 })).toContainText(/Invitada/)

    // Link is single use
    await page.goto(url)
    await page.waitForLoadState('networkidle')
    await page.locator('input[name="password"]').fill('Invitee12345')
    await page.locator('input[name="passwordConfirm"]').fill('Invitee12345')
    await page.getByRole('button', { name: /guardar y entrar|save and sign in/i }).click()
    await expect(page.getByRole('alert')).toBeVisible()
    await ctx.close()

    // Cleanup: delete the invitee
    const token = (await loggedIn.context().cookies()).find(c => c.name === 'access_token')?.value
    const headers = { Authorization: `Bearer ${token}` }
    const users = await loggedIn.request.get(`${API_BASE}/api/v1/auth/users`, { headers })
    const created = (await users.json()).data.find((u: { email: string }) => u.email === EMAIL)
    if (created) await loggedIn.request.delete(`${API_BASE}/api/v1/auth/users/${created.id}`, { headers })
  })
})

test.describe('non-admins never see the getting-started card', () => {
  test.use({ role: 'receptionist' })

  test('receptionist dashboard has no card', async ({ loggedIn }) => {
    await loggedIn.goto('/')
    await expect(loggedIn.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(loggedIn.getByRole('region', { name: /puesta en marcha|getting started/i })).toHaveCount(0)
  })
})
