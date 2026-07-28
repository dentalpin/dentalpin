// Matches the confirmed real useApi() shape (from useMedications.ts /
// the pasted useApi.ts): api.get<T>(path, { query }), full /api/v1/...
// paths, ApiResponse<T>/PaginatedResponse<T> envelopes.

import type { ApiResponse, PaginatedResponse } from '~/types'

export interface StaffPayrollProfile {
  id: string
  clinic_id: string
  user_id: string
  hourly_rate: number | null
  base_salary: number | null
  tax_regime: string | null
  has_bank_account: boolean
  has_tax_id: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface StaffPayrollProfileInput {
  user_id?: string // only on create
  hourly_rate?: number | null
  base_salary?: number | null
  tax_regime?: string | null
  bank_account?: string | null // plaintext, write-only — encrypted server-side
  tax_id?: string | null // plaintext, write-only — encrypted server-side
  is_active?: boolean
}

export interface PayrollPeriod {
  id: string
  clinic_id: string
  month: number
  year: number
  status: 'draft' | 'processed' | 'paid'
  processed_at: string | null
  created_at: string
  updated_at: string
}

export interface PayrollEntry {
  id: string
  clinic_id: string
  period_id: string
  staff_payroll_profile_id: string
  gross_pay: number
  deductions: number
  net_pay: number
  details: Record<string, unknown> | null
  is_paid: boolean
  paid_at: string | null
  created_at: string
  updated_at: string
}

export interface MonthlySummary {
  month: number
  year: number
  status: string
  total_gross: number
  total_deductions: number
  total_net: number
  employee_count: number
}

export interface AnnualSummary {
  year: number
  total_gross: number
  total_deductions: number
  total_net: number
  months_processed: number
}

export const usePayroll = () => {
  const api = useApi()

  const listStaff = () => api.get<PaginatedResponse<StaffPayrollProfile>>('/api/v1/payroll/staff')
  const createStaff = async (data: StaffPayrollProfileInput) => {
    const res = await api.post<ApiResponse<StaffPayrollProfile>>('/api/v1/payroll/staff', data)
    return res.data
  }
  const updateStaff = async (id: string, data: StaffPayrollProfileInput) => {
    const res = await api.put<ApiResponse<StaffPayrollProfile>>(`/api/v1/payroll/staff/${id}`, data)
    return res.data
  }

  const listPeriods = () => api.get<PaginatedResponse<PayrollPeriod>>('/api/v1/payroll/periods')
  const createPeriod = async (month: number, year: number) => {
    const res = await api.post<ApiResponse<PayrollPeriod>>('/api/v1/payroll/periods', { month, year })
    return res.data
  }
  const generateEntries = async (periodId: string) => {
    const res = await api.post<ApiResponse<PayrollEntry[]>>(`/api/v1/payroll/periods/${periodId}/generate`)
    return res.data
  }
  const processPeriod = async (periodId: string) => {
    const res = await api.post<ApiResponse<PayrollPeriod>>(`/api/v1/payroll/periods/${periodId}/process`)
    return res.data
  }
  const markPeriodPaid = async (periodId: string) => {
    const res = await api.post<ApiResponse<PayrollPeriod>>(`/api/v1/payroll/periods/${periodId}/mark-paid`)
    return res.data
  }
  const listPeriodEntries = async (periodId: string) => {
    const res = await api.get<ApiResponse<PayrollEntry[]>>(`/api/v1/payroll/periods/${periodId}/entries`)
    return res.data
  }

  const updateEntry = async (
    entryId: string,
    data: { staff_payroll_profile_id: string; gross_pay: number; deductions?: number; details?: Record<string, unknown> | null }
  ) => {
    const res = await api.put<ApiResponse<PayrollEntry>>(`/api/v1/payroll/entries/${entryId}`, data)
    return res.data
  }
  const markEntryPaid = async (entryId: string) => {
    const res = await api.post<ApiResponse<PayrollEntry>>(`/api/v1/payroll/entries/${entryId}/mark-paid`)
    return res.data
  }

  const monthlySummary = async (month: number, year: number) => {
    const res = await api.get<ApiResponse<MonthlySummary>>('/api/v1/payroll/reports/monthly', {
      query: { month, year }
    })
    return res.data
  }
  const annualSummary = async (year: number) => {
    const res = await api.get<ApiResponse<AnnualSummary>>('/api/v1/payroll/reports/annual', {
      query: { year }
    })
    return res.data
  }

  return {
    listStaff,
    createStaff,
    updateStaff,
    listPeriods,
    createPeriod,
    generateEntries,
    processPeriod,
    markPeriodPaid,
    listPeriodEntries,
    updateEntry,
    markEntryPaid,
    monthlySummary,
    annualSummary
  }
}
