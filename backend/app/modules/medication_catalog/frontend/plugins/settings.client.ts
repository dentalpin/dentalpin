/**
 * Registers medication_catalog's settings page on the host registry.
 * Mounted as a card under `/settings/clinical` and served at
 * `/settings/clinical/medications` via the host's dynamic category
 * route — same pattern as medical_reference / budget / recalls.
 *
 * Distinct from medical_reference's "medication list" entry: that one
 * manages patient-record reference flags; this is the clinic formulary
 * consumed by prescriptions.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'medications',
    category: 'clinical',
    labelKey: 'medications.settingsLabel',
    descriptionKey: 'medications.settingsDescription',
    icon: 'i-lucide-pill',
    // Gated on read, not write: dentists get read-only access (manifest
    // role_permissions) because prescribers need the list. The page hides
    // its write actions behind `canWrite`.
    permission: 'medication_catalog.read',
    component: () => import('../components/settings/MedicationCatalogSettingsPage.vue'),
    searchKeywords: ['medication', 'formulary', 'drug', 'dose', 'prescription', 'farmacia'],
    order: 45
  })
})
