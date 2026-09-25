import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface ImagingStudy {
  id: string
  clinic_id: string
  patient_id: string
  document_id: string
  study_uid: string
  modality: string | null
  study_date: string | null
  dicom_metadata: Record<string, unknown>
  status: string
  created_at: string
  updated_at: string
}

export function useImagingViewer() {
  const api = useApi()

  async function fetchStudies(patientId: string, page = 1, pageSize = 20) {
    return api.get<PaginatedResponse<ImagingStudy>>(
      `/api/v1/imaging_viewer/patients/${patientId}/studies`,
      { query: { page, page_size: pageSize } }
    )
  }

  async function fetchStudy(studyId: string) {
    const res = await api.get<ApiResponse<ImagingStudy>>(
      `/api/v1/imaging_viewer/studies/${studyId}`
    )
    return res.data
  }

  /**
   * Rendered PNG as an object URL.
   *
   * NOT a relative path: in docker-compose and Coolify the API lives on
   * another origin (NUXT_PUBLIC_API_BASE_URL / BACKEND_URL), so a plain
   * `<img src="/api/...">` hits the Nuxt origin and 404s. `api.raw()` is the
   * media-module pattern (getDocumentBlobUrl): it carries the session
   * cookies and the 401 -> refresh path, and the blob is same-origin-safe.
   * Caller must revokeObjectURL() when the view is torn down.
   */
  async function fetchRenderBlobUrl(studyId: string): Promise<string | null> {
    try {
      const response = await api.raw(`/api/v1/imaging_viewer/studies/${studyId}/render`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return URL.createObjectURL(await response.blob())
    } catch {
      return null
    }
  }

  async function fetchAnnotations(studyId: string) {
    const res = await api.get<ApiResponse<StudyAnnotation[]>>(
      `/api/v1/imaging_viewer/studies/${studyId}/annotations`
    )
    return res.data
  }

  async function createAnnotation(
    studyId: string,
    kind: 'ruler' | 'freehand' | 'note',
    points: Array<[number, number]>,
    text?: string
  ) {
    const res = await api.post<ApiResponse<StudyAnnotation>>(
      `/api/v1/imaging_viewer/studies/${studyId}/annotations`,
      { kind, payload: { points, ...(text ? { text } : {}) } }
    )
    return res.data
  }

  async function deleteAnnotation(annotationId: string) {
    await api.del(`/api/v1/imaging_viewer/annotations/${annotationId}`)
  }

  return { fetchStudies, fetchStudy, fetchRenderBlobUrl, fetchAnnotations, createAnnotation, deleteAnnotation }
}

export interface StudyAnnotation {
  id: string
  clinic_id: string
  patient_id: string
  study_id: string
  kind: 'ruler' | 'freehand' | 'note'
  payload: { points: Array<[number, number]>, text?: string, mm?: number }
  spacing_mm: number | null
  status: string
  created_at: string
  updated_at: string
}

export interface RvgImport {
  id: string
  clinic_id: string
  patient_id: string | null
  document_id: string | null
  study_id: string | null
  filename: string
  identity_tags: Record<string, unknown>
  suggested_patient_id: string | null
  match_score: number | null
  match_reason: string | null
  status: string
  error: string | null
  created_at: string
  updated_at: string
}

export interface RvgLink {
  id: string
  clinic_id: string
  patient_id: string
  dicom_patient_id: string
  created_at: string
  updated_at: string
}

export function useRvgImport() {
  const api = useApi()

  async function fetchImports(status?: string, page = 1, pageSize = 20) {
    return api.get<PaginatedResponse<RvgImport>>('/api/v1/imaging_viewer/rvg/imports', {
      query: { ...(status ? { status } : {}), page, page_size: pageSize }
    })
  }

  async function triggerScan(retryFailed = false) {
    const res = await api.post<ApiResponse<Record<string, number>>>(
      '/api/v1/imaging_viewer/rvg/scan',
      { retry_failed: retryFailed }
    )
    return res.data
  }

  async function approveImport(importId: string, patientId: string) {
    const res = await api.post<ApiResponse<RvgImport>>(
      `/api/v1/imaging_viewer/rvg/imports/${importId}/approve`,
      { patient_id: patientId }
    )
    return res.data
  }

  async function rejectImport(importId: string, reason?: string) {
    const res = await api.post<ApiResponse<RvgImport>>(
      `/api/v1/imaging_viewer/rvg/imports/${importId}/reject`,
      { reason: reason ?? null }
    )
    return res.data
  }

  async function fetchLinks() {
    const res = await api.get<ApiResponse<RvgLink[]>>('/api/v1/imaging_viewer/rvg/links')
    return res.data
  }

  async function deleteLink(linkId: string) {
    await api.del(`/api/v1/imaging_viewer/rvg/links/${linkId}`)
  }

  return { fetchImports, triggerScan, approveImport, rejectImport, fetchLinks, deleteLink }
}
