export type PurchaseOrderStatus =
  | 'draft' | 'sent' | 'confirmed' | 'partially_received' | 'fully_received' | 'cancelled'

export interface PurchaseOrderItem {
  id: string
  inventory_item_id: string
  description: string
  unit_price: string
  quantity_ordered: string
  quantity_received: string
  line_total: string
  display_order: number
}

export interface PurchaseOrder {
  id: string
  clinic_id: string
  po_number: string
  supplier_contact_id: string
  status: PurchaseOrderStatus
  order_date: string
  expected_delivery_date?: string | null
  shipping_cost: string
  tax_amount: string
  subtotal: string
  total: string
  notes?: string | null
  sent_at?: string | null
  confirmed_at?: string | null
  cancelled_at?: string | null
  cancellation_reason?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
  items: PurchaseOrderItem[]
}

export interface PurchaseOrderListItem {
  id: string
  po_number: string
  supplier_contact_id: string
  supplier_name: string
  status: PurchaseOrderStatus
  order_date: string
  expected_delivery_date?: string | null
  total: string
}

export interface PurchaseOrderItemCreatePayload {
  inventory_item_id: string
  description?: string | null
  unit_price: number
  quantity_ordered: number
}

export interface PurchaseOrderItemUpdatePayload {
  description?: string | null
  unit_price?: number
  quantity_ordered?: number
}

export type ReceiptLineQuality = 'good' | 'damaged' | 'expired' | 'wrong_item'

export interface PurchaseOrderReceiptLineCreatePayload {
  purchase_order_item_id: string
  quantity_received: number
  quality_status: ReceiptLineQuality
  notes?: string | null
}

export interface PurchaseOrderReceiptCreatePayload {
  received_date?: string | null
  notes?: string | null
  lines: PurchaseOrderReceiptLineCreatePayload[]
}

export interface PurchaseOrderReceiptLine {
  id: string
  purchase_order_item_id: string
  quantity_received: string
  quality_status: ReceiptLineQuality
  notes?: string | null
}

export interface PurchaseOrderReceipt {
  id: string
  purchase_order_id: string
  received_date: string
  received_by?: string | null
  notes?: string | null
  created_at: string
  lines: PurchaseOrderReceiptLine[]
}

export interface PurchaseOrderCreatePayload {
  supplier_contact_id: string
  expected_delivery_date?: string | null
  shipping_cost?: number
  tax_amount?: number
  notes?: string | null
  items?: PurchaseOrderItemCreatePayload[]
}

export interface PurchaseOrderUpdatePayload {
  expected_delivery_date?: string | null
  shipping_cost?: number
  tax_amount?: number
  notes?: string | null
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface PurchaseOrderFilters {
  status?: PurchaseOrderStatus
  supplier_contact_id?: string
  search?: string
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

export function usePurchaseOrders() {
  const api = useApi()

  async function list(filters: PurchaseOrderFilters = {}): Promise<ApiPaged<PurchaseOrderListItem>> {
    const qs = toQueryString(filters)
    return await api.get<ApiPaged<PurchaseOrderListItem>>(`/api/v1/purchase_orders/${qs ? `?${qs}` : ''}`)
  }

  async function get(id: string): Promise<ApiOk<PurchaseOrder>> {
    return await api.get<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}`)
  }

  async function create(payload: PurchaseOrderCreatePayload): Promise<ApiOk<PurchaseOrder>> {
    return await api.post<ApiOk<PurchaseOrder>>('/api/v1/purchase_orders/', payload)
  }

  async function update(id: string, payload: PurchaseOrderUpdatePayload): Promise<ApiOk<PurchaseOrder>> {
    return await api.patch<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}`, payload)
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/purchase_orders/${id}`)
  }

  async function addItem(id: string, payload: PurchaseOrderItemCreatePayload): Promise<ApiOk<PurchaseOrder>> {
    return await api.post<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/items`, payload)
  }

  async function updateItem(
    id: string,
    itemId: string,
    payload: PurchaseOrderItemUpdatePayload
  ): Promise<ApiOk<PurchaseOrder>> {
    return await api.patch<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/items/${itemId}`, payload)
  }

  async function removeItem(id: string, itemId: string): Promise<ApiOk<PurchaseOrder>> {
    return await api.del<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/items/${itemId}`)
  }

  async function send(id: string, sendEmail = true): Promise<ApiOk<PurchaseOrder>> {
    return await api.post<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/send?send_email=${sendEmail}`)
  }

  async function confirm(id: string): Promise<ApiOk<PurchaseOrder>> {
    return await api.post<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/confirm`)
  }

  async function cancel(id: string, reason: string): Promise<ApiOk<PurchaseOrder>> {
    return await api.post<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/cancel`, { reason })
  }

  async function listReceipts(id: string): Promise<ApiOk<PurchaseOrderReceipt[]>> {
    return await api.get<ApiOk<PurchaseOrderReceipt[]>>(`/api/v1/purchase_orders/${id}/receipts`)
  }

  async function recordReceipt(
    id: string,
    payload: PurchaseOrderReceiptCreatePayload
  ): Promise<ApiOk<PurchaseOrder>> {
    return await api.post<ApiOk<PurchaseOrder>>(`/api/v1/purchase_orders/${id}/receipts`, payload)
  }

  // The PDF endpoint requires the same Bearer-token auth as everything
  // else in useApi — a plain <a href> straight to the API URL would 401
  // since auth here isn't cookie-based. Fetch it through api.get instead:
  // ofetch auto-detects a non-JSON, non-text content-type (application/pdf)
  // and hands back a Blob directly, no manual conversion needed.
  async function fetchPdfBlob(id: string, locale = 'es'): Promise<Blob> {
    return await api.get<Blob>(`/api/v1/purchase_orders/${id}/pdf?locale=${locale}`)
  }

  async function openPdf(id: string, locale = 'es'): Promise<void> {
    const blob = await fetchPdfBlob(id, locale)
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
    // Revoke after a delay rather than immediately — the new tab needs
    // the URL to still be valid when it loads.
    setTimeout(() => URL.revokeObjectURL(url), 30000)
  }

  async function downloadPdf(id: string, poNumber: string, locale = 'es'): Promise<void> {
    const blob = await fetchPdfBlob(id, locale)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${poNumber}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  return {
    list, get, create, update, remove,
    addItem, updateItem, removeItem,
    send, confirm, cancel,
    listReceipts, recordReceipt,
    openPdf, downloadPdf
  }
}
