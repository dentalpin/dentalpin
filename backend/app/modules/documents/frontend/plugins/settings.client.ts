/**
 * Registers the documents settings pages on the host settings registry:
 * the letterhead editor under the ``billing`` category (clinic branding
 * lives alongside the other clinic-produced paper) and the informed-consent
 * template editor under ``clinical``. Mirrors the budget
 * module's settings plugin — the registry comes from the host shell
 * (``~~/app/composables/...``), never from another module.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'documents-letterhead',
    category: 'billing',
    labelKey: 'documents.settings.cards.letterhead.title',
    descriptionKey: 'documents.settings.cards.letterhead.description',
    icon: 'i-lucide-file-text',
    permission: PERMISSIONS.admin.clinicWrite,
    component: () => import('../components/settings/DocumentsLetterheadPage.vue'),
    searchKeywords: ['document', 'documento', 'letterhead', 'membrete', 'pdf', 'receta'],
    order: 60
  })
  registerSettingsPage({
    path: 'consent-templates',
    category: 'clinical',
    labelKey: 'documents.settings.cards.consentTemplates.title',
    descriptionKey: 'documents.settings.cards.consentTemplates.description',
    icon: 'i-lucide-file-signature',
    // Same gate as the API's template writes (POST/PUT /consent-templates).
    permission: PERMISSIONS.generatedDocuments.write,
    component: () => import('../components/settings/DocumentsConsentTemplatesPage.vue'),
    searchKeywords: ['consent', 'consentimiento', 'template', 'plantilla', 'informed', 'informado', 'firma', 'signature'],
    order: 65
  })
})
