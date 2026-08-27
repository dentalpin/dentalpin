import type { ApiResponse, TimelineCategory, TimelineEntry, TimelineResponse } from '~~/app/types'

// High-impact events get stronger visual emphasis in the UI (accent bar, denser
// hover). Everything else renders in the default, low-key style.
const HIGH_IMPACT_EVENT_TYPES = new Set([
  'appointment.completed',
  'treatment_plan.treatment_completed',
  'odontogram.treatment.performed',
  'budget.accepted',
  'invoice.paid',
  'patient.medical_updated'
])

// Events that should render denser/smaller — operational chatter rather than
// clinical milestones. The legacy email.* types remain for rows recorded
// before the generic notification.* events replaced them (issue #287).
const LOW_IMPACT_EVENT_TYPES = new Set([
  'email.sent',
  'email.failed',
  'notification.sent',
  'notification.failed',
  'appointment.confirmed'
])

export function usePatientTimeline(patientId: Ref<string | undefined>) {
  const api = useApi()
  const { t } = useI18n()

  const entries = ref<TimelineEntry[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const hasMore = ref(false)
  // Shared across components so the filter survives navigation between
  // patients within the same session.
  const selectedCategory = useState<TimelineCategory | null>(
    'patient-timeline:category',
    () => null
  )

  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const error = ref<string | null>(null)

  async function fetchTimeline(reset = true) {
    if (!patientId.value) return

    if (reset) {
      isLoading.value = true
      page.value = 1
      entries.value = []
    } else {
      isLoadingMore.value = true
    }

    error.value = null

    try {
      const params = new URLSearchParams({
        page: page.value.toString(),
        page_size: pageSize.value.toString()
      })

      if (selectedCategory.value) {
        params.append('category', selectedCategory.value)
      }

      const response = await api.get<ApiResponse<TimelineResponse>>(
        `/api/v1/patient_timeline/patients/${patientId.value}?${params.toString()}`
      )

      if (reset) {
        entries.value = response.data.entries
      } else {
        entries.value = [...entries.value, ...response.data.entries]
      }

      total.value = response.data.total
      hasMore.value = response.data.has_more
    } catch (e) {
      error.value = 'Failed to fetch timeline'
      console.error('Failed to fetch patient timeline:', e)
    } finally {
      isLoading.value = false
      isLoadingMore.value = false
    }
  }

  async function loadMore() {
    if (!hasMore.value || isLoadingMore.value) return
    page.value++
    await fetchTimeline(false)
  }

  function setCategory(category: TimelineCategory | null) {
    selectedCategory.value = category
    fetchTimeline(true)
  }

  function getEventIcon(eventType: string): string {
    const icons: Record<string, string> = {
      'appointment.scheduled': 'i-lucide-calendar',
      'appointment.confirmed': 'i-lucide-calendar-check-2',
      'appointment.checked_in': 'i-lucide-door-open',
      'appointment.in_treatment': 'i-lucide-stethoscope',
      'appointment.completed': 'i-lucide-calendar-check',
      'appointment.cancelled': 'i-lucide-calendar-x',
      'appointment.no_show': 'i-lucide-calendar-off',
      'odontogram.treatment.performed': 'i-lucide-stethoscope',
      'treatment_plan.created': 'i-lucide-clipboard-list',
      'treatment_plan.treatment_completed': 'i-lucide-clipboard-check',
      'treatment_plan.item_completed_without_note': 'i-lucide-alert-triangle',
      'treatment_plan.plan_note_created': 'i-lucide-sticky-note',
      'treatment_plan.item_note_created': 'i-lucide-notebook-pen',
      'agenda.visit_note_updated': 'i-lucide-file-edit',
      'budget.sent': 'i-lucide-send',
      'budget.accepted': 'i-lucide-file-check',
      'invoice.issued': 'i-lucide-receipt',
      'invoice.paid': 'i-lucide-banknote',
      'email.sent': 'i-lucide-mail',
      'email.failed': 'i-lucide-mail-warning',
      'notification.sent': 'i-lucide-message-square',
      'notification.failed': 'i-lucide-message-square-warning',
      'notification.reply_received': 'i-lucide-message-square-reply',
      'patient.medical_updated': 'i-lucide-heart-pulse',
      'document.uploaded': 'i-lucide-file-plus'
    }
    return icons[eventType] || 'i-lucide-circle-dot'
  }

  function getCategoryColor(category: TimelineCategory): string {
    const colors: Record<string, string> = {
      visit: 'primary',
      treatment: 'success',
      financial: 'warning',
      communication: 'info',
      medical: 'error',
      document: 'neutral',
      // Notes reuse the neutral palette; the sticky-note icon and the
      // "Notas clínicas" category chip give it a distinct identity without
      // introducing a new Tailwind color alias.
      note: 'neutral'
    }
    return colors[category] || 'neutral'
  }

  function isHighImpact(eventType: string): boolean {
    return HIGH_IMPACT_EVENT_TYPES.has(eventType)
  }

  function isLowImpact(eventType: string): boolean {
    return LOW_IMPACT_EVENT_TYPES.has(eventType)
  }

  const categoryOptions = computed(() => [
    { label: t('patients.timeline.categories.all'), value: null },
    { label: t('patients.timeline.categories.visit'), value: 'visit' as TimelineCategory },
    { label: t('patients.timeline.categories.treatment'), value: 'treatment' as TimelineCategory },
    { label: t('patients.timeline.categories.note'), value: 'note' as TimelineCategory },
    { label: t('patients.timeline.categories.financial'), value: 'financial' as TimelineCategory },
    { label: t('patients.timeline.categories.medical'), value: 'medical' as TimelineCategory },
    { label: t('patients.timeline.categories.document'), value: 'document' as TimelineCategory },
    { label: t('patients.timeline.categories.communication'), value: 'communication' as TimelineCategory }
  ])

  watch(patientId, (newId) => {
    if (newId) {
      fetchTimeline(true)
    } else {
      entries.value = []
      total.value = 0
      hasMore.value = false
    }
  }, { immediate: true })

  return {
    entries,
    total,
    page,
    pageSize,
    hasMore,
    selectedCategory,
    isLoading,
    isLoadingMore,
    error,
    categoryOptions,
    fetchTimeline,
    loadMore,
    setCategory,
    getEventIcon,
    getCategoryColor,
    isHighImpact,
    isLowImpact
  }
}
