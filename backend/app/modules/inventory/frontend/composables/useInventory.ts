export type ItemCategory = 'consumables' | 'equipment' | 'office' | 'other'
export type MovementReason = 'initial' | 'restock' | 'consumption' | 'adjustment' | 'correction'

export interface InventoryItem {
  id: string
  clinic_id: string
  name: string
  category: ItemCategory
  unit: string
  stock_quantity: string
  min_quantity: string
  unit_cost?: string | null
  is_low_stock: boolean
  is_active: boolean
  notes?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface StockMovement {
  id: string
  inventory_item_id: string
  delta: string
  reason: MovementReason
  note?: string | null
  reference_type?: string | null
  reference_id?: string | null
  created_by?: string | null
  created_by_name?: string | null
  created_at: string
}

export interface StockValuation {
  total_value: string
  valued_items: number
  unvalued_items: number
}

export interface InventoryItemCreatePayload {
  name: string
  category: ItemCategory
  unit: string
  stock_quantity: number
  min_quantity: number
  unit_cost?: number | null
  notes?: string | null
}

export interface InventoryItemUpdatePayload {
  name?: string
  category?: ItemCategory
  unit?: string
  stock_quantity?: number
  min_quantity?: number
  unit_cost?: number | null
  is_active?: boolean
  notes?: string | null
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface InventoryListFilters {
  category?: ItemCategory
  low_stock?: boolean
  include_inactive?: boolean
  page?: number
  page_size?: number
}

export function useInventory() {
  const api = useApi()

  async function list(filters: InventoryListFilters = {}): Promise<ApiPaged<InventoryItem>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '' || v === false) continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/inventory/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<InventoryItem>>(url)
  }

  async function create(payload: InventoryItemCreatePayload): Promise<ApiOk<InventoryItem>> {
    return await api.post<ApiOk<InventoryItem>>('/api/v1/inventory/', payload)
  }

  async function update(id: string, payload: InventoryItemUpdatePayload): Promise<ApiOk<InventoryItem>> {
    return await api.patch<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}`, payload)
  }

  async function adjust(
    id: string,
    delta: number,
    opts: { reason?: MovementReason, note?: string } = {}
  ): Promise<ApiOk<InventoryItem>> {
    return await api.post<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}/adjust`, {
      delta,
      reason: opts.reason ?? 'adjustment',
      note: opts.note ?? null
    })
  }

  async function movements(id: string, page = 1, pageSize = 50): Promise<ApiPaged<StockMovement>> {
    return await api.get<ApiPaged<StockMovement>>(
      `/api/v1/inventory/${id}/movements?page=${page}&page_size=${pageSize}`
    )
  }

  async function valuation(): Promise<ApiOk<StockValuation>> {
    return await api.get<ApiOk<StockValuation>>('/api/v1/inventory/valuation')
  }

  async function remove(id: string): Promise<void> {
    await api.del(`/api/v1/inventory/${id}`)
  }

  return { list, create, update, adjust, movements, valuation, remove }
}
