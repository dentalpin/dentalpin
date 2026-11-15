export interface JournalEntry {
  id: string
  clinic_id: string
  event_type: string
  actor_id?: string | null
  patient_id?: string | null
  source_table: string
  source_entity_id?: string | null
  payload: Record<string, unknown>
  occurred_at: string
}

interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface JournalListFilters {
  event_type?: string
  patient_id?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

// Event types the module subscribes to (see backend __init__.py
// _SUBSCRIBED) — drives the filter select so admins never have to type
// raw event strings. Keep in sync when the subscription set grows.
export const JOURNAL_EVENT_TYPES = [
  'appointment.scheduled',
  'appointment.confirmed',
  'appointment.checked_in',
  'appointment.in_treatment',
  'appointment.completed',
  'appointment.cancelled',
  'appointment.no_show',
  'budget.sent',
  'budget.accepted',
  'budget.rejected',
  'budget.cancelled',
  'budget.renegotiated',
  'budget.superseded',
  'invoice.sent',
  'payment.allocated',
  'payment.refunded',
  'patient.created',
  'patient.archived',
  'recall.created',
  'odontogram.treatment.added',
  'odontogram.treatment.status_changed',
  'odontogram.treatment.performed',
  'odontogram.treatment.deleted',
  'lab_order.status_changed',
  'treatment_plan.treatment_added',
  'treatment_plan.treatment_removed',
  'treatment_plan.item_session_completed',
  'treatment_plan.budget_sync_requested'
] as const

export function useActivityJournal() {
  const api = useApi()

  async function list(filters: JournalListFilters = {}): Promise<ApiPaged<JournalEntry>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/activity_journal/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<JournalEntry>>(url)
  }

  async function get(id: string): Promise<JournalEntry> {
    const res = await api.get<{ data: JournalEntry }>(`/api/v1/activity_journal/${id}`)
    return res.data
  }

  return { list, get }
}
