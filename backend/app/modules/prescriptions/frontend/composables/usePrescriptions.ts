import type { ApiResponse } from '~~/app/types'

export interface PrescriptionItem {
  id?: string
  medication_name: string
  catalog_ref?: string | null
  dosage?: string
  unit?: string
  route?: string | null
  frequency?: string
  duration?: string
  instructions?: string
  sort_order?: number
}

export interface Prescription {
  id: string
  patient_id: string
  prescriber_id: string
  status: 'draft' | 'issued' | 'cancelled'
  issued_at: string | null
  notes: string | null
  locale: string
  prescriber_name: string | null
  license_number: string | null
  compliance_data: Record<string, unknown>
  items: PrescriptionItem[]
}

export interface PrescriptionTemplate {
  id: string
  name: string
  items: PrescriptionItem[]
}

export function usePrescriptions() {
  const api = useApi()

  async function listForPatient(patientId: string): Promise<Prescription[]> {
    const response = await api.get<ApiResponse<Prescription[]>>(
      `/api/v1/prescriptions/patients/${patientId}/prescriptions`
    )
    return response.data
  }

  async function createDraft(patientId: string, items: PrescriptionItem[] = [], notes?: string): Promise<Prescription> {
    const response = await api.post<ApiResponse<Prescription>>(
      `/api/v1/prescriptions/patients/${patientId}/prescriptions`,
      { patient_id: patientId, notes: notes ?? null, items }
    )
    return response.data
  }

  async function updateDraft(id: string, payload: { notes?: string | null, items?: PrescriptionItem[] }): Promise<Prescription> {
    const response = await api.patch<ApiResponse<Prescription>>(
      `/api/v1/prescriptions/prescriptions/${id}`,
      payload
    )
    return response.data
  }

  async function issue(id: string): Promise<Prescription> {
    const response = await api.post<ApiResponse<Prescription>>(
      `/api/v1/prescriptions/prescriptions/${id}/issue`
    )
    return response.data
  }

  async function cancel(id: string): Promise<Prescription> {
    const response = await api.post<ApiResponse<Prescription>>(
      `/api/v1/prescriptions/prescriptions/${id}/cancel`
    )
    return response.data
  }

  async function warnings(patientId: string): Promise<{ allergies: string[], interaction_flags: string[] }> {
    const response = await api.get<ApiResponse<{ allergies: string[], interaction_flags: string[] }>>(
      `/api/v1/prescriptions/patients/${patientId}/prescribe-warnings`
    )
    return response.data
  }

  async function listTemplates(): Promise<PrescriptionTemplate[]> {
    const response = await api.get<ApiResponse<PrescriptionTemplate[]>>(
      '/api/v1/prescriptions/templates'
    )
    return response.data
  }

  async function createTemplate(name: string, items: PrescriptionItem[]): Promise<PrescriptionTemplate> {
    const response = await api.post<ApiResponse<PrescriptionTemplate>>(
      '/api/v1/prescriptions/templates',
      { name, items }
    )
    return response.data
  }

  async function deleteTemplate(id: string): Promise<void> {
    await api.del(`/api/v1/prescriptions/templates/${id}`)
  }

  async function updateTemplate(id: string, name: string): Promise<PrescriptionTemplate> {
    const response = await api.patch<ApiResponse<PrescriptionTemplate>>(
      `/api/v1/prescriptions/templates/${id}`,
      { name }
    )
    return response.data
  }

  return {
    listForPatient, createDraft, updateDraft, issue, cancel,
    warnings, listTemplates, createTemplate, updateTemplate, deleteTemplate
  }
}
