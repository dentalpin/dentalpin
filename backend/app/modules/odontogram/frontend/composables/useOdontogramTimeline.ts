/**
 * useOdontogramTimeline - Manages historical view of odontogram
 *
 * Handles:
 * - Fetching timeline dates
 * - Loading historical odontogram state at a specific date
 * - Switching between live and historical view
 */

import type {
  ApiResponse,
  OdontogramData,
  ToothRecord,
  Treatment
} from '~~/app/types'
import { normalizeTreatment } from './useTreatments'

export function useOdontogramTimeline() {
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
    loading.value = true
    try {
      const response = await api.get<ApiResponse<{
        dates: Array<{ date: string, change_count: number }>
        total: number
      }>>(
        `/api/v1/odontogram/patients/${patientId}/odontogram/timeline`
      )
      timelineDates.value = response.data.dates
    } catch (err) {
      console.error('Error fetching timeline:', err)
      timelineDates.value = []
    } finally {
      loading.value = false
    }
  }

  /** Fetch odontogram state at a specific date */
  async function fetchOdontogramAtDate(patientId: string, date: string): Promise<void> {
    loading.value = true
    try {
      const response = await api.get<ApiResponse<OdontogramData>>(
        `/api/v1/odontogram/patients/${patientId}/odontogram/at?date=${date}`,
        { errorToast: false }
      )
      historicalTeeth.value = response.data.teeth
      // The API says performed, the charts say existing (#1065).
      historicalTreatments.value = (response.data.treatments || []).map(normalizeTreatment)
      viewingDate.value = date
    } catch (err) {
      console.error('Error fetching historical odontogram:', err)
      toast.add({
        title: t('common.error'),
        color: 'error'
      })
    } finally {
      loading.value = false
    }
  }

  /** Return to current/live view */
  function returnToCurrentView(): void {
    viewingDate.value = null
    historicalTeeth.value = []
    historicalTreatments.value = []
  }

  /** Reset all timeline state */
  function reset(): void {
    timelineDates.value = []
    viewingDate.value = null
    historicalTeeth.value = []
    historicalTreatments.value = []
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
