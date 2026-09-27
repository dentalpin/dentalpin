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

const PARAM_SEGMENT_RE = /^[0-9a-f]{8,}|^\d+$|^[A-Za-z0-9-]{20,}$/

function collapseDynamicSegments(path: string, matchedRoute: string | undefined): string {
  // Prefer the matched route from Vue Router (e.g. `/patients/:id`) when
  // available — convert `:id` to `[id]` for parity with the docs source.
  if (matchedRoute && matchedRoute !== path) {
    return matchedRoute.replace(/:([A-Za-z0-9_]+)/g, '[$1]')
  }

  // Fallback: heuristically collapse UUID/hash-looking segments.
  return path
    .split('/')
    .map((segment, idx) =>
      idx > 0 && PARAM_SEGMENT_RE.test(segment) ? '[id]' : segment
    )
    .join('/')
}

function routeToSlug(route: string): string {
  const trimmed = route.replace(/^\/+|\/+$/g, '')
  if (!trimmed) return 'index'
  // Strip `[` `]` to match the portal's `routeToSlug` (filenames with
  // brackets clash with VitePress' dynamic-route convention).
  return trimmed.replace(/\//g, '_').replace(/[[\]]/g, '')
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
    routeToSlug(collapseDynamicSegments(route.path, matchedRoute.value))
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
