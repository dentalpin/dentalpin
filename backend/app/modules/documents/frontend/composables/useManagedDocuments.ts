/**
 * Composable for the documents module API.
 *
 * Typed wrappers over the `/api/v1/documents` endpoints. Named
 * `useManagedDocuments` so this layer's auto-import does not shadow the
 * media module's `useDocuments` composable across layers.
 */

import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface ManagedDocument {
  id: string
  clinic_id: string
  patient_id: string
  document_type: GeneratedDocumentType
  title: string
  status: DocumentStatus
  content: Record<string, unknown>
  file_path: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export type GeneratedDocumentType
  = | 'prescription'
    | 'medical_certificate'
    | 'referral'
    | 'radiology_request'

export type DocumentStatus = 'draft' | 'generated' | 'archived'

export interface MedicationDraft {
  name: string
  dose: string
  frequency: string
  duration: string
  notes: string
}

export interface DocumentListParams {
  patient_id?: string
  document_type?: GeneratedDocumentType
  status?: string
  page?: number
  page_size?: number
}

function truthy(value: string | undefined): string | undefined {
  return value ? value : undefined
}

export function useManagedDocuments() {
  const api = useApi()

  async function listDocuments(params: DocumentListParams = {}): Promise<PaginatedResponse<ManagedDocument>> {
    return api.get<PaginatedResponse<ManagedDocument>>('/api/v1/documents', {
      query: {
        patient_id: truthy(params.patient_id),
        document_type: truthy(params.document_type),
        status: truthy(params.status),
        page: params.page,
        page_size: params.page_size
      }
    })
  }

  async function getDocument(id: string): Promise<ApiResponse<ManagedDocument>> {
    return api.get<ApiResponse<ManagedDocument>>(`/api/v1/documents/${id}`)
  }

  async function createDocument(data: {
    patient_id: string
    document_type: GeneratedDocumentType
    title: string
    content: Record<string, unknown>
  }): Promise<ApiResponse<ManagedDocument>> {
    return api.post<ApiResponse<ManagedDocument>>('/api/v1/documents', data)
  }

  async function updateDocument(
    id: string,
    data: {
      title?: string
      content?: Record<string, unknown>
      status?: DocumentStatus
    }
  ): Promise<ApiResponse<ManagedDocument>> {
    return api.patch<ApiResponse<ManagedDocument>>(`/api/v1/documents/${id}`, data)
  }

  async function deleteDocument(id: string): Promise<void> {
    await api.del<null>(`/api/v1/documents/${id}`)
  }

  async function generateDocument(document_id: string): Promise<ApiResponse<ManagedDocument>> {
    return api.post<ApiResponse<ManagedDocument>>('/api/v1/documents/generate', { document_id })
  }

  /**
   * Download a generated document as PDF. Mirror of billing's
   * ``useInvoices.downloadPDF``: raw ``fetch`` (blob response) so the
   * file streams straight to a download, with the server's
   * ``Content-Disposition`` filename preserved.
   */
  async function downloadDocument(document_id: string): Promise<void> {
    const response = await api.raw(`/api/v1/documents/${document_id}/download`)

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.message || body?.detail || 'Failed to download PDF')
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    const contentDisposition = response.headers.get('Content-Disposition')
    const filenameMatch = contentDisposition?.match(/filename="?(.+)"?/)
    link.download = filenameMatch?.[1] || `document_${document_id.slice(0, 8)}.pdf`

    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  return {
    listDocuments,
    getDocument,
    createDocument,
    updateDocument,
    deleteDocument,
    generateDocument,
    downloadDocument
  }
}
