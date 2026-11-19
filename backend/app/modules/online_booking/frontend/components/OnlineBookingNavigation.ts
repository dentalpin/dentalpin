import { defineComponent } from 'vue'

export default defineComponent({
  setup() {
    const { currentClinic } = useClinicState()
    const badges = useNavigationBadges()
    const api = useApi()
    let revision = 0
    let timer: ReturnType<typeof setInterval> | undefined

    async function refresh() {
      const request = ++revision
      try {
        const response = await api.get<{ data: number }>('/api/v1/online_booking/requests/count', { errorToast: false })
        if (request === revision) badges.value['/online-booking'] = response.data
      } catch {
        if (request === revision) badges.value['/online-booking'] = undefined
      }
    }

    useDataBus().on('online_booking', () => void refresh())
    onMounted(() => {
      watch(() => currentClinic.value?.id, () => {
        badges.value['/online-booking'] = undefined
        void refresh()
      }, { immediate: true })
      timer = setInterval(() => void refresh(), 15_000)
    })
    onUnmounted(() => {
      revision++
      clearInterval(timer)
      badges.value['/online-booking'] = undefined
    })
    return () => null
  }
})
