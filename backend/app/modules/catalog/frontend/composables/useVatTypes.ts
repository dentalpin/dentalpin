/**
 * Composable for VAT type management.
 *
 * Handles CRUD operations for VAT types and provides computed helpers.
 */
import type { VatType, VatTypeCreate, VatTypeUpdate, ApiResponse } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

export function useVatTypes() {
  const api = useApi()
  const { t, locale } = useI18n()
  const toast = useToast()

  // State
  const vatTypes = useState<VatType[]>('vatTypes:list', () => [])
  const isLoading = useState<boolean>('vatTypes:loading', () => false)

  // Computed
  const activeVatTypes = computed(() =>
    vatTypes.value.filter(vt => vt.is_active)
  )

  const defaultVatType = computed(() =>
    vatTypes.value.find(vt => vt.is_default && vt.is_active)
  )

  // Get localized name for a VAT type
  function getVatTypeName(vt: VatType | undefined): string {
    if (!vt) return ''
    return vt.names[locale.value] || vt.names.es || vt.names.en || ''
  }

  // Get display label with rate: "Exento (0%)"
  function getVatTypeLabel(vt: VatType | undefined): string {
    if (!vt) return ''
    const name = getVatTypeName(vt)
    return `${name} (${vt.rate}%)`
  }

  // Get VAT type by ID
  function getVatTypeById(id: string | undefined): VatType | undefined {
    if (!id) return undefined
    return vatTypes.value.find(vt => vt.id === id)
  }

  // Fetch all VAT types for the clinic
  async function fetchVatTypes(includeInactive = false): Promise<void> {
    isLoading.value = true
    try {
      const params = includeInactive ? '?include_inactive=true' : ''
      const response = await api.get<ApiResponse<VatType[]>>(`/api/v1/catalog/vat-types${params}`)
      vatTypes.value = response.data
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('vatTypes.loadError')),
        color: 'red'
      })
    } finally {
      isLoading.value = false
    }
  }

  // Create a new VAT type
  async function createVatType(data: VatTypeCreate): Promise<VatType | null> {
    try {
      const response = await api.post<ApiResponse<VatType>>('/api/v1/catalog/vat-types', data)
      // If setting as default, update local state
      if (data.is_default) {
        vatTypes.value = vatTypes.value.map(vt => ({ ...vt, is_default: false }))
      }
      vatTypes.value.push(response.data)
      toast.add({
        title: t('common.success'),
        description: t('vatTypes.created'),
        color: 'green'
      })
      return response.data
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('vatTypes.createError')),
        color: 'red'
      })
      return null
    }
  }

  // Update a VAT type
  async function updateVatType(id: string, data: VatTypeUpdate): Promise<VatType | null> {
    try {
      const response = await api.put<ApiResponse<VatType>>(`/api/v1/catalog/vat-types/${id}`, data)
      // If setting as default, update local state
      if (data.is_default) {
        vatTypes.value = vatTypes.value.map(vt => ({
          ...vt,
          is_default: vt.id === id
        }))
      }
      // Update the item in the list
      const index = vatTypes.value.findIndex(vt => vt.id === id)
      if (index !== -1) {
        vatTypes.value[index] = response.data
      }
      toast.add({
        title: t('common.success'),
        description: t('vatTypes.updated'),
        color: 'green'
      })
      return response.data
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('vatTypes.updateError')),
        color: 'red'
      })
      return null
    }
  }

  // Delete a VAT type (soft delete)
  async function deleteVatType(id: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/catalog/vat-types/${id}`)
      // Mark as inactive in local state
      const index = vatTypes.value.findIndex(vt => vt.id === id)
      if (index !== -1) {
        vatTypes.value[index] = { ...vatTypes.value[index], is_active: false }
      }
      toast.add({
        title: t('common.success'),
        description: t('vatTypes.deleted'),
        color: 'green'
      })
      return true
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('vatTypes.deleteError')),
        color: 'red'
      })
      return false
    }
  }

  // Generate options for USelect components
  const vatTypeOptions = computed(() =>
    activeVatTypes.value.map(vt => ({
      value: vt.id,
      label: getVatTypeLabel(vt)
    }))
  )

  return {
    // State
    vatTypes,
    isLoading,

    // Computed
    activeVatTypes,
    defaultVatType,
    vatTypeOptions,

    // Methods
    fetchVatTypes,
    createVatType,
    updateVatType,
    deleteVatType,
    getVatTypeName,
    getVatTypeLabel,
    getVatTypeById
  }
}
