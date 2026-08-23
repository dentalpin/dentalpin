export type InventoryItemStatus = 'active' | 'inactive' | 'deleted'

export interface InventoryCategory {
  id: string
  clinic_id: string
  name: string
  description?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface InventoryItem {
  id: string
  clinic_id: string
  category_id?: string | null
  code: string
  name: string
  description?: string | null
  quantity: number
  min_quantity: number
  unit: string
  location?: string | null
  supplier?: string | null
  notes?: string | null
  status: InventoryItemStatus
  is_low_stock: boolean
  created_at: string
  updated_at: string
  category?: { id: string, name: string } | null
}

export interface InventoryItemCreatePayload {
  category_id?: string | null
  code: string
  name: string
  description?: string | null
  quantity?: number
  min_quantity?: number
  unit?: string
  location?: string | null
  supplier?: string | null
  notes?: string | null
}

export interface InventoryItemUpdatePayload {
  category_id?: string | null
  code?: string
  name?: string
  description?: string | null
  min_quantity?: number
  unit?: string
  location?: string | null
  supplier?: string | null
  notes?: string | null
  status?: InventoryItemStatus
}

export interface StockAdjustPayload {
  delta: number
  reason?: string | null
}

export interface LowStockItem {
  item_id: string
  code: string
  name: string
  quantity: number
  min_quantity: number
  unit: string
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface InventoryListFilters {
  status?: InventoryItemStatus
  category_id?: string
  low_stock?: boolean
  search?: string
  page?: number
  page_size?: number
}

export function useInventory() {
  const api = useApi()

  // --- Items ---

  async function listItems(filters: InventoryListFilters = {}): Promise<ApiPaged<InventoryItem>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/inventory/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<InventoryItem>>(url)
  }

  async function getItem(id: string): Promise<ApiOk<InventoryItem>> {
    return await api.get<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}`)
  }

  async function createItem(payload: InventoryItemCreatePayload): Promise<ApiOk<InventoryItem>> {
    return await api.post<ApiOk<InventoryItem>>('/api/v1/inventory/', payload)
  }

  async function updateItem(id: string, payload: InventoryItemUpdatePayload): Promise<ApiOk<InventoryItem>> {
    return await api.patch<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}`, payload)
  }

  async function deleteItem(id: string): Promise<void> {
    await api.del(`/api/v1/inventory/${id}`)
  }

  async function adjustStock(id: string, payload: StockAdjustPayload): Promise<ApiOk<InventoryItem>> {
    return await api.post<ApiOk<InventoryItem>>(`/api/v1/inventory/${id}/adjust-stock`, payload)
  }

  async function lowStock(): Promise<ApiOk<LowStockItem[]>> {
    return await api.get<ApiOk<LowStockItem[]>>('/api/v1/inventory/low-stock')
  }

  async function dashboard(): Promise<ApiOk<Record<string, number>>> {
    return await api.get<ApiOk<Record<string, number>>>('/api/v1/inventory/stats/dashboard')
  }

  // --- Categories ---

  async function listCategories(): Promise<ApiPaged<InventoryCategory>> {
    return await api.get<ApiPaged<InventoryCategory>>('/api/v1/inventory/categories')
  }

  async function createCategory(payload: { name: string, description?: string }): Promise<ApiOk<InventoryCategory>> {
    return await api.post<ApiOk<InventoryCategory>>('/api/v1/inventory/categories', payload)
  }

  return {
    listItems, getItem, createItem, updateItem, deleteItem,
    adjustStock, lowStock, dashboard,
    listCategories, createCategory,
  }
}
