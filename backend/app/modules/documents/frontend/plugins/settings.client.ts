/**
 * Registers the documents letterhead editor on the host settings
 * registry, under the ``billing`` category (clinic branding lives
 * alongside the other clinic-produced paper). Mirrors the budget
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
})
