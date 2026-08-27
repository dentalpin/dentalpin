import type {
  ApiResponse,
  Budget,
  BudgetAcceptRequest,
  BudgetCancelRequest,
  BudgetCreate,
  BudgetDetail,
  BudgetHistoryEntry,
  BudgetItem,
  BudgetItemCreate,
  BudgetItemUpdate,
  BudgetListItem,
  BudgetRejectRequest,
  BudgetSendRequest,
  BudgetStatus,
  BudgetUpdate,
  BudgetVersionList,
  PaginatedResponse
} from '~~/app/types'

export interface BudgetSignatureMeta {
  id: string
  budget_id: string
  signature_type: string
  signed_by_name: string
  signed_by_email: string | null
  relationship_to_patient: string
  signature_method: string
  ip_address: string | null
  signed_at: string
  document_hash: string | null
  created_at: string
}

export interface BudgetListParams {
  page?: number
  page_size?: number
  patient_id?: string
  status?: BudgetStatus[]
  created_by?: string
  date_from?: string
  date_to?: string
  expired?: boolean
  search?: string
}

// Status colors for badges
const STATUS_COLORS: Record<BudgetStatus, string> = {
  draft: 'gray',
  sent: 'blue',
  accepted: 'green',
  completed: 'emerald',
  rejected: 'red',
  expired: 'orange',
  cancelled: 'neutral'
}

