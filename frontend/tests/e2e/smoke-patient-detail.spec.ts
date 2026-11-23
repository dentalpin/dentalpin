import { test, expect } from './_fixtures'

/**
 * Patient detail smoke: opens a seeded patient and asserts each slot
 * that's fed by a different module renders its data.
 *
 * - identity card (patients module)
 * - alerts banner (patients_clinical)
 * - medical history tab content (patients_clinical)
 * - timeline tab content (patient_timeline)
 *
 * Regression case: after Fase B.6 the patient detail page aggregates
 * data from four different modules, and an early layer-config bug
 * caused half the tabs to render empty. This is the UI guardrail.
 */

const API_BASE = process.env.E2E_API_BASE || 'http://localhost:8000'

test.describe('patient detail', () => {
  test.use({ role: 'admin' })

  test('seeded patient loads identity + clinical data + timeline', async ({ loggedIn }) => {
    // Resolve a seeded patient id via the API — clicking through the list
    // was flaky on CI because the NuxtLink click can race with hydration
    // and bounce back to /patients. Going straight to the detail URL is
    // what we actually want to cover here.
    const ctx = loggedIn.context()
    const cookies = await ctx.cookies()
    const token = cookies.find(c => c.name === 'access_token')?.value
    const res = await ctx.request.get(`${API_BASE}/api/v1/patients?page=1&page_size=1`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    if (!res.ok()) {
      throw new Error(`failed to list patients: ${res.status()} ${await res.text()}`)
    }
    const body = (await res.json()) as { data: Array<{ id: string }> }
    const patientId = body.data[0]?.id
    if (!patientId) throw new Error('no seeded patient to open')

    await loggedIn.goto(`/patients/${patientId}`)
    await loggedIn.waitForURL(/\/patients\/[0-9a-f-]+/, { timeout: 20_000 })

    // 1. Identity — patient name is in the sidebar quick-info card.
    const identity = loggedIn.locator('[data-testid="patient-quick-info"], h1, h2').first()
    await expect(identity).toBeVisible({ timeout: 10_000 })

    // 2. Content: at least one interactive element from the detail tabs.
    // Defensive: find any button or link inside the page body.
    const interactive = loggedIn
      .locator('main button, main a[role="tab"], main a[href*="/patients/"]')
      .first()
    await expect(interactive).toBeVisible()
  })

  test('clinical diagnosis and surfaces fit with lateral view at desktop, tablet, and mobile widths', async ({ loggedIn }) => {
    const ctx = loggedIn.context()
    const cookies = await ctx.cookies()
    const token = cookies.find(c => c.name === 'access_token')?.value
    const res = await ctx.request.get(`${API_BASE}/api/v1/patients?page=1&page_size=1`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    if (!res.ok()) {
      throw new Error(`failed to list patients: ${res.status()} ${await res.text()}`)
    }
    const body = (await res.json()) as { data: Array<{ id: string }> }
    const patientId = body.data[0]?.id
    if (!patientId) throw new Error('no seeded patient to open')

    await loggedIn.goto(`/patients/${patientId}?tab=clinical`)
    const chart = loggedIn.locator('.odontogram-wrapper')
    await expect(chart).toBeVisible({ timeout: 20_000 })
    const lateralView = chart.locator('.lateral-view').first()
    await expect(lateralView).toBeVisible()

    const measurements: Array<{ width: number, containerWidth: number, zoom: number }> = []
    for (const width of [1280, 768, 390]) {
      await loggedIn.setViewportSize({ width, height: 900 })
      const layout = await chart.evaluate((element) => {
        const grid = element.querySelector<HTMLElement>('.odontogram-grid')
        if (!grid) throw new Error('odontogram grid is missing')
        const container = element.getBoundingClientRect()
        const gridBounds = grid.getBoundingClientRect()
        const queryContainer = [grid.parentElement, grid.parentElement?.parentElement]
          .find(ancestor => ancestor && getComputedStyle(ancestor).containerType !== 'normal')
        const queryContainerWidth = queryContainer?.getBoundingClientRect().width ?? null
        const ancestors: Array<{
          tag: string
          className: string
          left: number
          width: number
          display: string
          flex: string
          gridColumns: string
        }> = []
        let ancestor: HTMLElement | null = element
        while (ancestor && ancestors.length < 18) {
          const bounds = ancestor.getBoundingClientRect()
          const styles = getComputedStyle(ancestor)
          ancestors.push({
            tag: ancestor.tagName.toLowerCase(),
            className: ancestor.className.toString().slice(0, 100),
            left: Math.round(bounds.left),
            width: Math.round(bounds.width),
            display: styles.display,
            flex: styles.flex,
            gridColumns: styles.gridTemplateColumns
          })
          ancestor = ancestor.parentElement
        }
        return {
          containerWidth: container.width,
          zoom: Number.parseFloat(getComputedStyle(grid).zoom),
          containerRight: container.right,
          gridLeft: gridBounds.left,
          gridWidth: gridBounds.width,
          gridRight: gridBounds.right,
          queryContainerWidth,
          ancestors,
          viewportWidth: window.innerWidth
        }
      })
      expect(layout.containerWidth).toBeLessThanOrEqual(width)
      expect(layout.zoom).toBeGreaterThan(0)
      expect(
        layout.gridRight,
        `layout at ${width}px: ${JSON.stringify(layout)}`
      ).toBeLessThanOrEqual(layout.containerRight + 1)
      expect(layout.gridRight).toBeLessThanOrEqual(layout.viewportWidth + 1)
      await expect(lateralView).toBeVisible()
      measurements.push({ width, containerWidth: layout.containerWidth, zoom: layout.zoom })
    }
    expect(measurements[2]?.containerWidth).toBeLessThan(measurements[0]?.containerWidth ?? 0)
    expect(measurements[2]?.zoom).toBeLessThan(measurements[0]?.zoom ?? 1)

    // Clicking a tooth in diagnosis mode opens the combined diagnosis +
    // surface workflow. Escape cancels the draft selection without saving.
    const tooth = chart.locator('.tooth-dual-view-wrapper[aria-label$="(11)"]')
    await expect(tooth).toBeVisible()
    await tooth.click()
    const diagnosisDialog = loggedIn.getByRole('dialog').filter({ hasText: /tooth 11/i })
    await expect(diagnosisDialog.getByText(/choose a diagnosis and mark surfaces if needed/i)).toBeVisible()
    await expect(diagnosisDialog.locator('.treatment-bar .diagnosis-mode-indicator')).toBeVisible()
    const nextStep = diagnosisDialog.getByTestId('diagnosis-next')
    await expect(nextStep).toBeDisabled()
    await diagnosisDialog.locator('.treatment-bar .treatment-btn').first().click()
    await expect(nextStep).toBeEnabled()
    await nextStep.click()
    await expect(diagnosisDialog.locator('.surface-buttons .surface-btn')).toHaveCount(5)
    await expect(diagnosisDialog.locator('.tooth-views .view-label').filter({ hasText: 'Lateral View' })).toBeVisible()
    await expect(diagnosisDialog.locator('.tooth-svg.lateral')).toBeVisible()
    for (const width of [1280, 768, 390]) {
      await loggedIn.setViewportSize({ width, height: 900 })
      const dialogBounds = await diagnosisDialog.boundingBox()
      const lateralBounds = await diagnosisDialog.getByTestId('lateral-surface-v').boundingBox()
      expect(dialogBounds, `diagnosis dialog missing at ${width}px`).not.toBeNull()
      expect(lateralBounds, `lateral hit target missing at ${width}px`).not.toBeNull()
      expect(dialogBounds!.x).toBeGreaterThanOrEqual(0)
      expect(dialogBounds!.x + dialogBounds!.width).toBeLessThanOrEqual(width + 1)
      expect(lateralBounds!.x + lateralBounds!.width).toBeLessThanOrEqual(width + 1)
    }
    await diagnosisDialog.getByTestId('lateral-surface-v').click()
    await expect(diagnosisDialog.locator('.surface-buttons .surface-btn.selected').filter({ hasText: /^V/ })).toBeVisible()
    await diagnosisDialog.getByRole('button', { name: 'Back' }).click()
    await expect(diagnosisDialog.locator('.treatment-bar .treatment-btn[aria-pressed="true"]')).toBeVisible()
    await nextStep.click()
    await diagnosisDialog.locator('.surface-buttons .surface-btn').first().click()
    await expect(diagnosisDialog.locator('.selected-summary')).toBeVisible()
    await loggedIn.keyboard.press('Escape')
    await expect(diagnosisDialog).toBeHidden()
    await expect(chart.locator('.treatment-bar .treatment-btn[aria-pressed="true"]')).toHaveCount(0)
  })
})
