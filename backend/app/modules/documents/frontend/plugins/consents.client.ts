import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

export default defineNuxtPlugin(() => {
  registerSlot('patient.summary.cards', {
    id: 'documents.patient.consents',
    component: defineAsyncComponent(() => import('../components/consent/ConsentCard.vue')),
    permission: 'documents.read',
    order: 60
  })
})
