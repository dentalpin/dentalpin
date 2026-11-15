/**
 * useOdontogram - Facade composable for odontogram functionality
 *
 * Combines:
 * - useOdontogramData: tooth records and conditions
 * - useTreatments: treatment CRUD operations
 * - useOdontogramTimeline: historical view
 *
 * Use this composable for full odontogram functionality.
 * Use individual composables for specific needs.
 */

import type { ToothRecord, Treatment } from '~~/app/types'

// Re-export constants for backwards compatibility
export {
  PERMANENT_TEETH,
  DECIDUOUS_TEETH,
  CONDITION_COLORS,
  SURFACE_LABELS,
  TREATMENT_SHORTCUTS,
  ALL_DECIDUOUS_NUMBERS
} from '~~/app/constants/odontogram'

export function useOdontogram() {
  // Compose the three specialized composables
  const odontogramData = useOdontogramData()
  const treatmentsApi = useTreatments()
  const timeline = useOdontogramTimeline()

  // ============================================================================
  // Computed: Display teeth/treatments (historical or live)
  // ============================================================================

  /** Teeth to display (historical or live) */
  const displayTeeth = computed<ToothRecord[]>(() =>
    timeline.isViewingHistory.value
      ? timeline.historicalTeeth.value
      : odontogramData.teeth.value
  )

  /** Treatments to display (historical or live) */
  const displayTreatments = computed<Treatment[]>(() =>
    timeline.isViewingHistory.value
      ? timeline.historicalTreatments.value
      : treatmentsApi.treatments.value
  )

  // ============================================================================
  // Combined reset
  // ============================================================================

  /** Reset all state */
  function resetAll(): void {
    odontogramData.reset()
    treatmentsApi.reset()
    timeline.reset()
  }

  // ============================================================================
  // Return combined API
  // ============================================================================

  return {
    // === Odontogram Data ===
    odontogramData: odontogramData.odontogramData,
    teeth: odontogramData.teeth,
    loading: odontogramData.loading,
    error: odontogramData.error,
    conditionColors: odontogramData.conditionColors,
    availableConditions: odontogramData.availableConditions,
    fetchOdontogram: odontogramData.fetchOdontogram,
    updateTooth: odontogramData.updateTooth,
    bulkUpdateTeeth: odontogramData.bulkUpdateTeeth,
    fetchToothHistory: odontogramData.fetchToothHistory,
    fetchPatientHistory: odontogramData.fetchPatientHistory,
    getToothRecord: odontogramData.getToothRecord,
    getConditionColor: odontogramData.getConditionColor,
    isDeciduousTooth: odontogramData.isDeciduousTooth,
    reset: odontogramData.reset,

    // === Treatments ===
    treatments: treatmentsApi.treatments,
    treatmentsLoading: treatmentsApi.loading,
    treatmentsError: treatmentsApi.error,
    fetchTreatments: treatmentsApi.fetchTreatments,
    createTreatment: treatmentsApi.createTreatment,
    updateTreatment: treatmentsApi.updateTreatment,
    deleteTreatment: treatmentsApi.deleteTreatment,
    performTreatment: treatmentsApi.performTreatment,
    fetchToothWithTreatments: treatmentsApi.fetchToothWithTreatments,
    getToothTreatments: treatmentsApi.getToothTreatments,
    getTreatmentsByStatus: treatmentsApi.getTreatmentsByStatus,

    // === Timeline ===
    timelineDates: timeline.timelineDates,
    viewingDate: timeline.viewingDate,
    historicalTeeth: timeline.historicalTeeth,
    historicalTreatments: timeline.historicalTreatments,
    timelineLoading: timeline.loading,
    isViewingHistory: timeline.isViewingHistory,
    fetchTimeline: timeline.fetchTimeline,
    fetchOdontogramAtDate: timeline.fetchOdontogramAtDate,
    returnToCurrentView: timeline.returnToCurrentView,
    resetTimeline: timeline.reset,

    // === Combined ===
    displayTeeth,
    displayTreatments,
    resetAll
  }
}
