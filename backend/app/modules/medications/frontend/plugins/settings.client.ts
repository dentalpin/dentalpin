// Matches the real pattern from
// backend/app/modules/medical_reference/frontend/plugins/settings.client.ts
// (pasted directly by the user, 2026-07-25).

import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'medications',
    category: 'clinical',
    labelKey: 'medications.title',
    descriptionKey: 'medications.description',
    icon: 'i-lucide-pill',
    permission: 'medications.read',
    component: () => import('../components/settings/MedicationsSettingsPage.vue'),
    searchKeywords: ['medication', 'drug', 'prescription', 'dose'],
    order: 11
  })
})
