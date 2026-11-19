import { defineComponent } from 'vue'
import { MANUAL_WHATSAPP_PATH, useManualWhatsApp } from '../composables/useManualWhatsApp'

export default defineComponent({
  setup() {
    const { currentClinic } = useClinicState()
    const badges = useNavigationBadges()
    const api = useManualWhatsApp()
    let revision = 0
    let timer: ReturnType<typeof setInterval> | undefined

    async function refresh() {
      const request = ++revision
      try {
        const response = await api.count()
        if (request === revision) badges.value[MANUAL_WHATSAPP_PATH] = response.data
      } catch {
        if (request === revision) badges.value[MANUAL_WHATSAPP_PATH] = undefined
      }
    }

    onMounted(() => {
      watch(() => currentClinic.value?.id, () => {
        badges.value[MANUAL_WHATSAPP_PATH] = undefined
        void refresh()
      }, { immediate: true })
      timer = setInterval(() => {
        void refresh()
      }, 15_000)
    })
    onUnmounted(() => {
      revision++
      clearInterval(timer)
      badges.value[MANUAL_WHATSAPP_PATH] = undefined
    })
    return () => null
  }
})
