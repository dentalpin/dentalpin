import type {
  ApiResponse,
  BillingSummary,
  OverdueInvoice,
  PaymentMethodSummary,
  ProfessionalBillingSummary,
  VatSummaryItem,
  NumberingGap
} from '~~/app/types'
import { paymentMethodLabel } from '~~/app/utils/paymentMethod'

// Budget report types
export interface BudgetSummary {
  period_start: string
  period_end: string
  total_created: number
  total_amount: string
  accepted_count: number
  accepted_amount: string
  rejected_count: number
  pending_count: number
  completed_count: number
  completed_amount: string
  acceptance_rate: number
  average_value: string
}

export interface BudgetByProfessional {
  professional_id: string | null
  professional_name: string
  budget_count: number
  total_amount: string
  accepted_count: number
  acceptance_rate: number
}

export interface BudgetByTreatment {
  catalog_item_id: string | null
  treatment_name: string
  occurrence_count: number
  total_quantity: number
  total_amount: string
}

export interface BudgetByStatus {
  status: string
  count: number
  total_amount: string
}

// Scheduling report types
export interface SchedulingSummary {
  period_start: string
  period_end: string
  total_appointments: number
  completed: number
  cancelled: number
  no_show: number
  scheduled: number
  confirmed: number
  checked_in: number
  in_treatment: number
  completion_rate: number
  cancellation_rate: number
  no_show_rate: number
}

// Appointment lifecycle analytics (issue #49)
export interface AnalyticsBucket {
  label: string
  count: number
}

export interface WaitingTimeStats {
  period_start: string
  period_end: string
  sample_size: number
  avg_minutes: number | null
  median_minutes: number | null
  p90_minutes: number | null
  distribution: AnalyticsBucket[]
}

export interface PunctualityStats {
  period_start: string
  period_end: string
  sample_size: number
  avg_delta_minutes: number | null
  median_delta_minutes: number | null
  on_time_pct: number | null
  distribution: AnalyticsBucket[]
}

export interface DurationVarianceStats {
  period_start: string
  period_end: string
  sample_size: number
  avg_overrun_pct: number | null
  avg_delta_minutes: number | null
  overrun_count: number
  under_count: number
}

export interface AppointmentFunnel {
  period_start: string
  period_end: string
  total: number
  counts_by_status: Record<string, number>
  completion_rate: number | null
  no_show_rate: number | null
  cancellation_rate: number | null
}

export interface FirstVisitsSummary {
  period_start: string
  period_end: string
  new_patients: number
  total_appointments: number
  first_visit_rate: number
}

export interface HoursByProfessional {
  professional_id: string | null
  professional_name: string
  appointment_count: number
  completed_count: number
  cancelled_count: number
  no_show_count: number
  total_minutes: number
  total_hours: number
}

export interface CabinetUtilization {
  cabinet: string
  appointment_count: number
  completed_count: number
  total_minutes: number
  total_hours: number
}

export interface DayOfWeekStats {
  day_of_week: number
  day_name: string
  appointment_count: number
  completed_count: number
  cancelled_count: number
  no_show_count: number
}

// Payments report types (mirror backend/app/modules/payments/schemas.py).
export interface PaymentsSummaryReport {
  period_start: string
  period_end: string
  currency: string
  total_collected: string
  total_refunded: string
  net_collected: string
  patient_credit_total: string
  clinic_receivable_total: string
  refund_ratio: number
  payment_count: number
  refund_count: number
}

export interface PaymentsMethodBreakdown {
  method: string
  total: string
  count: number
}

export interface PaymentsProfessionalBreakdown {
  professional_id: string | null
  professional_name: string | null
  total_earned: string
  count: number
}

export interface PaymentsAgingBucket {
  label: string
  total: string
  patient_count: number
}

export interface PaymentsAgingBuckets {
  currency: string
  buckets: PaymentsAgingBucket[]
}

export interface PaymentsTrendsPoint {
  bucket_start: string
  collected: string
  refunded: string
  net: string
}

export interface PaymentsTrends {
  currency: string
  granularity: 'day' | 'week' | 'month' | 'year'
  points: PaymentsTrendsPoint[]
}

