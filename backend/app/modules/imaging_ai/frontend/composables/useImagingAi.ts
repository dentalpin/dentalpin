import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface AiJob {
  id: string
  clinic_id: string
  patient_id: string
  study_id: string
  document_id: string
  backend: string
  model_id: string
  model_version: string
  status: string
  log_excerpt: string | null
  error: string | null
  artifact_document_ids: string[]
  created_at: string
  updated_at: string
}

export function useImagingAi() {
  const api = useApi()

  async function queueJob(patientId: string, studyId: string, documentId: string) {
    const res = await api.post<ApiResponse<AiJob>>(
      `/api/v1/imaging_ai/patients/${patientId}/ai-jobs`,
      { study_id: studyId, document_id: documentId }
    )
    return res.data
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

  return { queueJob, fetchJobs, fetchJob }
}