export function useBudgets() {
  const api = useApi()
  const config = useRuntimeConfig()
  const auth = useAuth()

  // State
  const budgets = useState<BudgetListItem[]>('budgets:list', () => [])
  const currentBudget = useState<BudgetDetail | null>('budgets:current', () => null)
  const isLoading = useState<boolean>('budgets:loading', () => false)
  const error = useState<string | null>('budgets:error', () => null)
  const total = useState<number>('budgets:total', () => 0)

  // ============================================================================
  // CRUD Operations
  // ============================================================================

  async function fetchBudgets(params: BudgetListParams = {}): Promise<BudgetListItem[]> {
    isLoading.value = true
    error.value = null

    try {
      const searchParams = new URLSearchParams()

      if (params.page) searchParams.set('page', params.page.toString())
      if (params.page_size) searchParams.set('page_size', params.page_size.toString())
      if (params.patient_id) searchParams.set('patient_id', params.patient_id)
      if (params.status?.length) {
        params.status.forEach(s => searchParams.append('status', s))
      }
      if (params.created_by) searchParams.set('created_by', params.created_by)
      if (params.date_from) searchParams.set('date_from', params.date_from)
      if (params.date_to) searchParams.set('date_to', params.date_to)
      if (params.expired !== undefined) searchParams.set('expired', params.expired.toString())
      if (params.search) searchParams.set('search', params.search)

      const response = await api.get<PaginatedResponse<BudgetListItem>>(
        `/api/v1/budget/budgets?${searchParams.toString()}`
      )

      budgets.value = response.data
      total.value = response.total
      return response.data
    } catch (e) {
      error.value = 'Failed to fetch budgets'
      console.error('Failed to fetch budgets:', e)
      return []
    } finally {
      isLoading.value = false
    }
  }

  async function fetchBudget(id: string): Promise<BudgetDetail | null> {
    isLoading.value = true
    error.value = null

    try {
      const response = await api.get<ApiResponse<BudgetDetail>>(
        `/api/v1/budget/budgets/${id}`
      )
      currentBudget.value = response.data
      return response.data
    } catch (e) {
      error.value = 'Failed to fetch budget'
      console.error('Failed to fetch budget:', e)
      return null
    } finally {
      isLoading.value = false
    }
  }

  function toListItem(b: BudgetDetail): BudgetListItem {
    return {
      id: b.id,
      budget_number: b.budget_number,
      version: b.version,
      status: b.status,
      valid_from: b.valid_from,
      valid_until: b.valid_until,
      total: b.total,
      created_at: b.created_at,
      patient: b.patient,
      creator: b.creator
    }
  }

  async function createBudget(data: BudgetCreate): Promise<BudgetDetail> {
    const response = await api.post<ApiResponse<BudgetDetail>>(
      '/api/v1/budget/budgets',
      data
    )
    budgets.value = [toListItem(response.data), ...budgets.value]
    currentBudget.value = response.data
    return response.data
  }

  async function updateBudget(id: string, data: BudgetUpdate): Promise<BudgetDetail> {
    const response = await api.put<ApiResponse<BudgetDetail>>(
      `/api/v1/budget/budgets/${id}`,
      data
    )

    // Update local state
    budgets.value = budgets.value.map(b =>
      b.id === id
        ? {
            ...b,
            valid_from: response.data.valid_from,
            valid_until: response.data.valid_until,
            total: response.data.total
          }
        : b
    )
    if (currentBudget.value?.id === id) {
      currentBudget.value = response.data
    }

    return response.data
  }

  async function deleteBudget(id: string): Promise<void> {
    await api.del(`/api/v1/budget/budgets/${id}`)

    // Remove from local state
    budgets.value = budgets.value.filter(b => b.id !== id)
    if (currentBudget.value?.id === id) {
      currentBudget.value = null
    }
  }

  // ============================================================================
  // Item Operations
  // ============================================================================

  async function addItem(budgetId: string, data: BudgetItemCreate): Promise<BudgetItem> {
    const response = await api.post<ApiResponse<BudgetItem>>(
      `/api/v1/budget/budgets/${budgetId}/items`,
      data
    )

    // Refetch current budget to get updated totals
    if (currentBudget.value?.id === budgetId) {
      await fetchBudget(budgetId)
    }

    return response.data
  }

  async function updateItem(
    budgetId: string,
    itemId: string,
    data: BudgetItemUpdate
  ): Promise<BudgetItem> {
    const response = await api.put<ApiResponse<BudgetItem>>(
      `/api/v1/budget/budgets/${budgetId}/items/${itemId}`,
      data
    )

    // Refetch current budget to get updated totals
    if (currentBudget.value?.id === budgetId) {
      await fetchBudget(budgetId)
    }

    return response.data
  }

  async function removeItem(budgetId: string, itemId: string): Promise<void> {
    await api.del(`/api/v1/budget/budgets/${budgetId}/items/${itemId}`)

    // Refetch current budget to get updated totals
    if (currentBudget.value?.id === budgetId) {
      await fetchBudget(budgetId)
    }
  }

  // ============================================================================
  // Workflow Operations
  // ============================================================================

  async function sendBudget(id: string, data: BudgetSendRequest = {}): Promise<Budget> {
    const response = await api.post<ApiResponse<Budget>>(
      `/api/v1/budget/budgets/${id}/send`,
      data
    )

    // Update local state
    updateBudgetStatus(id, response.data.status)

    return response.data
  }

  async function acceptBudget(id: string, data: BudgetAcceptRequest): Promise<Budget> {
    const response = await api.post<ApiResponse<Budget>>(
      `/api/v1/budget/budgets/${id}/accept`,
      data
    )

    // Update local state
    updateBudgetStatus(id, response.data.status)

    return response.data
  }

  async function rejectBudget(id: string, data: BudgetRejectRequest = {}): Promise<Budget> {
    const response = await api.post<ApiResponse<Budget>>(
      `/api/v1/budget/budgets/${id}/reject`,
      data
    )

    // Update local state
    updateBudgetStatus(id, response.data.status)

    return response.data
  }

  async function cancelBudget(id: string, data: BudgetCancelRequest = {}): Promise<Budget> {
    const response = await api.post<ApiResponse<Budget>>(
      `/api/v1/budget/budgets/${id}/cancel`,
      data
    )

    // Update local state
    updateBudgetStatus(id, response.data.status)

    return response.data
  }

  async function duplicateBudget(id: string): Promise<BudgetDetail> {
    const response = await api.post<ApiResponse<BudgetDetail>>(
      `/api/v1/budget/budgets/${id}/duplicate`,
      {}
    )
    budgets.value = [toListItem(response.data), ...budgets.value]
    return response.data
  }

  async function resendBudget(id: string): Promise<BudgetDetail> {
    const response = await api.post<ApiResponse<BudgetDetail>>(
      `/api/v1/budget/budgets/${id}/resend`,
      {}
    )
    budgets.value = [toListItem(response.data), ...budgets.value]
    return response.data
  }

  // ============================================================================
  // Versions and History
  // ============================================================================

  async function fetchVersions(id: string): Promise<BudgetVersionList | null> {
    try {
      const response = await api.get<ApiResponse<BudgetVersionList>>(
        `/api/v1/budget/budgets/${id}/versions`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch budget versions:', e)
      return null
    }
  }

  async function fetchHistory(id: string): Promise<BudgetHistoryEntry[]> {
    try {
      const response = await api.get<ApiResponse<BudgetHistoryEntry[]>>(
        `/api/v1/budget/budgets/${id}/history`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch budget history:', e)
      return []
    }
  }

  // ============================================================================
  // PDF
  // ============================================================================

  async function downloadPDF(id: string, locale: string = 'es'): Promise<void> {
    await downloadPDFAt(`/api/v1/budget/budgets/${id}/pdf?locale=${locale}`, `presupuesto_${id}.pdf`)
  }

  async function downloadSignedPDF(id: string, locale: string = 'es'): Promise<void> {
    await downloadPDFAt(
      `/api/v1/budget/budgets/${id}/pdf/signed?locale=${locale}`,
      `presupuesto_${id}_firmado.pdf`
    )
  }

  async function downloadPDFAt(path: string, fallbackName: string): Promise<void> {
    const baseUrl = config.public.apiBaseUrl
    const token = auth.accessToken.value

    const response = await fetch(`${baseUrl}${path}`, {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (!response.ok) {
      // This path uses raw fetch (blob response), so it bypasses useApi
      // and its error shaping. Read the server's message rather than
      // throwing a hardcoded English string the UI would then show.
      const body = await response.json().catch(() => null)
      throw new Error(body?.message || body?.detail || 'Failed to download PDF')
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    const contentDisposition = response.headers.get('Content-Disposition')
    const filenameMatch = contentDisposition?.match(/filename="?(.+)"?/)
    link.download = filenameMatch?.[1] || fallbackName

    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  function getPDFPreviewUrl(id: string, locale: string = 'es'): string {
    const baseUrl = config.public.apiBaseUrl
    return `${baseUrl}/api/v1/budget/budgets/${id}/pdf/preview?locale=${locale}`
  }

  // ============================================================================
  // Signature
  // ============================================================================

  async function fetchSignature(id: string): Promise<BudgetSignatureMeta | null> {
    try {
      const response = await api.get<ApiResponse<BudgetSignatureMeta>>(
        `/api/v1/budget/budgets/${id}/signature`
      )
      return response.data
    } catch (e: unknown) {
      const status = (e as { statusCode?: number, status?: number })?.statusCode
        ?? (e as { statusCode?: number, status?: number })?.status
      // 404 is the legitimate "not signed" answer. Anything else is a
      // failed read and must NOT render as "not signed" (issue #101).
      if (status === 404) return null
      console.error('Failed to fetch budget signature:', e)
      throw e
    }
  }

  // ============================================================================
  // Helpers
  // ============================================================================

  function getStatusColor(status: BudgetStatus): string {
    return STATUS_COLORS[status] || 'gray'
  }

  function canEdit(budget: Budget | BudgetDetail | BudgetListItem): boolean {
    return budget.status === 'draft'
  }

  function canSend(budget: Budget | BudgetDetail | BudgetListItem): boolean {
    return budget.status === 'draft'
  }

  function canAccept(budget: Budget | BudgetDetail | BudgetListItem): boolean {
    return ['draft', 'sent'].includes(budget.status)
  }

  function canReject(budget: Budget | BudgetDetail | BudgetListItem): boolean {
    return ['draft', 'sent'].includes(budget.status)
  }

  function canCancel(budget: Budget | BudgetDetail | BudgetListItem): boolean {
    return !['completed', 'rejected', 'expired', 'cancelled'].includes(budget.status)
  }

  function canDuplicate(_budget: Budget | BudgetDetail | BudgetListItem): boolean {
    return true // Can always create a new version
  }

  function canResend(budget: Budget | BudgetDetail | BudgetListItem): boolean {
    // Mirrors the backend guard on POST /resend: only terminal budgets.
    return ['rejected', 'expired', 'cancelled'].includes(budget.status)
  }

  // Internal helper to update status in local state
  function updateBudgetStatus(id: string, status: BudgetStatus): void {
    budgets.value = budgets.value.map(b =>
      b.id === id ? { ...b, status } : b
    )
    if (currentBudget.value?.id === id) {
      currentBudget.value = { ...currentBudget.value, status }
    }
  }

  return {
    // State
    budgets: readonly(budgets),
    currentBudget: readonly(currentBudget),
    isLoading: readonly(isLoading),
    error: readonly(error),
    total: readonly(total),

    // CRUD
    fetchBudgets,
    fetchBudget,
    createBudget,
    updateBudget,
    deleteBudget,

    // Items
    addItem,
    updateItem,
    removeItem,

    // Workflow
    sendBudget,
    acceptBudget,
    rejectBudget,
    cancelBudget,
    duplicateBudget,
    resendBudget,

    // Versions and history
    fetchVersions,
    fetchHistory,

    // PDF
    downloadPDF,
    downloadSignedPDF,
    getPDFPreviewUrl,

    // Signature
    fetchSignature,

    // Helpers
    getStatusColor,
    canEdit,
    canSend,
    canAccept,
    canReject,
    canCancel,
    canDuplicate,
    canResend
  }
}
