import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface AiJob {
  id: string
  clinic_id: string
  patient_id: string
  document_id: string
  series_document_ids: string[]
  backend: string
  model_id: string
  model_version: string
  status: string
  review_status: string
  confirmed_by: string | null
  confirmed_at: string | null
  queued_by: string | null
  log_excerpt: string | null
  error: string | null
  artifact_document_ids: string[]
  created_at: string
  updated_at: string
}

export interface DicomDocument {
  id: string
  original_filename: string
  mime_type: string
  file_size: number
  created_at: string
}

export interface PatientOption {
  id: string
  first_name: string
  last_name: string
}

export function useImagingAi() {
  const api = useApi()

  async function queueJob(
    patientId: string,
    payload: { document_id: string, series_document_ids: string[], backend: string }
  ) {
    const res = await api.post<ApiResponse<AiJob>>(
      `/api/v1/imaging_ai/patients/${patientId}/ai-jobs`,
      payload
    )
    return res.data
  }

  async function confirmJob(jobId: string) {
    const res = await api.post<ApiResponse<AiJob>>(`/api/v1/imaging_ai/ai-jobs/${jobId}/confirm`)
    return res.data
  }

  async function cancelJob(jobId: string) {
    await api.del(`/api/v1/imaging_ai/ai-jobs/${jobId}`)
  }

  async function fetchJobs(patientId: string, page = 1, pageSize = 20) {
    return api.get<PaginatedResponse<AiJob>>(
      `/api/v1/imaging_ai/patients/${patientId}/ai-jobs`,
      { query: { page, page_size: pageSize } }
    )
  }

  async function fetchJob(jobId: string) {
    const res = await api.get<ApiResponse<AiJob>>(`/api/v1/imaging_ai/ai-jobs/${jobId}`)
    return res.data
  }

  async function fetchDicomDocuments(patientId: string) {
    const res = await api.get<ApiResponse<DicomDocument[]>>(
      `/api/v1/imaging_ai/patients/${patientId}/dicom-documents`
    )
    return res.data
  }

  async function searchPatients(search: string) {
    const res = await api.get<PaginatedResponse<PatientOption>>(
      '/api/v1/patients',
      { query: { search, page: 1, page_size: 10 } }
    )
    return res.data
  }

  return { queueJob, confirmJob, cancelJob, fetchJobs, fetchJob, fetchDicomDocuments, searchPatients }
}
