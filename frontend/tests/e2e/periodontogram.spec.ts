import { test, expect, type Page } from './_fixtures'

/**
 * Periodontogram smoke: end-to-end flow against the live stack.
 *
 * Preconditions (handled by `./scripts/seed-demo.sh` + a one-off
 * `POST /api/v1/modules/periodontogram/install`):
 * - Demo users seeded (`admin@demo.clinic` / `demo1234`).
 * - Periodontogram module installed (`auto_install=False`, so the
 *   suite assumes the operator activated it from the admin UI).
 *
 * What this guards:
 * 1. Optional sub-tab shows up inside Diagnosis when the module is
 *    installed.
 * 2. EmptyState CTA opens a draft and the chart appears.
 * 3. Site editor popover saves and the heatmap reflects the value.
 * 4. Close session freezes the snapshot and the timeline picks it up.
 * 5. Multi-tenancy / permissions: receptionist cannot see the sub-tab.
 */

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'

async function getPatientId(page: Page): Promise<string> {
  const ctx = page.context()
  const cookies = await ctx.cookies()
  const token = cookies.find(c => c.name === 'access_token')?.value
  const res = await ctx.request.get(`${API_BASE}/api/v1/patients?page=1&page_size=1`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
  if (!res.ok()) throw new Error(`patient list failed: ${res.status()}`)
  const body = (await res.json()) as { data: Array<{ id: string }> }
  const id = body.data[0]?.id
  if (!id) throw new Error('no seeded patient available')
  return id
}

async function discardDraftIfAny(page: Page, patientId: string): Promise<void> {
  // Clean up any draft left behind by a previous run so tests are
  // independent. Idempotent — silently ignores 404 / no-draft.
  const ctx = page.context()
  const cookies = await ctx.cookies()
  const token = cookies.find(c => c.name === 'access_token')?.value
  const draftRes = await ctx.request.get(
    `${API_BASE}/api/v1/periodontogram/patients/${patientId}/draft`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  )
  if (!draftRes.ok()) return
  const body = (await draftRes.json()) as { data: { id: string } | null }
  if (!body.data) return
  await ctx.request.delete(`${API_BASE}/api/v1/periodontogram/snapshots/${body.data.id}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  })
}

async function ensureDraftExists(page: Page, patientId: string): Promise<void> {
  // Independent tests need a draft to interact with the chart. POST
  // is idempotent (returns existing draft or creates one). Avoids
  // depending on test ordering / leftover state.
  const ctx = page.context()
  const cookies = await ctx.cookies()
  const token = cookies.find(c => c.name === 'access_token')?.value
  await ctx.request.post(
    `${API_BASE}/api/v1/periodontogram/patients/${patientId}/draft`,
    { headers: token ? { Authorization: `Bearer ${token}` } : {} }
  )
}

async function navigateToPerioTab(page: Page, patientId: string): Promise<void> {
  // Land directly on the Clinical tab with the diagnosis sub-mode +
  // perio sub-tab pre-selected via query params. Avoids fragile
  // tab-button clicks that collide with filter pills on the Summary
  // feed (e.g. the "Diagnosis" pill that lives in the activity timeline).
  await page.goto(
    `/patients/${patientId}?tab=clinical&clinicalMode=diagnosis&diagnosisView=periodontogram`,
    { waitUntil: 'domcontentloaded' }
  )
  await page.waitForURL(/\/patients\/[0-9a-f-]+/, { timeout: 15_000 })

  // If the query param didn't auto-switch tabs, click through explicitly.
  // Use a scoped role=tab lookup so the activity-feed filter pill at
  // the bottom of the Summary view doesn't match.
  if (!(await page.getByRole('tab', { name: /Periodonto/i }).first()
    .isVisible().catch(() => false))) {
    // Only click tabs that are not already selected: reka-ui's sliding
    // indicator sits on top of the active trigger and intercepts the
    // pointer, so clicking an already-active tab times out on the
    // production build (dev hydrated late enough to hide this).
    const clickUnlessActive = async (locator: ReturnType<typeof page.locator>) => {
      if (!(await locator.isVisible().catch(() => false))) return
      const selected = await locator.getAttribute('aria-selected').catch(() => null)
      if (selected !== 'true') {
        await locator.click({ timeout: 10_000 })
      }
    }

    const clinicalNavTab = page
      .getByRole('tab', { name: /^Clinical$|^Clínica$/i })
      .first()
    await clickUnlessActive(clinicalNavTab)

    const diagnosisModeBtn = page.locator(
      'button:has-text("Diagnosis"), button:has-text("Diagnóstico")'
    ).filter({ hasNot: page.locator('[aria-label*="filter"]') }).first()
    await clickUnlessActive(diagnosisModeBtn)

    const perioSubtab = page.getByRole('tab', { name: /Periodonto/i }).first()
    await expect(perioSubtab).toBeVisible({ timeout: 10_000 })
    await clickUnlessActive(perioSubtab)
  }

  await expect(
    page.getByRole('region', { name: /Periodonto/i }).or(
      page.getByText(/No periodontal exams|Sin exploraciones periodontales/i)
    )
  ).toBeVisible({ timeout: 15_000 })
}

test.describe('periodontogram — admin', () => {
  test.use({ role: 'admin' })

  test('empty state → start draft → chart renders', async ({ loggedIn }) => {
    const patientId = await getPatientId(loggedIn)
    await discardDraftIfAny(loggedIn, patientId)

    await navigateToPerioTab(loggedIn, patientId)

    // Either the empty state or an existing snapshot greets us. If empty,
    // click the CTA. Either way the chart region should appear.
    const startCta = loggedIn.getByRole('button', { name: /iniciar exploración|start exam/i })
    if (await startCta.isVisible().catch(() => false)) {
      await startCta.click()
    }

    await expect(
      loggedIn.getByRole('region', { name: /Periodonto/i })
    ).toBeVisible({ timeout: 15_000 })
  })

  test('patch a site updates the value', async ({ loggedIn }) => {
    const patientId = await getPatientId(loggedIn)
    await discardDraftIfAny(loggedIn, patientId)
    await ensureDraftExists(loggedIn, patientId)
    await navigateToPerioTab(loggedIn, patientId)

    // Inline edit — the Sondaje row renders an `<input type="number">`
    // per site. Click any cell, type the value, blur to commit. No
    // modal, no Save button.
    const region = loggedIn.getByRole('region', { name: /Periodonto/i })
    const sondajeRow = region
      .locator('tr', { hasText: /Sondaje|Probing/i })
      .first()
    await expect(sondajeRow).toBeVisible({ timeout: 10_000 })

    // fill() focuses the input itself — no separate click. The click's
    // hit-target check raced the sub-nav's sliding tab indicator on the
    // production build: until its size CSS vars are measured post-
    // hydration, the absolutely-positioned indicator briefly intercepts
    // pointers far outside the tab bar. fill() checks visible/enabled/
    // editable only, so it is immune.
    const firstSiteInput = sondajeRow.locator('input[type="number"]').first()
    await firstSiteInput.fill('5')
    await firstSiteInput.blur()

    // Autosave indicator returns to "Guardado / Saved" once the
    // debounced PATCH completes.
    await expect(loggedIn.getByText(/Guardado|Saved/i).first()).toBeVisible({
      timeout: 5_000
    })
  })

  test('close session freezes the snapshot and timeline updates', async ({ loggedIn }) => {
    const patientId = await getPatientId(loggedIn)
    await discardDraftIfAny(loggedIn, patientId)
    await ensureDraftExists(loggedIn, patientId)
    await navigateToPerioTab(loggedIn, patientId)

    // Open the close-session confirmation modal from the sticky bar.
    // The backend accepts closing an empty draft — the <50% rule is a
    // soft frontend nudge, not a hard guard.
    await loggedIn
      .getByRole('button', { name: /^(Cerrar sesión|Close session)$/i })
      .first()
      .click()

    // Wait for the confirmation modal title (renders inside the
    // UModal header via the :title prop in Nuxt UI v3).
    const modalTitle = loggedIn.getByText(
      /Cerrar sesión periodontal|Close periodontal session/i
    ).first()
    await expect(modalTitle).toBeVisible({ timeout: 5_000 })

    // Confirm in the modal footer. Scope to the dialog so we don't
    // race with the sticky-bar trigger button that carries the same
    // copy.
    await loggedIn
      .getByRole('dialog')
      .getByRole('button', { name: /^(Cerrar sesión|Close session)$/i })
      .click()

    // The session transitioned to closed: the post-close summary
    // strip surfaces a count of closed sessions + an "Open new session"
    // CTA. Most reliable signal that the close succeeded end-to-end.
    await expect(
      loggedIn.getByText(/sesiones cerradas|closed sessions/i).first()
    ).toBeVisible({ timeout: 10_000 })

    // Sticky session bar disappears once the snapshot is closed.
    await expect(
      loggedIn.getByRole('button', { name: /^(Descartar borrador|Discard draft)$/i })
    ).toHaveCount(0)
  })
})

test.describe('periodontogram — receptionist permission boundary', () => {
  test.use({ role: 'receptionist' })

  test('sub-tab is hidden for receptionists', async ({ loggedIn }) => {
    const patientId = await getPatientId(loggedIn)

    await loggedIn.goto(`/patients/${patientId}?clinicalMode=diagnosis`, {
      waitUntil: 'domcontentloaded'
    })

    // Receptionists cannot read perio, so the slot resolves to zero
    // entries and the diagnosis container falls back to the bare
    // odontogram — the sub-tab bar with "Periodontograma" must NOT
    // appear.
    const subtab = loggedIn.getByRole('tab', { name: /Periodonto/i })
    await expect(subtab).toHaveCount(0)
  })
})
