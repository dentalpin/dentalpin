import { test, expect } from './_fixtures'

/**
 * Smoke for the admin module manager at /settings/modules.
 * - Admin can reach the page and see the module list.
 * - Non-admin cannot (page shows a forbidden message).
 */

test.describe('admin sees module manager', () => {
  test.use({ role: 'admin' })

  test('admin loads /settings/modules and sees module cards', async ({ loggedIn }) => {
    await loggedIn.goto('/settings/modules')

    // Page title (ES or EN, depending on user locale).
    await expect(
      loggedIn.getByRole('heading', { level: 1, name: /módulos|modules/i })
    ).toBeVisible()

    // Search for "patients" — modules are alphabetical and there are
    // ~50 of them, so patients lands on page 2 at PAGE_SIZE = 20.
    await loggedIn.getByPlaceholder(/buscar módulos|search modules/i).fill('patients')

    // At least one of the core modules must be listed — they are always
    // discovered, so this is a deterministic smoke check.
    await expect(
      loggedIn.getByRole('heading', { level: 3, name: /^patients$/ })
    ).toBeVisible()
  })
})

test.describe('hygienist cannot reach module manager', () => {
  test.use({ role: 'hygienist' })

  test('hygienist sees forbidden message, no module cards', async ({ loggedIn }) => {
    await loggedIn.goto('/settings/modules')

    // No module cards rendered.
    await expect(
      loggedIn.getByRole('heading', { level: 3, name: /^patients$/ })
    ).toHaveCount(0)

    // The page renders a forbidden fallback.
    await expect(
      loggedIn.getByText(/acceso denegado|access denied/i)
    ).toBeVisible()
  })
})
