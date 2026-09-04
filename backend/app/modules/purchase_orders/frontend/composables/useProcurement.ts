/**
 * Composable for the shared procurement frontend (supplier suite #227).
 *
 * Typed wrappers over the `/api/v1/suppliers`, `/supplier_items`,
 * `/purchase_orders`, `/inventory_reorder` and `/supplier_ratings`
 * endpoints. One layer, five areas — the purchase_orders module owns
 * the layer, the calls stay per-module.
 */

import type { ApiResponse, PaginatedResponse } from '~~/app/types'

export interface ProcurementSupplier {
  id: string
  clinic_id: string
  name: string
  contact_type: string
  phone: string | null
  email: string | null
  address: string | null
  notes: string | null
  is_active: boolean
  website: string | null
  payment_terms: string | null
  lead_time_days: number | null
  is_preferred: boolean
  created_at: string
  updated_at: string
}

export interface SupplierCreatePayload {
  name: string
  phone?: string | null
  email?: string | null
  address?: string | null
  notes?: string | null
  website?: string | null
  payment_terms?: string | null
  lead_time_days?: number | null
  is_preferred?: boolean
}

export interface SupplierUpdatePayload {
  phone?: string | null
  email?: string | null
  address?: string | null
  notes?: string | null
  website?: string | null
  payment_terms?: string | null
  lead_time_days?: number | null
  is_preferred?: boolean
}

export interface SupplierListParams {
  search?: string
  is_preferred?: boolean
  include_inactive?: boolean
  page?: number
  page_size?: number
}

export interface SupplierItemLink {
  id: string
  clinic_id: string
  supplier_id: string
  inventory_item_id: string
  supplier_sku: string | null
  price: string | null
  is_active: boolean
  supplier_name?: string | null
  item_name?: string | null
}

export interface SupplierItemLinkCreate {
  supplier_id: string
  inventory_item_id: string
  supplier_sku?: string | null
  price?: string | null
}

export type PurchaseOrderStatus = 'draft' | 'sent' | 'confirmed' | 'received' | 'cancelled'

export interface PurchaseOrderLine {
  id: string
  inventory_item_id: string
  item_name?: string | null
  quantity_ordered: string
  quantity_received: string
  unit_price: string | null
}

export interface PurchaseOrder {
  id: string
  clinic_id: string
  supplier_id: string
  supplier_name: string
  status: PurchaseOrderStatus
  expected_date: string | null
  notes: string | null
  received_at: string | null
  created_at: string
  updated_at: string
  lines: PurchaseOrderLine[]
}

export interface PurchaseOrderLineInput {
  inventory_item_id: string
  quantity_ordered: string
  unit_price?: string | null
}

export interface PurchaseOrderCreatePayload {
  supplier_id: string
  expected_date?: string | null
  notes?: string | null
  lines: PurchaseOrderLineInput[]
}

export interface ReceiptLineInput {
  purchase_order_line_id: string
  quantity_received: string
  quality: 'good' | 'rejected'
}

export interface ReorderSuggestion {
  inventory_item_id: string
  item_name: string
  category: string
  unit: string
  usage_90d: string
  daily_usage: string
  supplier_id: string | null
  supplier_name: string | null
  lead_time_days: number | null
  unit_price: string | null
  stock_quantity: string
  on_order: string
  reorder_point: string
  suggested_quantity: string
}

export interface RatingMetrics {
  po_count: number
  received_count: number
  received_with_due_date: number
  on_time_deliveries: number
  on_time_rate: string | null
  received_quantity: string
  rejected_quantity: string
  reject_rate: string | null
}

