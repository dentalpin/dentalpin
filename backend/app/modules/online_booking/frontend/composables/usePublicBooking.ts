/**
 * Public (cookie-free, same-origin) booking API for `/p/booking/<clinicId>`.
 *
 *   GET  /api/v1/online_booking/public/{clinic}/config
 *   GET  /api/v1/online_booking/public/{clinic}/availability
 *   GET  /api/v1/online_booking/public/{clinic}/challenge   (fetched by the ALTCHA widget)
 *   GET  /api/v1/online_booking/public/{clinic}/logo        (<img src>)
 *   POST /api/v1/online_booking/public/{clinic}/requests
 *   POST /api/v1/online_booking/public/{clinic}/confirm
 */
import { PublicBookingError } from '../utils/publicBookingError'

export interface PublicReason {
  id: string
  name_es: string
  name_en: string
  duration_minutes: number
}

export interface PublicBranding {
  logo_url: string | null
  accent_color: string | null
  title_es: string | null
  intro_es: string | null
  title_en: string | null
  intro_en: string | null
}

export interface PublicBookingConfig {
  slot_minutes: number
  window_days: number
  ask_existing_patient: boolean
  allow_comment: boolean
  redirect_url: string | null
  privacy_url: string | null
  embed_origins: string[]
  branding: PublicBranding
  timezone: string
  reasons: PublicReason[]
}

export interface PublicRequestBody {
  start_time: string
  contact_name: string
  contact_first_name: string
  contact_last_name: string
  existing_patient: boolean | null
  comment: string | null
  contact_email: string
  contact_phone: string
  language: 'es' | 'en'
  reason: string
  website: string
  altcha: string
}

export function usePublicBooking(clinicId: string) {
  const runtime = useRuntimeConfig()
  const baseURL = String(runtime.public.apiBaseUrl || '')
  const path = `/api/v1/online_booking/public/${encodeURIComponent(clinicId)}`

  async function call<T>(suffix: string, options: Record<string, unknown> = {}): Promise<T> {
    try {
      const response = await $fetch<{ data: T }>(path + suffix, {
        baseURL,
        credentials: 'omit',
        referrerPolicy: 'no-referrer',
        cache: 'no-store',
        ...options
      })
      return response.data
    } catch (error) {
      throw new PublicBookingError((error as { status?: number, statusCode?: number }).status
        ?? (error as { statusCode?: number }).statusCode ?? 0)
    }
  }

  return {
    challengeUrl: `${baseURL}${path}/challenge`,
    logoUrl: `${baseURL}${path}/logo`,
    config: () => call<PublicBookingConfig>('/config'),
    availability: (fromDay: string, days: number, reason: string) =>
      call<{ days: { date: string, starts: string[] }[] }>('/availability', {
        query: { from_day: fromDay, days, reason }
      }),
    createRequest: (body: PublicRequestBody) =>
      call<{ message: string }>('/requests', { method: 'POST', body }),
    confirm: (token: string) =>
      call<{ status: string, start_time: string, timezone?: string }>('/confirm', {
        method: 'POST', body: { token }
      })
  }
}
