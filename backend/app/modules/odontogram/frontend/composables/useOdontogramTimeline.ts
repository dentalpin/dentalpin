/**
 * useOdontogramTimeline - Manages historical view of odontogram
 *
 * Handles:
 * - Fetching timeline dates
 * - Loading historical odontogram state at a specific date
 * - Switching between live and historical view
 */

import { PERMISSIONS } from '~~/app/config/permissions'
import type {
  ApiResponse,
  OdontogramData,
  ToothRecord,
  Treatment
} from '~~/app/types'

export function useOdontogramTimeline() {
  const { can } = usePermissions()
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  // ============================================================================
  // State
  // ============================================================================

  /** List of dates with changes */
  const timelineDates = ref<Array<{ date: string, change_count: number }>>([])

  /** Currently viewing date (null = live view) */
  const viewingDate = ref<string | null>(null)

  /** Historical teeth data */
  const historicalTeeth = ref<ToothRecord[]>([])

  /** Historical treatments data */
  const historicalTreatments = ref<Treatment[]>([])

  /** Loading state */
  const loading = ref(false)

  let activePatientId: string | null = null
  let timelineRequestSequence = 0
  let historyRequestSequence = 0

  function usePatient(patientId: string): void {
    if (activePatientId === patientId) return
    activePatientId = patientId
    timelineRequestSequence++
    historyRequestSequence++
    timelineDates.value = []
    viewingDate.value = null
    historicalTeeth.value = []
    historicalTreatments.value = []
    loading.value = false
  }
  // ============================================================================
  // Computed
  // ============================================================================

  /** Whether viewing historical state */
  const isViewingHistory = computed(() => viewingDate.value !== null)

  // ============================================================================
  // API Methods
  // ============================================================================

  /** Fetch timeline dates for a patient */
  async function fetchTimeline(patientId: string): Promise<void> {
    usePatient(patientId)
    const requestId = ++timelineRequestSequence
    if (!can(PERMISSIONS.odontogram.read)) {
      timelineDates.value = []
      loading.value = false
      return
    }
    loading.value = true
    try {
      const response = await api.get<ApiResponse<{
        dates: Array<{ date: string, change_count: number }>
        total: number
      }>>(
        `/api/v1/odontogram/patients/${patientId}/odontogram/timeline`
      )
      if (requestId === timelineRequestSequence) timelineDates.value = response.data.dates
    } catch (err) {
      console.error('Error fetching timeline:', err)
      if (requestId === timelineRequestSequence) timelineDates.value = []
    } finally {
      if (requestId === timelineRequestSequence) loading.value = false
    }
  }

  /** Fetch odontogram state at a specific date */
  async function fetchOdontogramAtDate(patientId: string, date: string): Promise<void> {
    usePatient(patientId)
    const requestId = ++historyRequestSequence
    loading.value = true
    try {
      const response = await api.get<ApiResponse<OdontogramData>>(
        `/api/v1/odontogram/patients/${patientId}/odontogram/at?date=${date}`,
        { errorToast: false }
      )
      if (requestId === historyRequestSequence) {
        historicalTeeth.value = response.data.teeth
        historicalTreatments.value = response.data.treatments || []
        viewingDate.value = date
      }
    } catch (err) {
      console.error('Error fetching historical odontogram:', err)
      if (requestId === historyRequestSequence) {
        toast.add({
          title: t('common.error'),
          color: 'error'
        })
      }
    } finally {
      if (requestId === historyRequestSequence) loading.value = false
    }
  }

  /** Return to current/live view */
  function returnToCurrentView(): void {
    historyRequestSequence++
    viewingDate.value = null
    historicalTeeth.value = []
    historicalTreatments.value = []
    loading.value = false
  }

  /** Reset all timeline state */
  function reset(): void {
    timelineRequestSequence++
    historyRequestSequence++
    activePatientId = null
    timelineDates.value = []
    viewingDate.value = null
    historicalTeeth.value = []
    historicalTreatments.value = []
    loading.value = false
  }

  // ============================================================================
  // Return
  // ============================================================================

  return {
    // State
    timelineDates,
    viewingDate,
    historicalTeeth,
    historicalTreatments,
    loading,

    // Computed
    isViewingHistory,

    // API
    fetchTimeline,
    fetchOdontogramAtDate,
    returnToCurrentView,
    reset
  }
}