export interface SupplierReview {
  id: string
  clinic_id: string
  supplier_id: string
  score: number
  comment: string | null
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface SupplierRating {
  supplier_id: string
  supplier_name: string
  metrics: RatingMetrics
  review: SupplierReview | null
}

export interface InventoryItem {
  id: string
  name: string
  category: string
  unit: string
  stock_quantity: string
  is_active: boolean
}

function defined<T>(value: T | undefined | null | ''): T | undefined {
  return value === undefined || value === null || value === '' ? undefined : (value as T)
}

export function useProcurement() {
  const api = useApi()

  // --- suppliers -------------------------------------------------------
  async function listSuppliers(params: SupplierListParams = {}): Promise<PaginatedResponse<ProcurementSupplier>> {
    return api.get<PaginatedResponse<ProcurementSupplier>>('/api/v1/suppliers', {
      query: {
        search: defined(params.search),
        is_preferred: params.is_preferred,
        include_inactive: params.include_inactive,
        page: params.page,
        page_size: params.page_size
      }
    })
  }

  async function createSupplier(payload: SupplierCreatePayload): Promise<ApiResponse<ProcurementSupplier>> {
    return api.post<ApiResponse<ProcurementSupplier>>('/api/v1/suppliers', payload)
  }

  async function updateSupplier(id: string, payload: SupplierUpdatePayload): Promise<ApiResponse<ProcurementSupplier>> {
    return api.patch<ApiResponse<ProcurementSupplier>>(`/api/v1/suppliers/${id}`, payload)
  }

  async function deleteSupplier(id: string): Promise<void> {
    await api.del<null>(`/api/v1/suppliers/${id}`)
  }

  // --- supplier <-> item links ------------------------------------------
  async function listSupplierItems(params: { supplier_id?: string, inventory_item_id?: string, page?: number, page_size?: number } = {}): Promise<PaginatedResponse<SupplierItemLink>> {
    return api.get<PaginatedResponse<SupplierItemLink>>('/api/v1/supplier_items', {
      query: {
        supplier_id: defined(params.supplier_id),
        inventory_item_id: defined(params.inventory_item_id),
        page: params.page,
        page_size: params.page_size
      }
    })
  }

  async function createSupplierItemLink(payload: SupplierItemLinkCreate): Promise<ApiResponse<SupplierItemLink>> {
    return api.post<ApiResponse<SupplierItemLink>>('/api/v1/supplier_items', payload)
  }

  async function deleteSupplierItemLink(id: string): Promise<void> {
    await api.del<null>(`/api/v1/supplier_items/${id}`)
  }

  // --- purchase orders ---------------------------------------------------
  async function listPurchaseOrders(params: { order_status?: string, supplier_id?: string, page?: number, page_size?: number } = {}): Promise<PaginatedResponse<PurchaseOrder>> {
    return api.get<PaginatedResponse<PurchaseOrder>>('/api/v1/purchase_orders', {
      query: {
        order_status: defined(params.order_status),
        supplier_id: defined(params.supplier_id),
        page: params.page,
        page_size: params.page_size
      }
    })
  }

  async function getPurchaseOrder(id: string): Promise<ApiResponse<PurchaseOrder>> {
    return api.get<ApiResponse<PurchaseOrder>>(`/api/v1/purchase_orders/${id}`)
  }

  async function createPurchaseOrder(payload: PurchaseOrderCreatePayload): Promise<ApiResponse<PurchaseOrder>> {
    return api.post<ApiResponse<PurchaseOrder>>('/api/v1/purchase_orders', payload)
  }

  async function transitionPurchaseOrder(id: string, status: string): Promise<ApiResponse<PurchaseOrder>> {
    return api.post<ApiResponse<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/status`, { status })
  }

  async function receivePurchaseOrder(id: string, lines: ReceiptLineInput[]): Promise<ApiResponse<PurchaseOrder>> {
    return api.post<ApiResponse<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/receive`, { lines })
  }

  function purchaseOrderPdfUrl(id: string, locale = 'es'): string {
    return `/api/v1/purchase_orders/${id}/pdf?locale=${locale}`
  }

  // --- reorder ------------------------------------------------------------
  async function listReorderSuggestions(): Promise<ApiResponse<ReorderSuggestion[]>> {
    return api.get<ApiResponse<ReorderSuggestion[]>>('/api/v1/inventory_reorder/suggestions')
  }

  async function generateReorderOrders(itemIds: string[]): Promise<ApiResponse<PurchaseOrder[]>> {
    return api.post<ApiResponse<PurchaseOrder[]>>('/api/v1/inventory_reorder/orders', { item_ids: itemIds })
  }

  // --- ratings -------------------------------------------------------------
  async function listSupplierRatings(params: { page?: number, page_size?: number } = {}): Promise<PaginatedResponse<SupplierRating>> {
    return api.get<PaginatedResponse<SupplierRating>>('/api/v1/supplier_ratings', {
      query: { page: params.page, page_size: params.page_size }
    })
  }

  async function createSupplierReview(payload: { supplier_id: string, score: number, comment?: string | null }): Promise<ApiResponse<SupplierReview>> {
    return api.post<ApiResponse<SupplierReview>>('/api/v1/supplier_ratings/reviews', payload)
  }

  async function updateSupplierReview(id: string, payload: { score: number, comment?: string | null }): Promise<ApiResponse<SupplierReview>> {
    return api.patch<ApiResponse<SupplierReview>>(`/api/v1/supplier_ratings/reviews/${id}`, payload)
  }

  async function deleteSupplierReview(id: string): Promise<void> {
    await api.del<null>(`/api/v1/supplier_ratings/reviews/${id}`)
  }

  // --- inventory lookup (for link/order line pickers) --------------------
  async function listInventoryItems(params: { page?: number, page_size?: number } = {}): Promise<PaginatedResponse<InventoryItem>> {
    return api.get<PaginatedResponse<InventoryItem>>('/api/v1/inventory/', {
      query: { page: params.page, page_size: params.page_size }
    })
  }

  return {
    listInventoryItems,
    listSuppliers,
    createSupplier,
    updateSupplier,
    deleteSupplier,
    listSupplierItems,
    createSupplierItemLink,
    deleteSupplierItemLink,
    listPurchaseOrders,
    getPurchaseOrder,
    createPurchaseOrder,
    transitionPurchaseOrder,
    receivePurchaseOrder,
    purchaseOrderPdfUrl,
    listReorderSuggestions,
    generateReorderOrders,
    listSupplierRatings,
    createSupplierReview,
    updateSupplierReview,
    deleteSupplierReview
  }
}
