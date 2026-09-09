/**
 * Composable for odontogram-catalog integration.
 *
 * Provides treatments from the catalog with odontogram mappings,
 * with fallback to hardcoded constants if catalog is empty.
 */

import type { ApiResponse, OdontogramTreatment, VisualizationRuleLayer } from '~~/app/types'
import {
  TREATMENT_CATEGORIES,
  TREATMENT_COLORS,
  VISUALIZATION_RULES,
  DIAGNOSTIC_CATEGORIES,
  THERAPEUTIC_CATEGORIES,
  isSurfaceTreatment,
  type TreatmentClinicalCategory
} from '~~/app/config/odontogramConstants'

export function useTreatmentCatalog() {
  const api = useApi()
  const { locale } = useLocale()

  // State
  const treatments = useState<OdontogramTreatment[]>('treatmentCatalog:treatments', () => [])
  const loading = useState<boolean>('treatmentCatalog:loading', () => false)
  const error = useState<string | null>('treatmentCatalog:error', () => null)
  const initialized = useState<boolean>('treatmentCatalog:initialized', () => false)

  // ============================================================================
  // Fetch treatments from catalog
  // ============================================================================

  async function fetchTreatments(): Promise<void> {
    try {
      loading.value = true
      error.value = null

      const response = await api.get<ApiResponse<OdontogramTreatment[]>>(
        '/api/v1/catalog/odontogram-treatments'
      )
      treatments.value = response.data
      initialized.value = true
    } catch (e) {
      error.value = 'Failed to fetch treatments from catalog'
      console.error('Error fetching treatments from catalog:', e)
      // Fallback will be used via computed properties
      initialized.value = true
    } finally {
      loading.value = false
    }
  }

  // ============================================================================
  // Computed - with fallback to constants
  // ============================================================================

  /**
   * Whether to use catalog treatments or fallback to constants.
   */
  const useCatalog = computed(() => treatments.value.length > 0)

  /**
   * Treatments grouped by clinical category.
   * Falls back to hardcoded constants if catalog is empty.
   */
  const treatmentsByCategory = computed(() => {
    if (useCatalog.value) {
      // Group catalog treatments by clinical_category.
      // Unmapped global items have none — they only surface via globalItems.
      const grouped: Record<string, OdontogramTreatment[]> = {}
      for (const treatment of treatments.value) {
        const category = treatment.clinical_category
        if (category == null) {
          continue
        }
        if (!grouped[category]) {
          grouped[category] = []
        }
        grouped[category].push(treatment)
      }
      return grouped
    }

    // Fallback to constants
    const grouped: Record<string, OdontogramTreatment[]> = {}
    for (const category of TREATMENT_CATEGORIES) {
      grouped[category.key] = category.treatments.map(treatmentType => ({
        id: treatmentType,
        internal_code: treatmentType.toUpperCase(),
        names: { es: treatmentType, en: treatmentType },
        default_price: null,
        pricing_strategy: 'flat',
        pricing_config: null,
        treatment_scope: 'tooth',
        requires_surfaces: isSurfaceTreatment(treatmentType),
        is_diagnostic: category.key === 'diagnostico',
        odontogram_treatment_type: treatmentType as OdontogramTreatment['odontogram_treatment_type'],
        visualization_rules: getVisualizationRulesForType(treatmentType),
        visualization_config: {
          color: TREATMENT_COLORS[treatmentType] || { light: '#6B7280', dark: '#9CA3AF' }
        },
        clinical_category: category.key,
        category_key: category.key,
        category_names: { es: category.labelKey, en: category.labelKey, fr: category.labelKey, ta: category.labelKey }
      }))
    }
    return grouped
  })

  /**
   * All available clinical categories.
   */
  const clinicalCategories = computed(() => {
    if (useCatalog.value) {
      return Object.keys(treatmentsByCategory.value)
    }
    return TREATMENT_CATEGORIES.map(c => c.key)
  })

  /**
   * Diagnostic categories only (for diagnosis mode in TreatmentBar).
   * These are categories for recording existing conditions.
   */
  const diagnosticCategories = computed(() => {
    return clinicalCategories.value.filter(cat =>
      DIAGNOSTIC_CATEGORIES.includes(cat as TreatmentClinicalCategory)
    )
  })

  /**
   * Therapeutic categories only (for planning mode in TreatmentBar).
   * These are categories for treatments that can be planned.
   */
  const therapeuticCategories = computed(() => {
    return clinicalCategories.value.filter(cat =>
      THERAPEUTIC_CATEGORIES.includes(cat as TreatmentClinicalCategory)
    )
  })

  /**
   * Get treatments for a specific category.
   * Falls back to constants if category not in catalog.
   */
  function getTreatmentsForCategory(categoryKey: string): OdontogramTreatment[] {
    const catalogTreatments = treatmentsByCategory.value[categoryKey]
    if (catalogTreatments && catalogTreatments.length > 0) {
      return catalogTreatments
    }

    // Fallback to constants for this specific category
    const constantCategory = TREATMENT_CATEGORIES.find(c => c.key === categoryKey)
    if (constantCategory) {
      return constantCategory.treatments.map(treatmentType => ({
        id: treatmentType,
        internal_code: treatmentType.toUpperCase(),
        names: { es: treatmentType, en: treatmentType },
        default_price: null,
        pricing_strategy: 'flat' as const,
        pricing_config: null,
        treatment_scope: 'tooth' as const,
        requires_surfaces: isSurfaceTreatment(treatmentType),
        is_diagnostic: categoryKey === 'diagnostico',
        odontogram_treatment_type: treatmentType as OdontogramTreatment['odontogram_treatment_type'],
        visualization_rules: getVisualizationRulesForType(treatmentType),
        visualization_config: {
          color: TREATMENT_COLORS[treatmentType] || { light: '#6B7280', dark: '#9CA3AF' }
        },
        clinical_category: categoryKey,
        category_key: categoryKey,
        category_names: { es: constantCategory.labelKey, en: constantCategory.labelKey, fr: constantCategory.labelKey, ta: constantCategory.labelKey }
      }))
    }

    return []
  }

  /**
   * Get a single treatment by its odontogram_treatment_type.
   */
  function getTreatmentByType(treatmentType: string): OdontogramTreatment | undefined {
    const normalized = treatmentType

    if (useCatalog.value) {
      return treatments.value.find(
        t => t.odontogram_treatment_type != null && t.odontogram_treatment_type === normalized
      )
    }

    // Fallback to creating from constants
    for (const category of TREATMENT_CATEGORIES) {
      if (category.treatments.includes(normalized)) {
        return {
          id: normalized,
          internal_code: normalized.toUpperCase(),
          names: { es: normalized, en: normalized },
          default_price: null,
          pricing_strategy: 'flat',
          pricing_config: null,
          treatment_scope: 'tooth',
          requires_surfaces: isSurfaceTreatment(normalized),
          is_diagnostic: category.key === 'diagnostico',
          odontogram_treatment_type: normalized as OdontogramTreatment['odontogram_treatment_type'],
          visualization_rules: getVisualizationRulesForType(normalized),
          visualization_config: {
            color: TREATMENT_COLORS[normalized] || { light: '#6B7280', dark: '#9CA3AF' }
          },
          clinical_category: category.key,
          category_key: category.key,
          category_names: { es: category.labelKey, en: category.labelKey, fr: category.labelKey, ta: category.labelKey }
        }
      }
    }

    return undefined
  }

  /**
   * Get effective treatment type for odontogram rendering.
   * This is what should be used when applying treatments to teeth.
   */
  function getEffectiveTreatmentType(catalogItemId: string | undefined, fallbackType: string): string {
    if (catalogItemId && useCatalog.value) {
      const treatment = treatments.value.find(t => t.id === catalogItemId)
      if (treatment?.odontogram_treatment_type != null) {
        return treatment.odontogram_treatment_type
      }
    }
    return fallbackType
  }

  /**
   * Get treatment label directly from treatment object, prioritizing frontend i18n translations.
   */
  function getTreatmentLabel(
    treatment: OdontogramTreatment | undefined,
    overrideLocale?: string
  ): string {
    if (!treatment) return ''
    const { t, te } = useI18n()
    const codeKey = `odontogram.treatments.items.${treatment.internal_code}`
    if (te(codeKey)) {
      return t(codeKey)
    }
    const loc = overrideLocale || locale.value
    return treatment.names[loc] || treatment.names.es || treatment.names.en || treatment.internal_code
  }

  /**
   * Get treatment name for display.
   */
  function getTreatmentName(
    treatmentType: string,
    overrideLocale?: string
  ): string {
    const treatment = getTreatmentByType(treatmentType)
    if (treatment) {
      return getTreatmentLabel(treatment, overrideLocale)
    }
    return treatmentType
  }

  /**
   * Get treatment price for display (in minor units).
   */
  function getTreatmentPrice(treatmentType: string): number | undefined {
    const treatment = getTreatmentByType(treatmentType)
    if (!treatment?.default_price) return undefined
    const parsed = Number(treatment.default_price)
    return Number.isFinite(parsed) ? parsed : undefined
  }

  /**
   * Check if treatment requires surface selection.
   */
  function treatmentRequiresSurfaces(treatmentType: string): boolean {
    const treatment = getTreatmentByType(treatmentType)
    return treatment?.requires_surfaces ?? isSurfaceTreatment(treatmentType)
  }

  /**
   * Check if treatment is diagnostic (should only allow 'existing' status).
   */
  function treatmentIsDiagnostic(treatmentType: string): boolean {
    const treatment = getTreatmentByType(treatmentType)
    return treatment?.is_diagnostic ?? false
  }

  // ============================================================================
  // Helpers
  // ============================================================================

  function getVisualizationRulesForType(treatmentType: string): VisualizationRuleLayer[] {
    const layers: VisualizationRuleLayer[] = []
    for (const [rule, treatments] of Object.entries(VISUALIZATION_RULES)) {
      if (treatments.includes(treatmentType)) {
        // Map legacy rule name (pattern_fill) to the new layer name (cenital_pattern).
        const layer = rule === 'pattern_fill' ? 'cenital_pattern' : rule
        layers.push({ layer: layer as VisualizationRuleLayer['layer'] })
      }
    }
    return layers
  }

  function getCategoryLabel(categoryKey: string, overrideLocale?: string): string {
    const { te, t } = useI18n()
    const i18nKey = `odontogram.treatments.categories.${categoryKey}`
    if (te(i18nKey)) {
      return t(i18nKey)
    }

    const loc = overrideLocale || locale.value
    if (useCatalog.value) {
      const first = treatmentsByCategory.value[categoryKey]?.[0]
      if (first) {
        return first.category_names[loc] || first.category_names.es || first.category_names.en || categoryKey
      }
    }

    // Fallback to constants
    const category = TREATMENT_CATEGORIES.find(c => c.key === categoryKey)
    return category?.labelKey ? t(category.labelKey) : categoryKey
  }

  function isCategoryDiagnostic(categoryKey: TreatmentClinicalCategory): boolean {
    return categoryKey === 'diagnostico'
  }

  // ============================================================================
  // Global treatments (boca completa / arcada)
  // ============================================================================

  /** Items whose scope is global_mouth — applied to the whole mouth. */
  const globalMouthItems = computed(() =>
    treatments.value.filter(t => t.treatment_scope === 'global_mouth')
  )

  /** Items whose scope is global_arch — require arch selection on apply. */
  const globalArchItems = computed(() =>
    treatments.value.filter(t => t.treatment_scope === 'global_arch')
  )

  /** Convenience: all global items split by scope for rendering. */
  const globalItems = computed(() => ({
    mouth: globalMouthItems.value,
    arch: globalArchItems.value
  }))

  return {
    // State
    treatments,
    loading,
    error,
    initialized,

    // Fetch
    fetchTreatments,

    // Computed
    useCatalog,
    treatmentsByCategory,
    clinicalCategories,
    diagnosticCategories,
    therapeuticCategories,

    // Treatment getters
    getTreatmentsForCategory,
    getTreatmentByType,
    getEffectiveTreatmentType,
    getTreatmentLabel,
    getTreatmentName,
    getTreatmentPrice,
    treatmentRequiresSurfaces,
    treatmentIsDiagnostic,

    // Helpers
    getCategoryLabel,
    isCategoryDiagnostic,

    // Globals
    globalMouthItems,
    globalArchItems,
    globalItems
  }
}
