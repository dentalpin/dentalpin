/**
 * Content-Security-Policy for the app shell (issue #355).
 *
 * Lives in Nitro rather than Caddy so (a) the e2e job — which runs the
 * production build without Caddy — enforces the same policy CI-side and
 * (b) the policy can reference the runtime API origin. Mode comes from
 * `NUXT_CSP_MODE`:
 *
 *   off     — no header (default; dev)
 *   report  — `Content-Security-Policy-Report-Only`, violations POSTed to
 *             the backend's /api/v1/security/csp-report (prod rollout step)
 *   enforce — `Content-Security-Policy` (e2e job; prod once reports are clean)
 *
 * Inventory the policy is derived from (prod build, 2026-09-05, see
 * docs/technical/security-csp.md): two Nuxt bootstrap inline scripts +
 * the JSON payload script, one `<style id="nuxt-ui-colors">` block and
 * inline `style=""` attributes, no external origins, SSE + API on the
 * configured API origin. `'unsafe-inline'` on script-src is the known
 * gap — nonces need a render-hook module; tracked in the doc.
 */
export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  const mode = String(config.cspMode || 'off')
  if (mode !== 'report' && mode !== 'enforce') return

  const path = event.path || ''
  // Assets and API passthroughs are not documents; only HTML needs a policy.
  if (path.startsWith('/_nuxt/') || path.startsWith('/api/') || path.startsWith('/__nuxt')) return

  const apiBase = String(config.public.apiBaseUrl || '')
  let apiOrigin = ''
  try {
    if (/^https?:\/\//.test(apiBase)) apiOrigin = new URL(apiBase).origin
  } catch {
    apiOrigin = ''
  }
  const connect = ['\'self\'', apiOrigin].filter(Boolean).join(' ')
  const reportUri = `${apiOrigin || ''}/api/v1/security/csp-report`

  const policy = [
    'default-src \'self\'',
    // Nuxt's bootstrap scripts are inline; nonces are the follow-up (#355).
    'script-src \'self\' \'unsafe-inline\'',
    // Nuxt UI theme block + Tailwind-driven style attributes.
    'style-src \'self\' \'unsafe-inline\'',
    'img-src \'self\' data: blob:',
    'font-src \'self\' data:',
    `connect-src ${connect}`,
    'worker-src \'self\' blob:',
    'frame-ancestors \'self\'',
    'base-uri \'self\'',
    'form-action \'self\'',
    'object-src \'none\'',
    `report-uri ${reportUri}`
  ].join('; ')

  setHeader(
    event,
    mode === 'enforce' ? 'Content-Security-Policy' : 'Content-Security-Policy-Report-Only',
    policy
  )
})
