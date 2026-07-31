import type { ApiResponse } from '~~/app/types'

export interface BudgetSettings {
  budget_expiry_days: number
  plan_auto_close_days_after_expiry: number
  budget_reminders_enabled: boolean
  budget_public_auth_disabled: boolean
}

export type BudgetSettingsPatch = Partial<BudgetSettings>

export function useBudgetSettings() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  const settings = ref<BudgetSettings | null>(null)
  const loading = ref(false)
  const saving = ref(false)

  async function fetch() {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<BudgetSettings>>(
        '/api/v1/auth/clinic/settings/budget'
      )
      settings.value = response.data
    } finally {
      loading.value = false
    }
  }

  async function update(payload: BudgetSettingsPatch) {
    saving.value = true
    try {
      const response = await api.patch<ApiResponse<BudgetSettings>>(
        '/api/v1/auth/clinic/settings/budget',
        payload
      )
      settings.value = response.data
      toast.add({ title: t('budget.settings.saved'), color: 'success' })
      return true
    } catch (error) {
      console.error('Error saving budget settings:', error)
      toast.add({ title: t('errors.updateFailed'), color: 'error' })
      return false
    } finally {
      saving.value = false
    }
  }

  return {
    settings,
    loading,
    saving,
    fetch,
    update
  }
}
