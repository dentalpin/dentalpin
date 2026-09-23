import type { ApiResponse } from '~~/app/types'

export interface OrthoCase {
  id: string
  clinic_id: string
  patient_id: string
  professional_id: string | null
  appliance_type: string
  status: 'active' | 'paused' | 'finished' | 'transferred_out'
  start_date: string
  estimated_months: number | null
  diagnosis_notes: string | null
  current_upper_wire: string | null
  current_lower_wire: string | null
  finished_at: string | null
  status_note: string | null
  control_count: number
  last_control_at: string | null
  next_due: string | null
}

export interface OrthoControl {
  id: string
  clinic_id: string
  case_id: string
  performed_at: string
  performed_by: string | null
  upper_wire: string | null
  lower_wire: string | null
  procedures: string[]
  procedures_other: string | null
  aligner_number: number | null
  hygiene: 'good' | 'fair' | 'poor' | null
  notes: string | null
  next_control_weeks: number | null
  next_due: string | null
}

export interface OrthoSettings {
  clinic_id: string
  wires: string[]
  procedures: string[]
}

export function useOrthodontics() {
  const api = useApi()

  async function listCases(params?: { patient_id?: string, status?: string }): Promise<OrthoCase[]> {
    const response = await api.get<ApiResponse<OrthoCase[]>>('/api/v1/orthodontics/cases', { params })
    return response.data
  }

  async function getCase(id: string): Promise<OrthoCase> {
    const response = await api.get<ApiResponse<OrthoCase>>(`/api/v1/orthodontics/cases/${id}`)
    return response.data
  }

  async function createCase(payload: {
    patient_id: string
    appliance_type: string
    start_date?: string
    estimated_months?: number | null
    professional_id?: string | null
    diagnosis_notes?: string | null
  }): Promise<OrthoCase> {
    const response = await api.post<ApiResponse<OrthoCase>>('/api/v1/orthodontics/cases', payload)
    return response.data
  }

  async function changeStatus(id: string, status: string, status_note?: string | null): Promise<OrthoCase> {
    const response = await api.post<ApiResponse<OrthoCase>>(
      `/api/v1/orthodontics/cases/${id}/status`,
      { status, status_note: status_note ?? null }
    )
    return response.data
  }

  async function listControls(caseId: string): Promise<OrthoControl[]> {
    const response = await api.get<ApiResponse<OrthoControl[]>>(
      `/api/v1/orthodontics/cases/${caseId}/controls`
    )
    return response.data
  }

  async function registerControl(caseId: string, payload: Record<string, unknown>): Promise<OrthoControl> {
    const response = await api.post<ApiResponse<OrthoControl>>(
      `/api/v1/orthodontics/cases/${caseId}/controls`,
      payload
    )
    return response.data
  }

  async function getSettings(): Promise<OrthoSettings> {
    const response = await api.get<ApiResponse<OrthoSettings>>('/api/v1/orthodontics/settings')
    return response.data
  }

  return { listCases, getCase, createCase, changeStatus, listControls, registerControl, getSettings }
}
