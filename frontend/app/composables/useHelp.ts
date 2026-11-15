/**
 * Maps the current Vue Router route + the user's locale to a URL on the
 * public documentation portal that serves the matching help fragment.
 *
 * The portal emits one HTML file per (locale, screen) at
 * `<docsUrl>/<lang>/help/<slug>.html` (see ADR 0009 / fase 5 of #75).
 * This composable does **only** URL construction; rendering is the
 * `<HelpButton />` drawer's responsibility.
 *
 * Slug rule (must match `routeToSlug` in
 * `docs/portal/.vitepress/help.ts`):
 *
 *   /                       → /index
 *   /patients               → /patients
 *   /patients/[id]          → /patients_[id]
 *   /settings/verifactu/queue → /settings_verifactu_queue
 *
 * Dynamic params in the live route (e.g. `/patients/abc-123`) collapse
 * to the static `[id]` form so they hit the same MD file the portal
 * built from the source.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const PARAM_SEGMENT_RE = /^[0-9a-f]{8,}|^\d+$|^[A-Za-z0-9-]{20,}$/i

function collapseDynamicSegments(path: string, matchedRoute: string | undefined): string {
  // Settings categories share one dynamic route, so use the generic
  // category guide. Module pages use the next catch-all and keep their real
  // category/page values to find the module-specific guide.
  if (matchedRoute === '/settings/:category') return '/settings/id'
  if (matchedRoute?.includes('/settings/:category/:page')) return path

  // Dynamic identifiers use the same stable `id` token as the docs build.
  if (matchedRoute && matchedRoute !== path) {
    const actual = path.split('/')
    const pattern = matchedRoute.split('/')
    return actual.map((segment, index) =>
      /^:[A-Za-z0-9_]+$/.test(pattern[index] || '') ? 'id' : segment
    ).join('/')
  }

  // Fallback for routes not described by Vue Router: preserve ordinary
  // names and collapse UUID-, number-, and token-like values only.
  return path
    .split('/')
    .map((segment, index) => index > 0 && PARAM_SEGMENT_RE.test(segment) ? 'id' : segment)
    .join('/')
}

function routeToSlug(route: string, query: Record<string, unknown>): string {
  const pathOnly = route.split(/[?#]/, 1)[0] || ''
  const trimmed = pathOnly.replace(/^\/+|\/+$/g, '')
  const pathSlug = trimmed
    ? trimmed.split('/').map(segment =>
        /^\{[^}]+\}$/.test(segment) || /^\[[^\]]+\]$/.test(segment) || /^:[A-Za-z0-9_]+$/.test(segment)
          ? 'id'
          : segment
      ).join('_')
    : 'index'

  // Diagnosis subviews have distinct contextual guides. Other query state
  // (tabs, filters, modal actions) continues to use the patient's guide.
  const queryPairs = ['clinicalMode', 'diagnosisView']
    .filter(key => query[key] !== undefined && query[key] !== null)
    .flatMap((key) => {
      const value = query[key]
      return (Array.isArray(value) ? value : [value]).map(item => [key, String(item)] as const)
    })
    .sort(([ak, av], [bk, bv]) => ak === bk ? (av < bv ? -1 : av > bv ? 1 : 0) : ak < bk ? -1 : 1)
    .map(([key, value]) => `${key}_${value}`)
    .join('_')
    .replace(/[^A-Za-z0-9_-]/g, '_')

  return queryPairs ? `${pathSlug}__${queryPairs}` : pathSlug
}

export function useHelp() {
  const config = useRuntimeConfig()
  const docsUrl = (config.public.docsUrl as string) || ''
  const route = useRoute()
  const { locale } = useI18n()

  const matchedRoute = computed<string | undefined>(() => {
    const matched = route.matched[route.matched.length - 1]
    return matched?.path
  })

  const slug = computed(() =>
    routeToSlug(collapseDynamicSegments(route.path, matchedRoute.value), route.query)
  )

  const lang = computed(() => (locale.value?.toLowerCase().startsWith('es') ? 'es' : 'en'))

  /** Iframe URL for the matching help fragment. Empty when the portal
   *  is not configured (NUXT_PUBLIC_DOCS_URL=''). */
  const helpUrl = computed(() =>
    docsUrl ? `${docsUrl.replace(/\/$/, '')}/${lang.value}/help/${slug.value}.html` : ''
  )

  /** Full-page user-manual URL on the portal — used by the drawer's
   *  "Open full manual" link. */
  const fullManualUrl = computed(() => {
    if (!docsUrl) return ''
    const base = docsUrl.replace(/\/$/, '')
    return `${base}/user-manual/${lang.value}/`
  })

  /** Whether the help button should be shown at all. */
  const isAvailable = computed(() => Boolean(docsUrl))

  return {
    helpUrl,
    fullManualUrl,
    isAvailable,
    lang,
    slug
  }
}
