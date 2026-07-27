export interface SupplierRating {
  id: string
  supplier_contact_id: string
  communication_score: number
  notes?: string | null
  rated_by?: string | null
  rated_at: string
}

export interface SupplierPerformanceDashboard {
  supplier_contact_id: string
  supplier_name: string
  on_time_delivery_pct?: number | null
  completed_order_count: number
  avg_unit_price?: string | null
  quality_good_pct?: number | null
  total_receipt_lines: number
  avg_communication_score?: number | null
  ratings: SupplierRating[]
}

interface ApiOk<T> { data: T, message?: string | null }

export function useSupplierRatings() {
  const api = useApi()

  async function getDashboard(supplierContactId: string): Promise<ApiOk<SupplierPerformanceDashboard>> {
    return await api.get<ApiOk<SupplierPerformanceDashboard>>(`/api/v1/supplier_ratings/${supplierContactId}`)
  }

  async function addRating(
    supplierContactId: string,
    communicationScore: number,
    notes?: string | null
  ): Promise<ApiOk<SupplierRating>> {
    return await api.post<ApiOk<SupplierRating>>(`/api/v1/supplier_ratings/${supplierContactId}`, {
      communication_score: communicationScore,
      notes: notes ?? null
    })
  }

  return { getDashboard, addRating }
}
