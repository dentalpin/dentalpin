export type ExpenseCategory =
  | 'rent'
  | 'utilities'
  | 'salaries'
  | 'supplies'
  | 'equipment'
  | 'insurance'
  | 'maintenance'
  | 'other'

export interface Expense {
  id: string
  clinic_id: string
  category: ExpenseCategory
  amount: string
  expense_date: string
  description?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface ExpenseCreatePayload {
  category: ExpenseCategory
  amount: number
  expense_date: string
  description?: string | null
}

export interface ExpenseMonthlyTotal {
  category: ExpenseCategory
  total: string
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface ExpenseListFilters {
  category?: ExpenseCategory
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export function useExpenses() {
  const api = useApi()

  async function list(filters: ExpenseListFilters = {}): Promise<ApiPaged<Expense>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/expenses/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<Expense>>(url)
  }

  async function create(payload: ExpenseCreatePayload): Promise<ApiOk<Expense>> {
    return await api.post<ApiOk<Expense>>('/api/v1/expenses/', payload)
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/expenses/${id}`)
  }

  async function monthlyTotals(year: number, month: number): Promise<ApiOk<ExpenseMonthlyTotal[]>> {
    return await api.get<ApiOk<ExpenseMonthlyTotal[]>>(
      `/api/v1/expenses/monthly-totals?year=${year}&month=${month}`
    )
  }

  return { list, create, remove, monthlyTotals }
}
