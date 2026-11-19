import { errorDetail, errorStatus } from '~/utils/error'

export interface MfaChallenge {
  mfa_required: true
  mfa_token: string
  mode: 'verify' | 'enroll'
  secret: string | null
  qr_code: string | null
}

export interface MfaProfile {
  enabled: boolean
  allowed: boolean
  required: boolean
}

export type MfaMode = 'off' | 'optional' | 'required_all' | 'required_roles'
export interface MfaPolicy {
  mode: MfaMode
  roles: string[]
}

export function useMfa() {
  const config = useRuntimeConfig()
  const auth = useAuth()
  const { t } = useI18n()
  const { csrfHeaders } = useSessionRequest()

  async function request<T>(
    path: string,
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    body?: object,
    clinicId?: string
  ): Promise<T> {
    const send = () => $fetch<T>(`/api/v1/auth/${path}`, {
      baseURL: config.public.apiBaseUrl,
      method,
      body,
      credentials: 'include',
      headers: csrfHeaders(method),
      query: clinicId ? { clinic_id: clinicId } : undefined
    })
    try {
      return await send()
    } catch (cause) {
      const detail = errorDetail(cause)
      if (
        path !== 'mfa/verify'
        && errorStatus(cause) === 401
        && (detail === 'Could not validate credentials' || detail === 'Not authenticated')
        && await auth.refresh()
      ) {
        return await send()
      }
      throw cause
    }
  }

  function message(error: unknown): string {
    const detail = errorDetail(error)
    if (detail === 'mfa_expired') return t('mfa.expired')
    if (detail === 'mfa_invalid_code') return t('mfa.invalidCode')
    if (detail === 'mfa_invalid_password') return t('auth.invalidCredentials')
    if (detail === 'mfa_unavailable') return t('mfa.unavailable')
    if (detail === 'mfa_not_enabled') return t('mfa.notEnabled')
    if (detail === 'mfa_reset_forbidden') return t('mfa.resetForbidden')
    if ((error as { statusCode?: number })?.statusCode === 429) return t('mfa.locked')
    return t('auth.serverError')
  }

  return { request, message }
}
