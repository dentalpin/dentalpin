/**
 * Registers medical_reference's settings page on the host registry.
 * Mounted as a card under `/settings/clinical` and as a full page at
 * `/settings/clinical/medical-reference` via the host's dynamic
 * category route. Mirrors the budget module pattern (ADR 0003): the
 * plugin imports the registry from `~~/app/composables/...` (host
 * shell), not from another module.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'medical-reference',
    category: 'clinical',
    labelKey: 'medicalReference.settingsLabel',
    descriptionKey: 'medicalReference.settingsDescription',
    icon: 'i-lucide-list-checks',
    permission: 'medical_reference.write',
    component: () => import('../components/settings/MedicalReferenceSettingsPage.vue'),
    searchKeywords: ['allergy', 'allergies', 'medication', 'disease', 'apci', 'reference'],
    order: 40
  })
})
