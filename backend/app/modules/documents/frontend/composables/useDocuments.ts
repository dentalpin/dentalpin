/**
 * Composable for document operations.
 * Wraps API calls and provides reactive state for the documents module.
 */
export function useDocuments() {
  const api = useApi()

  async function listDocuments(params: {
    patient_id?: string
    document_type?: string
    status?: string
    page?: number
    page_size?: number
  } = {}) {
    const query = new URLSearchParams()
    if (params.patient_id) query.set('patient_id', params.patient_id)
    if (params.document_type) query.set('document_type', params.document_type)
    if (params.status) query.set('status', params.status)
    if (params.page) query.set('page', String(params.page))
    if (params.page_size) query.set('page_size', String(params.page_size))

    return api.get(`/api/v1/documents?${query.toString()}`)
  }

  async function getDocument(id: string) {
    return api.get(`/api/v1/documents/${id}`)
  }

  async function createDocument(data: {
    patient_id: string
    document_type: string
    title: string
    content?: Record<string, any>
  }) {
    return api.post('/api/v1/documents', data)
  }

  async function updateDocument(
    id: string,
    data: {
      title?: string
      content?: Record<string, any>
      status?: string
    }
  ) {
    return api.patch(`/api/v1/documents/${id}`, data)
  }

  async function deleteDocument(id: string) {
    return api.delete(`/api/v1/documents/${id}`)
  }

  async function generateDocument(document_id: string) {
    return api.post('/api/v1/documents/generate', { document_id })
  }

  return {
    listDocuments,
    getDocument,
    createDocument,
    updateDocument,
    deleteDocument,
    generateDocument
  }
}
