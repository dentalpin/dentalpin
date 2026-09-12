const SETUP_PATH = '/setup'

// Module-level cache. The system can only flip from uninitialized → initialized
// (never back), so once we've seen `true` we stop asking the backend.
let systemInitialized: boolean | null = null

async function isSystemInitialized(): Promise<boolean> {
  if (systemInitialized === true) return true
  const config = useRuntimeConfig()
  const baseURL = import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
  try {
    const res = await $fetch<{ data: { initialized: boolean } }>(
      '/api/v1/auth/setup/status',
      { baseURL }
    )
    systemInitialized = res.data.initialized
  } catch {
    // Backend unreachable: don't trap the user on /setup — assume initialized
    // so they land on /login and hit the normal error path there.
    systemInitialized = true
  }
  return systemInitialized
}

export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth()

  // ``/p/budget/<token>`` is the patient-facing budget view (ADR 0006),
  // authorized server-side via a token-scoped 2FA cookie; let it render.
  // ``/p/push/<token>`` is the patient push-subscribe view (notifications
  // T6), authorized server-side via the single-use token itself.
  const publicRoutes = ['/login', SETUP_PATH, '/set-password', '/p/budget', '/p/push']
  const isPublicRoute = publicRoutes.some(route => to.path === route || to.path.startsWith(route + '/'))

  // Initialize auth state (fetch user if token exists) - works on server and client
  await auth.init()

  if (auth.isAuthenticated.value) {
    // Authenticated users skip both the login page and the first-run wizard.
    if (to.path === '/login' || to.path === SETUP_PATH) return navigateTo('/')
    return
  }

  // Unauthenticated. A fresh system has no account yet → first-run wizard.
  if (!(await isSystemInitialized())) {
    return to.path === SETUP_PATH ? undefined : navigateTo(SETUP_PATH)
  }

  // System already initialized: the wizard is closed.
  if (to.path === SETUP_PATH) return navigateTo('/login')

  if (!isPublicRoute) return navigateTo('/login')
})
