import type { Ref } from 'vue'

// Mirror of the backend literal types — kept narrow so the call-list
// UI stays type-safe even though the host has no shared types file
// for the recalls module.
export type RecallReason
  = | 'hygiene'
    | 'checkup'
    | 'ortho_review'
    | 'implant_review'
    | 'post_op'
    | 'treatment_followup'
    | 'other'

export type RecallStatus
  = | 'pending'
    | 'contacted_no_answer'
    | 'contacted_scheduled'
    | 'contacted_declined'
    | 'done'
    | 'cancelled'
    | 'needs_review'

export type RecallPriority = 'low' | 'normal' | 'high'

export type RecallChannel = 'phone' | 'whatsapp' | 'sms' | 'email'

export type RecallOutcome
  = | 'no_answer'
    | 'voicemail'
    | 'scheduled'
    | 'declined'
    | 'wrong_number'

export interface PatientBriefForRecall {
  id: string
  first_name: string
  last_name: string
  phone?: string | null
  email?: string | null
  do_not_contact: boolean
  status: string
}

export interface RecallContactAttempt {
  id: string
  recall_id: string
  attempted_at: string
  attempted_by: string
  channel: RecallChannel
  outcome: RecallOutcome
  note?: string | null
}

export interface Recall {
  id: string
  clinic_id: string
  patient_id: string
  due_month: string // ISO date (day-1)
  due_date?: string | null
  reason: RecallReason
  reason_note?: string | null
  priority: RecallPriority
  status: RecallStatus
  recommended_by?: string | null
  assigned_professional_id?: string | null
  last_contact_attempt_at?: string | null
  contact_attempt_count: number
  linked_appointment_id?: string | null
  linked_treatment_id?: string | null
  linked_treatment_category_key?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
  patient?: PatientBriefForRecall
  attempts?: RecallContactAttempt[]
}

export interface RecallCreatePayload {
  patient_id: string
  due_month: string // YYYY-MM-01
  due_date?: string | null
  reason: RecallReason
  reason_note?: string | null
  priority?: RecallPriority
  assigned_professional_id?: string | null
  linked_treatment_id?: string | null
  linked_treatment_category_key?: string | null
}

export interface RecallUpdatePayload {
  due_month?: string | null
  due_date?: string | null
  reason?: RecallReason
  reason_note?: string | null
  priority?: RecallPriority
  assigned_professional_id?: string | null
}

export interface AttemptCreatePayload {
  channel: RecallChannel
  outcome: RecallOutcome
  note?: string | null
  linked_appointment_id?: string | null
}

export interface RecallSettings {
  clinic_id: string
  reason_intervals: Record<string, number>
  category_to_reason: Record<string, string>
  auto_suggest_on_treatment_completed: boolean
  auto_link_on_appointment_scheduled: boolean
  updated_at: string
}

export interface RecallDashboardStats {
  due_this_week: number
  due_this_month: number
  overdue: number
  scheduled_this_month: number
  completed_this_month: number
  conversion_rate: number
}

export interface RecallSuggestion {
  patient_id: string
  reason: RecallReason
  due_month: string
  interval_months: number
  treatment_category_key?: string | null
  treatment_id?: string | null
  matched_setting: boolean
}

interface ApiOk<T> { data: T }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface RecallListFilters {
  month?: string // ISO date (any day)
  reason?: RecallReason
  professional_id?: string
  status?: RecallStatus
  priority?: RecallPriority
  overdue?: boolean
  patient_id?: string
  page?: number
  page_size?: number
}

