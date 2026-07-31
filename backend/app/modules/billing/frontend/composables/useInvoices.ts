import type {
  ApiResponse,
  BillingSettings,
  BillingSettingsUpdate,
  CreditNoteCreate,
  Invoice,
  InvoiceCreate,
  InvoiceDetail,
  InvoiceFromBudgetCreate,
  InvoiceHistoryEntry,
  InvoiceItem,
  InvoiceItemCreate,
  InvoiceItemUpdate,
  InvoiceIssueRequest,
  InvoiceListItem,
  InvoiceSeries,
  InvoiceSeriesCreate,
  InvoiceSeriesUpdate,
  InvoiceSendRequest,
  InvoiceStatus,
  InvoiceUpdate,
  PaginatedResponse,
  PatientBillingSummary,
  InvoicePayment,
  InvoicePaymentApply,
  SeriesResetRequest
} from '~~/app/types'
import { paymentMethodLabel } from '~~/app/utils/paymentMethod'

export interface InvoiceListParams {
  page?: number
  page_size?: number
  patient_id?: string
  status?: InvoiceStatus[]
  date_from?: string
  date_to?: string
  due_from?: string
  due_to?: string
  overdue?: boolean
  search?: string
  budget_id?: string
  is_credit_note?: boolean
  // Generic compliance severity filter — `ok | warning | pending |
  // error`. Backend matches any country in compliance_data whose
  // severity is in the list. Owned by compliance modules.
  compliance_severity?: string[]
}

