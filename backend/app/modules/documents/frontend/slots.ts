/**
 * Slot registrations for the documents module.
 *
 * Registers the documents tab in the patient detail view so users
 * can access documents directly from the patient file.
 */
import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~/composables/useModuleSlots'

registerSlot('patient.detail.tabs', {
  id: 'documents.patient.tab',
  component: defineAsyncComponent(() => import('../components/DocumentsTab.vue')),
  order: 55,
  permission: 'documents.read'
})
