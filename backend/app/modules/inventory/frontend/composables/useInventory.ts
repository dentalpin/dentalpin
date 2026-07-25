export type InventoryCategory = 'consumables' | 'ppe' | 'materials' | 'medication' | 'other'
export type InventoryMovementReason =
  | 'purchase'
  | 'return'
  | 'donation'
  | 'adjustment'
  | 'damaged'
  | 'expired'
  | 'lost'
  | 'used'

export interface InventoryItem {
  id: string
  clinic_id: string
  name: string
  category: InventoryCategory
  unit?: string | null
  quantity_on_hand: string
  low_stock_threshold: string
  unit_cost?: string | null
  average_cost?: string | null
  is_low_stock: boolean
  notes?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface InventoryItemCreatePayload {
  name: string
  category: InventoryCategory
  unit?: string | null
  quantity_on_hand?: number
  low_stock_threshold?: number
  unit_cost?: number | null
  notes?: string | null
}

export interface InventoryItemUpdatePayload {
  name?: string
  category?: InventoryCategory
  unit?: string | null
  low_stock_threshold?: number
  unit_cost?: number | null
  notes?: string | null
}

export interface InventoryMovement {
  id: string
  clinic_id: string
  item_id: string
  reason: InventoryMovementReason
  quantity_delta: string
  quantity_after: string
  unit_cost?: string | null
  reference?: string | null
  notes?: string | null
  movement_date: string
  created_by?: string | null
  created_at: string
}

export interface InventoryMovementCreatePayload {
  reason: InventoryMovementReason
  quantity_delta: number
  unit_cost?: number | null
  reference?: string | null
  notes?: string | null
  movement_date?: string | null
}

export interface InventoryUsageSummary {
  item_id: string
  used_this_week: string
  used_this_month: string
  total_used: string
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface InventoryListFilters {
  category?: InventoryCategory
  search?: string
  low_stock_only?: boolean
  page?: number
  page_size?: number
}

export interface InventoryMovementFilters {
  reason?: InventoryMovementReason
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

function toQueryString(filters: Record<string, unknown>): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) {
    if (v === undefined || v === null || v === '') continue
    qs.append(k, String(v))
  }
  return qs.toString()
}

export function useInventory() {
  const api = useApi()

  async function list(filters: InventoryListFilters = {}): Promise<ApiPaged<InventoryItem>> {
    const qs = toQueryString(filters)
    return await api.get<ApiPaged<InventoryItem>>(`/api/v1/inventory/${qs ? `?${qs}` : ''}`)
  }

  async function create(payload: InventoryItemCreatePayload): Promise<ApiOk<InventoryItem>> {
    return await api.post<ApiOk<InventoryItem>>('/api/v1/inventory/', payload)
  }

  async function update(id: string, payload: InventoryItemUpdatePayload): Promise<ApiOk<InventoryItem>> {
    return await api.patch<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}`, payload)
  }

  async function adjust(id: string, delta: number, note?: string): Promise<ApiOk<InventoryItem>> {
    return await api.post<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}/adjust`, { delta, note })
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/inventory/${id}`)
  }

  async function listMovements(
    id: string,
    filters: InventoryMovementFilters = {}
  ): Promise<ApiPaged<InventoryMovement>> {
    const qs = toQueryString(filters)
    return await api.get<ApiPaged<InventoryMovement>>(`/api/v1/inventory/${id}/movements${qs ? `?${qs}` : ''}`)
  }

  async function createMovement(
    id: string,
    payload: InventoryMovementCreatePayload
  ): Promise<ApiOk<InventoryMovement>> {
    return await api.post<ApiOk<InventoryMovement>>(`/api/v1/inventory/${id}/movements`, payload)
  }

  async function getUsage(id: string): Promise<ApiOk<InventoryUsageSummary>> {
    return await api.get<ApiOk<InventoryUsageSummary>>(`/api/v1/inventory/${id}/usage`)
  }

  return { list, create, update, adjust, remove, listMovements, createMovement, getUsage }
}
