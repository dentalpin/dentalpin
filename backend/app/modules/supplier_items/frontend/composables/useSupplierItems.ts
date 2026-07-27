export interface SupplierItem {
  id: string
  clinic_id: string
  supplier_contact_id: string
  supplier_name: string
  inventory_item_id: string
  item_name: string
  supplier_sku?: string | null
  unit_price: string
  is_preferred_supplier: boolean
  lead_time_days?: number | null
  notes?: string | null
  created_at: string
  updated_at: string
}

export interface SupplierItemCreatePayload {
  supplier_contact_id: string
  inventory_item_id: string
  supplier_sku?: string | null
  unit_price: number
  is_preferred_supplier?: boolean
  notes?: string | null
}

export interface SupplierItemUpdatePayload {
  supplier_sku?: string | null
  unit_price?: number
  is_preferred_supplier?: boolean
  notes?: string | null
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface SupplierItemFilters {
  supplier_contact_id?: string
  inventory_item_id?: string
  page?: number
  page_size?: number
}

export function useSupplierItems() {
  const api = useApi()

  async function list(filters: SupplierItemFilters = {}): Promise<ApiPaged<SupplierItem>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    return await api.get<ApiPaged<SupplierItem>>(`/api/v1/supplier_items/${qs.toString() ? `?${qs.toString()}` : ''}`)
  }

  async function create(payload: SupplierItemCreatePayload): Promise<ApiOk<SupplierItem>> {
    return await api.post<ApiOk<SupplierItem>>('/api/v1/supplier_items/', payload)
  }

  async function update(id: string, payload: SupplierItemUpdatePayload): Promise<ApiOk<SupplierItem>> {
    return await api.patch<ApiOk<SupplierItem>>(`/api/v1/supplier_items/${id}`, payload)
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/supplier_items/${id}`)
  }

  return { list, create, update, remove }
}
