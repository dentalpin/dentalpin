/**
 * Composable for the payroll frontend (issue #391).
 *
 * Typed wrappers over `/api/v1/payroll/*` plus the clinic staff roster
 * (`/api/v1/auth/users`) used by the profile picker. Bank/tax values are
 * write-only: they are sent on create/replace and never read back —
 * responses expose `has_*` + `last_4` only.
 */

import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface PayrollProfile {
  id: string
  clinic_id: string
  user_id: string
  payment_type: 'monthly' | 'hourly'
  base_amount: string | null
  currency: string
  has_bank_account: boolean
  bank_last_4: string | null
  has_tax_id: boolean
  tax_last_4: string | null
  is_active: boolean
  country_code: string | null
  created_at: string
  updated_at: string
}

export interface PayrollProfileCreate {
  user_id: string
  payment_type?: 'monthly' | 'hourly'
  base_amount?: string | null
  currency?: string
  bank_account?: string | null
  tax_id?: string | null
  country_code?: string | null
}

export interface PayrollProfileUpdate {
  payment_type?: 'monthly' | 'hourly'
  base_amount?: string | null
  currency?: string
  bank_account?: string | null
  tax_id?: string | null
  is_active?: boolean
  country_code?: string | null
}

export type PayrollPeriodStatus = 'draft' | 'closed' | 'paid'

export interface PayrollPeriod {
  id: string
  clinic_id: string
  month: string
  status: PayrollPeriodStatus
  created_at: string
  updated_at: string
}

export interface PayrollEntry {
  id: string
  clinic_id: string
  period_id: string
  user_id: string
  gross: string
  deductions: string
  net: string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PayrollEntryCreate {
  period_id: string
  user_id: string
  gross: string
  deductions: string
  net: string
  notes?: string | null
}

export interface PayrollEntryUpdate {
  gross?: string
  deductions?: string
  net?: string
  notes?: string | null
}

export interface PeriodReport {
  period_id: string
  month: string
  status: string
  currency: string
  entry_count: number
  total_gross: string
  total_deductions: string
  total_net: string
}

export interface AnnualReport {
  year: string
  currency: string
  period_count: number
  entry_count: number
  total_gross: string
  total_deductions: string
  total_net: string
}

export interface StaffUser {
  id: string
  email: string
  first_name: string
  last_name: string
  role: string
}

export function usePayroll() {
  const api = useApi()

  async function listProfiles(page = 1, pageSize = 20) {
    return api.get<PaginatedResponse<PayrollProfile>>('/api/v1/payroll/profiles', {
      query: { page, page_size: pageSize }
    })
  }

  async function createProfile(payload: PayrollProfileCreate) {
    return api.post<ApiResponse<PayrollProfile>>('/api/v1/payroll/profiles', payload)
  }

  async function updateProfile(id: string, payload: PayrollProfileUpdate) {
    return api.patch<ApiResponse<PayrollProfile>>(`/api/v1/payroll/profiles/${id}`, payload)
  }

  async function listPeriods(page = 1, pageSize = 20) {
    return api.get<PaginatedResponse<PayrollPeriod>>('/api/v1/payroll/periods', {
      query: { page, page_size: pageSize }
    })
  }

  async function createPeriod(month: string) {
    return api.post<ApiResponse<PayrollPeriod>>('/api/v1/payroll/periods', { month })
  }

  async function transitionPeriod(id: string, status: PayrollPeriodStatus) {
    return api.post<ApiResponse<PayrollPeriod>>(`/api/v1/payroll/periods/${id}/status`, {
      status
    })
  }

  async function listEntries(periodId: string, page = 1, pageSize = 50) {
    return api.get<PaginatedResponse<PayrollEntry>>(
      `/api/v1/payroll/periods/${periodId}/entries`,
      { query: { page, page_size: pageSize } }
    )
  }

  async function createEntry(payload: PayrollEntryCreate) {
    return api.post<ApiResponse<PayrollEntry>>('/api/v1/payroll/entries', payload)
  }

  async function updateEntry(id: string, payload: PayrollEntryUpdate) {
    return api.patch<ApiResponse<PayrollEntry>>(`/api/v1/payroll/entries/${id}`, payload)
  }

  async function deleteEntry(id: string) {
    await api.del<null>(`/api/v1/payroll/entries/${id}`, { errorToast: false })
  }

  async function deletePeriod(id: string) {
    await api.del<null>(`/api/v1/payroll/periods/${id}`, { errorToast: false })
  }

  async function monthlyReport(month: string) {
    return api.get<ApiResponse<PeriodReport>>('/api/v1/payroll/reports/monthly', { query: { month } })
  }

  async function annualReport(year: string) {
    return api.get<ApiResponse<AnnualReport>>('/api/v1/payroll/reports/annual', { query: { year } })
  }

  async function listStaff() {
    return api.get<PaginatedResponse<StaffUser>>('/api/v1/auth/users', {
      query: { page: 1, page_size: 200 }
    })
  }

  return {
    listProfiles,
    createProfile,
    updateProfile,
    listPeriods,
    createPeriod,
    transitionPeriod,
    listEntries,
    createEntry,
    updateEntry,
    deleteEntry,
    deletePeriod,
    monthlyReport,
    annualReport,
    listStaff
  }
}
