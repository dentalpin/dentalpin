import type { ApiResponse, PaginatedResponse } from '~/types'
import { errorDetail } from '~/utils/error'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface UseApiOptions {
  method?: HttpMethod
  // Accept any plain object so callers can pass a typed domain payload
  // (e.g. ``BudgetCreate``) without an ``as unknown as Record<…>`` cast.
  // ``$fetch`` serializes via JSON.stringify, which handles any object.
  body?: object | null
  headers?: Record<string, string>
  skipAuth?: boolean
  // Query-string params appended to the path. Undefined/null values are
  // skipped. Provided because $fetch's own ``query`` was not wired here,
  // so callers that passed ``{ params: … }`` had it silently dropped
  // (e.g. the Veri*Factu queue tabs all rendered the same list).
  query?: Record<string, string | number | boolean | undefined | null>
  // Optional AbortSignal so callers can cancel in-flight requests
  // (debounced lookups, component unmount, etc.).
  signal?: AbortSignal
  // 400/409/422 toast the backend's own message by default before
  // rethrowing (#101 — an uncaught rethrow used to be a silent
  // failure). Callers that surface the error themselves (their own
  // toast, inline form error, modal copy) pass ``errorToast: false``
  // to keep single-toast behaviour. 404 never auto-toasts: it is
  // routinely semantic ("not signed", probe-style reads) and its
  // handling belongs to the caller.
  errorToast?: boolean
}

function _withQuery(path: string, query?: UseApiOptions['query']): string {
  if (!query) return path
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null) qs.set(k, String(v))
  }
  const s = qs.toString()
  if (!s) return path
  return path.includes('?') ? `${path}&${s}` : `${path}?${s}`
}

export function useApi() {
  const config = useRuntimeConfig()
  const auth = useAuth()
  const { csrfHeaders } = useSessionRequest()
  // SSR: the browser's session cookies arrive on the incoming request;
  // forward them to the backend so server-rendered pages authenticate
  // the same way the client does (ADR 0023). Read per call, not once:
  // a server-side refresh earlier in the same render rotates the jar.
  const { cookieHeaders } = useSsrCookies()
  const { t } = useI18n()
  const toast = useToast()

  // Use different API URL for server (Docker internal) vs client (browser)
  const apiBaseUrl = computed(() =>
    import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
  )

  async function $api<T>(
    path: string,
    options: UseApiOptions = {}
  ): Promise<T> {
    const { skipAuth, method, body, headers: optionHeaders, signal, query, errorToast = true } = options

    const headers: Record<string, string> = {
      ...(optionHeaders || {})
    }

    // Session cookie auth (ADR 0023): the browser attaches the HttpOnly
    // cookies itself; unsafe methods add the double-submit CSRF header.
    if (!skipAuth) {
      Object.assign(headers, csrfHeaders(method), cookieHeaders())
    }

    const url = _withQuery(path, query)

    try {
      return await $fetch<T>(url, {
        baseURL: apiBaseUrl.value,
        timeout: 10000, // 10 seconds
        method,
        body,
        headers,
        credentials: 'include',
        signal
      })
    } catch (error: unknown) {
      const fetchError = error as { name?: string, statusCode?: number, data?: { message?: string } }

      // Caller-initiated cancellation: don't toast, just rethrow so the
      // caller can no-op. AbortController is used by orchestrators
      // (e.g. dashboard) to cancel stale parallel fetches.
      if (fetchError.name === 'AbortError' || signal?.aborted) {
        throw error
      }

      // Handle specific error codes
      if (fetchError.statusCode === 401) {
        // Try to refresh token
        const refreshed = await auth.refresh()
        if (refreshed) {
          // Retry with the rotated cookies (+ the CSRF token, unchanged
          // across refreshes but re-read in case this was a fresh login).
          Object.assign(headers, csrfHeaders(method), cookieHeaders())
          return await $fetch<T>(url, {
            baseURL: apiBaseUrl.value,
            method,
            body,
            headers,
            credentials: 'include'
          })
        }
        // Redirect to login
        await auth.logout()
        throw error
      }

      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('common.forbidden', 'Acceso denegado'),
          color: 'error'
        })
        throw error
      }

      if (fetchError.statusCode === 404) {
        // Semantic more often than exceptional (probe-reads, "not
        // signed", lookups) — never auto-toast; the caller owns it.
        throw error
      }

      if (
        errorToast
        && (fetchError.statusCode === 400
          || fetchError.statusCode === 409
          || fetchError.statusCode === 422)
      ) {
        // Surface the backend's own message so a rethrow nobody catches
        // is no longer silent (#101). Callers that present the error
        // themselves suppress this with ``errorToast: false``.
        toast.add({
          title: t('common.error'),
          description: errorDetail(error) ?? t('common.serverError'),
          color: 'error'
        })
        throw error
      }

      if (
        fetchError.statusCode === 400
        || fetchError.statusCode === 409
        || fetchError.statusCode === 422
      ) {
        throw error
      }

      if (fetchError.statusCode && fetchError.statusCode >= 500) {
        toast.add({
          title: t('common.error'),
          description: t('common.serverError'),
          color: 'error'
        })
        throw error
      }

      // Network error
      if (!fetchError.statusCode) {
        toast.add({
          title: t('common.error'),
          description: t('common.networkError'),
          color: 'error'
        })
      }

      throw error
    }
  }

  /**
   * Raw ``fetch`` against the API with the session cookies attached —
   * for blob downloads and streams where ``$fetch``'s JSON handling gets
   * in the way. Returns the ``Response``; the caller checks ``ok``.
   *
   * A 401 is refreshed and retried once, exactly like ``$api``: a blob
   * download is a plain fetch, so without this an idle longer than the
   * access cookie's lifetime turns "Download PDF" into "Not
   * authenticated" while the rest of the page recovers silently (#440).
   */
  async function raw(path: string, init: RequestInit = {}): Promise<Response> {
    const method = (init.method || 'GET').toUpperCase()
    const send = () => fetch(`${apiBaseUrl.value}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        ...csrfHeaders(method),
        ...cookieHeaders(),
        ...(init.headers as Record<string, string> | undefined)
      }
    })
    const response = await send()
    if (response.status !== 401) return response
    if (await auth.refresh()) return await send()
    // The family is gone: end the session as $api does, and hand the 401
    // back so the caller still shows its own message.
    await auth.logout()
    return response
  }

  // Convenience methods
  async function get<T>(path: string, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'GET' })
  }

  async function post<T>(path: string, body?: object | null, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'POST', body })
  }

  async function put<T>(path: string, body?: object | null, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'PUT', body })
  }

  async function patch<T>(path: string, body?: object | null, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'PATCH', body })
  }

  async function del<T>(path: string, options: Omit<UseApiOptions, 'method' | 'body'> = {}): Promise<T> {
    return $api<T>(path, { ...options, method: 'DELETE' })
  }

  return {
    $api,
    get,
    post,
    put,
    patch,
    del,
    raw
  }
}

// Type helpers for API responses
export type { ApiResponse, PaginatedResponse }
