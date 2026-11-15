import type { ApiResponse } from '~~/app/types'
import type { Shift, WeekdayShifts } from './useProfessionalHours'

export interface AssistantBrief {
  user_id: string
  first_name: string
  last_name: string
}

export interface AssistantHours {
  id: string
  clinic_id: string
  user_id: string
  is_active: boolean
  days: WeekdayShifts[]
}

export interface AssistantOverride {
  id: string
  clinic_id: string
  user_id: string
  start_date: string
  end_date: string
  kind: 'unavailable' | 'custom_hours'
  reason: string | null
  shifts: Shift[]
}

export interface AssistantOverridePayload {
  start_date: string
  end_date: string
  kind: 'unavailable' | 'custom_hours'
  reason?: string | null
  shifts: { start_time: string, end_time: string }[]
}

export interface AssistantWorkload {
  assistant_id: string
  assistant_name: string
  appointment_count: number
  booked_minutes: number
  available_minutes: number
  utilization_rate: number
  conflict_count: number
}

export interface AssistantConflict {
  assistant_id: string
  assistant_name: string
  kind: 'overlap' | 'outside_shift'
  appointment_id: string
  other_appointment_id: string | null
  start_at: string
  end_at: string
}

export function useAssistantHours() {
  const api = useApi()

  async function fetchAssistants(): Promise<AssistantBrief[]> {
    const res = await api.get<ApiResponse<AssistantBrief[]>>('/api/v1/schedules/assistants')
    return res.data
  }

  async function fetchHours(userId: string): Promise<AssistantHours> {
    const res = await api.get<ApiResponse<AssistantHours>>(`/api/v1/schedules/assistants/${userId}/hours`)
    return res.data
  }

  async function updateHours(userId: string, days: WeekdayShifts[]): Promise<AssistantHours> {
    const res = await api.put<ApiResponse<AssistantHours>>(
      `/api/v1/schedules/assistants/${userId}/hours`, { days }, { errorToast: false }
    )
    return res.data
  }

  async function fetchOverrides(userId: string): Promise<AssistantOverride[]> {
    const res = await api.get<ApiResponse<AssistantOverride[]>>(`/api/v1/schedules/assistants/${userId}/overrides`)
    return res.data
  }

  async function createOverride(userId: string, payload: AssistantOverridePayload): Promise<AssistantOverride> {
    const res = await api.post<ApiResponse<AssistantOverride>>(
      `/api/v1/schedules/assistants/${userId}/overrides`, payload, { errorToast: false }
    )
    return res.data
  }

  async function updateOverride(userId: string, id: string, payload: AssistantOverridePayload): Promise<AssistantOverride> {
    const res = await api.put<ApiResponse<AssistantOverride>>(
      `/api/v1/schedules/assistants/${userId}/overrides/${id}`, payload, { errorToast: false }
    )
    return res.data
  }

  async function deleteOverride(userId: string, id: string): Promise<void> {
    await api.del(`/api/v1/schedules/assistants/${userId}/overrides/${id}`)
  }

  async function fetchWorkload(start: string, end: string): Promise<{ rows: AssistantWorkload[], conflicts: AssistantConflict[] }> {
    const res = await api.get<ApiResponse<{ rows: AssistantWorkload[], conflicts: AssistantConflict[] }>>(
      `/api/v1/schedules/analytics/assistant-workload?start=${start}&end=${end}`, { errorToast: false }
    )
    return res.data
  }

  return {
    fetchAssistants, fetchHours, updateHours, fetchOverrides,
    createOverride, updateOverride, deleteOverride, fetchWorkload
  }
}
