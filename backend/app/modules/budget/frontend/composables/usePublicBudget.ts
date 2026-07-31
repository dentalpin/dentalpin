/**
 * Patient-facing budget flow.
 *
 * Wraps the five public endpoints (ADR 0006):
 *   GET    /api/v1/budget/public/budgets/{token}/meta
 *   POST   /api/v1/budget/public/budgets/{token}/verify   → cookie
 *   GET    /api/v1/budget/public/budgets/{token}          (cookie)
 *   POST   /api/v1/budget/public/budgets/{token}/accept   (cookie)
 *   POST   /api/v1/budget/public/budgets/{token}/reject   (cookie)
 *
 * The session cookie is HttpOnly + path-scoped to ``{token}`` and managed
 * server-side; ``credentials: 'include'`` ensures the browser sends it.
 */

export type PublicAuthMethod = 'phone_last4' | 'dob' | 'manual_code' | 'none'

export interface PublicMeta {
  requires_verification: boolean
  method: PublicAuthMethod
  locked: boolean
  expired: boolean
  already_decided: boolean
  decided_status: string | null
  clinic_name: string | null
  clinic_phone: string | null
  clinic_email: string | null
  clinic_address_line: string | null
  clinic_language: string | null
  clinic_currency: string | null
  patient_first_name: string | null
  budget_number: string | null
  budget_total: string | null
  valid_until: string | null
}

export interface PublicBudgetItem {
  id: string
  unit_price: number
  quantity: number
  line_total: number
  tooth_number: number | null
  notes: string | null
  // Backend exposes ``names`` as an i18n map (es/en/...). Pick the
  // current locale or fall back in the template.
  catalog_item?: {
    internal_code?: string
    names?: Record<string, string>
  } | null
}

export interface PublicBudget {
  id: string
  budget_number: string
  status: string
  valid_from: string
  valid_until: string | null
  subtotal: number
  total_discount: number
  total_tax: number
  total: number
  patient_notes: string | null
  items: PublicBudgetItem[]
}

export type VerifyError
  = | 'locked'
    | 'expired'
    | 'rate_limited'
    | 'method_mismatch'
    | 'invalid'
    | 'unknown'

function apiBase(): string {
  const config = useRuntimeConfig()
  // The host frontend exposes the backend URL as ``public.apiBaseUrl``
  // (see frontend/nuxt.config.ts). Falling back to ``apiBase`` keeps
  // the composable resilient if the key gets renamed.
  return (
    (config.public.apiBaseUrl as string)
    || (config.public.apiBase as string)
    || ''
  )
}

export function usePublicBudget(token: string) {
  const meta = ref<PublicMeta | null>(null)
  const budget = ref<PublicBudget | null>(null)
  const loading = ref(false)
  const verifying = ref(false)
  const submitting = ref(false)
  const verifyAttemptsLeft = ref<number | null>(null)
  const lastError = ref<VerifyError | null>(null)
  const decided = ref<'accepted' | 'rejected' | null>(null)

  const baseUrl = computed(() => `${apiBase()}/api/v1/budget/public/budgets/${token}`)

  async function fetchMeta() {
    loading.value = true
    lastError.value = null
    try {
      const res = await $fetch<{ data: PublicMeta }>(`${baseUrl.value}/meta`, {
        credentials: 'include'
      })
      meta.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchBudget() {
    loading.value = true
    try {
      const res = await $fetch<{ data: PublicBudget }>(baseUrl.value, {
        credentials: 'include'
      })
      budget.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function verify(method: PublicAuthMethod, value: string): Promise<boolean> {
    verifying.value = true
    lastError.value = null
    try {
      await $fetch(`${baseUrl.value}/verify`, {
        method: 'POST',
        body: { method, value },
        credentials: 'include'
      })
      return true
    } catch (err) {
      const e = err as { statusCode?: number, data?: { detail?: string } }
      const status = e.statusCode
      if (status === 401) {
        const detail = e.data?.detail
        lastError.value = (detail === 'method_mismatch') ? 'method_mismatch' : 'invalid'
      } else if (status === 410) {
        lastError.value = 'expired'
      } else if (status === 423) {
        lastError.value = 'locked'
      } else if (status === 429) {
        lastError.value = 'rate_limited'
      } else {
        lastError.value = 'unknown'
      }
      return false
    } finally {
      verifying.value = false
    }
  }

  async function accept(payload: {
    signer_name: string
    signature_data?: { png?: string }
  }): Promise<boolean> {
    submitting.value = true
    try {
      await $fetch(`${baseUrl.value}/accept`, {
        method: 'POST',
        body: payload,
        credentials: 'include'
      })
      decided.value = 'accepted'
      if (meta.value) meta.value = { ...meta.value, already_decided: true, decided_status: 'accepted' }
      return true
    } catch {
      return false
    } finally {
      submitting.value = false
    }
  }

  async function downloadSignedPdf(): Promise<'ok' | 'verification_required' | 'not_signed' | 'error'> {
    try {
      const response = await fetch(`${baseUrl.value}/pdf/signed`, {
        credentials: 'include'
      })
      if (response.status === 401) return 'verification_required'
      if (response.status === 404) return 'not_signed'
      if (!response.ok) return 'error'

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      const cd = response.headers.get('Content-Disposition')
      const match = cd?.match(/filename="?(.+?)"?$/)
      link.download = match?.[1] || `presupuesto_firmado.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      return 'ok'
    } catch {
      return 'error'
    }
  }

  async function reject(payload: { reason: string, note?: string }): Promise<boolean> {
    submitting.value = true
    try {
      await $fetch(`${baseUrl.value}/reject`, {
        method: 'POST',
        body: payload,
        credentials: 'include'
      })
      decided.value = 'rejected'
      if (meta.value) meta.value = { ...meta.value, already_decided: true, decided_status: 'rejected' }
      return true
    } catch {
      return false
    } finally {
      submitting.value = false
    }
  }

  return {
    meta,
    budget,
    loading,
    verifying,
    submitting,
    verifyAttemptsLeft,
    lastError,
    decided,
    fetchMeta,
    fetchBudget,
    verify,
    accept,
    reject,
    downloadSignedPdf
  }
}