export function useInvoices() {
  const api = useApi()
  const config = useRuntimeConfig()
  const auth = useAuth()
  const { t } = useI18n()

  // State
  const invoices = useState<InvoiceListItem[]>('invoices:list', () => [])
  const currentInvoice = useState<InvoiceDetail | null>('invoices:current', () => null)
  const isLoading = useState<boolean>('invoices:loading', () => false)
  const error = useState<string | null>('invoices:error', () => null)
  const total = useState<number>('invoices:total', () => 0)

  // ============================================================================
  // Series Operations
  // ============================================================================

  async function fetchSeries(seriesType?: string, activeOnly: boolean = true): Promise<InvoiceSeries[]> {
    try {
      const params = new URLSearchParams()
      if (seriesType) params.set('series_type', seriesType)
      if (!activeOnly) params.set('active_only', 'false')

      const response = await api.get<ApiResponse<InvoiceSeries[]>>(
        `/api/v1/billing/series?${params.toString()}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch series:', e)
      return []
    }
  }

  async function createSeries(data: InvoiceSeriesCreate): Promise<InvoiceSeries> {
    const response = await api.post<ApiResponse<InvoiceSeries>>(
      '/api/v1/billing/series',
      data
    )
    return response.data
  }

  async function updateSeries(id: string, data: InvoiceSeriesUpdate): Promise<InvoiceSeries> {
    const response = await api.put<ApiResponse<InvoiceSeries>>(
      `/api/v1/billing/series/${id}`,
      data
    )
    return response.data
  }

  async function resetSeriesCounter(id: string, data: SeriesResetRequest): Promise<InvoiceSeries> {
    const response = await api.post<ApiResponse<InvoiceSeries>>(
      `/api/v1/billing/series/${id}/reset`,
      data
    )
    return response.data
  }

  // ============================================================================
  // CRUD Operations
  // ============================================================================

  async function fetchInvoices(params: InvoiceListParams = {}): Promise<InvoiceListItem[]> {
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
      if (params.date_from) searchParams.set('date_from', params.date_from)
      if (params.date_to) searchParams.set('date_to', params.date_to)
      if (params.due_from) searchParams.set('due_from', params.due_from)
      if (params.due_to) searchParams.set('due_to', params.due_to)
      if (params.overdue !== undefined) searchParams.set('overdue', params.overdue.toString())
      if (params.search) searchParams.set('search', params.search)
      if (params.budget_id) searchParams.set('budget_id', params.budget_id)
      if (params.is_credit_note !== undefined) searchParams.set('is_credit_note', params.is_credit_note.toString())
      if (params.compliance_severity?.length) {
        params.compliance_severity.forEach(s => searchParams.append('compliance_severity', s))
      }

      const response = await api.get<PaginatedResponse<InvoiceListItem>>(
        `/api/v1/billing/invoices?${searchParams.toString()}`
      )

      invoices.value = response.data
      total.value = response.total
      return response.data
    } catch (e) {
      error.value = 'Failed to fetch invoices'
      console.error('Failed to fetch invoices:', e)
      return []
    } finally {
      isLoading.value = false
    }
  }

  async function fetchInvoice(id: string): Promise<InvoiceDetail | null> {
    isLoading.value = true
    error.value = null

    try {
      const response = await api.get<ApiResponse<InvoiceDetail>>(
        `/api/v1/billing/invoices/${id}`
      )
      currentInvoice.value = response.data
      return response.data
    } catch (e) {
      error.value = 'Failed to fetch invoice'
      console.error('Failed to fetch invoice:', e)
      return null
    } finally {
      isLoading.value = false
    }
  }

  function toListItem(inv: Invoice): InvoiceListItem {
    return {
      id: inv.id,
      invoice_number: inv.invoice_number,
      status: inv.status,
      issue_date: inv.issue_date,
      due_date: inv.due_date,
      total: inv.total,
      total_paid: inv.total_paid,
      balance_due: inv.balance_due,
      created_at: inv.created_at,
      patient: inv.patient,
      creator: inv.creator,
    }
  }

  async function createInvoice(data: InvoiceCreate): Promise<Invoice> {
    const response = await api.post<ApiResponse<Invoice>>(
      '/api/v1/billing/invoices',
      data
    )
    invoices.value = [toListItem(response.data), ...invoices.value]
    return response.data
  }

  async function createFromBudget(budgetId: string, data: InvoiceFromBudgetCreate): Promise<Invoice> {
    const response = await api.post<ApiResponse<Invoice>>(
      `/api/v1/billing/invoices/from-budget/${budgetId}`,
      data
    )
    invoices.value = [toListItem(response.data), ...invoices.value]
    return response.data
  }

  async function updateInvoice(id: string, data: InvoiceUpdate): Promise<Invoice> {
    const response = await api.put<ApiResponse<Invoice>>(
      `/api/v1/billing/invoices/${id}`,
      data
    )

    // Update local state
    invoices.value = invoices.value.map(i =>
      i.id === id
        ? {
            ...i,
            total: response.data.total,
            total_paid: response.data.total_paid,
            balance_due: response.data.balance_due
          }
        : i
    )
    if (currentInvoice.value?.id === id) {
      currentInvoice.value = { ...currentInvoice.value, ...response.data }
    }

    return response.data
  }

  async function updateBillingParty(
    id: string,
    data: {
      billing_name?: string | null
      billing_tax_id?: string | null
      billing_address?: Record<string, unknown> | null
      expected_updated_at?: string | null
    }
  ): Promise<Invoice> {
    const response = await api.patch<ApiResponse<Invoice>>(
      `/api/v1/billing/invoices/${id}/billing-party`,
      data
    )
    if (currentInvoice.value?.id === id) {
      currentInvoice.value = { ...currentInvoice.value, ...response.data }
    }
    return response.data
  }

  async function deleteInvoice(id: string): Promise<void> {
    await api.del(`/api/v1/billing/invoices/${id}`)

    // Remove from local state
    invoices.value = invoices.value.filter(i => i.id !== id)
    if (currentInvoice.value?.id === id) {
      currentInvoice.value = null
    }
  }

  // ============================================================================
  // Item Operations
  // ============================================================================

  async function addItem(invoiceId: string, data: InvoiceItemCreate): Promise<InvoiceItem> {
    const response = await api.post<ApiResponse<InvoiceItem>>(
      `/api/v1/billing/invoices/${invoiceId}/items`,
      data
    )

    // Refetch current invoice to get updated totals
    if (currentInvoice.value?.id === invoiceId) {
      await fetchInvoice(invoiceId)
    }

    return response.data
  }

  async function updateItem(
    invoiceId: string,
    itemId: string,
    data: InvoiceItemUpdate
  ): Promise<InvoiceItem> {
    const response = await api.put<ApiResponse<InvoiceItem>>(
      `/api/v1/billing/invoices/${invoiceId}/items/${itemId}`,
      data
    )

    // Refetch current invoice to get updated totals
    if (currentInvoice.value?.id === invoiceId) {
      await fetchInvoice(invoiceId)
    }

    return response.data
  }

  async function removeItem(invoiceId: string, itemId: string): Promise<void> {
    await api.del(`/api/v1/billing/invoices/${invoiceId}/items/${itemId}`)

    // Refetch current invoice to get updated totals
    if (currentInvoice.value?.id === invoiceId) {
      await fetchInvoice(invoiceId)
    }
  }

  // ============================================================================
  // Workflow Operations
  // ============================================================================

  async function issueInvoice(id: string, data: InvoiceIssueRequest = {}): Promise<Invoice> {
    const response = await api.post<ApiResponse<Invoice>>(
      `/api/v1/billing/invoices/${id}/issue`,
      data
    )

    // Update local state
    updateInvoiceStatus(id, response.data.status)

    return response.data
  }

  async function voidInvoice(id: string, reason?: string): Promise<Invoice> {
    const params = reason ? `?reason=${encodeURIComponent(reason)}` : ''
    const response = await api.post<ApiResponse<Invoice>>(
      `/api/v1/billing/invoices/${id}/void${params}`,
      {}
    )

    // Update local state
    updateInvoiceStatus(id, response.data.status)

    return response.data
  }

  async function sendInvoice(id: string, data: InvoiceSendRequest): Promise<Invoice> {
    const response = await api.post<ApiResponse<Invoice>>(
      `/api/v1/billing/invoices/${id}/send-email`,
      data
    )

    return response.data
  }

  async function createCreditNote(id: string, data: CreditNoteCreate): Promise<Invoice> {
    const response = await api.post<ApiResponse<Invoice>>(
      `/api/v1/billing/invoices/${id}/credit-note`,
      data
    )
    invoices.value = [toListItem(response.data), ...invoices.value]
    updateInvoiceStatus(id, 'cancelled')
    return response.data
  }

  // ============================================================================
  // Payment Operations
  // ============================================================================

  async function fetchPayments(invoiceId: string): Promise<InvoicePayment[]> {
    try {
      const response = await api.get<ApiResponse<InvoicePayment[]>>(
        `/api/v1/billing/invoices/${invoiceId}/payments`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch payments:', e)
      return []
    }
  }

  // POST /api/v1/billing/invoices/{id}/payments — the "factura + cobro"
  // orchestrator. Creates a Payment via the payments module under the
  // hood, links it to this invoice, and recomputes status. For pure
  // anticipos (no invoice), use /api/v1/payments directly.
  async function recordPayment(invoiceId: string, data: InvoicePaymentApply): Promise<InvoicePayment> {
    const response = await api.post<ApiResponse<InvoicePayment>>(
      `/api/v1/billing/invoices/${invoiceId}/payments`,
      data
    )

    // Refetch invoice to pick up the recomputed totals + status.
    if (currentInvoice.value?.id === invoiceId) {
      await fetchInvoice(invoiceId)
    }

    return response.data
  }

  // ============================================================================
  // History
  // ============================================================================

  async function fetchHistory(id: string): Promise<InvoiceHistoryEntry[]> {
    try {
      const response = await api.get<ApiResponse<InvoiceHistoryEntry[]>>(
        `/api/v1/billing/invoices/${id}/history`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch invoice history:', e)
      return []
    }
  }

  // ============================================================================
  // Settings
  // ============================================================================

  async function fetchSettings(): Promise<BillingSettings | null> {
    try {
      const response = await api.get<ApiResponse<BillingSettings>>(
        '/api/v1/billing/settings'
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch billing settings:', e)
      return null
    }
  }

  async function updateSettings(data: BillingSettingsUpdate): Promise<BillingSettings> {
    const response = await api.put<ApiResponse<BillingSettings>>(
      '/api/v1/billing/settings',
      data
    )
    return response.data
  }

  // ============================================================================
  // Patient Summary (used by patient billing tab)
  // ============================================================================

  async function fetchPatientSummary(patientId: string): Promise<PatientBillingSummary | null> {
    try {
      const response = await api.get<ApiResponse<PatientBillingSummary>>(
        `/api/v1/billing/patients/${patientId}/summary`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch patient billing summary:', e)
      return null
    }
  }

  // ============================================================================
  // PDF
  // ============================================================================

  async function downloadPDF(id: string, locale: string = 'es'): Promise<void> {
    const baseUrl = config.public.apiBaseUrl
    const token = auth.accessToken.value

    const response = await fetch(
      `${baseUrl}/api/v1/billing/invoices/${id}/pdf?locale=${locale}`,
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    )

    if (!response.ok) {
      // Raw fetch (blob response) bypasses useApi's error shaping — read
      // the server's message instead of a hardcoded English string.
      const body = await response.json().catch(() => null)
      throw new Error(body?.message || body?.detail || 'Failed to download PDF')
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url

    // Extract filename from Content-Disposition header or generate one
    const contentDisposition = response.headers.get('Content-Disposition')
    const filenameMatch = contentDisposition?.match(/filename="?(.+)"?/)
    link.download = filenameMatch?.[1] || `factura_${id}.pdf`

    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  function getPDFPreviewUrl(id: string, locale: string = 'es'): string {
    const baseUrl = config.public.apiBaseUrl
    return `${baseUrl}/api/v1/billing/invoices/${id}/pdf/preview?locale=${locale}`
  }

  // ============================================================================
  // Helpers
  // ============================================================================

  function getPaymentMethodLabel(method: string): string {
    return paymentMethodLabel(t, method)
  }

  function canEdit(invoice: Invoice | InvoiceDetail | InvoiceListItem): boolean {
    return invoice.status === 'draft'
  }

  function canIssue(invoice: Invoice | InvoiceDetail | InvoiceListItem): boolean {
    return invoice.status === 'draft'
  }

  function canRecordPayment(invoice: Invoice | InvoiceDetail | InvoiceListItem): boolean {
    return ['issued', 'partial'].includes(invoice.status)
  }

  function canVoid(invoice: Invoice | InvoiceDetail | InvoiceListItem): boolean {
    return invoice.status === 'draft'
  }

  function canCreateCreditNote(invoice: Invoice | InvoiceDetail | InvoiceListItem): boolean {
    // Can't create credit note for a credit note (check if it's already a rectificativa)
    const isCreditNote = 'credit_note_for_id' in invoice && invoice.credit_note_for_id != null
    return ['issued', 'partial', 'paid'].includes(invoice.status) && !isCreditNote
  }

  function canSend(invoice: Invoice | InvoiceDetail | InvoiceListItem): boolean {
    // Can only send issued, partial, or paid invoices (not drafts or voided)
    return ['issued', 'partial', 'paid'].includes(invoice.status)
  }

  const { format: formatCurrency } = useCurrency()

  // Internal helper to update status in local state
  function updateInvoiceStatus(id: string, status: InvoiceStatus): void {
    invoices.value = invoices.value.map(i =>
      i.id === id ? { ...i, status } : i
    )
    if (currentInvoice.value?.id === id) {
      currentInvoice.value = { ...currentInvoice.value, status }
    }
  }

  return {
    // State
    invoices: readonly(invoices),
    currentInvoice: readonly(currentInvoice),
    isLoading: readonly(isLoading),
    error: readonly(error),
    total: readonly(total),

    // Series
    fetchSeries,
    createSeries,
    updateSeries,
    resetSeriesCounter,

    // CRUD
    fetchInvoices,
    fetchInvoice,
    createInvoice,
    createFromBudget,
    updateInvoice,
    updateBillingParty,
    deleteInvoice,

    // Items
    addItem,
    updateItem,
    removeItem,

    // Workflow
    issueInvoice,
    voidInvoice,
    sendInvoice,
    createCreditNote,

    // Payments (links to ``InvoicePayment``). Refunds happen in the
    // payments module — not exposed from this composable.
    fetchPayments,
    recordPayment,

    // History
    fetchHistory,

    // Settings
    fetchSettings,
    updateSettings,

    // Patient Summary
    fetchPatientSummary,

    // PDF
    downloadPDF,
    getPDFPreviewUrl,

    // Helpers
    getPaymentMethodLabel,
    canEdit,
    canIssue,
    canRecordPayment,
    canVoid,
    canCreateCreditNote,
    canSend,
    formatCurrency
  }
}
