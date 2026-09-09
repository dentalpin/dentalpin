import { test, expect } from '@playwright/test'

/**
 * First-run wizard. Needs an UNINITIALIZED database (no users) — run via
 * ``./scripts/e2e-fresh.sh`` which resets the DB, runs this spec with
 * ``E2E_FRESH=1`` and re-seeds the demo afterwards.
 */
test.skip(!process.env.E2E_FRESH, 'requires a fresh DB (scripts/e2e-fresh.sh)')

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'

test('fresh install: /setup creates an operative Spanish clinic and shows the getting-started card', async ({ page }) => {
  await page.goto('/')
  await page.waitForURL(url => url.pathname === '/setup', { timeout: 15_000 })
  // Let Nuxt hydrate before typing — values typed pre-hydration are wiped.
  await page.waitForLoadState('networkidle')

  // Step 1 — admin account
  await page.getByRole('textbox', { name: /nombre$|first name/i }).fill('Ana')
  await page.getByRole('textbox', { name: /apellidos|last name/i }).fill('Pérez')
  await page.getByRole('textbox', { name: /correo|email/i }).fill('ana@e2e.clinic')
  await page.locator('input[name="password"]').fill('Secure123xyz')
  await page.locator('input[name="passwordConfirm"]').fill('Secure123xyz')
  await page.getByRole('button', { name: /siguiente|next/i }).click()

  // Step 2 — clinic + country
  await page.getByRole('textbox', { name: /nombre de la clínica|clinic name/i }).fill('Clínica E2E')
  const country = page.getByRole('button', { name: /show popup/i }).first()
  await country.click()
  // Labels follow the UI locale (Intl.DisplayNames): "Spain" (en) / "España" (es).
  const search = page.getByRole('combobox', { name: /search country|buscar país/i })
  await search.fill('Spain')
  if (await page.getByRole('option', { name: /^Spain$/ }).count() === 0) await search.fill('España')
  await page.getByRole('option', { name: /^España$|^Spain$/ }).first().click()
  await expect(page.getByRole('listbox')).toHaveCount(0)
  const taxId = page.locator('input[name="taxId"]')
  await expect(taxId).toBeVisible()
  await taxId.click()
  await taxId.fill('B12345674')
  await expect(taxId).toHaveValue('B12345674')
  await page.getByRole('button', { name: /crear mi clínica|create my clinic/i }).click()

  await page.waitForURL(url => url.pathname === '/', { timeout: 30_000 })

  // Seeded defaults are visible through the API
  const token = (await page.context().cookies()).find(c => c.name === 'access_token')?.value
  expect(token).toBeTruthy()
  const headers = { Authorization: `Bearer ${token}` }
  const series = await page.request.get(`${API_BASE}/api/v1/billing/series`, { headers })
  expect((await series.json()).data.map((s: { prefix: string }) => s.prefix).sort()).toEqual(['FAC', 'RECT'])
  const cabinets = await page.request.get(`${API_BASE}/api/v1/agenda/cabinets`, { headers })
  expect((await cabinets.json()).data).toHaveLength(1)
  const items = await page.request.get(`${API_BASE}/api/v1/catalog/items?page_size=1`, { headers })
  expect((await items.json()).total).toBeGreaterThan(100)

  // Getting-started card with pending steps (clinic address, team…)
  const card = page.getByRole('region', { name: /puesta en marcha|getting started/i })
  await expect(card).toBeVisible()
  await expect(card.getByRole('button', { name: /configurar|set up/i }).first()).toBeVisible()

  // Skip persists server-side (survives a reload)
  const before = await card.getByRole('button', { name: /omitir|skip/i }).count()
  await card.getByRole('button', { name: /omitir|skip/i }).first().click()
  await expect(card.getByRole('button', { name: /omitir|skip/i })).toHaveCount(before - 1)
  await page.reload()
  await expect(page.getByRole('region', { name: /puesta en marcha|getting started/i })
    .getByRole('button', { name: /omitir|skip/i })).toHaveCount(before - 1)
})
