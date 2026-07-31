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
      'paciente'
    ],
    order: 10
  })
})
