/**
 * Composable for managing the treatment catalog.
 *
 * Provides CRUD operations for catalog categories and items,
 * including search and filtering capabilities.
 */

import type {
  ApiResponse,
  PaginatedResponse,
  TreatmentCatalogCategory,
  TreatmentCatalogCategoryCreate,
  TreatmentCatalogCategoryUpdate,
  TreatmentCatalogItem,
  TreatmentCatalogItemCreate,
  TreatmentCatalogItemUpdate
} from '~~/app/types'

/**
 * Extract the FastAPI error `detail` from a fetch error, so toasts can show
 * the exact server message instead of a generic one. Returns null for
 * network errors or unexpected bodies (caller falls back to generic text).
 */
function apiErrorDetail(e: unknown): string | null {
  const detail = (e as { data?: { detail?: unknown } }).data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // 422 validation errors: [{loc: ["body", "field"], msg: "..."}]
    const parts = (detail as Array<{ loc?: unknown[], msg?: string }>)
      .map(d => [Array.isArray(d.loc) ? d.loc.slice(1).join('.') : '', d.msg].filter(Boolean).join(': '))
      .filter(Boolean)
    return parts.length ? parts.join('; ') : null
  }
  return null
}

export function useCatalog() {
  const api = useApi()
  const { t, locale } = useI18n()
  const toast = useToast()

  // State
  const categories = useState<TreatmentCatalogCategory[]>('catalog:categories', () => [])
  const items = useState<TreatmentCatalogItem[]>('catalog:items', () => [])
  const totalItems = useState<number>('catalog:totalItems', () => 0)
  const currentPage = useState<number>('catalog:currentPage', () => 1)
  const pageSize = useState<number>('catalog:pageSize', () => 20)
  const loading = useState<boolean>('catalog:loading', () => false)
  const error = useState<string | null>('catalog:error', () => null)

  // ============================================================================
  // Category Operations
  // ============================================================================

  async function fetchCategories(includeInactive = false): Promise<void> {
    try {
      loading.value = true
      error.value = null

      const params = new URLSearchParams()
      if (includeInactive) params.set('include_inactive', 'true')

      const response = await api.get<ApiResponse<TreatmentCatalogCategory[]>>(
        `/api/v1/catalog/categories?${params.toString()}`
      )
      categories.value = response.data
    } catch (e) {
      error.value = 'Failed to fetch categories'
      console.error('Error fetching categories:', e)
    } finally {
      loading.value = false
    }
  }

  async function getCategory(categoryId: string): Promise<TreatmentCatalogCategory | null> {
    try {
      const response = await api.get<ApiResponse<TreatmentCatalogCategory>>(
        `/api/v1/catalog/categories/${categoryId}`
      )
      return response.data
    } catch (e) {
      console.error('Error fetching category:', e)
      return null
    }
  }

  async function createCategory(data: TreatmentCatalogCategoryCreate): Promise<TreatmentCatalogCategory | null> {
    try {
      const response = await api.post<ApiResponse<TreatmentCatalogCategory>>(
        '/api/v1/catalog/categories',
        data as Record<string, unknown>
      )

      toast.add({
        title: t('common.success'),
        description: t('catalog.categoryCreated'),
        color: 'success'
      })

      // Refresh categories list
      await fetchCategories()

      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number, data?: { message?: string } }
      if (fetchError.statusCode === 409) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.categoryKeyExists'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: apiErrorDetail(e) || t('catalog.categoryCreateFailed'),
          color: 'error'
        })
      }
      return null
    }
  }

  async function updateCategory(
    categoryId: string,
    data: TreatmentCatalogCategoryUpdate
  ): Promise<TreatmentCatalogCategory | null> {
    try {
      const response = await api.put<ApiResponse<TreatmentCatalogCategory>>(
        `/api/v1/catalog/categories/${categoryId}`,
        data as Record<string, unknown>
      )

      toast.add({
        title: t('common.success'),
        description: t('catalog.categoryUpdated'),
        color: 'success'
      })

      // Refresh categories list
      await fetchCategories()

      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.cannotModifySystemCategory'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: apiErrorDetail(e) || t('catalog.categoryUpdateFailed'),
          color: 'error'
        })
      }
      return null
    }
  }

  async function deleteCategory(categoryId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/catalog/categories/${categoryId}`)

      toast.add({
        title: t('common.success'),
        description: t('catalog.categoryDeleted'),
        color: 'success'
      })

      // Refresh categories list
      await fetchCategories()

      return true
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.cannotDeleteSystemCategory'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: apiErrorDetail(e) || t('catalog.categoryDeleteFailed'),
          color: 'error'
        })
      }
      return false
    }
  }

  // ============================================================================
  // Item Operations
  // ============================================================================

  interface FetchItemsOptions {
    page?: number
    pageSize?: number
    categoryId?: string
    isActive?: boolean
    treatmentScope?: 'surface' | 'whole_tooth'
    hasOdontogramMapping?: boolean
    search?: string
  }

  async function fetchItems(options: FetchItemsOptions = {}): Promise<void> {
    try {
      loading.value = true
      error.value = null

      const params = new URLSearchParams()
      params.set('page', String(options.page || currentPage.value))
      params.set('page_size', String(options.pageSize || pageSize.value))

      if (options.categoryId) params.set('category_id', options.categoryId)
      if (options.isActive !== undefined) params.set('is_active', String(options.isActive))
      if (options.treatmentScope) params.set('treatment_scope', options.treatmentScope)
      if (options.hasOdontogramMapping !== undefined) {
        params.set('has_odontogram_mapping', String(options.hasOdontogramMapping))
      }
      if (options.search) params.set('search', options.search)

      const response = await api.get<PaginatedResponse<TreatmentCatalogItem>>(
        `/api/v1/catalog/items?${params.toString()}`
      )

      items.value = response.data
      totalItems.value = response.total
      currentPage.value = response.page
      pageSize.value = response.page_size
    } catch (e) {
      error.value = 'Failed to fetch items'
      console.error('Error fetching items:', e)
    } finally {
      loading.value = false
    }
  }

  async function getItem(itemId: string): Promise<TreatmentCatalogItem | null> {
    try {
      const response = await api.get<ApiResponse<TreatmentCatalogItem>>(
        `/api/v1/catalog/items/${itemId}`
      )
      return response.data
    } catch (e) {
      console.error('Error fetching item:', e)
      return null
    }
  }

  async function createItem(data: TreatmentCatalogItemCreate): Promise<TreatmentCatalogItem | null> {
    try {
      const response = await api.post<ApiResponse<TreatmentCatalogItem>>(
        '/api/v1/catalog/items',
        data as Record<string, unknown>
      )

      toast.add({
        title: t('common.success'),
        description: t('catalog.itemCreated'),
        color: 'success'
      })

      // Refresh items list
      await fetchItems()

      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 409) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.itemCodeExists'),
          color: 'error'
        })
      } else if (fetchError.statusCode === 400) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.categoryNotFound'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: apiErrorDetail(e) || t('catalog.itemCreateFailed'),
          color: 'error'
        })
      }
      return null
    }
  }

  async function updateItem(
    itemId: string,
    data: TreatmentCatalogItemUpdate
  ): Promise<TreatmentCatalogItem | null> {
    try {
      const response = await api.put<ApiResponse<TreatmentCatalogItem>>(
        `/api/v1/catalog/items/${itemId}`,
        data as Record<string, unknown>
      )

      toast.add({
        title: t('common.success'),
        description: t('catalog.itemUpdated'),
        color: 'success'
      })

      // Refresh items list
      await fetchItems()

      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.cannotModifySystemItem'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: apiErrorDetail(e) || t('catalog.itemUpdateFailed'),
          color: 'error'
        })
      }
      return null
    }
  }

  async function deleteItem(itemId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/catalog/items/${itemId}`)

      toast.add({
        title: t('common.success'),
        description: t('catalog.itemDeleted'),
        color: 'success'
      })

      // Refresh items list
      await fetchItems()

      return true
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      if (fetchError.statusCode === 403) {
        toast.add({
          title: t('common.error'),
          description: t('catalog.cannotDeleteSystemItem'),
          color: 'error'
        })
      } else {
        toast.add({
          title: t('common.error'),
          description: apiErrorDetail(e) || t('catalog.itemDeleteFailed'),
          color: 'error'
        })
      }
      return false
    }
  }

  interface SearchItemsResult {
    id: string
    internal_code: string
    names: Record<string, string>
    default_price?: number
    is_active: boolean
  }

  async function searchItems(query: string, limit = 20): Promise<SearchItemsResult[]> {
    try {
      const response = await api.get<ApiResponse<SearchItemsResult[]>>(
        `/api/v1/catalog/items/search?q=${encodeURIComponent(query)}&limit=${limit}`
      )
      return response.data
    } catch (e) {
      console.error('Error searching items:', e)
      return []
    }
  }

  // ============================================================================
  // Computed
  // ============================================================================

  const totalPages = computed(() => Math.ceil(totalItems.value / pageSize.value))

  const categoriesByKey = computed(() => {
    const map: Record<string, TreatmentCatalogCategory> = {}
    for (const category of categories.value) {
      map[category.key] = category
    }
    return map
  })

  const activeCategories = computed(() => categories.value.filter(c => c.is_active))

  // ============================================================================
  // Helpers
  // ============================================================================

  function getCategoryName(category: TreatmentCatalogCategory, overrideLocale?: string): string {
    const loc = overrideLocale || locale.value
    return category.names[loc] || category.names.es || category.names.en || category.key
  }

  function getItemName(item: TreatmentCatalogItem, overrideLocale?: string): string {
    const loc = overrideLocale || locale.value
    return item.names[loc] || item.names.es || item.names.en || item.internal_code
  }

  // Clinic-wide currency from useCurrency. The legacy second arg
  // (currency override) is ignored — kept in the signature so existing
  // callers compile without churn.
  const { format } = useCurrency()
  function formatPrice(price: number | undefined | null, _currency?: string): string {
    if (price === undefined || price === null) return '-'
    return format(price)
  }

  return {
    // State
    categories,
    items,
    totalItems,
    currentPage,
    pageSize,
    loading,
    error,

    // Category operations
    fetchCategories,
    getCategory,
    createCategory,
    updateCategory,
    deleteCategory,

    // Item operations
    fetchItems,
    getItem,
    createItem,
    updateItem,
    deleteItem,
    searchItems,

    // Computed
    totalPages,
    categoriesByKey,
    activeCategories,

    // Helpers
    getCategoryName,
    getItemName,
    formatPrice
  }
}
