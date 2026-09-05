/**
 * CSP enforcement (issue #355). The e2e job runs the production build
 * with NUXT_CSP_MODE=enforce, so any inline handler, external origin or
 * blocked asset a change introduces shows up here as a console
 * "Refused to …" line — and fails CI with the offending directive.
 */
import { test, expect } from '@playwright/test'
import { login } from './_fixtures'

const VIOLATION = /Content Security Policy|Refused to (load|execute|apply|connect|frame)/i

test.describe('content security policy', () => {
  test('policy header is present on documents', async ({ request }) => {
    const res = await request.get('/login')
    const enforced = res.headers()['content-security-policy']
    const reportOnly = res.headers()['content-security-policy-report-only']
    const policy = enforced ?? reportOnly
    test.skip(!policy, 'NUXT_CSP_MODE is off — nothing to assert')
    expect(policy).toContain('default-src \'self\'')
    expect(policy).toContain('frame-ancestors \'self\'')
    expect(policy).toContain('object-src \'none\'')
  })

  test('login page and dashboard render without violations', async ({ page }) => {
    const violations: string[] = []
    page.on('console', (msg) => {
      if (VIOLATION.test(msg.text())) violations.push(msg.text())
    })

    await page.goto('/login')
    await expect(page.locator('input[name="email"], input[type="email"]').first()).toBeVisible()

    await login(page, 'admin')
    await page.goto('/')
    await expect(page.locator('body')).toBeVisible()
    // Give deferred assets (icons, fonts, lazy chunks) a moment to settle.
    await page.waitForLoadState('networkidle')

    expect(violations, violations.join('\n')).toEqual([])
  })
})
