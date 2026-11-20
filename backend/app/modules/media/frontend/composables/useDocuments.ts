import type { ApiResponse, Document, DocumentType, PaginatedResponse } from '~~/app/types'

interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}

export function useDocuments() {
  const config = useRuntimeConfig()
  const { csrfHeaders } = useSessionRequest()
  const { t } = useI18n()
  const toast = useToast()

  const documents = ref<Document[]>([])
  const loading = ref(false)
  const uploading = ref(false)
  const uploadProgress = ref<UploadProgress | null>(null)
  const total = ref(0)

  const api = useApi()
  const auth = useAuth()
  const apiBaseUrl = computed(() =>
    import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
  )

  async function fetchDocuments(
    patientId: string,
    documentType?: DocumentType,
    page = 1,
    pageSize = 20,
    mediaKind?: 'document' | 'photo' | 'xray' | 'scan' | 'video'
  ) {
    loading.value = true
    try {
      const response = await api.get<PaginatedResponse<Document>>(
        `/api/v1/media/patients/${patientId}/documents`,
        {
          query: {
            page,
            page_size: pageSize,
            document_type: documentType,
            media_kind: mediaKind
          }
        }
      )

      documents.value = response.data
      total.value = response.total
    } catch (error) {
      // useApi already toasts 403/5xx/network; don't say it twice.
      console.error('Error fetching documents:', error)
    } finally {
      loading.value = false
    }
  }

  async function uploadDocument(
    patientId: string,
    file: File,
    documentType: DocumentType,
    title: string,
    description?: string
  ): Promise<Document | null> {
    uploading.value = true
    uploadProgress.value = { loaded: 0, total: file.size, percentage: 0 }

    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_type', documentType)
    formData.append('title', title)
    if (description) {
      formData.append('description', description)
    }

    // The upload stays on ``$fetch``: it carries FormData and reports
    // progress, neither of which ``useApi`` models. So it carries its own
    // 401 recovery instead — one refresh, one retry, the same contract as
    // ``useApi`` (#452).
    const send = () => $fetch<ApiResponse<Document>>(
      `/api/v1/media/patients/${patientId}/documents`,
      {
        baseURL: apiBaseUrl.value,
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers: csrfHeaders('POST'),
        // No Content-Type: ofetch leaves it unset for FormData bodies so
        // the browser adds the multipart boundary.
        onRequestError() {
          uploadProgress.value = null
        },
        onResponse() {
          uploadProgress.value = { loaded: file.size, total: file.size, percentage: 100 }
        }
      }
    )

    try {
      let response: ApiResponse<Document>
      try {
        response = await send()
      } catch (error: unknown) {
        if ((error as { statusCode?: number })?.statusCode !== 401) throw error
        if (!(await auth.refresh())) {
          await auth.logout()
          throw error
        }
        response = await send()
      }

      toast.add({
        title: t('common.success'),
        description: t('documents.uploadSuccess', 'Document uploaded successfully'),
        color: 'success'
      })

      return response.data
    } catch (error) {
      console.error('Error uploading document:', error)
      toast.add({
        title: t('common.error'),
        description: t('documents.uploadError', 'Error uploading document'),
        color: 'error'
      })
      return null
    } finally {
      uploading.value = false
      uploadProgress.value = null
    }
  }

  async function downloadDocument(documentId: string, filename: string) {
    try {
      // api.raw carries the session cookies and refreshes once on 401, so
      // a download after a long idle still works (#440).
      const response = await api.raw(`/api/v1/media/documents/${documentId}/download?variant=full`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      // Create download link
      const url = window.URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Error downloading document:', error)
      toast.add({
        title: t('common.error'),
        description: t('documents.downloadError', 'Error downloading document'),
        color: 'error'
      })
    }
  }

  /**
   * Get blob URL for viewing document inline.
   * Caller is responsible for calling URL.revokeObjectURL() when done.
   */
  async function getDocumentBlobUrl(documentId: string): Promise<string | null> {
    try {
      const response = await api.raw(`/api/v1/media/documents/${documentId}/download`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return URL.createObjectURL(await response.blob())
    } catch (error) {
      console.error('Error fetching document blob:', error)
      toast.add({
        title: t('common.error'),
        description: t('documents.viewError'),
        color: 'error'
      })
      return null
    }
  }

  async function deleteDocument(documentId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/media/documents/${documentId}`)

      // Remove from local list
      documents.value = documents.value.filter(d => d.id !== documentId)

      toast.add({
        title: t('common.success'),
        description: t('documents.deleteSuccess', 'Document deleted'),
        color: 'success'
      })

      return true
    } catch (error) {
      console.error('Error deleting document:', error)
      return false
    }
  }

  async function updateDocument(
    documentId: string,
    // description: null clears it; an omitted key leaves it untouched.
    data: { title?: string, description?: string | null, document_type?: DocumentType }
  ): Promise<Document | null> {
    try {
      const response = await api.put<ApiResponse<Document>>(
        `/api/v1/media/documents/${documentId}`,
        data
      )

      // Update local list
      const idx = documents.value.findIndex(d => d.id === documentId)
      if (idx !== -1) {
        documents.value[idx] = response.data
      }

      toast.add({
        title: t('common.success'),
        description: t('documents.updateSuccess', 'Document updated'),
        color: 'success'
      })

      return response.data
    } catch (error) {
      console.error('Error updating document:', error)
      return null
    }
  }

  // Document type labels
  const documentTypeLabels: Record<DocumentType, string> = {
    consent: 'documents.types.consent',
    id_scan: 'documents.types.id_scan',
    insurance: 'documents.types.insurance',
    report: 'documents.types.report',
    referral: 'documents.types.referral',
    other: 'documents.types.other'
  }

  function getDocumentTypeLabel(type: DocumentType): string {
    return t(documentTypeLabels[type] || 'documents.types.other')
  }

  // Format file size
  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // Get icon for document type
  function getDocumentIcon(type: DocumentType): string {
    const icons: Record<DocumentType, string> = {
      consent: 'i-lucide-file-signature',
      id_scan: 'i-lucide-id-card',
      insurance: 'i-lucide-shield',
      report: 'i-lucide-file-text',
      referral: 'i-lucide-file-output',
      other: 'i-lucide-file'
    }
    return icons[type] || 'i-lucide-file'
  }

  // Get icon for mime type
  function getMimeTypeIcon(mimeType: string): string {
    if (mimeType === 'application/pdf') return 'i-lucide-file-text'
    if (mimeType.startsWith('image/')) return 'i-lucide-image'
    return 'i-lucide-file'
  }

  return {
    documents,
    loading,
    uploading,
    uploadProgress,
    total,
    fetchDocuments,
    uploadDocument,
    downloadDocument,
    getDocumentBlobUrl,
    deleteDocument,
    updateDocument,
    getDocumentTypeLabel,
    formatFileSize,
    getDocumentIcon,
    getMimeTypeIcon
  }
}
