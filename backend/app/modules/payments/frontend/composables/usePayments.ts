import type {
  ApiResponse,
  PaginatedResponse,
  PatientLedger,
  PaymentRecord,
  PaymentRecordCreate,
  PaymentRefund,
  PaymentRefundCreate,
  PaymentReallocate,
  PaymentsSummary,
  PaymentsTrends,
  MethodBreakdown,
  ProfessionalBreakdown,
  AgingBuckets,
  RefundsReport,
  PaymentAllocation
} from '~~/app/types'

export interface PaymentListParams {
  page?: number
  page_size?: number
  date_from?: string
  date_to?: string
  method?: string
  patient_id?: string
  has_refunds?: boolean
  has_unallocated?: boolean
  amount_min?: number
  amount_max?: number
  sort?: string
}

// Cross-module summary shapes. The hosting modules (/patients,
// /budgets) consume these via slots — they never import the payments
// composable directly. See docs/technical/payments/cross-module-summaries.md.
export interface BudgetPaymentSummary {
  collected: string
  pending: string
  payment_status: 'unpaid' | 'partial' | 'paid'
}

export interface PatientPaymentSummary {
  total_paid: string
  debt: string
  on_account_balance: string
}

export interface FilterIdsResult {
  budget_ids?: string[]
  patient_ids?: string[]
  truncated: boolean
}

export function usePayments() {
  const api = useApi()

  const payments = useState<PaymentRecord[]>('payments:list', () => [])
  const total = useState<number>('payments:total', () => 0)
  const isLoading = useState<boolean>('payments:loading', () => false)
  const error = useState<string | null>('payments:error', () => null)

  async function list(params: PaymentListParams = {}): Promise<PaymentRecord[]> {
    isLoading.value = true
    error.value = null
    try {
      const search = new URLSearchParams()
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') search.set(k, String(v))
      })
      const qs = search.toString() ? `?${search.toString()}` : ''
      const resp = await api.get<PaginatedResponse<PaymentRecord>>(`/api/v1/payments${qs}`)
      payments.value = resp.data
      total.value = resp.total
      return resp.data
    } catch (e) {
      error.value = (e as Error).message
      return []
    } finally {
      isLoading.value = false
    }
  }

  async function get(id: string): Promise<PaymentRecord | null> {
    try {
      const resp = await api.get<ApiResponse<PaymentRecord>>(`/api/v1/payments/${id}`)
      return resp.data
    } catch (e) {
      error.value = (e as Error).message
      return null
    }
  }

  async function create(payload: PaymentRecordCreate): Promise<PaymentRecord | null> {
    try {
      const resp = await api.post<ApiResponse<PaymentRecord>>('/api/v1/payments', payload)
      return resp.data
    } catch (e) {
      error.value = (e as Error).message
      return null
    }
  }

  async function reallocate(id: string, payload: PaymentReallocate): Promise<PaymentRecord | null> {
    try {
      const resp = await api.post<ApiResponse<PaymentRecord>>(`/api/v1/payments/${id}/reallocate`, payload)
      return resp.data
    } catch (e) {
      error.value = (e as Error).message
      return null
    }
  }

  async function refund(id: string, payload: PaymentRefundCreate): Promise<PaymentRefund | null> {
    try {
      const resp = await api.post<ApiResponse<PaymentRefund>>(`/api/v1/payments/${id}/refunds`, payload)
      return resp.data
    } catch (e) {
      error.value = (e as Error).message
      return null
    }
  }

  async function listRefunds(id: string): Promise<PaymentRefund[]> {
    try {
      const resp = await api.get<ApiResponse<PaymentRefund[]>>(`/api/v1/payments/${id}/refunds`)
      return resp.data
    } catch {
      return []
    }
  }

  async function fetchPatientLedger(patientId: string): Promise<PatientLedger | null> {
    try {
      const resp = await api.get<ApiResponse<PatientLedger>>(`/api/v1/payments/patients/${patientId}/ledger`)
      return resp.data
    } catch {
      return null
    }
  }

  interface PendingCharge {
    entry_id: string
    treatment_id: string
    session_id: string | null
    description: string | null
    amount: string
    occurred_at: string
  }

  async function fetchPendingCharges(patientId: string): Promise<PendingCharge[]> {
    try {
      const resp = await api.get<ApiResponse<PendingCharge[]>>(
        `/api/v1/payments/patients/${patientId}/pending-charges`
      )
      return resp.data
    } catch {
      return []
    }
  }

  async function fetchBudgetAllocations(budgetId: string): Promise<PaymentAllocation[]> {
    try {
      const resp = await api.get<ApiResponse<PaymentAllocation[]>>(`/api/v1/payments/budgets/${budgetId}/allocations`)
      return resp.data
    } catch {
      return []
    }
  }

  // --- Cross-module bulk reads -------------------------------------------
  //
  // Used by /patients and /budgets list pages via slot fillers. The
  // hosting pages call these from their page-level fetcher; the slot
  // component just renders the value it receives via ctx.

  async function fetchBudgetSummaries(ids: string[]): Promise<Record<string, BudgetPaymentSummary>> {
    if (!ids.length) return {}
    try {
      const resp = await api.post<ApiResponse<{ summaries: Record<string, BudgetPaymentSummary> }>>(
        '/api/v1/payments/summary/by-budgets',
        { budget_ids: ids }
      )
      return resp.data.summaries
    } catch {
      return {}
    }
  }

  async function fetchPatientDebtSummaries(ids: string[]): Promise<Record<string, PatientPaymentSummary>> {
    if (!ids.length) return {}
    try {
      const resp = await api.post<ApiResponse<{ summaries: Record<string, PatientPaymentSummary> }>>(
        '/api/v1/payments/summary/by-patients',
        { patient_ids: ids }
      )
      return resp.data.summaries
    } catch {
      return {}
    }
  }

  async function fetchBudgetIdsByPaymentStatus(
    statuses: Array<'unpaid' | 'partial' | 'paid'>,
    opts: { patient_id?: string, assigned_professional_id?: string } = {}
  ): Promise<FilterIdsResult> {
    if (!statuses.length) return { budget_ids: [], truncated: false }
    const search = new URLSearchParams()
    for (const s of statuses) search.append('status', s)
    if (opts.patient_id) search.set('patient_id', opts.patient_id)
    if (opts.assigned_professional_id) {
      search.set('assigned_professional_id', opts.assigned_professional_id)
    }
    try {
      const resp = await api.get<ApiResponse<FilterIdsResult>>(
        `/api/v1/payments/filters/budgets-by-status?${search.toString()}`
      )
      return resp.data
    } catch {
      return { budget_ids: [], truncated: false }
    }
  }

  async function fetchPatientIdsWithDebt(minDebt: number = 0.01): Promise<FilterIdsResult> {
    try {
      const resp = await api.get<ApiResponse<FilterIdsResult>>(
        `/api/v1/payments/filters/patients-with-debt?min_debt=${minDebt}`
      )
      return resp.data
    } catch {
      return { patient_ids: [], truncated: false }
    }
  }

  return {
    payments,
    total,
    isLoading,
    error,
    list,
    get,
    create,
    reallocate,
    refund,
    listRefunds,
    fetchPatientLedger,
    fetchPendingCharges,
    fetchBudgetAllocations,
    fetchBudgetSummaries,
    fetchPatientDebtSummaries,
    fetchBudgetIdsByPaymentStatus,
    fetchPatientIdsWithDebt
  }
}