export function useReports() {
  const api = useApi()
  const { t } = useI18n()

  // Shared "a report fetch failed" flag (issue #101). The fetchers keep
  // their catch-and-default contract (null / []), so callers alone cannot
  // distinguish a failed read from a legitimately empty period. Pages call
  // `resetFetchFailed()` before a load batch and render a visible error
  // state (instead of 0 € / empty charts) when `fetchFailed` is set after.
  const fetchFailed = useState<boolean>('reports:fetch-failed', () => false)

  function resetFetchFailed() {
    fetchFailed.value = false
  }

  // ============================================================================
  // Billing Reports
  // ============================================================================

  async function fetchBillingSummary(
    dateFrom: string,
    dateTo: string
  ): Promise<BillingSummary | null> {
    try {
      const response = await api.get<ApiResponse<BillingSummary>>(
        `/api/v1/reports/billing/summary?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch billing summary:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchOverdueInvoices(): Promise<OverdueInvoice[]> {
    try {
      const response = await api.get<ApiResponse<OverdueInvoice[]>>(
        '/api/v1/reports/billing/overdue'
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch overdue invoices:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchByPaymentMethod(
    dateFrom: string,
    dateTo: string
  ): Promise<PaymentMethodSummary[]> {
    try {
      const response = await api.get<ApiResponse<PaymentMethodSummary[]>>(
        `/api/v1/reports/billing/by-payment-method?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch payments by method:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchBillingByProfessional(
    dateFrom: string,
    dateTo: string
  ): Promise<ProfessionalBillingSummary[]> {
    try {
      const response = await api.get<ApiResponse<ProfessionalBillingSummary[]>>(
        `/api/v1/reports/billing/by-professional?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch billing by professional:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchVatSummary(
    dateFrom: string,
    dateTo: string
  ): Promise<VatSummaryItem[]> {
    try {
      const response = await api.get<ApiResponse<VatSummaryItem[]>>(
        `/api/v1/reports/billing/vat-summary?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch VAT summary:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchNumberingGaps(): Promise<NumberingGap[]> {
    try {
      const response = await api.get<ApiResponse<NumberingGap[]>>(
        '/api/v1/reports/billing/gaps'
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch numbering gaps:', e)
      fetchFailed.value = true
      return []
    }
  }

  // ============================================================================
  // Budget Reports
  // ============================================================================

  async function fetchBudgetSummary(
    dateFrom: string,
    dateTo: string
  ): Promise<BudgetSummary | null> {
    try {
      const response = await api.get<ApiResponse<BudgetSummary>>(
        `/api/v1/reports/budgets/summary?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch budget summary:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchBudgetsByProfessional(
    dateFrom: string,
    dateTo: string
  ): Promise<BudgetByProfessional[]> {
    try {
      const response = await api.get<ApiResponse<BudgetByProfessional[]>>(
        `/api/v1/reports/budgets/by-professional?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch budgets by professional:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchBudgetsByTreatment(
    dateFrom: string,
    dateTo: string,
    limit: number = 10
  ): Promise<BudgetByTreatment[]> {
    try {
      const response = await api.get<ApiResponse<BudgetByTreatment[]>>(
        `/api/v1/reports/budgets/by-treatment?date_from=${dateFrom}&date_to=${dateTo}&limit=${limit}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch budgets by treatment:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchBudgetsByStatus(
    dateFrom: string,
    dateTo: string
  ): Promise<BudgetByStatus[]> {
    try {
      const response = await api.get<ApiResponse<BudgetByStatus[]>>(
        `/api/v1/reports/budgets/by-status?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch budgets by status:', e)
      fetchFailed.value = true
      return []
    }
  }

  // ============================================================================
  // Scheduling Reports
  // ============================================================================

  async function fetchSchedulingSummary(
    dateFrom: string,
    dateTo: string
  ): Promise<SchedulingSummary | null> {
    try {
      const response = await api.get<ApiResponse<SchedulingSummary>>(
        `/api/v1/reports/scheduling/summary?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch scheduling summary:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchFirstVisits(
    dateFrom: string,
    dateTo: string
  ): Promise<FirstVisitsSummary | null> {
    try {
      const response = await api.get<ApiResponse<FirstVisitsSummary>>(
        `/api/v1/reports/scheduling/first-visits?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch first visits:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchHoursByProfessional(
    dateFrom: string,
    dateTo: string
  ): Promise<HoursByProfessional[]> {
    try {
      const response = await api.get<ApiResponse<HoursByProfessional[]>>(
        `/api/v1/reports/scheduling/by-professional?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch hours by professional:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchCabinetUtilization(
    dateFrom: string,
    dateTo: string
  ): Promise<CabinetUtilization[]> {
    try {
      const response = await api.get<ApiResponse<CabinetUtilization[]>>(
        `/api/v1/reports/scheduling/by-cabinet?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch cabinet utilization:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchByDayOfWeek(
    dateFrom: string,
    dateTo: string
  ): Promise<DayOfWeekStats[]> {
    try {
      const response = await api.get<ApiResponse<DayOfWeekStats[]>>(
        `/api/v1/reports/scheduling/by-day-of-week?date_from=${dateFrom}&date_to=${dateTo}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch by day of week:', e)
      fetchFailed.value = true
      return []
    }
  }

  function _buildAnalyticsQuery(
    dateFrom: string,
    dateTo: string,
    filters?: { cabinetId?: string | null, professionalId?: string | null }
  ): string {
    const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
    if (filters?.cabinetId) params.set('cabinet_id', filters.cabinetId)
    if (filters?.professionalId) params.set('professional_id', filters.professionalId)
    return params.toString()
  }

  async function fetchWaitingTimes(
    dateFrom: string,
    dateTo: string,
    filters?: { cabinetId?: string | null, professionalId?: string | null }
  ): Promise<WaitingTimeStats | null> {
    try {
      const response = await api.get<ApiResponse<WaitingTimeStats>>(
        `/api/v1/reports/scheduling/waiting-times?${_buildAnalyticsQuery(dateFrom, dateTo, filters)}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch waiting times:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchPunctuality(
    dateFrom: string,
    dateTo: string,
    filters?: { cabinetId?: string | null, professionalId?: string | null }
  ): Promise<PunctualityStats | null> {
    try {
      const response = await api.get<ApiResponse<PunctualityStats>>(
        `/api/v1/reports/scheduling/punctuality?${_buildAnalyticsQuery(dateFrom, dateTo, filters)}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch punctuality:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchDurationVariance(
    dateFrom: string,
    dateTo: string,
    filters?: { cabinetId?: string | null, professionalId?: string | null }
  ): Promise<DurationVarianceStats | null> {
    try {
      const response = await api.get<ApiResponse<DurationVarianceStats>>(
        `/api/v1/reports/scheduling/duration-variance?${_buildAnalyticsQuery(dateFrom, dateTo, filters)}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch duration variance:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchFunnel(
    dateFrom: string,
    dateTo: string,
    filters?: { cabinetId?: string | null, professionalId?: string | null }
  ): Promise<AppointmentFunnel | null> {
    try {
      const response = await api.get<ApiResponse<AppointmentFunnel>>(
        `/api/v1/reports/scheduling/funnel?${_buildAnalyticsQuery(dateFrom, dateTo, filters)}`
      )
      return response.data
    } catch (e) {
      console.error('Failed to fetch funnel:', e)
      fetchFailed.value = true
      return null
    }
  }

  // ============================================================================
  // Payments Reports (consumed from the payments module's public endpoints).
  // No service-level imports — only HTTP. Permissions enforced server-side
  // via ``payments.reports.read``.
  // ============================================================================

  async function fetchPaymentsSummary(
    dateFrom: string,
    dateTo: string,
    options?: { signal?: AbortSignal }
  ): Promise<PaymentsSummaryReport | null> {
    try {
      const response = await api.get<ApiResponse<PaymentsSummaryReport>>(
        `/api/v1/payments/reports/summary?date_from=${dateFrom}&date_to=${dateTo}`,
        { signal: options?.signal }
      )
      return response.data
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return null
      console.error('Failed to fetch payments summary:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchPaymentsTrends(
    dateFrom: string,
    dateTo: string,
    granularity: 'day' | 'week' | 'month' | 'year' = 'day',
    options?: { signal?: AbortSignal }
  ): Promise<PaymentsTrends | null> {
    try {
      const response = await api.get<ApiResponse<PaymentsTrends>>(
        `/api/v1/payments/reports/trends?date_from=${dateFrom}&date_to=${dateTo}&granularity=${granularity}`,
        { signal: options?.signal }
      )
      return response.data
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return null
      console.error('Failed to fetch payments trends:', e)
      fetchFailed.value = true
      return null
    }
  }

  async function fetchPaymentsByMethod(
    dateFrom: string,
    dateTo: string,
    options?: { signal?: AbortSignal }
  ): Promise<PaymentsMethodBreakdown[]> {
    try {
      const response = await api.get<ApiResponse<PaymentsMethodBreakdown[]>>(
        `/api/v1/payments/reports/by-method?date_from=${dateFrom}&date_to=${dateTo}`,
        { signal: options?.signal }
      )
      return response.data
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return []
      console.error('Failed to fetch payments by method:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchPaymentsByProfessional(
    dateFrom: string,
    dateTo: string,
    options?: { signal?: AbortSignal }
  ): Promise<PaymentsProfessionalBreakdown[]> {
    try {
      const response = await api.get<ApiResponse<PaymentsProfessionalBreakdown[]>>(
        `/api/v1/payments/reports/by-professional?date_from=${dateFrom}&date_to=${dateTo}`,
        { signal: options?.signal }
      )
      return response.data
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return []
      console.error('Failed to fetch payments by professional:', e)
      fetchFailed.value = true
      return []
    }
  }

  async function fetchAgingReceivables(
    options?: { signal?: AbortSignal }
  ): Promise<PaymentsAgingBuckets | null> {
    try {
      const response = await api.get<ApiResponse<PaymentsAgingBuckets>>(
        '/api/v1/payments/reports/aging-receivables',
        { signal: options?.signal }
      )
      return response.data
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return null
      console.error('Failed to fetch aging receivables:', e)
      fetchFailed.value = true
      return null
    }
  }

  // ============================================================================
  // Helpers
  // ============================================================================

  // Currency follows clinic.currency; locale follows the user's UI.
  const { format } = useCurrency()
  function formatCurrency(value: string | number): string {
    const num = typeof value === 'string' ? parseFloat(value) : value
    return format(num)
  }

  function getBudgetStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      draft: t('budget.status.draft'),
      accepted: t('budget.status.accepted'),
      rejected: t('budget.status.rejected'),
      completed: t('budget.status.completed'),
      expired: t('budget.status.expired'),
      cancelled: t('budget.status.cancelled')
    }
    return labels[status] || status
  }

  function getBudgetStatusColor(status: string): string {
    const colors: Record<string, string> = {
      draft: 'neutral',
      accepted: 'success',
      rejected: 'error',
      completed: 'info',
      expired: 'warning',
      cancelled: 'neutral'
    }
    return colors[status] || 'neutral'
  }

  function getDayOfWeekLabel(dayName: string): string {
    const labels: Record<string, string> = {
      sunday: t('common.days.sunday'),
      monday: t('common.days.monday'),
      tuesday: t('common.days.tuesday'),
      wednesday: t('common.days.wednesday'),
      thursday: t('common.days.thursday'),
      friday: t('common.days.friday'),
      saturday: t('common.days.saturday')
    }
    return labels[dayName] || dayName
  }

  function formatHours(minutes: number): string {
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    if (hours === 0) return `${mins}m`
    if (mins === 0) return `${hours}h`
    return `${hours}h ${mins}m`
  }

  function getPaymentMethodLabel(method: string): string {
    return paymentMethodLabel(t, method)
  }

  return {
    // Error state — set by any failed fetch, reset by pages before a batch.
    fetchFailed: readonly(fetchFailed),
    resetFetchFailed,
    // Billing
    fetchBillingSummary,
    fetchOverdueInvoices,
    fetchByPaymentMethod,
    fetchBillingByProfessional,
    fetchVatSummary,
    fetchNumberingGaps,
    // Budget
    fetchBudgetSummary,
    fetchBudgetsByProfessional,
    fetchBudgetsByTreatment,
    fetchBudgetsByStatus,
    // Scheduling
    fetchSchedulingSummary,
    fetchFirstVisits,
    fetchHoursByProfessional,
    fetchCabinetUtilization,
    fetchByDayOfWeek,
    fetchWaitingTimes,
    fetchPunctuality,
    fetchDurationVariance,
    fetchFunnel,
    // Payments
    fetchPaymentsSummary,
    fetchPaymentsTrends,
    fetchPaymentsByMethod,
    fetchPaymentsByProfessional,
    fetchAgingReceivables,
    // Helpers
    formatCurrency,
    getBudgetStatusLabel,
    getBudgetStatusColor,
    getDayOfWeekLabel,
    formatHours,
    getPaymentMethodLabel
  }
}
