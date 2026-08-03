/**
 * Registers treatment_consumables under Settings → Clinical Configuration.
 * It previously had its own top-level sidebar entry; that's been removed
 * (see this module's __init__.py) in favour of living here, alongside
 * medications/medical_reference/recalls — same category, same pattern.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'treatment-consumables',
    category: 'clinical',
    labelKey: 'treatmentConsumables.settings.title',
    descriptionKey: 'treatmentConsumables.settings.description',
    icon: 'i-lucide-link',
    permission: 'treatment_consumables.read',
    component: () => import('../pages/treatment-consumables/index.vue'),
    searchKeywords: [
      'consumables',
      'consommables',
      'consumibles',
      'treatment',
      'traitement',
      'tratamiento',
      'stock',
      'inventory',
    ],
    order: 30,
  })
})