export function usePaymentReports() {
  const api = useApi()

  // Shared "a report fetch failed" flag (issue #101). The fetchers keep
  // their catch-and-default contract (null / []), so callers alone cannot
  // distinguish a failed read from a legitimately empty period. The reports
  // page calls `resetFetchFailed()` before a load batch and renders a
  // visible error state (instead of 0 € / empty charts) when it is set.
  const fetchFailed = useState<boolean>('payments:reports-fetch-failed', () => false)

  function resetFetchFailed() {
    fetchFailed.value = false
  }

  async function summary(date_from: string, date_to: string): Promise<PaymentsSummary | null> {
    try {
      const resp = await api.get<ApiResponse<PaymentsSummary>>(
        `/api/v1/payments/reports/summary?date_from=${date_from}&date_to=${date_to}`
      )
      return resp.data
    } catch {
      fetchFailed.value = true
      return null
    }
  }

  async function byMethod(date_from: string, date_to: string): Promise<MethodBreakdown[]> {
    try {
      const resp = await api.get<ApiResponse<MethodBreakdown[]>>(
        `/api/v1/payments/reports/by-method?date_from=${date_from}&date_to=${date_to}`
      )
      return resp.data
    } catch {
      fetchFailed.value = true
      return []
    }
  }

  async function byProfessional(date_from: string, date_to: string): Promise<ProfessionalBreakdown[]> {
    try {
      const resp = await api.get<ApiResponse<ProfessionalBreakdown[]>>(
        `/api/v1/payments/reports/by-professional?date_from=${date_from}&date_to=${date_to}`
      )
      return resp.data
    } catch {
      fetchFailed.value = true
      return []
    }
  }

  async function aging(): Promise<AgingBuckets | null> {
    try {
      const resp = await api.get<ApiResponse<AgingBuckets>>('/api/v1/payments/reports/aging-receivables')
      return resp.data
    } catch {
      fetchFailed.value = true
      return null
    }
  }

  async function refunds(date_from: string, date_to: string): Promise<RefundsReport | null> {
    try {
      const resp = await api.get<ApiResponse<RefundsReport>>(
        `/api/v1/payments/reports/refunds?date_from=${date_from}&date_to=${date_to}`
      )
      return resp.data
    } catch {
      fetchFailed.value = true
      return null
    }
  }

  async function trends(
    date_from: string,
    date_to: string,
    granularity: 'day' | 'week' | 'month' | 'year' = 'month'
  ): Promise<PaymentsTrends | null> {
    try {
      const resp = await api.get<ApiResponse<PaymentsTrends>>(
        `/api/v1/payments/reports/trends?date_from=${date_from}&date_to=${date_to}&granularity=${granularity}`
      )
      return resp.data
    } catch {
      fetchFailed.value = true
      return null
    }
  }

  return {
    summary,
    byMethod,
    byProfessional,
    aging,
    refunds,
    trends,
    fetchFailed: readonly(fetchFailed),
    resetFetchFailed
  }
}
