export type InventoryCategory = 'consumables' | 'ppe' | 'materials' | 'medication' | 'other'

export interface InventoryItem {
  id: string
  clinic_id: string
  name: string
  category: InventoryCategory
  unit?: string | null
  quantity_on_hand: string
  low_stock_threshold: string
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
  notes?: string | null
}

export interface InventoryItemUpdatePayload {
  name?: string
  category?: InventoryCategory
  unit?: string | null
  low_stock_threshold?: number
  notes?: string | null
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

export function useInventory() {
  const api = useApi()

  async function list(filters: InventoryListFilters = {}): Promise<ApiPaged<InventoryItem>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
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

  async function adjust(id: string, delta: number, note?: string): Promise<ApiOk<InventoryItem>> {
    return await api.post<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}/adjust`, { delta, note })
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/inventory/${id}`)
  }

  return { list, create, update, adjust, remove }
}
