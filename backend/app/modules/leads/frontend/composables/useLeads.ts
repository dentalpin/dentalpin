import type { ApiResponse, PaginatedResponse } from '~~/app/types'
// DayOfWeek / AvailabilitySlot are derived from the DAY_ORDER / SLOT_ORDER
// constants in ../utils/leadAvailability. Declaring them here as well made Nuxt
// auto-import the same two type names from two modules — `nuxt typecheck`
// reported "Duplicated imports … has been ignored" and which definition won was
// an accident of resolution order.
import type { AvailabilitySlot, DayOfWeek } from '../utils/leadAvailability'

export type LeadStatus = 'new' | 'contacted' | 'converted' | 'discarded'
export type LeadSubmitOutcome = 'lead_created' | 'recall_queued'

export interface Lead {
  id: string
  clinic_id: string
  full_name: string
  phone: string
  email: string | null
  motive: string
  description: string | null
  availability_days: DayOfWeek[] | null
  availability_slot: AvailabilitySlot | null
  status: LeadStatus
  patient_id: string | null
  converted_at: string | null
  created_at: string
  updated_at: string
}

export interface LeadPatientBrief {
  id: string
  first_name: string
  last_name: string
  phone: string | null
  email: string | null
}

export interface LeadCreatePayload {
  full_name: string
  phone: string
  email?: string | null
  motive: string
  description?: string | null
  availability_days?: DayOfWeek[] | null
  availability_slot?: AvailabilitySlot | null
}

export interface LeadUpdatePayload {
  full_name?: string
  phone?: string
  email?: string | null
  motive?: string
  description?: string | null
  availability_days?: DayOfWeek[] | null
  availability_slot?: AvailabilitySlot | null
  status?: LeadStatus
}

export interface LeadConvertPayload {
  first_name: string
  last_name: string
  phone?: string | null
  email?: string | null
  date_of_birth?: string | null
  national_id?: string | null
  notes?: string | null
}

export interface LeadSubmitResponse {
  outcome: LeadSubmitOutcome
  lead: Lead | null
  recalled_patient: LeadPatientBrief | null
}

export interface LeadConvertResponse {
  lead: Lead
  patient: LeadPatientBrief
}

export interface LeadListFilters {
  status?: string
  search?: string
  page?: number
  page_size?: number
  sort?: string
}

export function useLeads() {
  const api = useApi()

  async function list(filters: LeadListFilters = {}): Promise<PaginatedResponse<Lead>> {
    const qs = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null || value === '') continue
      qs.append(key, String(value))
    }
    // Trailing slash is mandatory: the backend runs with
    // redirect_slashes=False and mounts the collection at /api/v1/leads/.
    const url = `/api/v1/leads/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<PaginatedResponse<Lead>>(url)
  }

  async function get(id: string): Promise<ApiResponse<Lead>> {
    return await api.get<ApiResponse<Lead>>(`/api/v1/leads/${id}`)
  }

  // The page toasts its own message for these three (the outcome union is
  // an expected branch, not an error), hence errorToast: false.
  async function create(payload: LeadCreatePayload): Promise<ApiResponse<LeadSubmitResponse>> {
    return await api.post<ApiResponse<LeadSubmitResponse>>('/api/v1/leads/', payload, {
      errorToast: false
    })
  }

  async function update(id: string, payload: LeadUpdatePayload): Promise<ApiResponse<Lead>> {
    return await api.patch<ApiResponse<Lead>>(`/api/v1/leads/${id}`, payload, {
      errorToast: false
    })
  }

  async function convert(
    id: string,
    payload: LeadConvertPayload
  ): Promise<ApiResponse<LeadConvertResponse>> {
    return await api.post<ApiResponse<LeadConvertResponse>>(
      `/api/v1/leads/${id}/convert`,
      payload,
      { errorToast: false }
    )
  }

  return { list, get, create, update, convert }
}
