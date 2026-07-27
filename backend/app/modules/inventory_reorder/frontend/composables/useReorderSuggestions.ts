export interface ReorderSuggestion {
  inventory_item_id: string
  item_name: string
  quantity_on_hand: string
  low_stock_threshold: string
  reorder_max_quantity?: string | null
  avg_daily_usage: string
  lead_time_days: number
  suggested_quantity: string
  supplier_contact_id?: string | null
  supplier_name?: string | null
  unit_price?: string | null
  estimated_cost?: string | null
  low_confidence: boolean
}

export interface ReorderSelectionPayload {
  inventory_item_id: string
  supplier_contact_id: string
  quantity: number
  unit_price: number
}

interface ApiOk<T> { data: T, message?: string | null }

export function useReorderSuggestions() {
  const api = useApi()

  async function getSuggestions(): Promise<ApiOk<ReorderSuggestion[]>> {
    return await api.get<ApiOk<ReorderSuggestion[]>>('/api/v1/inventory_reorder/suggestions')
  }

  async function generatePOs(
    selections: ReorderSelectionPayload[]
  ): Promise<ApiOk<{ purchase_order_ids: string[] }>> {
    return await api.post<ApiOk<{ purchase_order_ids: string[] }>>(
      '/api/v1/inventory_reorder/generate-pos',
      { selections }
    )
  }

  return { getSuggestions, generatePOs }
}
