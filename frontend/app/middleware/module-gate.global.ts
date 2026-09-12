/**
 * Route-level module-activation gate (issue #326).
 *
 * Prod bakes every layer (#174), so the route table contains the pages
 * of modules that may not be installed. Rendering gated at component
 * level still downloads the chunk and runs whatever precedes the
 * permission check — this middleware 404s the navigation instead.
 *
 * The route → module map comes from `modules.json` via runtimeConfig
 * (`scripts/modules-json.mjs` walks each layer's pages/). Matching
 * mirrors `usePermissions().moduleActive` semantics: gate only when the
 * layer is baked into this build AND the active-modules list is loaded
 * AND the module is absent from it. Unauthenticated navigation (login,
 * the public budget link) has no active list → passes untouched.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const routes = useRuntimeConfig().public.moduleRoutes as Record<string, string>
  // Direct navigation lands here before any layout fetched the active
  // list — load it (idempotent, 1-min cache) so a deep link to an
  // uninstalled module's page can't slip through the null window.
  const auth = useAuth()
  if (auth.hasSession.value && useActiveModulesState().value === null) {
    try {
      await useModules().ensureLoaded()
    } catch {
      // Backend unreachable — fall through ungated, matching moduleActive.
    }
  }
  const active = useActiveModulesState().value
  if (!active) return // unknown (or unauthenticated) → no gate

  const toSegs = to.path.replace(/\/+$/, '').split('/').filter(Boolean)

  let owner: string | null = null
  let ownerSpecificity = -1
  for (const [pattern, module] of Object.entries(routes)) {
    const pSegs = pattern.split('/').filter(Boolean)
    if (pSegs.length !== toSegs.length) continue
    let ok = true
    let literal = 0
    for (let i = 0; i < pSegs.length; i++) {
      const p = pSegs[i]!
      if (p.startsWith(':')) continue
      if (p !== toSegs[i]) {
        ok = false
        break
      }
      literal += 1
    }
    if (ok && literal > ownerSpecificity) {
      owner = module
      ownerSpecificity = literal
    }
  }
  if (!owner) return // host route

  const builtLayers = new Set(useRuntimeConfig().public.moduleLayers as string[])
  if (!builtLayers.has(owner)) return
  if (active.some(m => m.name === owner)) return

  throw createError({ statusCode: 404, statusMessage: 'Not found', fatal: true })
})
