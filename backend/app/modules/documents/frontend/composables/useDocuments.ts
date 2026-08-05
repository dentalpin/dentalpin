import type { ApiResponse, PaginatedResponse } from '~/types'

export type DocumentType = 'prescription' | 'certificate' | 'referral' | 'radiology_request'
export type CertificateType = 'work_absence' | 'school_absence' | 'fitness_for_work'
export type ReferralUrgency = 'routine' | 'urgent'

export interface PrescriptionItem {
  drug_name: string
  dosage: string
  instructions: string
  quantity?: string | null
  medication_id?: string | null
}

export interface GeneratedDocument {
  id: string
  clinic_id: string
  patient_id: string
  created_by: string
  document_type: DocumentType
  title: string
  payload: Record<string, any>
  file_path?: string | null
  created_at: string
}

export interface PrescriptionCreatePayload {
  patient_id: string
  items: PrescriptionItem[]
  notes?: string | null
}

export interface CertificateCreatePayload {
  patient_id: string
  certificate_type: CertificateType
  start_date: string
  end_date?: string | null
  reason?: string | null
  notes?: string | null
}

export interface ReferralCreatePayload {
  patient_id: string
  specialist_name: string
  specialty: string
  reason: string
  clinical_history?: string | null
  urgency?: ReferralUrgency
}

export interface RadiologyRequestCreatePayload {
  patient_id: string
  exam_type: string
  tooth_reference?: string | null
  clinical_indication: string
  notes?: string | null
}

export interface Letterhead {
  id: string
  clinic_id: string
  practice_name: string
  legal_name?: string | null
  address?: Record<string, any> | null
  phone?: string | null
  email?: string | null
  logo_url?: string | null
  registration_number?: string | null
  footer_text?: string | null
  created_at: string
  updated_at: string
}

export interface LetterheadPayload {
  practice_name: string
  legal_name?: string | null
  address?: Record<string, any> | null
  phone?: string | null
  email?: string | null
  logo_url?: string | null
  registration_number?: string | null
  footer_text?: string | null
}

export interface DocumentListFilters {
  document_type?: DocumentType
  patient_id?: string
  limit?: number
  offset?: number
}

export function useDocuments() {
  const api = useApi()

  async function list(filters: DocumentListFilters = {}): Promise<PaginatedResponse<GeneratedDocument>> {
    return await api.get<PaginatedResponse<GeneratedDocument>>('/api/v1/documents/', {
      query: filters as Record<string, string | number | boolean | undefined | null>
    })
  }

  async function get(id: string): Promise<ApiResponse<GeneratedDocument>> {
    return await api.get<ApiResponse<GeneratedDocument>>(`/api/v1/documents/${id}`)
  }

  async function createPrescription(payload: PrescriptionCreatePayload): Promise<ApiResponse<GeneratedDocument>> {
    return await api.post<ApiResponse<GeneratedDocument>>('/api/v1/documents/prescription', payload)
  }

  async function createCertificate(payload: CertificateCreatePayload): Promise<ApiResponse<GeneratedDocument>> {
    return await api.post<ApiResponse<GeneratedDocument>>('/api/v1/documents/certificate', payload)
  }

  async function createReferral(payload: ReferralCreatePayload): Promise<ApiResponse<GeneratedDocument>> {
    return await api.post<ApiResponse<GeneratedDocument>>('/api/v1/documents/referral', payload)
  }

  async function createRadiologyRequest(payload: RadiologyRequestCreatePayload): Promise<ApiResponse<GeneratedDocument>> {
    return await api.post<ApiResponse<GeneratedDocument>>('/api/v1/documents/radiology-request', payload)
  }

  async function getLetterhead(): Promise<ApiResponse<Letterhead | null>> {
    return await api.get<ApiResponse<Letterhead | null>>('/api/v1/documents/letterhead')
  }

  async function saveLetterhead(payload: LetterheadPayload): Promise<ApiResponse<Letterhead>> {
    return await api.put<ApiResponse<Letterhead>>('/api/v1/documents/letterhead', payload)
  }

  // useApi()'s UseApiOptions has no `responseType` — it always calls
  // $fetch with no override, which JSON-parses by default and breaks on
  // a binary PDF body. There's no way to get a Blob back through
  // useApi() as written, so this bypasses it and mirrors $api's own
  // auth logic (Bearer token from useAuth(), client-side base URL from
  // useRuntimeConfig()) by hand — this is the one place doing that is
  // actually correct, not a guess-around.
  async function downloadPdf(doc: GeneratedDocument): Promise<void> {
    const config = useRuntimeConfig()
    const auth = useAuth()

    const response = await fetch(
      `${config.public.apiBaseUrl}/api/v1/documents/${doc.id}/pdf`,
      {
        headers: auth.accessToken.value
          ? { Authorization: `Bearer ${auth.accessToken.value}` }
          : {}
      }
    )
    if (!response.ok) {
      throw new Error(`Failed to download PDF (${response.status})`)
    }
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${doc.document_type}_${doc.id}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  return {
    list,
    get,
    createPrescription,
    createCertificate,
    createReferral,
    createRadiologyRequest,
    getLetterhead,
    saveLetterhead,
    downloadPdf
  }
}
