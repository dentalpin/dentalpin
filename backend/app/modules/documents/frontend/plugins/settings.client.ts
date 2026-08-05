/**
 * Registers documents' letterhead settings page on the host registry.
 * Mounted as a card under `/settings/general` (clinic-identity info,
 * same category as ClinicInfoPage — letterhead is exactly that kind of
 * setting, just consumed by generated documents instead of the UI
 * chrome) and as a full page at `/settings/general/letterhead` via the
 * host's dynamic category route. Mirrors medical_reference's plugin
 * (ADR 0003): imports the registry from `~~/app/composables/...` (host
 * shell), not from another module.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'letterhead',
    category: 'general',
    labelKey: 'documents.letterhead.title',
    descriptionKey: 'documents.letterhead.settingsDescription',
    icon: 'i-lucide-file-signature',
    permission: 'documents.write',
    component: () => import('../pages/settings/letterhead.vue'),
    searchKeywords: ['letterhead', 'practice', 'logo', 'prescription', 'certificate'],
    order: 20
  })
})
