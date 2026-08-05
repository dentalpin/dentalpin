export type WorkType =
  | 'crown'
  | 'bridge'
  | 'denture'
  | 'implant'
  | 'veneer'
  | 'orthodontic'
  | 'repair'
  | 'other'

export type OrderStatus = 'sent' | 'in_progress' | 'ready' | 'received' | 'cancelled'

export type ImpressionType = 'alginate' | 'pvs_silicone' | 'digital_scan' | 'other'

export const VITA_CLASSICAL_SHADES = [
  'A1', 'A2', 'A3', 'A3.5', 'A4',
  'B1', 'B2', 'B3', 'B4',
  'C1', 'C2', 'C3', 'C4',
  'D2', 'D3', 'D4'
] as const
export type Shade = typeof VITA_CLASSICAL_SHADES[number]

export interface LabOrder {
  id: string
  clinic_id: string
  patient_id: string
  lab_contact_id: string
  work_type: WorkType
  tooth_reference?: string | null
  impression_type?: ImpressionType | null
  antagonist_info?: string | null
  shade?: Shade | null
  status: OrderStatus
  sent_date: string
  expected_date?: string | null
  received_date?: string | null
  notes?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface LabOrderCreatePayload {
  patient_id: string
  lab_contact_id: string
  work_type: WorkType
  tooth_reference?: string | null
  impression_type?: ImpressionType | null
  antagonist_info?: string | null
  shade?: Shade | null
  sent_date: string
  expected_date?: string | null
  notes?: string | null
}

export interface LabOrderUpdatePayload {
  lab_contact_id?: string
  work_type?: WorkType
  tooth_reference?: string | null
  impression_type?: ImpressionType | null
  antagonist_info?: string | null
  shade?: Shade | null
  status?: OrderStatus
  expected_date?: string | null
  received_date?: string | null
  notes?: string | null
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface LabOrderListFilters {
  patient_id?: string
  lab_contact_id?: string
  order_status?: OrderStatus
  page?: number
  page_size?: number
}

export function useLabOrders() {
  const api = useApi()

  async function list(filters: LabOrderListFilters = {}): Promise<ApiPaged<LabOrder>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/lab_orders/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<LabOrder>>(url)
  }

  async function create(payload: LabOrderCreatePayload): Promise<ApiOk<LabOrder>> {
    return await api.post<ApiOk<LabOrder>>('/api/v1/lab_orders/', payload)
  }

  async function update(id: string, payload: LabOrderUpdatePayload): Promise<ApiOk<LabOrder>> {
    return await api.patch<ApiOk<LabOrder>>(`/api/v1/lab_orders/${id}`, payload)
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/lab_orders/${id}`)
  }

  return { list, create, update, remove }
}