export function useRecalls() {
  const api = useApi()

  async function list(filters: RecallListFilters = {}): Promise<ApiPaged<Recall>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/recalls/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<Recall>>(url)
  }

  async function get(id: string): Promise<ApiOk<Recall>> {
    return await api.get<ApiOk<Recall>>(`/api/v1/recalls/${id}`)
  }

  async function listForPatient(patientId: string): Promise<ApiOk<Recall[]>> {
    return await api.get<ApiOk<Recall[]>>(`/api/v1/recalls/patients/${patientId}`)
  }

  async function create(payload: RecallCreatePayload): Promise<ApiOk<Recall>> {
    return await api.post<ApiOk<Recall>>('/api/v1/recalls/', payload)
  }

  async function update(id: string, payload: RecallUpdatePayload): Promise<ApiOk<Recall>> {
    return await api.patch<ApiOk<Recall>>(`/api/v1/recalls/${id}`, payload)
  }

  async function snooze(id: string, months: number, note?: string): Promise<ApiOk<Recall>> {
    return await api.post<ApiOk<Recall>>(`/api/v1/recalls/${id}/snooze`, {
      months,
      reason_note: note ?? null
    })
  }

  async function cancel(id: string, note?: string): Promise<ApiOk<Recall>> {
    return await api.post<ApiOk<Recall>>(`/api/v1/recalls/${id}/cancel`, {
      note: note ?? null
    })
  }

  async function markDone(id: string): Promise<ApiOk<Recall>> {
    return await api.post<ApiOk<Recall>>(`/api/v1/recalls/${id}/done`, {})
  }

  async function logAttempt(id: string, payload: AttemptCreatePayload): Promise<ApiOk<RecallContactAttempt>> {
    return await api.post<ApiOk<RecallContactAttempt>>(
      `/api/v1/recalls/${id}/attempts`,
      payload
    )
  }

  async function linkAppointment(id: string, appointmentId: string): Promise<ApiOk<Recall>> {
    return await api.post<ApiOk<Recall>>(`/api/v1/recalls/${id}/link-appointment`, {
      appointment_id: appointmentId
    })
  }

  async function suggestNext(params: {
    patient_id: string
    treatment_category_key?: string | null
    treatment_id?: string | null
  }): Promise<ApiOk<RecallSuggestion | null>> {
    const qs = new URLSearchParams()
    qs.append('patient_id', params.patient_id)
    if (params.treatment_category_key) qs.append('treatment_category_key', params.treatment_category_key)
    if (params.treatment_id) qs.append('treatment_id', params.treatment_id)
    return await api.get<ApiOk<RecallSuggestion | null>>(
      `/api/v1/recalls/suggestions/next?${qs.toString()}`
    )
  }

  async function getSettings(): Promise<ApiOk<RecallSettings>> {
    return await api.get<ApiOk<RecallSettings>>('/api/v1/recalls/settings')
  }

  async function updateSettings(payload: Partial<RecallSettings>): Promise<ApiOk<RecallSettings>> {
    return await api.put<ApiOk<RecallSettings>>('/api/v1/recalls/settings', payload)
  }

  async function dashboardStats(): Promise<ApiOk<RecallDashboardStats>> {
    return await api.get<ApiOk<RecallDashboardStats>>('/api/v1/recalls/stats/dashboard')
  }

  function exportCsvUrl(filters: RecallListFilters = {}): string {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const base = '/api/v1/recalls/export.csv'
    return qs.toString() ? `${base}?${qs.toString()}` : base
  }

  return {
    list,
    get,
    listForPatient,
    create,
    update,
    snooze,
    cancel,
    markDone,
    logAttempt,
    linkAppointment,
    suggestNext,
    getSettings,
    updateSettings,
    dashboardStats,
    exportCsvUrl
  }
}

export type UseRecallsReturn = ReturnType<typeof useRecalls>

// Utility for callers that already have a reactive recall ref.
export function useRecallActions(recall: Ref<Recall | null>) {
  const recalls = useRecalls()
  return {
    recalls,
    isCallable: computed(
      () => !!recall.value?.patient?.phone && !recall.value?.patient?.do_not_contact
    )
  }
}

// --- Per-patient shared state ----------------------------------------------

/**
 * Shared per-patient recall list. Both `SetRecallButton` (action +
 * inline next-recall card on the patient hero) and
 * `RecallSummaryFeed` (recent-history card on the summary feed)
 * read from the same `useState` slot so the patient page only fires
 * one ``GET /api/v1/recalls/patients/:id`` per visit.
 *
 * Pure host plumbing — no cross-module imports beyond the host's
 * `useState`. ``manifest.depends`` stays at ``["patients", "agenda"]``.
 */
export function usePatientRecalls(patientId: string) {
  const stateKey = `recalls:patient:${patientId}`
  const recalls = useState<Recall[]>(stateKey, () => [])
  const isLoading = useState<boolean>(`${stateKey}:loading`, () => false)
  const loaded = useState<boolean>(`${stateKey}:loaded`, () => false)
  const api = useRecalls()

  async function refresh() {
    if (!patientId) {
      recalls.value = []
      return
    }
    isLoading.value = true
    try {
      const res = await api.listForPatient(patientId)
      recalls.value = res.data
      loaded.value = true
    } catch {
      recalls.value = []
    } finally {
      isLoading.value = false
    }
  }

  /** Idempotent — only fetches the first time per (page, patient). */
  async function ensureLoaded() {
    if (loaded.value || isLoading.value) return
    await refresh()
  }

  const activeRecalls = computed(() =>
    recalls.value.filter(r =>
      ['pending', 'contacted_no_answer', 'contacted_scheduled'].includes(r.status)
    )
  )

  // Most-due active recall (smallest due_month wins; tiebreaker on
  // creation order) — what the patient hero pins under the CTA.
  const nextActiveRecall = computed(() => {
    const active = [...activeRecalls.value]
    active.sort((a, b) => {
      if (a.due_month !== b.due_month) return a.due_month < b.due_month ? -1 : 1
      return a.created_at < b.created_at ? -1 : 1
    })
    return active[0] ?? null
  })

  return {
    recalls,
    isLoading,
    loaded,
    refresh,
    ensureLoaded,
    activeRecalls,
    nextActiveRecall
  }
}
