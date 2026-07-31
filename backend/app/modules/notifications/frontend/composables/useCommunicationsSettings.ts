import type { ApiResponse } from '~~/app/types'
import { errorDetail } from '~~/app/utils/error'

export interface CommunicationsSettings {
  language: string
}

export type CommunicationsSettingsPatch = Partial<CommunicationsSettings>

export function useCommunicationsSettings() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  const settings = ref<CommunicationsSettings | null>(null)
  const loading = ref(false)
  const saving = ref(false)

  async function fetch() {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<CommunicationsSettings>>(
        '/api/v1/auth/clinic/settings/communications',
      )
      settings.value = response.data
    } finally {
      loading.value = false
    }
  }

  async function update(payload: CommunicationsSettingsPatch) {
    saving.value = true
    try {
      const response = await api.patch<ApiResponse<CommunicationsSettings>>(
        '/api/v1/auth/clinic/settings/communications',
        payload,
      )
      settings.value = response.data
      toast.add({
        title: t('notifications.communications.language.saved'),
        color: 'success',
      })
      return true
    } catch (e) {
      toast.add({ title: t('errors.updateFailed'), description: errorDetail(e), color: 'error' })
      return false
    } finally {
      saving.value = false
    }
  }

  return { settings, loading, saving, fetch, update }
}
