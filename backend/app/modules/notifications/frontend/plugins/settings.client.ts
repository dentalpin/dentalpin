/**
 * Registers notifications-owned settings cards on the host registry.
 * Mounted under ``/settings/communications`` (the host shell exposes
 * a "communications" category — see ``useSettingsRegistry.ts``).
 *
 * Imports the registry from the host (``~~``) and never from another
 * module, keeping ``manifest.depends`` clean.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'language',
    category: 'communications',
    labelKey: 'notifications.communications.language.cardTitle',
    descriptionKey: 'notifications.communications.language.cardDescription',
    icon: 'i-lucide-languages',
    permission: 'admin.clinic.write',
    component: () => import('../components/settings/ClinicLanguagePage.vue'),
    searchKeywords: [
      'idioma',
      'language',
      'comunicaciones',
      'communications',
      'patient',
      'paciente',
    ],
    order: 10,
  })

  // Phase 7: template management UI — previously templates could only be
  // created via the raw API (no frontend existed for this at all).
  registerSettingsPage({
    path: 'templates',
    category: 'communications',
    labelKey: 'notifications.templatesPage.cardTitle',
    descriptionKey: 'notifications.templatesPage.cardDescription',
    icon: 'i-lucide-file-text',
    permission: 'notifications.templates.write',
    component: () => import('../components/settings/TemplatesSettingsPage.vue'),
    searchKeywords: [
      'template',
      'plantilla',
      'modèle',
      'recall_reminder',
      'email',
      'sms',
      'whatsapp',
    ],
    order: 11,
  })
})
