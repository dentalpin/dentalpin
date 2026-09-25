/**
 * Registers prescriptions' templates page on the host registry.
 * Mounted as a card under `/settings/clinical` via the host's dynamic
 * category route — same pattern as medication_catalog.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'prescription-templates',
    category: 'clinical',
    labelKey: 'prescriptions.settingsLabel',
    descriptionKey: 'prescriptions.settingsDescription',
    icon: 'i-lucide-pill',
    permission: 'prescriptions.read',
    component: () => import('../components/settings/PrescriptionTemplatesSettingsPage.vue'),
    searchKeywords: ['prescription', 'template', 'receta', 'plantilla'],
    order: 46
  })
  registerSettingsPage({
    path: 'prescriber-identity',
    category: 'clinical',
    labelKey: 'prescriptions.profileLabel',
    descriptionKey: 'prescriptions.profileDescription',
    icon: 'i-lucide-badge-check',
    permission: 'prescriptions.read',
    component: () => import('../components/settings/PrescriberProfileSettingsPage.vue'),
    searchKeywords: ['prescription', 'license', 'receta', 'cedula', 'prescriptor'],
    order: 47
  })
})
