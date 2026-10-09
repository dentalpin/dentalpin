import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

/**
 * Slot registrations for the `notifications` module.
 *
 * The patient WhatsApp conversation thread (channel-agnostic comms log +
 * reply box) renders as a card on the patient summary. The per-patient
 * channel opt-out card (email/WhatsApp/SMS toggles) renders below it.
 * The slot registry is the only contract — no host import.
 */
export default defineNuxtPlugin(() => {
  registerSlot('patient.summary.cards', {
    id: 'notifications.patient.conversation',
    component: defineAsyncComponent(() => import('../components/ConversationThread.vue')),
    permission: PERMISSIONS.notifications.logsRead,
    order: 60
  })
  registerSlot('patient.summary.cards', {
    id: 'notifications.patient.prefs',
    component: defineAsyncComponent(() => import('../components/PatientNotificationPrefs.vue')),
    permission: PERMISSIONS.notifications.preferencesRead,
    order: 61
  })
})
