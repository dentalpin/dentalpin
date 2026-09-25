/**
 * Registers the website-form settings page under Settings -> Integrations.
 *
 * Registered here (not in the host) so installing the module adds the
 * page and uninstalling removes it — the same boundary the other module
 * layers use: `~~` reaches the host shell only.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'leads',
    category: 'integrations',
    labelKey: 'leads.settings.title',
    descriptionKey: 'leads.settings.description',
    icon: 'i-lucide-inbox',
    // Read is enough to *see* the page; changing the cap or rotating the
    // key needs leads.settings.write, checked inside the component.
    permission: 'leads.settings.read',
    component: () => import('../components/settings/LeadsIntakeSettingsPage.vue'),
    searchKeywords: [
      'leads',
      'contactos',
      'formulario',
      'web',
      'website',
      'intake',
      'limite',
      'cap'
    ],
    order: 52
  })
})
